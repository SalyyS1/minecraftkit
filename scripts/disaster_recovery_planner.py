"""Minecraft Server Backup & Disaster Recovery Planner + Restore-Test Simulator.

Generates zero-corruption live-world backup workflows (RCON save-off -> save-all flush ->
restic/rclone S3/B2 off-site snapshot -> save-on), RPO/RTO capacity math, and an automated
staging restore-verification recipe combining mcstage check-world + headless bot join QA.
"""

from __future__ import annotations

from typing import Any


def plan_disaster_recovery(
    *,
    server_name: str = "MyRPGServer",
    world_size_gb: float = 12.0,
    retention_days: int = 14,
    backup_interval_hours: int = 6,
    offsite_target: str = "s3",
    rcon_host: str = "127.0.0.1",
    rcon_port: int = 25575,
) -> dict[str, Any]:
    """Build a crash-safe Minecraft backup, off-site retention, and automated restore-test plan."""
    size_gb = max(0.1, float(world_size_gb))
    ret_days = max(1, min(365, int(retention_days)))
    interval_h = max(1, min(168, int(backup_interval_hours)))
    target = offsite_target.strip().lower()
    if target not in ("s3", "b2", "sftp", "r2"):
        target = "s3"

    snapshots_per_day = max(1, 24 // interval_h)
    total_snapshots = snapshots_per_day * ret_days
    # Deduplicated incremental restic/borg storage estimate: 1 full + ~7% delta per snapshot
    est_storage_gb = round(size_gb * (1.0 + 0.07 * max(0, total_snapshots - 1)), 2)
    est_rto_minutes = max(3, int(round(size_gb * 1.4 + 4)))

    repo_uri = {
        "s3": f"s3:s3.amazonaws.com/mc-backups-{server_name.lower()}",
        "r2": f"s3:https://${{R2_ACCOUNT_ID}}.r2.cloudflarestorage.com/mc-backups-{server_name.lower()}",
        "b2": f"b2:mc-backups-{server_name.lower()}",
        "sftp": f"sftp:backup@backup.internal:/srv/backups/{server_name.lower()}",
    }[target]

    backup_script = "\n".join([
        "#!/usr/bin/env bash",
        "set -euo pipefail",
        "# Credentials MUST come from environment variables (never hardcoded!)",
        f'export RESTIC_REPOSITORY="{repo_uri}"',
        'export RESTIC_PASSWORD="${MCKIT_BACKUP_KEY:?Set MCKIT_BACKUP_KEY}"',
        "",
        "cleanup() {",
        f'  mcrcon -H {rcon_host} -P {rcon_port} -p "${{MCKIT_RCON_PASS:?Set MCKIT_RCON_PASS}}" "save-on" || true',
        "}",
        "trap cleanup EXIT",
        "",
        "# 1. Flush chunks & pause world writes so Anvil .mca sectors stay 100% consistent",
        f'mcrcon -H {rcon_host} -P {rcon_port} -p "${{MCKIT_RCON_PASS}}" "save-off" "save-all flush"',
        "sleep 2",
        "",
        "# 2. Deduplicated encrypted snapshot (worlds + plugin configs)",
        f'restic backup /srv/minecraft/{server_name}/world /srv/minecraft/{server_name}/world_nether /srv/minecraft/{server_name}/world_the_end /srv/minecraft/{server_name}/plugins --exclude "*.jar" --exclude "cache/*"',
        "",
        "# 3. Prune according to retention policy",
        f"restic forget --keep-within {ret_days}d --prune",
    ])

    restore_drill = [
        {"step": 1, "action": "restic restore latest --target /tmp/mckit-restore-drill"},
        {"step": 2, "action": "mcstage check-world /tmp/mckit-restore-drill/world --require-unlocked --sarif restore-world.sarif"},
        {"step": 3, "action": "mc_bot_run_stages (tier1-protocol, 42 MB RAM) against ephemeral staging server restoring /tmp/mckit-restore-drill"},
        {"step": 4, "action": "rm -rf /tmp/mckit-restore-drill && record drill pass timestamp"},
    ]

    return {
        "ok": True,
        "server_name": server_name,
        "offsite_target": target,
        "rpo_hours": interval_h,
        "estimated_rto_minutes": est_rto_minutes,
        "world_size_gb": size_gb,
        "retention_days": ret_days,
        "total_retained_snapshots": total_snapshots,
        "estimated_dedup_storage_gb": est_storage_gb,
        "anvil_safe_save_flush": True,
        "secrets_from_env_only": True,
        "backup_script_sh": backup_script,
        "restore_verification_drill": restore_drill,
    }
