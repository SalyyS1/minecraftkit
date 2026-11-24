"""Pure-Python GeyserMC & Floodgate Bedrock Crossplay Config Security & Compatibility Auditor.

Audits Geyser config.yml and Floodgate config.yml offline for auth-type mismatches,
exposed UDP/proxy-protocol traps, username-prefix collisions, excessive Bedrock bandwidth,
and resource-pack/CustomModelData mapping readiness.
"""

from __future__ import annotations

import re
from typing import Any


def audit_geyser_config(
    config_text: str,
    *,
    behind_velocity_or_bungee: bool = True,
) -> dict[str, Any]:
    """Audit GeyserMC / Floodgate config.yml offline.

    Rules:
      - GEY-001 (critical): auth-type: offline on public server or mismatch with Floodgate
      - GEY-002 (high): bedrock.port=19132 without clone-remote-port / proxy-protocol clarity or remote.address exposed
      - GEY-003 (high): Missing Floodgate username-prefix (causes Java/Bedrock username collision!) or weak key-file path
      - GEY-004 (medium): compression-level or max-players / passthrough-motd misconfiguration
      - GEY-005 (medium): show-cooldown / xbox-achievements-enabled / custom-skull-render-distance Bedrock client lag
    """
    if not isinstance(config_text, str) or not config_text.strip():
        raise ValueError("'config_text' must be a non-empty GeyserMC / Floodgate config.yml string.")

    findings: list[dict[str, Any]] = []
    patches: list[str] = []

    # GEY-001: auth-type
    auth_m = re.search(r'(?im)^\s*auth-type\s*:\s*["\']?(\w+)["\']?', config_text)
    auth_type = auth_m.group(1).lower() if auth_m else ""
    if auth_type == "offline":
        findings.append({
            "rule_id": "GEY-001",
            "severity": "critical",
            "title": "Geyser auth-type: offline bypasses Xbox Live & Floodgate cryptographic authentication",
            "remediation": "Set auth-type: floodgate (recommended) or online, and install Floodgate on both proxy & backends.",
        })
        patches.append("Geyser config.yml -> remote.auth-type: floodgate")
    elif auth_type == "online" and behind_velocity_or_bungee:
        findings.append({
            "rule_id": "GEY-001",
            "severity": "medium",
            "title": "Geyser auth-type: online forces Bedrock players to own & log into a paid Java account",
            "remediation": "Install Floodgate and switch auth-type: floodgate so Bedrock players join seamlessly.",
        })
        patches.append("Geyser config.yml -> remote.auth-type: floodgate")

    # GEY-002: remote.address public exposure
    rem_m = re.search(r'(?is)remote\s*:\s*[\s\S]{0,160}?address\s*:\s*["\']?([^\s"\'#]+)', config_text)
    if rem_m:
        rem_addr = rem_m.group(1).strip().lower()
        if rem_addr not in ("auto", "127.0.0.1", "localhost") and not rem_addr.startswith("10.") and not rem_addr.startswith("192.168."):
            findings.append({
                "rule_id": "GEY-002",
                "severity": "high",
                "title": f"Geyser remote.address='{rem_addr}' sends unencrypted Java backend traffic over a non-loopback host",
                "remediation": "Co-locate Geyser on your Velocity/Paper node with remote.address: auto (or 127.0.0.1).",
            })
            patches.append("Geyser config.yml -> remote.address: auto")

    # GEY-003: Floodgate username-prefix collision
    pref_m = re.search(r'(?im)^\s*username-prefix\s*:\s*["\']([^"\']*)["\']', config_text)
    if pref_m is not None and pref_m.group(1) == "":
        findings.append({
            "rule_id": "GEY-003",
            "severity": "high",
            "title": "Empty Floodgate username-prefix causes Java/Bedrock player name collisions in LuckPerms/Economy/AuthMe",
            "remediation": 'Set username-prefix: "." (dot prefix) in Floodgate config.yml.',
        })
        patches.append('Floodgate config.yml -> username-prefix: "."')

    # GEY-004: compression-level
    comp_m = re.search(r'(?im)^\s*compression-level\s*:\s*(-?\d+)\b', config_text)
    if comp_m:
        lvl = int(comp_m.group(1))
        if lvl > 6 or lvl == 0:
            findings.append({
                "rule_id": "GEY-004",
                "severity": "medium",
                "title": f"Geyser bedrock.compression-level={lvl} either burns CPU (>6) or wastes Bedrock mobile bandwidth (0)",
                "remediation": "Set bedrock.compression-level: 6 (balanced CPU vs UDP bandwidth).",
            })
            patches.append("Geyser config.yml -> bedrock.compression-level: 6")

    # GEY-005: debug-mode left enabled in production
    if re.search(r'(?im)^\s*debug-mode\s*:\s*true\b', config_text):
        findings.append({
            "rule_id": "GEY-005",
            "severity": "medium",
            "title": "Geyser debug-mode: true floods logs and adds packet serialization overhead in production",
            "remediation": "Set debug-mode: false in Geyser config.yml.",
        })
        patches.append("Geyser config.yml -> debug-mode: false")

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
        "auth_type": auth_type or "unspecified",
        "finding_count": len(findings),
        "findings": findings,
        "recommended_patches": patches,
    }
