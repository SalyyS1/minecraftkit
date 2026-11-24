---
description: Connect headlessly to Minecraft hosting panels (with TOTP 2FA) and VPS SFTP endpoints through mc:ops.
argument-hint: "[hosting panel domain, 2FA/API action, SFTP log tail, config patch, or JAR deploy task]"
---

# /mc:ops

Activate the installed `mc-ops` skill for the `/mc:ops` route:

<request>$ARGUMENTS</request>

Operate hosting panels (Pterodactyl, Pelican, Crafty, PufferPanel) and SFTP endpoints completely off-screen via `mc_hosting_connect_plan`, `mc_hosting_server_action`, and `mc_sftp_operations`. Dry-run mutating actions first, create `.bak` backups before config patches, use atomic JAR swaps, and ensure every credential and 2FA seed remains redacted.
