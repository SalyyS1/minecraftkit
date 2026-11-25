# Headless Hosting Panel (2FA) & Atomic VPS SFTP Guide (EN / VI)

Connect MinecraftKit to your **Pterodactyl, Pelican, Crafty Controller, PufferPanel, Multicraft, or Linux VPS** completely **off-screen** (zero browser popups, zero desktop window hijacking, zero leaked credentials).

> **Tiếng Việt:** Hướng dẫn kết nối MinecraftKit tự động tới Hosting Panel (hỗ trợ cả **TOTP 2FA**) và **VPS SFTP** hoàn toàn chạy ngầm, không chiếm màn hình, tự động ẩn mật khẩu/token và tạo bản sao lưu `.mckit.bak` trước khi sửa file.

---

## 1. Security Model (Zero Leaks / Bảo mật tuyệt đối)

| Safeguard | How MinecraftKit Enforces It |
|---|---|
| **Local Vault (`chmod 0600`)** | `mc_ops_profile_vault` stores profiles only on your machine with strict owner-only permissions and **always returns masked values** (`****`) to AI chat. |
| **RFC 6238 TOTP 2FA** | Pure-Python HMAC-SHA1 6-digit OTP generator (`mc_hosting_connect_plan`) computes live 2FA codes locally from `env:MCKIT_TOTP_SECRET` without opening a browser or phone app. |
| **Atomic JAR Swaps** | `mc_sftp_operations` uploads to `.tmp`, verifies SHA-256 checksum, then atomically renames into `plugins/` so a mid-upload crash never corrupts your server. |
| **Automatic `.mckit.bak` Rollback** | Config edits automatically save a timestamped `.mckit.bak` backup before patching. |
| **Loopback-Only Companion Bridges** | `mckit-bridge-plugin` (`127.0.0.1:25590`, including live `/api/v1/threads` deadlock telemetry) and `mckit-visual-client-mod` (`/api/v1/captures`, `/api/v1/render-metrics`, `/api/v1/pack-status`) bind strictly to localhost with constant-time `X-MCKit-Token` verification. |

---

## 2. Quick Setup — Pterodactyl / Pelican / Crafty Panel (+ 2FA)

1. Export credentials in your local shell (never paste raw secrets into public repos):
   ```bash
   export MCKIT_PANEL_URL="https://panel.yourdomain.net"
   export MCKIT_PANEL_KEY="ptlc_your_client_api_key"
   export MCKIT_TOTP_SECRET="JBSWY3DPEHPK3PXP"   # optional if panel enforces TOTP 2FA
   ```
2. Save a named profile once via MCP:
   ```json
   {
     "tool": "mc_ops_profile_vault",
     "arguments": {
       "action": "save",
       "profile_name": "prod-survival",
       "panel_type": "pterodactyl",
       "panel_domain": "panel.yourdomain.net",
       "sftp_host": "node1.yourdomain.net",
       "sftp_port": 2022,
       "sftp_username": "srv_abcd1234"
     }
   }
   ```
3. Run headless server power/console actions or backup freshness checks:
   - `mc_hosting_server_action` (`status`, `start`, `restart`, `stop`, `command`)
   - `mc_hosting_backup_verify` (flags stale or truncated archives before deployment)

---

## 3. Atomic SFTP Deployment & Safe Log Tailing

Use `mc_sftp_operations` with IP/domain, port (`22` for VPS, `2022` for Pterodactyl Wings), username, and password/key from env:

- **List server tree**: `operation="list"`, `remote_path="/plugins"` (or via hosting panel API: `mc_hosting_server_action` with `action="list_files"`, `directory="/plugins"`)
- **Tail `latest.log` with SEVERE highlights**: `operation="tail_log"`, `remote_path="/logs/latest.log"`, `tail_lines=80`
- **Safe config patch (auto `.mckit.bak`)**: `operation="patch_config"`, `remote_path="/plugins/MyRPG/config.yml"`
- **Atomic plugin JAR deploy & SHA-256 verification**: `operation="deploy_jar"`, `local_path="build/libs/MyRPG.jar"`, `remote_path="/plugins/MyRPG.jar"` followed by `operation="verify_jar"` (asserts `PK\x03\x04` ZIP/JAR header + remote SHA-256 match)
- **Remote Anvil World Integrity Stat (`stat_world`)**: `operation="stat_world"`, `remote_path="/world"` (checks remote `level.dat` GZIP header, `session.lock` state, and `region/*.mca` 4096-byte sector alignment headlessly)

---

## 4. Full 5-Phase Autonomous QA Loop (1 MCP Call)

Once your hosting/SFTP profile is configured, run **`mc_qa_run_full_lifecycle`**:
1. **Phase 0**: `mc_bot_probe_protocol_matrix` (1.20.4..26.3 compatibility check)
2. **Phase 1**: Static JAR / Folia / exploit / permission audit (`pluginscope` + `foliascan`)
3. **Phase 2**: Headless SFTP atomic upload + Hosting Panel restart
4. **Phase 3**: Off-screen Tier-1 headless bot auto-join, AuthMe/nLogin auto-auth (passwords scrubbed), GUI/stage assertions
5. **Phase 4**: Companion `mckit-bridge-plugin` 60s TPS/MSPT sparkline PNG + single-file dark-mode HTML QA proof artifact attached directly into chat!
