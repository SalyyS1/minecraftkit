"""Offline Skript (.sk) Performance & Command-Injection Security Auditor.

Catches server-crashing and OP-escalation Skript patterns before deployment:
  - SK-001 (error): `every 1..4 ticks` or `on any move:` global loops crushing Paper/Folia TPS
  - SK-002 (error): `loop all entities` / `loop all blocks in radius > 32` main-thread stalls
  - SK-003 (error): Unsanitized `execute console command` with user input (`%arg%`, `%message%`) -> OP injection
  - SK-004 (warning): Unbounded persistent `{...::*}` list variables without `delete`/`clear` cleanup
  - SK-005 (warning): Synchronous SQL/HTTP calls on the tick thread without `async`
"""

from __future__ import annotations

import re
from typing import Any


_FAST_LOOP_RE = re.compile(r"\bevery\s+([1-4])\s+ticks?\b|\bon\s+any\s+move\s*:", re.IGNORECASE)
_HEAVY_SCAN_RE = re.compile(
    r"\bloop\s+all\s+entities\b|\bloop\s+all\s+blocks\s+in\s+radius\s+(\d+)",
    re.IGNORECASE,
)
_CMD_INJECT_RE = re.compile(
    r"(?:execute|make)\s+console\s+(?:execute\s+)?command\s+['\"][^'\"]*%(?:arg(?:-\d+|\s+\d+)?|message|chat\s+message)%",
    re.IGNORECASE,
)
_LIST_ADD_RE = re.compile(r"\badd\b[^\n]+\bto\s+\{[a-zA-Z0-9_.:%-]+::\*\}", re.IGNORECASE)
_LIST_CLEAR_RE = re.compile(r"\b(?:delete|clear|remove)\b[^\n]+\{[a-zA-Z0-9_.:%-]+::", re.IGNORECASE)
_SYNC_IO_RE = re.compile(r"\b(?:send\s+(?:a\s+)?(?:http\s+)?request\s+to|execute\s+['\"](?:SELECT|INSERT|UPDATE|DELETE))\b", re.IGNORECASE)
_ASYNC_HINT_RE = re.compile(r"\basync\b|\basync\s+effect\b|\bin\s+async\b", re.IGNORECASE)


def audit_skript_code(skript_text: str) -> dict[str, Any]:
    """Audit Skript (.sk) source offline for TPS hazards and console command injection."""
    if not isinstance(skript_text, str) or not skript_text.strip():
        raise ValueError("'skript_text' must be a non-empty Skript (.sk) source string.")

    findings: list[dict[str, str]] = []

    if _FAST_LOOP_RE.search(skript_text):
        findings.append({
            "rule_id": "SK-001",
            "severity": "error",
            "title": "High-frequency tick loop (`every 1-4 ticks` or `on any move`) degrades TPS",
            "detail": "Detected sub-5-tick periodic loop or unthrottled `on any move:` event.",
            "remediation": "Throttle periodic checks to `every 10 ticks` / `every 1 second` and use `on player move:` with distance checks instead of `on any move:`.",
        })

    heavy_hit = False
    for m in _HEAVY_SCAN_RE.finditer(skript_text):
        if m.group(1) is None or int(m.group(1)) > 32:
            heavy_hit = True
            break
    if heavy_hit:
        findings.append({
            "rule_id": "SK-002",
            "severity": "error",
            "title": "World-wide `loop all entities` or oversized block-radius scan blocks tick thread",
            "detail": "Scanning all loaded entities or >32-block spheres causes severe MSPT spikes.",
            "remediation": "Restrict to `loop all entities in radius 16 around player` and keep block scans <= 16 blocks or offload to FAWE/Java.",
        })

    if _CMD_INJECT_RE.search(skript_text):
        findings.append({
            "rule_id": "SK-003",
            "severity": "error",
            "title": "Unsanitized user input interpolated into `execute console command` (OP/RCE risk)",
            "detail": "Detected `%arg%` or `%message%` inside a console command execution string.",
            "remediation": "Validate strictly against an allowlist regex (`^[A-Za-z0-9_]{3,16}$`) or use native Skript effects instead of console command interpolation.",
        })

    if _LIST_ADD_RE.search(skript_text) and not _LIST_CLEAR_RE.search(skript_text):
        findings.append({
            "rule_id": "SK-004",
            "severity": "warning",
            "title": "Persistent list variable `{...::*}` appended without any `delete`/`clear` cleanup",
            "detail": "Unbounded persistent lists bloat `variables.csv` and slow server boot.",
            "remediation": "Use local temporary variables (`{_tmp::*}`) for transient data or prune persistent lists on `on quit` / scheduled cleanup.",
        })

    if _SYNC_IO_RE.search(skript_text) and not _ASYNC_HINT_RE.search(skript_text):
        findings.append({
            "rule_id": "SK-005",
            "severity": "warning",
            "title": "Synchronous HTTP or SQL call detected without `async` execution",
            "detail": "Blocking network/database I/O inside a Skript trigger stalls the entire server tick.",
            "remediation": "Wrap database/HTTP requests in skript-db / ReqN `async` sections or move persistence to an async Java/Kotlin plugin with HikariCP.",
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
            "label": "skript audit",
            "message": f"grade {grade} · {errors} errors · {warns} warnings",
            "color": color,
        },
    }
