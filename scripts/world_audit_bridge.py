#!/usr/bin/env python3
"""Pure-Python Minecraft Anvil world (.mca), level.dat, playerdata & rollback safety auditor.

Complements mcstage's JVM WorldIntegrityChecker without requiring Java on the host:
  - WORLD-001: Missing or non-GZIP level.dat (checks level.dat_old recovery presence)
  - WORLD-002: Stale or malformed session.lock (must be 8-byte big-endian epoch ms)
  - WORLD-003: Truncated, unaligned, or out-of-bounds Anvil .mca chunk sector pointers
  - WORLD-004: Zero-byte or non-GZIP playerdata/*.dat files (corrupt player inventory risk)
  - WORLD-005: Oversized region file hotspot (> max_region_mb, e.g. chunk-ban / entity bloat)
"""

from __future__ import annotations

import struct
from pathlib import Path
from typing import Any

SECTOR_BYTES = 4096
MIN_MCA_BYTES = 8192
GZIP_MAGIC = b"\x1f\x8b"


def _is_gzip_file(path: Path) -> bool:
    try:
        with path.open("rb") as fh:
            return fh.read(2) == GZIP_MAGIC
    except OSError:
        return False


def _inspect_mca_file(path: Path) -> tuple[int, list[dict[str, Any]]]:
    issues: list[dict[str, Any]] = []
    valid_chunks = 0
    try:
        size = path.stat().st_size
    except OSError as exc:
        return 0, [{"code": "WORLD-003", "severity": "error", "path": str(path), "message": f"Cannot stat region file: {exc}"}]

    if size == 0:
        return 0, [{"code": "WORLD-003", "severity": "error", "path": str(path), "message": "Empty 0-byte Anvil .mca region file."}]
    if size < MIN_MCA_BYTES:
        return 0, [{"code": "WORLD-003", "severity": "error", "path": str(path), "message": f"Truncated Anvil .mca header ({size} bytes < 8192 bytes)."}]
    if size % SECTOR_BYTES != 0:
        issues.append({
            "code": "WORLD-003",
            "severity": "warning",
            "path": str(path),
            "message": f"Region file size {size} bytes is not a multiple of 4096-byte Anvil sectors.",
        })

    total_sectors = size // SECTOR_BYTES
    try:
        with path.open("rb") as fh:
            loc_table = fh.read(SECTOR_BYTES)
    except OSError as exc:
        return 0, [{"code": "WORLD-003", "severity": "error", "path": str(path), "message": f"Cannot read location table: {exc}"}]

    oob_count = 0
    for idx in range(1024):
        entry = struct.unpack(">I", loc_table[idx * 4 : idx * 4 + 4])[0]
        if entry == 0:
            continue
        offset = entry >> 8
        count = entry & 0xFF
        if offset < 2 or count == 0 or (offset + count) > total_sectors:
            oob_count += 1
        else:
            valid_chunks += 1

    if oob_count > 0:
        issues.append({
            "code": "WORLD-003",
            "severity": "error",
            "path": str(path),
            "message": f"{oob_count} chunk location pointer(s) point outside the {total_sectors}-sector Anvil file.",
        })
    return valid_chunks, issues


def audit_world_directory(
    world_dir: str | Path,
    *,
    require_session_lock_cleared: bool = False,
    max_region_mb: float = 64.0,
) -> dict[str, Any]:
    root = Path(world_dir).expanduser().resolve()
    if not root.is_dir():
        return {
            "ok": False,
            "grade": "F",
            "score": 0,
            "world_dir": str(root),
            "error": f"World directory does not exist: {root}",
            "issues": [],
        }

    issues: list[dict[str, Any]] = []
    level_dat = root / "level.dat"
    level_dat_old = root / "level.dat_old"
    level_dat_valid = level_dat.is_file() and _is_gzip_file(level_dat)
    if not level_dat.is_file():
        issues.append({
            "code": "WORLD-001",
            "severity": "error",
            "path": str(level_dat),
            "message": "Missing level.dat (world metadata cannot boot)."
            + (" level.dat_old backup IS present for recovery." if level_dat_old.is_file() else ""),
        })
    elif not level_dat_valid:
        issues.append({
            "code": "WORLD-001",
            "severity": "error",
            "path": str(level_dat),
            "message": "level.dat does not start with valid GZIP header (0x1F 0x8B).",
        })

    session_lock = root / "session.lock"
    session_lock_present = session_lock.is_file()
    if session_lock_present:
        try:
            lock_size = session_lock.stat().st_size
            if lock_size != 8:
                issues.append({
                    "code": "WORLD-002",
                    "severity": "warning",
                    "path": str(session_lock),
                    "message": f"session.lock has unexpected size {lock_size} bytes (expected 8-byte timestamp).",
                })
            elif require_session_lock_cleared:
                issues.append({
                    "code": "WORLD-002",
                    "severity": "warning",
                    "path": str(session_lock),
                    "message": "session.lock is still present while require_session_lock_cleared=true (unclean shutdown or active server).",
                })
        except OSError:
            pass

    region_files_scanned = 0
    valid_chunk_headers = 0
    region_sizes: list[tuple[int, str]] = []
    max_region_bytes = int(max(1.0, max_region_mb) * 1024 * 1024)

    for sub in ("region", "entities", "poi"):
        subdir = root / sub
        if not subdir.is_dir():
            continue
        for mca in sorted(subdir.glob("*.mca")):
            region_files_scanned += 1
            fsize = mca.stat().st_size if mca.exists() else 0
            region_sizes.append((fsize, str(mca.relative_to(root))))
            chunks, mca_issues = _inspect_mca_file(mca)
            valid_chunk_headers += chunks
            issues.extend(mca_issues)
            if fsize > max_region_bytes:
                issues.append({
                    "code": "WORLD-005",
                    "severity": "warning",
                    "path": str(mca),
                    "message": f"Oversized region file {mca.name} ({fsize / (1024 * 1024):.1f} MB > {max_region_mb:.1f} MB threshold); check for chunk-ban NBT or entity leaks.",
                })

    playerdata_scanned = 0
    playerdata_dir = root / "playerdata"
    if playerdata_dir.is_dir():
        for pdat in sorted(playerdata_dir.glob("*.dat")):
            playerdata_scanned += 1
            if pdat.stat().st_size == 0 or not _is_gzip_file(pdat):
                issues.append({
                    "code": "WORLD-004",
                    "severity": "error",
                    "path": str(pdat),
                    "message": f"Corrupt or empty playerdata file {pdat.name} (missing GZIP NBT header).",
                })

    region_sizes.sort(reverse=True)
    top_heavy_regions = [
        {"relative_path": rel, "size_bytes": sz, "size_mb": round(sz / (1024 * 1024), 3)}
        for sz, rel in region_sizes[:10]
    ]

    penalty = sum(25 if i["severity"] == "error" else 10 for i in issues)
    score = max(0, min(100, 100 - penalty))
    grade = "A" if score >= 90 else "B" if score >= 78 else "C" if score >= 62 else "D" if score >= 45 else "F"
    ok = not any(i["severity"] == "error" for i in issues)

    return {
        "ok": ok,
        "grade": grade,
        "score": score,
        "world_dir": str(root),
        "level_dat_valid": level_dat_valid,
        "level_dat_old_present": level_dat_old.is_file(),
        "session_lock_present": session_lock_present,
        "region_files_scanned": region_files_scanned,
        "valid_chunk_headers": valid_chunk_headers,
        "playerdata_files_scanned": playerdata_scanned,
        "top_heavy_regions": top_heavy_regions,
        "issue_count": len(issues),
        "issues": issues,
        "rollback_checklist": [
            "Verify server is cleanly stopped (no active JVM holding session.lock) before copying region/*.mca.",
            "Keep level.dat_old alongside level.dat so emergency single-file restore takes <5 seconds.",
            "Run mc_hosting_backup_verify + mc_world_audit_integrity in CI before deploying major world-gen or RPG item plugins.",
        ],
    }
