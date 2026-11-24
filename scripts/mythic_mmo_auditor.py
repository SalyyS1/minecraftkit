"""Offline MythicMobs & MMOItems/MythicCrucible YAML Lag & Exploit Auditor.

Catches server-crashing RPG skill/item configurations before deployment:
  - RPG-001: Ultra-high-frequency timer (~onTimer:1..4) or recursive skill loop without cooldown
  - RPG-002: Massive @EIR / @EntitiesInRadius / radius > 64 chunk-scan lag bomb
  - RPG-003: Excessive particle/effect burst (> 500 particles) causing client/Geyser packet kicks
  - RPG-004: Combat/economy stat exploit (negative cooldown/cost/health or extreme damage > 10000)
  - RPG-005: Spam-trigger skill (~onSwing / ~onUse / ~onAttack / ~onRightClick) missing Cooldown
"""

from __future__ import annotations

import re
from typing import Any


_TIMER_RE = re.compile(r"~onTimer\s*:\s*(\d+)", re.IGNORECASE)
_RADIUS_RE = re.compile(r"(?:@(?:EIR|EntitiesInRadius|PIR|PlayersInRadius)\{[^}]*\br(?:adius)?\s*=\s*(\d+(?:\.\d+)?)|\bradius\s*[:=]\s*(\d+(?:\.\d+)?))", re.IGNORECASE)
_PARTICLE_RE = re.compile(r"(?:particles?|effect:particles?)\{[^}]*\b(?:a|amount|count|points)\s*=\s*(\d+)", re.IGNORECASE)
_DAMAGE_RE = re.compile(r"(?:attack-damage|damage|skill-damage|max-health)\s*[:=]\s*(-?\d+(?:\.\d+)?)", re.IGNORECASE)
_NEG_COST_RE = re.compile(r"(?:cooldown|mana|stamina|price|cost|buy-price)\s*[:=]\s*(-\d+(?:\.\d+)?)", re.IGNORECASE)
_SPAM_TRIG_RE = re.compile(r"~on(?:Swing|Attack|Use|RightClick|Interact)\b", re.IGNORECASE)
_COOLDOWN_RE = re.compile(r"\bcooldown\s*[:=]\s*(\d+(?:\.\d+)?)", re.IGNORECASE)


def audit_mythic_mmo_yaml(
    yaml_text: str,
    *,
    ecosystem: str = "auto",
) -> dict[str, Any]:
    """Audit MythicMobs or MMOItems/MythicCrucible YAML text offline for lag & exploit rules."""
    if not isinstance(yaml_text, str) or not yaml_text.strip():
        raise ValueError("'yaml_text' must be a non-empty MythicMobs or MMOItems YAML string.")

    lower = yaml_text.lower()
    detected = ecosystem.strip().lower() if ecosystem and ecosystem.strip().lower() != "auto" else (
        "mythicmobs" if ("skills:" in lower or "~on" in lower or "@eir" in lower or "type:" in lower) else "mmoitems"
    )

    findings: list[dict[str, Any]] = []
    seen_rules: set[str] = set()

    def add(rule_id: str, severity: str, title: str, detail: str, remediation: str) -> None:
        if rule_id in seen_rules:
            return
        seen_rules.add(rule_id)
        findings.append({
            "rule_id": rule_id,
            "severity": severity,
            "title": title,
            "detail": detail,
            "remediation": remediation,
        })

    # RPG-001: Ultra-fast ~onTimer (< 5 ticks)
    fast_timers = [int(m.group(1)) for m in _TIMER_RE.finditer(yaml_text) if int(m.group(1)) < 5]
    if fast_timers:
        add(
            "RPG-001",
            "error",
            "Sub-5-tick ~onTimer trigger risks severe main-thread / Folia region TPS collapse",
            f"Found ultra-frequent timer interval(s): {sorted(set(fast_timers))} tick(s).",
            "Raise ~onTimer to >= 10-20 ticks (0.5s-1s) or gate heavy work behind conditions/cooldowns.",
        )

    # RPG-002: Huge entity targeter radius (> 64 blocks)
    huge_radii: list[float] = []
    for m in _RADIUS_RE.finditer(yaml_text):
        raw_val = m.group(1) or m.group(2)
        if raw_val:
            val = float(raw_val)
            if val > 64.0:
                huge_radii.append(val)
    if huge_radii:
        add(
            "RPG-002",
            "error",
            "Oversized entity targeter radius (> 64 blocks) causes chunk-scan lag bombs",
            f"Detected targeter radius up to {max(huge_radii):.1f} blocks.",
            "Cap @EIR / @PIR / radius to <= 32-48 blocks and add target limiters (e.g., limit=12, sort=NEAREST).",
        )

    # RPG-003: Particle flood (> 500)
    heavy_particles = [int(m.group(1)) for m in _PARTICLE_RE.finditer(yaml_text) if int(m.group(1)) > 500]
    if heavy_particles:
        add(
            "RPG-003",
            "warning",
            "Excessive particle burst risks Netty bandwidth spikes and Bedrock/Geyser kicks",
            f"Found particle emission count(s) up to {max(heavy_particles)} per trigger.",
            "Keep particle amount/points <= 120 per burst and set viewDistance <= 32.",
        )

    # RPG-004: Extreme damage / negative stats or costs
    bad_stats: list[str] = []
    for m in _DAMAGE_RE.finditer(yaml_text):
        val = float(m.group(1))
        if val < 0.0 or val > 10000.0:
            bad_stats.append(m.group(0).strip())
    for m in _NEG_COST_RE.finditer(yaml_text):
        bad_stats.append(m.group(0).strip())
    if bad_stats:
        add(
            "RPG-004",
            "error",
            "Combat or economy stat exploit detected (negative cost/stat or >10,000 damage)",
            f"Flagged suspicious values: {', '.join(bad_stats[:5])}.",
            "Clamp damage/health to intended server tier bounds and enforce strictly non-negative cooldown/price/mana.",
        )

    # RPG-005: Spam trigger missing Cooldown
    has_spam_trigger = bool(_SPAM_TRIG_RE.search(yaml_text))
    has_positive_cd = any(float(m.group(1)) > 0.0 for m in _COOLDOWN_RE.finditer(yaml_text))
    if has_spam_trigger and not has_positive_cd:
        add(
            "RPG-005",
            "warning",
            "Spam-able player/mob interaction trigger lacks a positive Cooldown",
            "Detected ~onSwing / ~onUse / ~onAttack / ~onRightClick without any positive Cooldown field.",
            "Add `Cooldown: 2` (or skill-level cooldown) so auto-clickers cannot spam skill execution 20x/sec.",
        )

    errors = sum(1 for f in findings if f["severity"] == "error")
    warnings = sum(1 for f in findings if f["severity"] == "warning")
    if errors >= 2:
        grade = "F"
    elif errors == 1:
        grade = "D"
    elif warnings >= 2:
        grade = "C"
    elif warnings == 1:
        grade = "B"
    else:
        grade = "A"

    color = "brightgreen" if grade == "A" else ("green" if grade == "B" else ("yellow" if grade == "C" else "red"))
    return {
        "ok": errors == 0,
        "status": "fail" if errors > 0 else ("warn" if warnings > 0 else "pass"),
        "grade": grade,
        "ecosystem": detected,
        "finding_count": len(findings),
        "error_count": errors,
        "warning_count": warnings,
        "findings": findings,
        "badge_json": {
            "schemaVersion": 1,
            "label": f"{detected} yaml",
            "message": f"grade {grade} · {errors} errors · {warnings} warnings",
            "color": color,
        },
    }
