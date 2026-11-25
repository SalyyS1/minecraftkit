"""Offline WorldGuard `regions.yml` Grief-Prevention & Flag-Inheritance Auditor.

Audits WorldGuard region definitions offline for production griefing & exploit risks:
  - WG-001 (error): Spawn/hub region missing critical grief flags (pvp/tnt/creeper-explosion/fire-spread: deny)
  - WG-002 (error): `__global__` region explicitly sets `build: allow` on protected/hub worlds
  - WG-003 (warning): Region sets `use: deny` without explicit `interact` or `chest-access` policy
  - WG-004 (error): Privileged command flag (`console-command-on-entry`) or dangerous bypass in flags
  - WG-005 (warning): Non-global regions defined with `priority: 0` risking flag-inheritance conflicts
"""

from __future__ import annotations

import re
from typing import Any


def audit_worldguard_regions(yaml_text: str, *, is_hub_world: bool = False) -> dict[str, Any]:
    """Audit WorldGuard `regions.yml` text offline and emit findings, grade & badge JSON."""
    if not isinstance(yaml_text, str) or not yaml_text.strip():
        raise ValueError("'yaml_text' must be a non-empty WorldGuard regions.yml string.")

    lower = yaml_text.lower()
    findings: list[dict[str, str]] = []

    has_spawn_region = bool(re.search(r"^\s{2,4}(?:spawn|hub|lobby|safezone)\s*:", lower, re.MULTILINE))
    if has_spawn_region:
        missing_flags = [
            flag for flag in ("pvp", "tnt", "creeper-explosion", "fire-spread")
            if not re.search(rf"\b{flag}\s*:\s*deny\b", lower)
        ]
        if missing_flags:
            findings.append({
                "rule_id": "WG-001",
                "severity": "error",
                "title": "Spawn/Hub region missing critical anti-grief deny flags",
                "detail": f"Missing `deny` protection for: {', '.join(missing_flags)}.",
                "remediation": "Set `pvp: deny`, `tnt: deny`, `creeper-explosion: deny`, and `fire-spread: deny` on your spawn/hub region.",
            })

    if "__global__:" in lower and re.search(r"build\s*:\s*allow\b", lower) and (is_hub_world or has_spawn_region):
        findings.append({
            "rule_id": "WG-002",
            "severity": "error",
            "title": "`__global__` region allows unrestricted building on hub/protected world",
            "detail": "Detected `build: allow` alongside `__global__`.",
            "remediation": "Set `build: deny` (or `passthrough: deny`) on `__global__` in lobby/hub worlds and grant build strictly in explicit child regions.",
        })

    if re.search(r"\buse\s*:\s*deny\b", lower) and not re.search(r"\b(?:interact|chest-access)\s*:", lower):
        findings.append({
            "rule_id": "WG-003",
            "severity": "warning",
            "title": "`use: deny` may silently break RPG NPCs, doors, anvils, and shop menus",
            "detail": "Found `use: deny` without explicit `interact` or `chest-access` flags.",
            "remediation": "Verify NPC/GUI clicks with `mc_bot_run_stages` or set `interact: allow` for player-facing hubs.",
        })

    if re.search(r"console-command-on-(?:entry|leave)\s*:", lower) or re.search(r"\b(?:op|lp\s+user)\b", lower):
        findings.append({
            "rule_id": "WG-004",
            "severity": "error",
            "title": "High-privilege console command flag detected inside WorldGuard region",
            "detail": "Region triggers console-level commands on player entry/leave.",
            "remediation": "Remove console-command triggers from WorldGuard flags or restrict edits strictly to signed GitOps deployments.",
        })

    non_global_text = re.sub(r"__global__:(?:\n[ \t]{4,}[^\n]*)*", "", lower)
    if re.search(r"\bpriority\s*:\s*0\b", non_global_text) and has_spawn_region:
        findings.append({
            "rule_id": "WG-005",
            "severity": "warning",
            "title": "Protected region uses `priority: 0`, risking ambiguous flag overlap",
            "detail": "Overlapping regions with identical priority 0 can inherit unintended PvP/build flags.",
            "remediation": "Assign explicit priority tiers (e.g. spawn=100, shop_zone=50, arena=20, __global__=0).",
        })

    errors = sum(1 for f in findings if f["severity"] == "error")
    warns = sum(1 for f in findings if f["severity"] == "warning")
    grade = "F" if errors >= 2 else ("D" if errors == 1 else ("C" if warns >= 2 else ("B" if warns == 1 else "A")))
    color = "brightgreen" if grade == "A" else ("green" if grade == "B" else ("yellow" if grade == "C" else "red"))

    return {
        "ok": errors == 0,
        "status": "fail" if errors > 0 else ("warn" if warns > 0 else "pass"),
        "grade": grade,
        "error_count": errors,
        "warning_count": warns,
        "findings": findings,
        "badge_json": {
            "schemaVersion": 1,
            "label": "worldguard",
            "message": f"grade {grade} · {errors} errors · {warns} warnings",
            "color": color,
        },
    }
