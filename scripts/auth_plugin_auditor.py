#!/usr/bin/env python3
"""Static AuthMe / nLogin / OpeNLogin / LimboAuth Security & Autonomous Bot-QA Compatibility Auditor."""

from __future__ import annotations

import re
from typing import Any


def _find_yaml_val(text: str, key: str) -> str:
    m = re.search(rf'(?m)^\s*{re.escape(key)}\s*:\s*["\']?([^"\'\r\n#]+)["\']?', text)
    return m.group(1).strip() if m else ""


def audit_auth_plugin_config(
    *,
    config_yml: str,
    plugin_type: str = "authme",
    staging_bot_testing: bool = True,
) -> dict[str, Any]:
    ptype = (plugin_type or "authme").strip().lower()
    findings: list[dict[str, Any]] = []

    hash_algo = (
        _find_yaml_val(config_yml, "passwordHash")
        or _find_yaml_val(config_yml, "algorithm")
        or _find_yaml_val(config_yml, "hash")
    ).upper()
    if hash_algo in ("MD5", "SHA1", "PLAINTEXT", "PLAIN", "NONE"):
        findings.append({
            "code": "AUTH-001",
            "severity": "critical",
            "message": f"Weak password hashing algorithm '{hash_algo}' detected in {ptype} config.",
            "remediation": "Switch passwordHash to BCRYPT or ARGON2 immediately.",
        })

    allow_chat = _find_yaml_val(config_yml, "allowChat").lower()
    allow_move = _find_yaml_val(config_yml, "allowMovement").lower()
    if allow_chat == "true":
        findings.append({
            "code": "AUTH-002",
            "severity": "high",
            "message": "Unauthenticated players have allowChat: true before /login completes.",
            "remediation": "Set allowChat: false and restrict allowCommands strictly to /login, /l, /register, /reg.",
        })
    if allow_move == "true":
        findings.append({
            "code": "AUTH-002",
            "severity": "high",
            "message": "Unauthenticated players have allowMovement: true (can interact with spawn chests/portals before login).",
            "remediation": "Set allowMovement: false and enable teleportUnAuthedToSpawn: true.",
        })

    max_reg_ip = _find_yaml_val(config_yml, "maxRegPerIp")
    max_join_ip = _find_yaml_val(config_yml, "maxJoinPerIp") or _find_yaml_val(config_yml, "maxLoginPerIp")
    if staging_bot_testing:
        for label, raw in (("maxRegPerIp", max_reg_ip), ("maxJoinPerIp", max_join_ip)):
            if raw.isdigit() and int(raw) <= 1:
                findings.append({
                    "code": "AUTH-003",
                    "severity": "warning",
                    "message": f"{label}={raw} will block multi-bot headless stress tests originating from 127.0.0.1.",
                    "remediation": f"Raise {label} to >= 15 on staging/QA nodes or add 127.0.0.1 to AuthMe/nLogin IP bypass.",
                })

    sessions_enabled = _find_yaml_val(config_yml, "sessions").lower()
    session_timeout = _find_yaml_val(config_yml, "sessionTimeout")
    if sessions_enabled == "true" and session_timeout.isdigit() and int(session_timeout) > 60:
        findings.append({
            "code": "AUTH-004",
            "severity": "warning",
            "message": f"Auto-login sessionTimeout={session_timeout}m (>60m) increases IP-shared account takeover risk.",
            "remediation": "Keep sessionTimeout <= 15 minutes (or disable sessions on public cracked servers).",
        })

    penalty = sum(
        30 if f["severity"] == "critical" else 18 if f["severity"] == "high" else 8
        for f in findings
    )
    score = max(0, min(100, 100 - penalty))
    grade = "A" if score >= 90 else "B" if score >= 78 else "C" if score >= 62 else "D" if score >= 45 else "F"

    bot_auth_profile = {
        "plugin": ptype,
        "register_template": "/register <env:MCKIT_BOT_PASS> <env:MCKIT_BOT_PASS>",
        "login_template": "/login <env:MCKIT_BOT_PASS>",
        "recommended_prompt_regex": r"(?:please\s+(?:login|register)|/login|/register|đăng nhập|đăng ký)",
        "secrets_redacted": True,
    }

    return {
        "ok": not any(f["severity"] in ("critical", "high") for f in findings),
        "grade": grade,
        "score": score,
        "plugin_type": ptype,
        "detected_hash": hash_algo or "unspecified",
        "bot_auth_profile": bot_auth_profile,
        "finding_count": len(findings),
        "findings": findings,
    }
