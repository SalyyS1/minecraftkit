"""Pure-Python Minecraft Anti-Cheat Compatibility & RPG False-Positive Auditor.

Audits GrimAC, Vulcan, Matrix, Polar, Spartan, and Negativity plugin stacks alongside
RPG skill plugins (MythicMobs, MMOCore, MMOItems, ModelEngine), Geyser/Floodgate Bedrock
crossplay, and MinecraftKit autonomous QA bot permissions.
"""

from __future__ import annotations

from typing import Any

PACKET_ANTICHEATS = ("grimac", "grim", "vulcan", "matrix", "polar", "spartan", "intave", "negativity")
RPG_SKILL_PLUGINS = ("mythicmobs", "mmocore", "mmoitems", "modelengine", "mythiccrucible", "mythicdungeons")


def audit_anticheat_compat(
    plugins: list[str],
    *,
    has_bedrock_geyser: bool = False,
    floodgate_exempt_configured: bool = False,
    bot_bypass_configured: bool = False,
    config_text: str = "",
) -> dict[str, Any]:
    """Audit anti-cheat plugin stack for conflicts, Bedrock falses, RPG skill kicks & bot QA compatibility."""
    if not isinstance(plugins, list) or not plugins:
        raise ValueError("'plugins' must be a non-empty list of installed plugin names.")

    low = [str(p).strip().lower() for p in plugins if str(p).strip()]
    ac_found = [p for p in low if any(ac in p for ac in PACKET_ANTICHEATS)]
    rpg_found = [p for p in low if any(r in p for r in RPG_SKILL_PLUGINS)]
    has_packetevents = any("packetevents" in p for p in low)
    has_geyser = has_bedrock_geyser or any("geyser" in p for p in low)
    has_floodgate = any("floodgate" in p for p in low)

    findings: list[dict[str, Any]] = []
    bot_perms: list[str] = []

    # AC-001: Multiple anti-cheats stacking
    if len(ac_found) >= 2:
        findings.append({
            "rule_id": "AC-001",
            "severity": "critical",
            "title": f"Multiple anti-cheats stacked ({', '.join(ac_found)}) cause packet cancellation loops and rubberbanding",
            "remediation": "Run ONE primary packet anti-cheat (e.g. GrimAC) rather than stacking overlapping movement checks.",
        })

    # AC-002: GrimAC without PacketEvents
    if any("grim" in p for p in ac_found) and not has_packetevents:
        findings.append({
            "rule_id": "AC-002",
            "severity": "high",
            "title": "GrimAC requires PacketEvents (shaded or plugin) aligned to your Paper/Folia MC version",
            "remediation": "Install the matching PacketEvents release for your Minecraft server version (1.21.4–26.3).",
        })

    # AC-003: RPG skill plugins + anti-cheat false positive risk
    if ac_found and rpg_found:
        if "exempt" not in config_text.lower() and "ignore-velocity" not in config_text.lower():
            findings.append({
                "rule_id": "AC-003",
                "severity": "high",
                "title": f"RPG skill/boss plugins ({', '.join(rpg_found)}) with {', '.join(ac_found)} risk movement/velocity false kicks",
                "remediation": "Enable velocity/knockback grace ticks or anti-cheat API exemptions during dash/leap/boss-pull skills.",
            })

    # AC-004: Bedrock Geyser/Floodgate exemptions
    if ac_found and has_geyser and not floodgate_exempt_configured:
        findings.append({
            "rule_id": "AC-004",
            "severity": "high",
            "title": "Geyser/Bedrock crossplay detected with anti-cheat without Floodgate exemption configured",
            "remediation": (
                "Install Floodgate and enable Bedrock/Floodgate check exemptions in your anti-cheat config "
                "(Bedrock physics/bridging/combat differ from Java packets)."
                if not has_floodgate
                else "Enable Floodgate Bedrock exemptions in your anti-cheat config to eliminate Bedrock falses."
            ),
        })

    # AC-005: QA bot bypass permissions
    for ac in ac_found:
        if "grim" in ac:
            bot_perms.append("grim.exempt")
        elif "vulcan" in ac:
            bot_perms.append("vulcan.bypass")
        elif "matrix" in ac:
            bot_perms.append("matrix.bypass")
        elif "polar" in ac:
            bot_perms.append("polar.exempt")
        elif "spartan" in ac:
            bot_perms.append("spartan.bypass")

    if ac_found and not bot_bypass_configured:
        findings.append({
            "rule_id": "AC-005",
            "severity": "medium",
            "title": "Headless QA bot group lacks explicit anti-cheat bypass permission for automated movement/click stages",
            "remediation": f"Grant {', '.join(bot_perms) or 'anticheat.bypass'} to a dedicated staging-only QA bot group in LuckPerms.",
        })

    crit = sum(1 for f in findings if f["severity"] == "critical")
    high = sum(1 for f in findings if f["severity"] == "high")
    med = sum(1 for f in findings if f["severity"] == "medium")
    score = max(0, 100 - crit * 30 - high * 15 - med * 8)
    grade = "A" if score >= 90 else ("B" if score >= 78 else ("C" if score >= 62 else ("D" if score >= 45 else "F")))

    return {
        "ok": crit == 0 and high == 0,
        "status": "pass" if (crit == 0 and high == 0) else "fail",
        "grade": grade,
        "score": score,
        "anticheats_detected": ac_found,
        "rpg_plugins_detected": rpg_found,
        "recommended_qa_bot_permissions": sorted(set(bot_perms)),
        "finding_count": len(findings),
        "findings": findings,
    }
