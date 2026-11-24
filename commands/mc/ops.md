---
description: Connect headlessly to Minecraft hosting panels (with TOTP 2FA) and VPS SFTP endpoints through mc:ops.
argument-hint: "[hosting panel domain, 2FA/API action, SFTP log tail, config patch, or JAR deploy task]"
---

# /mc:ops

Activate the installed `mc-ops` skill for the `/mc:ops` route:

<request>$ARGUMENTS</request>

Operate hosting panels (Pterodactyl, Pelican, Crafty, PufferPanel) and SFTP/RCON/VPS endpoints completely off-screen via `mc_ops_profile_vault`, `mc_hosting_connect_plan`, `mc_hosting_server_action`, `mc_sftp_operations`, `mc_ops_rcon_execute`, `mc_ops_vps_ssh_preflight`, and `mc_ops_generate_docker_stack`. Inspect live server health & inline PNG TPS sparklines via `mc_bridge_plugin_query` (`tps-history`, `entities`, `errors`). Dry-run mutating actions first, create `.mckit.bak` backups before config patches, use atomic JAR swaps, and ensure every credential and 2FA seed remains redacted.
