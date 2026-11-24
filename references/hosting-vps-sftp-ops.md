# Headless Hosting Panel, VPS, 2FA & SFTP Operations (`mc:ops`)

Use this guide when connecting AI agents to remote Minecraft hosting panels or VPS nodes completely off-screen.

## Supported Hosting Panels (Headless)

- **Pterodactyl / Pelican** (`/api/client/servers/{id}/resources`, `/power`, `/command`, `/backups`)
- **Crafty Controller v4** (`/api/v2/auth/login`, `/api/v2/servers/{id}/stats`, `/action/*`, `/stdin`)
- **PufferPanel**, **Multicraft**, and generic headless web panels.
- **RFC 6238 TOTP 2FA**: Built-in pure-Python generator (`mc_hosting_connect_plan`) supporting 6/8-digit Base32 secrets and `otpauth://totp/...` URIs.

## SFTP & Safe Remote Operations

- Use `mc_sftp_operations` with `dry_run=true` first to verify normalized remote paths and atomic deploy plans.
- Always take `.mckit.bak` backups before patching YAML/TOML/properties configs.
- Deploy built plugin JARs via temp staging file + SHA-256 checksum + atomic POSIX rename (`plugins/<name>.jar.mckit.tmp -> plugins/<name>.jar`).
- Never expose passwords, `ptlc_*` API keys, or TOTP seeds in prompts, logs, or commits.
