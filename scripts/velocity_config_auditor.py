"""Pure-Python Velocity (velocity.toml) & BungeeCord/Waterfall Proxy Security & Performance Auditor.

Audits proxy forwarding modes, secret hygiene, kick-existing-players session hijack risk,
backend bind exposure, and Netty compression settings offline with strict secret redaction.
"""

from __future__ import annotations

import re
from typing import Any


def audit_velocity_config(
    config_text: str,
    *,
    has_auth_plugin: bool = False,
) -> dict[str, Any]:
    """Audit velocity.toml or BungeeCord config.yml offline.

    Rules:
      - VEL-001 (critical): player-info-forwarding-mode = 'legacy' or 'none' (vulnerable to IP/UUID spoofing)
      - VEL-002 (critical): online-mode = false without declared AuthMe/LimboAuth protection
      - VEL-003 (critical): Weak/default or short inline forwarding-secret (never echoed in output!)
      - VEL-004 (high): Backend server addresses exposed on 0.0.0.0 / non-loopback without VPC isolation
      - VEL-005 (high/medium): kick-existing-players=true on offline-mode proxy or suboptimal compression/failover
    """
    if not isinstance(config_text, str) or not config_text.strip():
        raise ValueError("'config_text' must be a non-empty velocity.toml or BungeeCord config.yml string.")

    findings: list[dict[str, Any]] = []
    patches: list[str] = []

    # VEL-001: forwarding mode
    fwd_m = re.search(r'(?im)^\s*player-info-forwarding-mode\s*=\s*["\']?(\w+)["\']?', config_text)
    fwd_mode = fwd_m.group(1).lower() if fwd_m else ""
    if fwd_mode in ("legacy", "none"):
        findings.append({
            "rule_id": "VEL-001",
            "severity": "critical",
            "title": f"Insecure player-info-forwarding-mode='{fwd_mode}' allows backend UUID/IP spoofing",
            "remediation": "Set player-info-forwarding-mode = \"modern\" and match forwarding.secret on Paper/Folia backends.",
        })
        patches.append('velocity.toml -> player-info-forwarding-mode = "modern"')

    # VEL-002: online-mode
    online_m = re.search(r'(?im)^\s*online-mode\s*[:=]\s*(true|false)\b', config_text)
    online_mode = (online_m.group(1).lower() == "true") if online_m else True
    if not online_mode and not has_auth_plugin:
        findings.append({
            "rule_id": "VEL-002",
            "severity": "critical",
            "title": "Proxy online-mode=false without an authenticated LimboAuth/AuthMe layer",
            "remediation": "Enable online-mode = true for premium servers, or enforce LimboAuth/nLogin with Argon2 on a dedicated auth limbo.",
        })
        patches.append("velocity.toml -> online-mode = true (or enforce LimboAuth/AuthMe Velocity)")

    # VEL-003: weak inline forwarding-secret (NEVER echo secret value!)
    sec_m = re.search(r'(?im)^\s*forwarding-secret\s*=\s*["\']([^"\'\r\n]+)["\']', config_text)
    if sec_m:
        raw_sec = sec_m.group(1).strip()
        if len(raw_sec) < 16 or raw_sec.lower() in ("changeme", "secret", "password", "123456", "default", "velocity"):
            findings.append({
                "rule_id": "VEL-003",
                "severity": "critical",
                "title": "Weak or default inline forwarding-secret detected (value redacted)",
                "remediation": "Use forwarding-secret-file = \"forwarding.secret\" with a 32+ char cryptographically random secret (chmod 0600).",
            })
            patches.append('velocity.toml -> forwarding-secret-file = "forwarding.secret" (32+ random bytes)')

    # VEL-004: backend bind exposure in [servers]
    servers_block = re.search(r'(?is)\[servers\](.*?)(?:\n\[|\Z)', config_text)
    if servers_block:
        for line in servers_block.group(1).splitlines():
            m = re.match(r'^\s*([a-zA-Z0-9_-]+)\s*=\s*["\']([^"\']+)["\']', line)
            if not m:
                continue
            srv_name, addr = m.group(1), m.group(2).strip()
            if srv_name.lower() == "try":
                continue
            host = addr.split(":", 1)[0].strip()
            if host in ("0.0.0.0", "*") or (
                not host.startswith("127.")
                and host != "localhost"
                and not host.startswith("10.")
                and not host.startswith("192.168.")
                and not re.match(r"^172\.(1[6-9]|2\d|3[01])\.", host)
                and not host.endswith(".internal")
            ):
                findings.append({
                    "rule_id": "VEL-004",
                    "severity": "high",
                    "title": f"Backend server '{srv_name}' targets non-loopback/public host '{host}'",
                    "remediation": "Bind backends to 127.0.0.1 or a private VPC CIDR and block external TCP 25565 via ufw/iptables.",
                })
                patches.append(f"ufw deny 25565/tcp (allow only proxy IP for backend '{srv_name}')")

    # VEL-005: kick-existing-players / failover / compression
    kick_m = re.search(r'(?im)^\s*kick-existing-players\s*=\s*(true|false)\b', config_text)
    if kick_m and kick_m.group(1).lower() == "true" and not online_mode:
        findings.append({
            "rule_id": "VEL-005",
            "severity": "high",
            "title": "kick-existing-players=true on an offline-mode proxy allows kicking live staff/players by username",
            "remediation": "Set kick-existing-players = false when online-mode = false.",
        })
        patches.append("velocity.toml -> kick-existing-players = false")

    failover_m = re.search(r'(?im)^\s*failover-on-unexpected-server-disconnect\s*=\s*(true|false)\b', config_text)
    if failover_m and failover_m.group(1).lower() == "false":
        findings.append({
            "rule_id": "VEL-005",
            "severity": "medium",
            "title": "failover-on-unexpected-server-disconnect=false drops all players instead of routing to lobby",
            "remediation": "Set failover-on-unexpected-server-disconnect = true so restarts gracefully fall back to lobby.",
        })
        patches.append("velocity.toml -> failover-on-unexpected-server-disconnect = true")

    comp_m = re.search(r'(?im)^\s*compression-threshold\s*=\s*(-?\d+)\b', config_text)
    if comp_m and 0 <= int(comp_m.group(1)) < 128:
        findings.append({
            "rule_id": "VEL-005",
            "severity": "medium",
            "title": f"compression-threshold={comp_m.group(1)} burns proxy CPU on tiny packets",
            "remediation": "Set compression-threshold = 256 and compression-level = -1 (default).",
        })
        patches.append("velocity.toml -> compression-threshold = 256")

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
        "online_mode": online_mode,
        "forwarding_mode": fwd_mode or "unspecified",
        "secrets_redacted": True,
        "finding_count": len(findings),
        "findings": findings,
        "recommended_patches": patches,
    }
