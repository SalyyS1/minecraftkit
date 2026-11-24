"""Offline Crontab & Backup Shell Script Safety Auditor for Minecraft VPS Hosts.

Detects world-corrupting and credential-leaking backup jobs before they run:
  - CRON-001 (error): Live world tar/zip/rsync without save-off + save-all flush (corrupt .mca risk)
  - CRON-002 (warning): Too-frequent full backups (every <= 30m) causing continuous disk I/O stalls
  - CRON-003 (error): Hardcoded RCON/SFTP/S3/R2 secrets inside crontab or shell script
  - CRON-004 (warning): Missing retention pruning policy risking 100% disk exhaustion
  - CRON-005 (warning): Missing offsite sync or restore/integrity verification (restic check / rclone)
"""

from __future__ import annotations

import re
from typing import Any


_LIVE_COPY_RE = re.compile(r"\b(tar|zip|rsync|cp\s+-r|restic\s+backup)\b", re.IGNORECASE)
_SAVE_FLUSH_RE = re.compile(r"save-off|save-all\s+flush|save-all", re.IGNORECASE)
_FREQ_CRON_RE = re.compile(r"(?:^|\n)\s*\*(?:/([1-9]|[12]\d|30))?\s+\*\s+\*\s+\*\s+\*", re.MULTILINE)
_SECRET_LEAK_RE = re.compile(
    r"(?:AWS_SECRET_ACCESS_KEY|RESTIC_PASSWORD|B2_ACCOUNT_KEY)\s*=\s*['\"]?[^\s$'\"#]{6,}|"
    r"sshpass\s+-p\s+['\"]?[^\s$'\"]+|"
    r"mcrcon\b[^\n]*\s-p\s+['\"]?[^\s$'\"]+",
    re.IGNORECASE,
)
_PRUNE_RE = re.compile(r"forget\s+--keep|prune|--delete|find\s+[^\n]*-mtime\s+\+\d+[^\n]*-delete|logrotate", re.IGNORECASE)
_OFFSITE_OR_VERIFY_RE = re.compile(r"\b(rclone|aws\s+s3|s3://|b2:|restic\s+check|mcstage\s+check-world|sha256sum)\b", re.IGNORECASE)


def audit_crontab_backups(script_text: str) -> dict[str, Any]:
    """Audit Minecraft VPS crontab / backup shell scripts offline."""
    if not isinstance(script_text, str) or not script_text.strip():
        raise ValueError("'script_text' must be a non-empty crontab or backup shell script string.")

    findings: list[dict[str, str]] = []

    if _LIVE_COPY_RE.search(script_text) and not _SAVE_FLUSH_RE.search(script_text):
        findings.append({
            "rule_id": "CRON-001",
            "severity": "error",
            "title": "Hot world backup lacks save-off + save-all flush coordination",
            "detail": "Detected tar/zip/rsync/restic backup without RCON/screen `save-off` and `save-all flush`.",
            "remediation": "Run `save-off` -> `save-all flush` -> backup -> `save-on` (using a `trap` so `save-on` always executes) to avoid torn Anvil `.mca` chunks.",
        })

    if _FREQ_CRON_RE.search(script_text):
        findings.append({
            "rule_id": "CRON-002",
            "severity": "warning",
            "title": "Over-frequent backup cron schedule (<= 30 minutes) risks disk I/O stalls",
            "detail": "Cron schedule runs every <= 30 minutes across all hours.",
            "remediation": "Schedule full incremental backups every 4-6 hours (e.g. `0 */6 * * *`) with ionice/nice throttling.",
        })

    if _SECRET_LEAK_RE.search(script_text):
        findings.append({
            "rule_id": "CRON-003",
            "severity": "error",
            "title": "Hardcoded RCON/SFTP/S3/Restic credential detected in cron or script",
            "detail": "Plaintext secret or password found inline (redacted from output).",
            "remediation": "Move secrets into a `chmod 0600` environment file (e.g. `/etc/minecraft/backup.env`) and reference via `--password-file` or `EnvironmentFile=`.",
        })

    if not _PRUNE_RE.search(script_text):
        findings.append({
            "rule_id": "CRON-004",
            "severity": "warning",
            "title": "No backup retention pruning policy found",
            "detail": "Backup script never prunes expired archives, risking 100% VPS disk exhaustion.",
            "remediation": "Add `restic forget --keep-daily 7 --keep-weekly 4 --prune` or `find /backups -name '*.tar.zst' -mtime +14 -delete`.",
        })

    if not _OFFSITE_OR_VERIFY_RE.search(script_text):
        findings.append({
            "rule_id": "CRON-005",
            "severity": "warning",
            "title": "No offsite replication or restore integrity verification detected",
            "detail": "Local-only backups fail on VPS disk failure or ransomware.",
            "remediation": "Replicate encrypted snapshots offsite (S3/R2/B2 via restic/rclone) and verify periodically with `restic check` + `mcstage check-world`.",
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
        "secrets_redacted": True,
        "findings": findings,
        "badge_json": {
            "schemaVersion": 1,
            "label": "backup cron",
            "message": f"grade {grade} · {errors} errors · {warns} warnings",
            "color": color,
        },
    }
