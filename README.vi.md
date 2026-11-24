# Salyyy Minecraft Kit (v3.8.0)

[English (README.md)](README.md) · [**Trang Giới Thiệu Chính (Showcase)**](https://salyys1.github.io/minecraftkit/showcase.html) · [RPG API Explorer](https://salyys1.github.io/minecraftkit/) · [Ecosystem Atlas](https://salyys1.github.io/minecraftkit/ecosystem.html) · [Diagnostics Lab](https://salyys1.github.io/minecraftkit/playground.html) · [Wiki Song Ngữ](https://salyys1.github.io/minecraftkit/wiki.html) · [Chiến Lược Cộng Đồng](docs/GROWTH_STRATEGY.md)

Bộ công cụ AI Engineering, **50 công cụ MCP**, **14 kỹ năng `/mc:*`**, **Bot Kiểm Thử Tự Động siêu nhẹ không chiếm màn hình (Java SLP + Bot giao thức thuần Python Login->Config->Play gõ lệnh trực tiếp ~18MB + Bedrock/Geyser RakNet, Stages & Freeform nhiều lượt)**, **Báo cáo kiểm thử HTML tự khép kín nhúng ảnh PNG**, **Kiểm tra đồng bộ Resource Pack & Item Model (`MMOItems`/`ItemsAdder`/`Nexo`)**, **Kiểm tra Backup Hosting/VPS chống lỗi file 0-byte**, **Sinh tự động kịch bản `mcstage v0.12.0` + GitHub Actions QA**, **So sánh ảnh PNG Visual Diff & Quay video MP4 Timelapse chạy ngầm**, **Kho Profile ẩn mật khẩu (`chmod 0600`)**, **Kết nối Hosting/VPS có 2FA, Console WebSocket, Source RCON & SFTP**, **Companion Testing Plugin (kèm `/api/v1/command` sandbox) & Fabric Client Mod**, và **tích hợp trọn bộ 10 công cụ Minecraft của SalyVn / Salyyy**.

## Điểm Nổi Bật Ở Bản v3.3.0

1. **Bedrock/Geyser UDP Ping, Preset Test Chuyên Dụng & WebSocket Console (`mc_bot_ping_bedrock`, `mc_bot_generate_stage_preset`, `mc_hosting_console_stream_plan`)**:
   - Ping trực tiếp máy chủ crossplay Bedrock/GeyserMC qua giao thức RakNet UDP thuần Python.
   - 5 bộ kịch bản test dựng sẵn cho máy chủ thực tế (`authme_lobby`, `rpg_shop_gui`, `resource_pack_itemsadder_nexo`, `mythicmobs_dungeon`, `folia_region_stress`).
   - Hỗ trợ kế hoạch kết nối Live Console WebSocket không chiếm màn hình cho Pterodactyl/Pelican (ẩn hoàn toàn JWT/API key).

1. **Phiên Bot Tự Do Nhiều Lượt, So Sánh Ảnh Visual Diff & Quay Video MP4 (`mc_bot_session_*`, `mc_bot_visual_diff`, `mc_bot_capture_timelapse`)**:
   - AI có thể mở phiên bot sống liên tục (`mc_bot_session_start`), điều khiển từng bước (`mc_bot_session_action`: gõ lệnh, di chuyển, bấm slot GUI, nhận pack, chụp ảnh PNG trả ngay về khung chat), ghép chuỗi khung hình thành **video MP4 chạy ngầm qua `ffmpeg`**, và chạy **so sánh ảnh pixel-exact (`mc_bot_visual_diff`)** tô đỏ vùng GUI/HUD bị lệch sau khi sửa code!
2. **Kho Profile Bảo Mật Cho Hosting / VPS / SFTP / Bot (`mc_ops_profile_vault`)**:
   - Lưu cấu hình server tại `~/.minecraftkit/profiles.json` với quyền `chmod 0600`, hỗ trợ tham chiếu `env:TEN_BIEN` và tự động ẩn toàn bộ mật khẩu, API key, khóa TOTP 2FA khi AI đọc hồ sơ.
3. **Bot Kiểm Thử Tự Động Tối Ưu Tài Nguyên (`bot/`, `docker/`, `mc_bot_*`)**:
   - **Tier 1 — Bot Protocol không mở app Minecraft (~42 MB RAM/bot, không chiếm màn hình)**: Chạy cùng lúc 10–25 bot mà chỉ tốn < 1 GB RAM (tiết kiệm > 95% RAM so với mở 10 tab Minecraft!). Tự động join server, tự nhận diện & gõ `/register` `/login` (AuthMe, nLogin, LimboAuth...) với mật khẩu luôn được ẩn (`[REDACTED_PASSWORD]`), chạy theo stages hoặc tự do, tự chụp ảnh PNG giao diện HUD/GUI/Inventory/Minimap/Chat trả thẳng vào khung chat AI.
   - **Tier 2 — Docker Xvfb Visual Client (`docker/docker-compose.testgrid.yml`)**: Chạy 1 client Fabric trong container Xvfb + Mesa + ffmpeg để test shader/resource pack/model 3D và quay video MP4 chạy ngầm 100%, kết hợp cùng N-1 bot protocol!
4. **Tự Kết Nối Hosting/VPS 2FA & SFTP Không Chiếm Màn Hình (`mc_hosting_*`, `mc_sftp_operations`)**:
   - Hỗ trợ **Pterodactyl, Pelican, Crafty Controller, PufferPanel, Multicraft** với domain, tài khoản/API key và bộ sinh mã **2FA TOTP chuẩn RFC 6238** tích hợp sẵn.
   - SFTP đầy đủ: xem file, đọc `logs/latest.log` lọc lỗi tự động, sửa config có backup `.mckit.bak`, và đẩy file `.jar` an toàn qua file tạm + SHA-256.
5. **Plugin & Mod Hỗ Trợ Test Chuyên Dụng (`bridge-plugin/`, `client-mod/`)**:
   - `mckit-bridge-plugin` (Paper & Folia Java 21): mở cầu nối cục bộ `127.0.0.1:25590` có xác thực token `X-MCKit-Token` giúp AI đọc TPS/MSPT, RAM, GUI người chơi (`/api/v1/gui`), danh sách thế giới (`/api/v1/worlds`) và lỗi `SEVERE` theo thời gian thực.
   - `mckit-client-mod` (Fabric 1.21.4+): hỗ trợ chụp ảnh framebuffer và bắt lỗi reload shader/resource pack trong môi trường Xvfb/Docker.
6. **Tích Hợp Toàn Bộ 10 Repo Minecraft Của SalyVn (`mc_suite_*`, `mc_run_qa_pipeline`)**:
   - `mcstage`, `shadersmith`, `packmigrate`, `packmerge`, `glyphsmith`, `pluginscope`, `serverdoctor`, `foliascan`, `rp-engine`, `texlab`.

## Cài Đặt Nhanh

```bash
npx minecraftkit install --target both
npx minecraftkit mcp --print-config
```

Cấu hình MCP nhanh cho Claude Code / Cursor / Windsurf / Antigravity:

```json
{
  "mcpServers": {
    "minecraftkit": {
      "command": "npx",
      "args": ["-y", "minecraftkit", "mcp"]
    }
  }
}
```
