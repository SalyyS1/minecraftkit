"""Offline `bukkit.yml` & `spigot.yml` Anti-Lag & Entity-Budget Auditor (SPG-001..005)."""

from __future__ import annotations

import re
from typing import Any


def audit_bukkit_spigot_yml(config_text: str) -> dict[str, Any]:
    """Audit bukkit.yml / spigot.yml snippets offline for entity & tick-lag traps."""
    if not isinstance(config_text, str) or not config_text.strip():
        raise ValueError("'config_text' must be a non-empty bukkit.yml or spigot.yml string.")

    findings: list[dict[str, str]] = []
    lower = config_text.lower()

    m_mob = re.search(r"\bmonsters\s*:\s*(\d+)", lower)
    if m_mob and int(m_mob.group(1)) > 60:
        findings.append({
            "rule_id": "SPG-001",
            "severity": "warning",
            "title": "High bukkit.yml monster spawn limit increases AI tick load",
            "detail": f"spawn-limits.monsters is {m_mob.group(1)} (> 60).",
            "remediation": "Lower `spawn-limits.monsters` to 35-50 (paired with `per-player-mob-spawns: true` in Paper).",
        })

    m_act = re.search(r"entity-activation-range:[\s\S]{0,160}?\bmonsters\s*:\s*(\d+)", lower)
    if m_act and int(m_act.group(1)) > 28:
        findings.append({
            "rule_id": "SPG-002",
            "severity": "warning",
            "title": "Wide spigot.yml entity-activation-range wastes CPU on distant mobs",
            "detail": f"entity-activation-range.monsters is {m_act.group(1)} blocks (> 28).",
            "remediation": "Set `monsters: 24`, `animals: 16`, `raiders: 48`, `misc: 8` for high-player-count survival.",
        })

    m_item = re.search(r"merge-radius:[\s\S]{0,80}?\bitem\s*:\s*(\d+(?:\.\d+)?)", lower)
    if m_item and float(m_item.group(1)) < 2.5:
        findings.append({
            "rule_id": "SPG-003",
            "severity": "warning",
            "title": "Small `merge-radius.item` leaves excessive ground item entities",
            "detail": f"merge-radius.item is {m_item.group(1)} (< 2.5).",
            "remediation": "Raise `merge-radius.item: 3.5` and `merge-radius.exp: 4.5` to collapse farm drops.",
        })

    m_range = re.search(r"\bmob-spawn-range\s*:\s*(\d+)", lower)
    if m_range and int(m_range.group(1)) > 6:
        findings.append({
            "rule_id": "SPG-004",
            "severity": "warning",
            "title": "Large `mob-spawn-range` spawns mobs in unticked outer chunks",
            "detail": f"mob-spawn-range is {m_range.group(1)} (> 6).",
            "remediation": "Set `mob-spawn-range: 5` or `6` (must stay <= simulation-distance - 1).",
        })

    if re.search(r"\bbungeecord\s*:\s*true\b", lower):
        findings.append({
            "rule_id": "SPG-005",
            "severity": "error",
            "title": "Legacy `bungeecord: true` forwarding enabled (vulnerable to UUID spoofing if port exposed)",
            "detail": "spigot.yml uses legacy unauthenticated BungeeCord forwarding.",
            "remediation": "Migrate to Velocity modern HMAC forwarding (`mc_ops_plan_proxy_migration`) and set `bungeecord: false`.",
        })

    errors = sum(1 for f in findings if f["severity"] == "error")
    warns = sum(1 for f in findings if f["severity"] == "warning")
    grade = "F" if errors >= 2 else ("D" if errors == 1 else ("C" if warns >= 3 else ("B" if warns >= 1 else "A")))
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
            "label": "spigot/bukkit",
            "message": f"grade {grade} · {errors} errors · {warns} warnings",
            "color": color,
        },
    }
