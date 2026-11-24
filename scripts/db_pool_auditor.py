#!/usr/bin/env python3
"""Static Minecraft Plugin Database Pool (HikariCP / MySQL / MariaDB / SQLite / Redis) Auditor."""

from __future__ import annotations

import re
from typing import Any

WEAK_DB_PASSWORDS = {"", "password", "123456", "root", "admin", "changeme", "secret", "minecraft"}


def _extract_val(text: str, *keys: str) -> str:
    for key in keys:
        m = re.search(rf'(?im)^\s*{re.escape(key)}\s*[:=]\s*["\']?([^"\'\r\n#]+)["\']?', text)
        if m:
            return m.group(1).strip()
    return ""


def audit_database_pool(
    *,
    config_text: str,
    network_server_count: int = 1,
) -> dict[str, Any]:
    text = config_text or ""
    low = text.lower()
    servers = max(1, int(network_server_count))
    findings: list[dict[str, Any]] = []

    db_type = _extract_val(text, "storage-method", "storage", "type", "driver").lower()
    host = _extract_val(text, "address", "host", "hostname", "mysql-host")
    username = _extract_val(text, "username", "user")
    password = _extract_val(text, "password", "pass")
    pool_raw = _extract_val(text, "maximum-pool-size", "max-pool-size", "pool-size")
    conn_timeout_raw = _extract_val(text, "connection-timeout")
    max_lifetime_raw = _extract_val(text, "maximum-lifetime", "max-lifetime")

    if ("mysql" in low or "mariadb" in low or host) and password.lower() in WEAK_DB_PASSWORDS:
        findings.append({
            "code": "DB-001",
            "severity": "critical",
            "message": f"Weak or default database password detected for user '{username or 'unspecified'}' (<redacted:len={len(password)}>).",
            "remediation": "Use a >=20-char random DB password and a least-privilege non-root SQL user scoped strictly to the plugin database.",
        })

    if pool_raw.isdigit():
        pool_sz = int(pool_raw)
        total_conns = pool_sz * servers
        if pool_sz > 20 or total_conns > 120:
            findings.append({
                "code": "DB-002",
                "severity": "high",
                "message": f"maximum-pool-size={pool_sz} across {servers} server(s) opens up to {total_conns} connections, risking MySQL max_connections exhaustion.",
                "remediation": "Set maximum-pool-size between 4 and 10 per backend node (HikariCP formula: cores * 2 + 1).",
            })

    if conn_timeout_raw.isdigit() and int(conn_timeout_raw) > 10000:
        findings.append({
            "code": "DB-003",
            "severity": "warning",
            "message": f"connection-timeout={conn_timeout_raw}ms (>10s) delays failover and risks watchdog timeouts if any caller blocks.",
            "remediation": "Set connection-timeout: 5000 (5 seconds) and keep all queries on AsyncScheduler.",
        })
    if max_lifetime_raw.isdigit() and int(max_lifetime_raw) >= 1800000:
        findings.append({
            "code": "DB-003",
            "severity": "warning",
            "message": f"maximum-lifetime={max_lifetime_raw}ms (>=30m) may exceed MariaDB/MySQL wait_timeout and cause stale socket errors.",
            "remediation": "Set maximum-lifetime: 1500000 (25 min, safely below MySQL wait_timeout).",
        })

    is_local_host = host.lower() in ("", "localhost", "127.0.0.1", "::1")
    if not is_local_host and ("usessl=false" in low or "use-ssl: false" in low):
        findings.append({
            "code": "DB-004",
            "severity": "warning",
            "message": f"Remote database host '{host}' disables TLS (useSSL=false); credentials & player data transit plaintext.",
            "remediation": "Enable TLS (`useSSL=true&requireSSL=true`) or connect exclusively over WireGuard / private VPC.",
        })

    if servers > 1 and ("sqlite" in db_type or "h2" in db_type or "sqlite" in low):
        findings.append({
            "code": "DB-005",
            "severity": "high",
            "message": f"Embedded SQLite/H2 storage configured for a {servers}-server proxy network causes split-brain player data & item dupes on /server switches.",
            "remediation": "Switch to shared MariaDB/MySQL + Redis cross-server locking/messaging for multi-server networks.",
        })

    penalty = sum(
        30 if f["severity"] == "critical" else 18 if f["severity"] == "high" else 10
        for f in findings
    )
    score = max(0, min(100, 100 - penalty))
    grade = "A" if score >= 90 else "B" if score >= 78 else "C" if score >= 62 else "D" if score >= 45 else "F"

    return {
        "ok": not any(f["severity"] in ("critical", "high") for f in findings),
        "grade": grade,
        "score": score,
        "network_server_count": servers,
        "detected_storage": db_type or ("mysql/mariadb" if host else "unspecified"),
        "password_redacted": f"<redacted:len={len(password)}>",
        "finding_count": len(findings),
        "findings": findings,
    }
