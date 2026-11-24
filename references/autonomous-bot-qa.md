# Autonomous Headless Bot QA & Off-Screen Visual Capture (`mc:bot`)

Use this guide when testing Minecraft servers with automated bots without opening desktop Minecraft windows or exploding host RAM.

## 3-Tier Resource-Optimized Architecture

1. **Tier 1 — Headless Protocol Bot (`bot/worker.mjs`, ~42 MB RAM/bot):**
   - Zero OpenGL/LWJGL, zero window focus stealing, runs 10–25+ concurrent bots in < 1 GB RAM.
   - Best for auth flows (`/register`, `/login`), commands, RPG GUIs, economy/shop interactions, scoreboards, chat assertions, and multi-player load testing.
   - Off-screen PNG snapshots (`scripts/visual_capture.py`) render live HUD, 9×4 GUI slots, minimap, scoreboard, and redacted chat straight into MCP chat responses.
2. **Tier 2 — Headless Docker/Xvfb Visual Client (`docker/Dockerfile.visual-bot`, ~1.4 GB RAM/bot):**
   - Runs a real Fabric client + `mckit-client-mod` inside Xvfb + Mesa/EGL + ffmpeg.
   - Zero desktop focus stealing; use a **Hybrid 1 Visual + N-1 Protocol** split (`mc_bot_plan_resources`) to save > 85% RAM versus desktop tabs.
3. **Tier 3 — Companion Server Telemetry (`bridge-plugin/`):**
   - Loopback-only (`127.0.0.1:25590`) token-authenticated Paper/Folia plugin exposing TPS/MSPT, heap, player/GUI state, and grouped SEVERE log traces.

## Auto-Auth & Credential Safety

- Supports AuthMe, nLogin, OpeNLogin, LimboAuth, VelocityAuth, and Vietnamese/English prompts.
- Passwords passed via `mc_bot_run_stages` or `MCKIT_BOT_PASSWORD` are scrubbed with `[REDACTED_PASSWORD]` before any chat log, PNG card, or MCP payload is emitted.
- Never commit server credentials or test passwords to version control.
