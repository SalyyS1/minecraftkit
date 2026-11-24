---
name: mc-ops
description: "Connect headlessly to Minecraft hosting panels (Pterodactyl, Pelican, Crafty, PufferPanel, Multicraft) with domain, credentials, and RFC 6238 TOTP 2FA, plus SFTP/SSH log tailing, safe config patching, and atomic plugin JAR deploys without screen lock. Use whenever remote Minecraft server management, hosting panel automation, 2FA login, or SFTP deployment is requested."
---

# Headless Hosting, VPS, 2FA & SFTP Operations (`mc-ops`)

Manage remote Minecraft servers headlessly with strict secret redaction and backup-before-edit safety.

## Workflow

1. Locate the shared `minecraftkit` root (`../minecraftkit` after global install, or `../..` from source) and verify `SKILL.md` and `references/hosting-vps-sftp-ops.md`.
2. Validate panel endpoints and RFC 6238 TOTP 2FA configuration via `mc_hosting_connect_plan`.
3. Preview mutating operations with `dry_run=true` on `mc_hosting_server_action` and `mc_sftp_operations` before executing live restarts, config patches (with `.mckit.bak` backups), or atomic JAR deployments.
4. Keep every password, API key, cookie, and TOTP seed redacted from outputs and commits. Author credit: `SalyVn / Salyyy`.
