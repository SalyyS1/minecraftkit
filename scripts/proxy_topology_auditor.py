#!/usr/bin/env python3
"""Static Velocity / BungeeCord / Paper / Geyser-Floodgate Proxy Forwarding Topology Auditor.

Catches the highest-severity Minecraft network authentication & UUID-spoofing misconfigurations
without leaking forwarding secrets in logs or MCP outputs:
  - PROXY-001: Velocity forwarding mode is legacy/none instead of modern
  - PROXY-002: Missing, placeholder, or weak (<16 chars) forwarding secret
  - PROXY-003: Secret mismatch between Velocity and Paper backend, or Paper velocity.enabled=false
  - PROXY-004: Backend server-ip exposed on wildcard (0.0.0.0 / blank) with online-mode=false
  - PROXY-005: Geyser/Floodgate auth-type misconfiguration
"""

from __future__ import annotations

import re
from typing import Any

PLACEHOLDER_SECRETS = {
    "",
    "changeme",
    "secret",
    "your-secret-here",
    "velocity-secret",
    "mysecret",
    "123456",
    "password",
    "default",
}


def _redact_secret(val: str) -> str:
    if not val:
        return "<empty>"
    return f"<redacted:len={len(val)}>"


def _extract_toml_value(text: str, key: str) -> str:
    m = re.search(rf'(?m)^\s*{re.escape(key)}\s*=\s*["\']?([^"\'\r\n#]+)["\']?', text)
    return m.group(1).strip() if m else ""


def _extract_prop(text: str, key: str) -> str:
    m = re.search(rf'(?m)^\s*{re.escape(key)}\s*[:=]\s*([^\r\n#]*)', text)
    return m.group(1).strip() if m else ""


def _extract_yaml_scalar(text: str, key: str) -> str:
    m = re.search(rf'(?m)^\s*{re.escape(key)}\s*:\s*["\']?([^"\'\r\n#]+)["\']?', text)
    return m.group(1).strip() if m else ""


def audit_proxy_topology(
    *,
    velocity_toml: str = "",
    forwarding_secret: str = "",
    paper_global_yml: str = "",
    backend_server_properties: str = "",
    geyser_config_yml: str = "",
) -> dict[str, Any]:
    findings: list[dict[str, Any]] = []

    vel_mode = _extract_toml_value(velocity_toml, "player-info-forwarding-mode").lower()
    vel_online = _extract_toml_value(velocity_toml, "online-mode").lower()
    vel_secret = forwarding_secret.strip() or _extract_toml_value(velocity_toml, "forwarding-secret")

    # Extract Paper velocity block heuristically
    paper_vel_enabled = ""
    paper_vel_secret = ""
    if paper_global_yml:
        vel_block_match = re.search(r'(?ms)^\s*velocity\s*:\s*\n((?:\s{2,}.*\n?)*)', paper_global_yml)
        block = vel_block_match.group(1) if vel_block_match else paper_global_yml
        paper_vel_enabled = _extract_yaml_scalar(block, "enabled").lower()
        paper_vel_secret = _extract_yaml_scalar(block, "secret")

    backend_online = _extract_prop(backend_server_properties, "online-mode").lower()
    backend_ip = _extract_prop(backend_server_properties, "server-ip").strip()
    is_loopback_or_private = (
        backend_ip in ("127.0.0.1", "::1", "localhost")
        or backend_ip.startswith("10.")
        or backend_ip.startswith("192.168.")
        or bool(re.match(r"^172\.(1[6-9]|2\d|3[0-1])\.", backend_ip))
    )

    if velocity_toml:
        if vel_mode in ("legacy", "none", "bungeeguard", ""):
            sev = "critical" if vel_mode in ("legacy", "none", "") else "warning"
            findings.append({
                "code": "PROXY-001",
                "severity": sev,
                "component": "velocity.toml",
                "message": f"Velocity player-info-forwarding-mode is '{vel_mode or 'unset'}'; modern Paper 1.19+ / 1.21+ / 26.x backends should use 'modern'.",
                "remediation": 'Set player-info-forwarding-mode = "modern" in velocity.toml and match secret in config/paper-global.yml.',
            })
        if vel_online == "false":
            findings.append({
                "code": "PROXY-001",
                "severity": "warning",
                "component": "velocity.toml",
                "message": "Velocity edge online-mode = false (cracked/offline network). Ensure AuthMe/nLogin/LimboAuth is enforced before backend transfers.",
                "remediation": "Isolate unauthenticated players on an Auth Limbo server and block /server commands until login succeeds.",
            })

    if vel_mode == "modern" or paper_vel_enabled == "true" or vel_secret or paper_vel_secret:
        effective_secret = vel_secret or paper_vel_secret
        if effective_secret.lower() in PLACEHOLDER_SECRETS or len(effective_secret) < 16:
            findings.append({
                "code": "PROXY-002",
                "severity": "critical",
                "component": "forwarding.secret",
                "message": f"Velocity modern forwarding secret is missing, placeholder, or too short ({_redact_secret(effective_secret)}).",
                "remediation": "Generate a >=32-byte cryptographically random secret (openssl rand -hex 24) and store it with chmod 0600.",
            })

    if vel_secret and paper_vel_secret and vel_secret != paper_vel_secret:
        findings.append({
            "code": "PROXY-003",
            "severity": "critical",
            "component": "paper-global.yml",
            "message": f"Forwarding secret mismatch between Velocity ({_redact_secret(vel_secret)}) and Paper ({_redact_secret(paper_vel_secret)}). All players will be disconnected on join.",
            "remediation": "Copy the exact forwarding.secret string into config/paper-global.yml -> proxies.velocity.secret.",
        })

    if velocity_toml and paper_global_yml and vel_mode == "modern" and paper_vel_enabled != "true":
        findings.append({
            "code": "PROXY-003",
            "severity": "critical",
            "component": "paper-global.yml",
            "message": "Velocity uses modern forwarding, but Paper proxies.velocity.enabled is not true.",
            "remediation": "Set proxies.velocity.enabled: true and proxies.velocity.online-mode: true in config/paper-global.yml.",
        })

    if backend_server_properties and backend_online == "false" and not is_loopback_or_private:
        findings.append({
            "code": "PROXY-004",
            "severity": "critical",
            "component": "server.properties",
            "message": f"Backend server has online-mode=false while server-ip='{backend_ip or '0.0.0.0'}' is publicly routable (UUID spoofing / OP takeover bypass!).",
            "remediation": "Bind server-ip=127.0.0.1 (or private VPC IP) and drop direct external TCP 25565 traffic via ufw/nftables.",
        })

    if geyser_config_yml:
        g_auth = _extract_yaml_scalar(geyser_config_yml, "auth-type").lower()
        if g_auth == "offline":
            findings.append({
                "code": "PROXY-005",
                "severity": "warning",
                "component": "geyser/config.yml",
                "message": "Geyser remote.auth-type is 'offline'; Bedrock players lack Xbox Live Floodgate UUID verification.",
                "remediation": "Install Floodgate on Velocity + backends and set remote.auth-type: floodgate with matching key.pem.",
            })

    penalty = sum(
        30 if f["severity"] == "critical" else 15 if f["severity"] == "warning" else 5
        for f in findings
    )
    score = max(0, min(100, 100 - penalty))
    grade = "A" if score >= 90 else "B" if score >= 78 else "C" if score >= 62 else "D" if score >= 45 else "F"

    return {
        "ok": not any(f["severity"] == "critical" for f in findings),
        "grade": grade,
        "score": score,
        "summary": {
            "velocity_forwarding_mode": vel_mode or "not-provided",
            "velocity_secret_redacted": _redact_secret(vel_secret),
            "paper_velocity_enabled": paper_vel_enabled or "not-provided",
            "paper_secret_redacted": _redact_secret(paper_vel_secret),
            "backend_online_mode": backend_online or "not-provided",
            "backend_bind_ip": backend_ip or "0.0.0.0 (wildcard)",
            "backend_isolated": is_loopback_or_private,
        },
        "finding_count": len(findings),
        "findings": findings,
    }
