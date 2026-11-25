"""Offline `plugin.yml` & `paper-plugin.yml` Manifest Security & Folia Auditor (PLG-001..005)."""

from __future__ import annotations

import re
from typing import Any


def audit_plugin_yml(manifest_text: str, *, target_folia: bool = False) -> dict[str, Any]:
    """Audit plugin.yml / paper-plugin.yml offline for API, Folia, and permission hygiene."""
    if not isinstance(manifest_text, str) or not manifest_text.strip():
        raise ValueError("'manifest_text' must be a non-empty plugin.yml or paper-plugin.yml string.")

    lower = manifest_text.lower()
    findings: list[dict[str, str]] = []

    if not re.search(r"^\s*api-version\s*:\s*['\"]?1\.(?:19|20|21)|^\s*api-version\s*:\s*['\"]?26\.", lower, re.MULTILINE):
        findings.append({
            "rule_id": "PLG-001",
            "severity": "error",
            "title": "Missing or legacy `api-version` in plugin descriptor",
            "detail": "Modern Paper/Folia servers require an explicit `api-version` (e.g. `1.21` or `26.3`).",
            "remediation": "Add `api-version: '1.21'` (or `'26.3'`) so Paper skips expensive legacy bytecode remapping.",
        })

    if target_folia and not re.search(r"^\s*folia-supported\s*:\s*true\b", lower, re.MULTILINE):
        findings.append({
            "rule_id": "PLG-002",
            "severity": "error",
            "title": "Missing `folia-supported: true` while targeting Folia",
            "detail": "Folia refuses to load plugins that omit `folia-supported: true`.",
            "remediation": "Verify region-thread safety with `foliascan` and declare `folia-supported: true`.",
        })

    if re.search(r"^\s*commands\s*:", lower, re.MULTILINE) and not re.search(r"^\s+permission\s*:", lower, re.MULTILINE):
        findings.append({
            "rule_id": "PLG-003",
            "severity": "warning",
            "title": "Declared commands lack explicit `permission:` guards",
            "detail": "Commands without a `permission:` node in plugin.yml rely solely on runtime checks.",
            "remediation": "Attach explicit `permission:` nodes to every admin/economy/debug command.",
        })

    if re.search(r"(?:admin|reload|give|eco|staff|bypass)[^\n]*\n(?:[ \t]+[^\n]*\n){0,3}[ \t]+default\s*:\s*true\b", lower):
        findings.append({
            "rule_id": "PLG-004",
            "severity": "error",
            "title": "Privileged permission node defaults to `default: true` (all players)",
            "detail": "Detected admin/reload/give/staff/bypass permission granted by default to non-OP players.",
            "remediation": "Change `default: true` to `default: op` (or `default: false`) and assign via LuckPerms.",
        })

    if not re.search(r"^\s*main\s*:\s*[a-z0-9_.]+\.[a-z0-9_]+", lower, re.MULTILINE):
        findings.append({
            "rule_id": "PLG-005",
            "severity": "error",
            "title": "Missing or invalid `main:` fully-qualified class name",
            "detail": "Plugin loader requires a valid `main: com.example.MyPlugin` entry.",
            "remediation": "Set `main:` to your exact JavaPlugin subclass and verify with `mcstage inspect-jar`.",
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
            "label": "plugin.yml",
            "message": f"grade {grade} · {errors} errors · {warns} warnings",
            "color": color,
        },
    }
