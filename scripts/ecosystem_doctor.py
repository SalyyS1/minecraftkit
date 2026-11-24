#!/usr/bin/env python3
"""Unified SalyVn MinecraftKit + 10-Tool Ecosystem Readiness Scorecard."""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

import qa_smoke_doctor
import toolchain_bridge


def run_full_ecosystem_doctor(kit_root: Path) -> dict[str, Any]:
    local_doc = qa_smoke_doctor.run_kit_doctor(kit_root)
    tools_list = list(getattr(toolchain_bridge, "SUITE_TOOLS", ()))

    installed_suite = 0
    suite_status: list[dict[str, Any]] = []
    for entry in tools_list:
        if not isinstance(entry, dict):
            continue
        tid = str(entry.get("id", ""))
        bin_names = entry.get("binary_names") or [tid]
        binary = str(bin_names[0])
        found_path = ""
        for cand in bin_names:
            hit = shutil.which(str(cand))
            if hit:
                found_path = hit
                break
        if found_path:
            installed_suite += 1
        suite_status.append({
            "id": tid,
            "repo": entry.get("repo", f"SalyyS1/{tid}"),
            "category": entry.get("category", "toolchain"),
            "binary": binary,
            "installed_locally": bool(found_path),
            "path": found_path,
        })

    skills_dir = kit_root / "skills"
    skill_count = len([p for p in skills_dir.iterdir() if p.is_dir()]) if skills_dir.is_dir() else 0
    bridge_ready = (kit_root / "bridge-plugin" / "src" / "main" / "java" / "com" / "salyvn" / "mckit" / "bridge" / "McKitBridgePlugin.java").is_file()
    mod_ready = (kit_root / "client-mod" / "src" / "main" / "java" / "com" / "salyvn" / "mckit" / "client" / "McKitVisualClientMod.java").is_file()
    docker_ready = (kit_root / "docker" / "docker-compose.testgrid.yml").is_file()

    return {
        "ok": bool(local_doc.get("ok", True)),
        "kit_version": local_doc.get("kit_version", "5.0.0"),
        "local_runtime_grade": local_doc.get("grade", "A"),
        "local_runtime_score": local_doc.get("score", 100),
        "skill_count": skill_count,
        "companion_components": {
            "bridge_plugin_ready": bridge_ready,
            "fabric_client_mod_ready": mod_ready,
            "docker_testgrid_ready": docker_ready,
        },
        "suite_tool_count": len(suite_status),
        "suite_installed_count": installed_suite,
        "suite_tools": suite_status,
        "runtimes": local_doc.get("checks", []),
    }
