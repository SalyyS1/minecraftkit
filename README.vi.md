# Salyyy Minecraft Kit (v3.1.0)

[English (README.md)](README.md) · [**Trang Giới Thiệu Chính (Showcase)**](https://salyys1.github.io/minecraftkit/showcase.html) · [RPG API Explorer](https://salyys1.github.io/minecraftkit/) · [Ecosystem Atlas](https://salyys1.github.io/minecraftkit/ecosystem.html) · [Diagnostics Lab](https://salyys1.github.io/minecraftkit/playground.html) · [Wiki Song Ngữ](https://salyys1.github.io/minecraftkit/wiki.html) · [Chiến Lược Cộng Đồng](docs/GROWTH_STRATEGY.md)

Bộ công cụ AI Engineering, **33 công cụ MCP**, **14 kỹ năng `/mc:*`**, **Bot Kiểm Thử Tự Động siêu nhẹ không chiếm màn hình**, **Kết nối Hosting/VPS có 2FA & SFTP**, **Companion Testing Plugin & Fabric Client Mod**, và **tích hợp trọn bộ 10 công cụ Minecraft của SalyVn / Salyyy**.

## Điểm Nổi Bật Ở Bản v3.1.0

1. **Bot Kiểm Thử Tự Động Tối Ưu Tài Nguyên (`bot/`, `docker/`, `mc_bot_*`)**:
   - **Tier 1 — Bot Protocol không mở app Minecraft (~42 MB RAM/bot, không chiếm màn hình)**: Chạy cùng lúc 10–25 bot mà chỉ tốn < 1 GB RAM (tiết kiệm > 95% RAM so với mở 10 tab Minecraft!). Tự động join server, tự nhận diện & gõ `/register` `/login` (AuthMe, nLogin, LimboAuth...) với mật khẩu luôn được ẩn (`[REDACTED_PASSWORD]`), chạy theo stages hoặc tự do, tự chụp ảnh PNG giao diện HUD/GUI/Inventory/Minimap/Chat trả thẳng vào khung chat AI.
   - **Tier 2 — Docker Xvfb Visual Client (`docker/docker-compose.testgrid.yml`)**: Chạy 1 client Fabric trong container Xvfb + Mesa + ffmpeg để test shader/resource pack/model 3D và quay video MP4 chạy ngầm 100%, kết hợp cùng N-1 bot protocol!
2. **Tự Kết Nối Hosting/VPS 2FA & SFTP Không Chiếm Màn Hình (`mc_hosting_*`, `mc_sftp_operations`)**:
   - Hỗ trợ **Pterodactyl, Pelican, Crafty Controller, PufferPanel, Multicraft** với domain, tài khoản/API key và bộ sinh mã **2FA TOTP chuẩn RFC 6238** tích hợp sẵn.
   - SFTP đầy đủ: xem file, đọc `logs/latest.log` lọc lỗi tự động, sửa config có backup `.mckit.bak`, và đẩy file `.jar` an toàn qua file tạm + SHA-256.
3. **Plugin & Mod Hỗ Trợ Test Chuyên Dụng (`bridge-plugin/`, `client-mod/`)**:
   - `mckit-bridge-plugin` (Paper & Folia Java 21): mở cầu nối cục bộ `127.0.0.1:25590` có xác thực token `X-MCKit-Token` giúp AI đọc TPS/MSPT, RAM, GUI người chơi và danh sách lỗi `SEVERE` theo thời gian thực.
   - `mckit-client-mod` (Fabric 1.21.4+): hỗ trợ chụp ảnh framebuffer và bắt lỗi reload shader/resource pack trong môi trường Xvfb/Docker.
4. **Tích Hợp Toàn Bộ 10 Repo Minecraft Của SalyVn (`mc_suite_*`, `mc_run_qa_pipeline`)**:
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
