#!/usr/bin/env python3
"""Static Minecraft 1.21+ / 26.x Datapack Integrity & Performance Auditor (DP-001..DP-004).

Validates a datapack directory (or inline pack.mcmeta + file map) before deploying to Paper/Folia:
  - DP-001: Deprecated plural folders (functions/, loot_tables/, recipes/, advancements/, predicates/, structures/) on pack_format >= 48 (MC 1.21+)
  - DP-002: Missing/malformed pack.mcmeta or pack_format mismatch for target Minecraft version
  - DP-003: Invalid JSON syntax in loot_table/recipe/advancement/tag/predicate files
  - DP-004: Performance & 1.21+ syntax hazards in .mcfunction (unbounded @e selectors, legacy NBT item syntax)
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

PLURAL_TO_SINGULAR = {
    "functions": "function",
    "loot_tables": "loot_table",
    "recipes": "recipe",
    "advancements": "advancement",
    "predicates": "predicate",
    "item_modifiers": "item_modifier",
    "structures": "structure",
}

TARGET_MIN_FORMAT = {
    "1.21": 48,
    "1.21.1": 48,
    "1.21.4": 61,
    "1.21.5": 71,
    "1.21.11": 94,
    "26.1": 101,
    "26.3": 101,
}


def audit_datapack_directory(
    datapack_dir: str | Path,
    *,
    target_mc_version: str = "1.21.4",
) -> dict[str, Any]:
    root = Path(datapack_dir).expanduser().resolve()
    if not root.is_dir():
        return {
            "ok": False,
            "grade": "F",
            "score": 0,
            "datapack_dir": str(root),
            "error": f"Datapack directory not found: {root}",
            "findings": [],
        }

    findings: list[dict[str, Any]] = []
    pack_mcmeta = root / "pack.mcmeta"
    pack_format: int | None = None
    expected_min = TARGET_MIN_FORMAT.get(target_mc_version, 48)

    if not pack_mcmeta.is_file():
        findings.append({
            "code": "DP-002",
            "severity": "error",
            "path": "pack.mcmeta",
            "message": "Missing pack.mcmeta at datapack root.",
            "remediation": f'Create pack.mcmeta with {{"pack": {{"pack_format": {expected_min}, "description": "..."}}}}.',
        })
    else:
        try:
            meta = json.loads(pack_mcmeta.read_text(encoding="utf-8"))
            pf = meta.get("pack", {}).get("pack_format") if isinstance(meta, dict) else None
            if isinstance(pf, int):
                pack_format = pf
                if pf < expected_min:
                    findings.append({
                        "code": "DP-002",
                        "severity": "warning",
                        "path": "pack.mcmeta",
                        "message": f"pack_format={pf} is older than Minecraft {target_mc_version} (expected >= {expected_min}).",
                        "remediation": f"Bump pack_format to {expected_min} (or add supported_formats range) and migrate singular folder names.",
                    })
            else:
                findings.append({
                    "code": "DP-002",
                    "severity": "error",
                    "path": "pack.mcmeta",
                    "message": "pack.mcmeta is missing integer pack.pack_format.",
                    "remediation": f"Set pack.pack_format to {expected_min}.",
                })
        except (OSError, json.JSONDecodeError) as exc:
            findings.append({
                "code": "DP-002",
                "severity": "error",
                "path": "pack.mcmeta",
                "message": f"Invalid pack.mcmeta JSON: {exc}",
                "remediation": "Fix JSON syntax errors in pack.mcmeta.",
            })

    data_dir = root / "data"
    json_checked = 0
    mcfunction_checked = 0
    namespaces: list[str] = []

    if data_dir.is_dir():
        for ns_dir in sorted(p for p in data_dir.iterdir() if p.is_dir()):
            namespaces.append(ns_dir.name)
            for child in sorted(p for p in ns_dir.iterdir() if p.is_dir()):
                if child.name in PLURAL_TO_SINGULAR and (pack_format is None or pack_format >= 48 or expected_min >= 48):
                    singular = PLURAL_TO_SINGULAR[child.name]
                    findings.append({
                        "code": "DP-001",
                        "severity": "error",
                        "path": str(child.relative_to(root)),
                        "message": f"Deprecated 1.20 plural folder 'data/{ns_dir.name}/{child.name}/' is ignored in Minecraft 1.21+ (pack_format >= 48).",
                        "remediation": f"Rename directory to 'data/{ns_dir.name}/{singular}/'.",
                    })

        for jf in sorted(data_dir.rglob("*.json")):
            json_checked += 1
            try:
                json.loads(jf.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as exc:
                findings.append({
                    "code": "DP-003",
                    "severity": "error",
                    "path": str(jf.relative_to(root)),
                    "message": f"Malformed JSON file: {exc}",
                    "remediation": "Validate and fix JSON syntax before loading datapack on Paper/Folia.",
                })

        for fn in sorted(data_dir.rglob("*.mcfunction")):
            mcfunction_checked += 1
            rel = str(fn.relative_to(root))
            try:
                text = fn.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            for lineno, raw_line in enumerate(text.splitlines(), 1):
                line = raw_line.strip()
                if not line or line.startswith("#"):
                    continue
                if re.search(r"@e(?:\s|$)", line):
                    findings.append({
                        "code": "DP-004",
                        "severity": "warning",
                        "path": f"{rel}:{lineno}",
                        "message": "Unfiltered '@e' entity selector scans every loaded entity across all dimensions (severe tick lag on tick.json).",
                        "remediation": "Restrict with type/tag/distance filters, e.g. @e[type=minecraft:marker,tag=mckit,distance=..32].",
                    })
                if re.search(r"\{[^}]*CustomModelData\s*:", line):
                    findings.append({
                        "code": "DP-004",
                        "severity": "warning",
                        "path": f"{rel}:{lineno}",
                        "message": "Legacy 1.20 NBT '{CustomModelData:...}' item syntax detected; Minecraft 1.21+ requires Data Components.",
                        "remediation": "Migrate to component syntax [minecraft:custom_model_data=...] or 1.21.4+ minecraft:item_model.",
                    })

    penalty = sum(25 if f["severity"] == "error" else 10 for f in findings)
    score = max(0, min(100, 100 - penalty))
    grade = "A" if score >= 90 else "B" if score >= 78 else "C" if score >= 62 else "D" if score >= 45 else "F"

    return {
        "ok": not any(f["severity"] == "error" for f in findings),
        "grade": grade,
        "score": score,
        "datapack_dir": str(root),
        "target_mc_version": target_mc_version,
        "pack_format": pack_format,
        "namespaces": namespaces,
        "json_files_checked": json_checked,
        "mcfunction_files_checked": mcfunction_checked,
        "finding_count": len(findings),
        "findings": findings,
    }
