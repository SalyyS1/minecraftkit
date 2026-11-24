"""MinecraftKit Local Environment & Autonomous QA Readiness Doctor."""

from __future__ import annotations

import os
import platform
import shutil
import stat
import sys
from pathlib import Path
from typing import Any


def run_kit_doctor(root: Path) -> dict[str, Any]:
    """Audit local runtimes, optional headless capture backends, vault permissions, and kit files."""
    checks: list[dict[str, Any]] = []

    def _add(name: str, ok: bool, detail: str, required: bool = False) -> None:
        checks.append({"name": name, "ok": ok, "required": required, "detail": detail})

    py_ok = sys.version_info >= (3, 10)
    _add("python3", py_ok, f"Python {platform.python_version()}", required=True)

    node_bin = shutil.which("node")
    _add("nodejs", bool(node_bin), node_bin or "not found (optional for Node Mineflayer pool)", required=False)

    java_bin = shutil.which("java")
    _add("java", bool(java_bin), java_bin or "not found (optional for mcstage & bridge-plugin)", required=False)

    docker_bin = shutil.which("docker")
    _add("docker", bool(docker_bin), docker_bin or "not found (optional for Tier-2 Xvfb visual containers)", required=False)

    ffmpeg_bin = shutil.which("ffmpeg")
    _add("ffmpeg", bool(ffmpeg_bin), ffmpeg_bin or "not found (optional for MP4 timelapse encoding)", required=False)

    xvfb_bin = shutil.which("xvfb-run")
    _add("xvfb", bool(xvfb_bin), xvfb_bin or "not found (optional for off-screen X11 visual capture)", required=False)

    try:
        import paramiko  # type: ignore  # noqa: F401
        _add("paramiko_sftp", True, "installed (live Python SFTP enabled)", required=False)
    except ImportError:
        _add("paramiko_sftp", False, "not installed (OpenSSH sftp + dry-run fallback active)", required=False)

    vault_path = Path.home() / ".minecraftkit" / "profiles.json"
    if vault_path.is_file():
        mode = stat.S_IMODE(vault_path.stat().st_mode)
        perms_ok = (mode & 0o077) == 0
        _add("profile_vault_perms", perms_ok, f"{vault_path} mode={oct(mode)}", required=False)
    else:
        _add("profile_vault_perms", True, "vault not created yet (will use chmod 0600)", required=False)

    manifest_ok = (root / "manifest.json").is_file() and (root / "data").is_dir()
    _add("kit_catalog_integrity", manifest_ok, f"root={root}", required=True)

    required_ok = all(c["ok"] for c in checks if c["required"])
    optional_passed = sum(1 for c in checks if not c["required"] and c["ok"])
    optional_total = sum(1 for c in checks if not c["required"])
    score = (50 if required_ok else 0) + round((optional_passed / max(1, optional_total)) * 50)
    grade = "A" if score >= 90 else ("B" if score >= 75 else ("C" if score >= 60 else "D"))

    return {
        "ok": required_ok,
        "grade": grade,
        "score": score,
        "os": platform.system(),
        "arch": platform.machine(),
        "screen_lock_free_ready": py_ok,
        "checks": checks,
    }
