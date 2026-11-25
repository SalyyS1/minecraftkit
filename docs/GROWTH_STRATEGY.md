# MinecraftKit Community Growth, Promotion & Issue-Driven Adoption Playbook

**Goal:** Grow `SalyyS1/minecraftkit` into the #1 open-source AI Engineering, MCP Server, Autonomous Bot QA & Server Ops toolkit for Paper, Folia, Purpur, Fabric, and RPG Minecraft developers worldwide and in Vietnam.

---

## 1. Core Positioning & Viral Hook ("Why Developers Star Immediately")

Don't pitch "just another docs repo." Lead with the **3 unmistakable painkillers**:
1. **"Stop opening 10 Minecraft windows that melt your 16 GB laptop."**
   - Show the visual benchmark: **10 Headless Protocol Bots = 420 MB RAM (0 desktop focus lock)** vs **10 Desktop Minecraft Clients = 26 GB RAM**.
2. **"Your AI coding agent can now join your server, `/login`, open `/shop`, take a screenshot, read the console crash, and fix the Java bug automatically."**
   - Record a 45-second screen recording showing Claude Code / Cursor calling `mc_run_qa_pipeline`, receiving an inline PNG GUI snapshot in chat, spotting a broken MythicMobs/MMOItems slot, patching the plugin, deploying via SFTP, and passing on the second run.
3. **"One MCP install unlocks 100 verified tools (v10.3.0 GRAND FLAGSHIP), 7 Auto-Attached Inline PNG Charts (Bridge TPS/Entities/Chunks/Heap, JVM GC Pause, Bot Load-Test, Executive GO/NO-GO Release Scorecard), 10-Engine Offline Diagnostics Lab (1-click JSON/SARIF export), 14 Ready-to-Run Bot QA Presets (incl. MMOCore ActionBar HUD, Geyser Crossplay, Economy Anti-Dupe & Velocity Transfer), `assert_actionbar` & `assert_gui_title`, Pool RSS Anti-OOM Watchdog, 6 hardened anti-OOM cloud bot grids (including Oracle Cloud Always-Free 24 GB ARM64 $0/mo), SFTP `verify_jar` SHA-256 + `stat_world` + Panel `list_files` + `.mckit.bak` rollback, Companion Paper/Folia Bridge (`/api/v1/system`, 11/11 Java) & Fabric Visual Client Mod (`/api/v1/gui-state`, 8 endpoints), 14 `/mc:*` skills, 41,887 bytecode-verified RPG APIs, and 10 specialized SalyVn CLI tools (`mcstage` 38-tool MCP, `foliascan`, `shadersmith`, `pluginscope`, `serverdoctor`, ...)."**
   - Shareable deep-dive guides ready for Reddit/Discord/Facebook links: [HOSTING_2FA_SFTP_GUIDE.md](HOSTING_2FA_SFTP_GUIDE.md) & [BOT_OPTIMIZATION_BENCHMARKS.md](BOT_OPTIMIZATION_BENCHMARKS.md).

---

## 2. GitHub Issue-Driven Growth & Contributor Funnel (Inside `SalyyS1/minecraftkit`)

> **Rule:** Never spam unrelated external repositories. Instead, turn `SalyyS1/minecraftkit`'s own Issues, Discussions, and Releases into a high-trust magnet that ranks in Google/GitHub search!

### Recommended Pinned Public Issues on `SalyyS1/minecraftkit`
1. **Issue #1 (Pinned Roadmap & Feature Voting):** `[Roadmap] MinecraftKit v3.x -> v4.0: Autonomous Bot QA, Visual Docker Grid & Community Integrations`
   - Let server owners react with `:+1:` on requested integrations (Velocity LimboAuth presets, ItemsAdder/Oraxen/Nexo pack hooks, Bedrock Geyser bot probes, Pterodactyl WebSocket live log streaming).
2. **Issue #2 (Showcase & Stage Recipe Thread):** `[Community] Share your mc_bot_run_stages QA Recipes (AuthMe, RPG Shops, Dungeons, Bedwars)`
   - Encourages developers to share reusable YAML/JSON stage scripts, creating organic search traffic and repeat visits.
3. **Issue #3 (`good first issue` / `help wanted`):** `[Good First Issue] Add Auth Prompt Regex Presets for Additional Login Plugins & Hosting Panels`
   - Low-barrier PR entry point that converts users into contributors (and contributors share repos they're listed on!).
4. **Issue #4 (Compatibility Matrix Tracker):** `[Compatibility] Minecraft 1.21.4 -> 26.3+ Paper/Folia/Fabric Bot & Bridge Verification Matrix`

---

## 3. High-ROI Distribution Channels (Ready-to-Use Launch Templates)

### Channel A: Official MCP Directories & Awesome Lists (High-Intent AI Developers)
Submit clean, policy-compliant PRs/listings to:
- **Glama MCP Directory** (`glama.json` already present — verify score badge is updated for v10.3.0 / 100 tools!)
- **Smithery.ai** (`smithery.yaml` already present — publish v10.3.0 with 100 tools!)
- **Official MCP Registry** (`server.json` already aligned with schema!)
- **Awesome MCP Servers** (`punkpeye/awesome-mcp-servers`, `wong2/awesome-mcp-servers`, `appcypher/awesome-mcp-servers`) — 1 concise bullet highlighting *100 Minecraft engineering + headless QA bot + SFTP/2FA hosting tools*.

### Channel B: Global Minecraft Developer Communities
- **Reddit `r/admincraft` & `r/MinecraftPlugins`**
  - *Title Idea:* `I built an open-source MCP server + ~42MB headless test bot so Claude Code / Cursor can auto-join my Paper/Folia server, /login, inspect GUIs via inline PNGs, and fix crashes`
  - *Include:* Link to the live interactive GitHub Pages Showcase (`https://salyys1.github.io/minecraftkit/showcase.html`) + 30-second GIF of the RAM calculator and inline PNG bot snapshot.
- **PaperMC Forums / Hangar / SpigotMC Resources / BuiltByBit / Modrinth**
  - Publish `mckit-bridge-plugin` as a free developer-utility plugin linking back to `SalyyS1/minecraftkit` and `SalyyS1/mcstage`.
- **Discord Developer Communities**
  - PaperMC `#showcase`, Folia community, MythicCraft / Phoenix Development (MMOItems/MMOCore), Fabric Discord `#showcase`.

### Channel C: Vietnamese Minecraft & AI Dev Communities (Strong Home-Base Multiplier)
- Share bilingual demo posts + short vertical videos (TikTok / YouTube Shorts / Facebook Groups: Minecraft Dev VN, J2TEAM Community, Nghiện AI / Claude Code VN):
  - *Hook (VI):* **"Tự động hóa 100% quy trình test server Minecraft bằng AI: Bot 42MB tự join, tự `/register` `/login`, mở `/shop` chụp ảnh gửi thẳng về chat AI, tự kết nối Hosting 2FA + SFTP sửa bug không chiếm màn hình!"**
  - Link directly to `https://salyys1.github.io/minecraftkit/showcase.html` (which has a 1-click **VI / EN** toggle!).

---

## 4. 4-Week Launch Cadence Checklist

| Week | Focus | Deliverable |
| :--- | :--- | :--- |
| **Week 1** | Polish & Proof | Tag `v10.3.0`, publish GitHub Release with demo GIF + SHA-256 checksums, deploy updated GitHub Pages Showcase (12 interactive bot presets, 1-click RAM presets, Copy MCP & Stage YAML) & 10-Engine Diagnostics Lab (1-click JSON/SARIF), keep pinned community issues updated on `SalyyS1/minecraftkit`. |
| **Week 2** | MCP Registries & Dev Socials | Update Glama, Smithery, npm (`minecraftkit@10.3.0`), submit Awesome-MCP PRs, publish `r/admincraft` + `r/MinecraftPlugins` deep-dive post. |
| **Week 3** | Video Proof & Companion Plugin | Publish 60s YouTube Short / TikTok showing live bot stage QA + auto-fix; publish `mckit-bridge-plugin` on Hangar/Modrinth linking to MinecraftKit. |
| **Week 4** | Ecosystem Cross-Linking | Cross-link all 10 SalyyS1 Minecraft repos (`mcstage`, `foliascan`, `shadersmith`, `pluginscope`, `serverdoctor`, `packmigrate`, `packmerge`, `glyphsmith`, `rp-engine`, `texlab`) with a unified footer banner pointing to MinecraftKit Showcase. |

---

## 5. Copy-Paste-Ready Launch Posts (English & Vietnamese)

### A. Awesome-MCP-Servers PR Snippet (1-line Markdown bullet)
```markdown
- [SalyyS1/minecraftkit](https://github.com/SalyyS1/minecraftkit) 🐍 📇 🏠 - All-in-one Minecraft engineering & autonomous QA MCP server (100 tools, 7 inline PNG charts): 18-42 MB headless test bots (Java 1.20.4-26.3, Bedrock/Geyser, 14 QA presets, actionbar/GUI/XP/lore assertions, RSS watchdog, Oracle Always-Free ARM64 grid), auto-auth, visual diff/GIF/MP4 timelapse, 10-engine offline Diagnostics Lab (JSON/SARIF export), headless 2FA hosting/Pelican/RCON/SFTP (atomic deploy + SHA-256 verify_jar + stat_world + list_files + .mckit.bak rollback), companion Paper/Folia (`/api/v1/system`) & Fabric (`/api/v1/gui-state`) bridges, 41,887 offline RPG APIs, and 10 integrated Minecraft CLI tools (`mcstage` 38-tool MCP).
```

### B. Reddit (`r/admincraft` / `r/MinecraftPlugins`) & PaperMC Showcase Post
> **Title:** I built an open-source 100-tool Minecraft MCP server + 42 MB headless QA bot so Claude Code / Cursor can auto-join my Paper/Folia server, `/login`, inspect GUIs via inline PNG/GIF diffs, and fix bugs off-screen
>
> **Body:**
> Testing custom RPG plugins on Paper/Folia used to mean launching multiple desktop Minecraft clients (2.6 GB RAM each, stealing window focus every time) while bouncing between SFTP, Pterodactyl/Pelican, and `latest.log`.
>
> So I built **Salyyy Minecraft Kit** (`v10.3.0 GRAND FLAGSHIP`, 100% local-first, 242+ automated tests):
> - **Tier-1 Headless Protocol Bots (~18–42 MB RAM/bot, 0 GUI, 0 focus lock)** + pure-Python wire-level Login/Play probe + Bedrock/Geyser RakNet UDP ping + **14 Ready-to-Run Stage Presets** (AuthMe, RPG Shop, ItemsAdder/Nexo, MythicMobs Dungeon, MMOCore ActionBar HUD, Geyser Crossplay, Folia Stress, Economy Anti-Dupe, Velocity Transfer) + `assert_actionbar` & `assert_gui_title` + **Pool RSS Anti-OOM Watchdog** + **Oracle Cloud Always-Free ARM64 ($0/mo, 24 GB RAM) Off-Screen Grid**. Auto-detects AuthMe/nLogin/OpeNLogin `/register` & `/login` with strict `[REDACTED_PASSWORD]` scrubbing.
> - **7 Auto-Attached Inline PNG Charts & Visual Proof** (Bridge TPS/Entities/Chunks/Memory, JVM GC Pause, Bot Load-Test, Executive GO/NO-GO Release Scorecard) + Pixel-Exact Diff, Stitched Storyboard GIFs & ffmpeg MP4 Timelapses returned directly inside Claude Code / Cursor / Codex chat.
> - **Headless Hosting/VPS (Pterodactyl, Pelican, Crafty, PufferPanel) with pure-Python RFC 6238 TOTP 2FA, Source RCON, Live WS Console plans, Anti-OOM JVM Preflight, Panel `list_files` & Atomic SFTP JAR Deploy + SHA-256 `verify_jar` + `stat_world` + `.mckit.bak` Rollback** + `chmod 0600` masked profile vault.
> - **10-Engine Zero-Upload Offline Diagnostics Lab** (`playground.html` with 1-Click JSON/SARIF Export) + Static Auditors: Anvil `.mca` world corruption, Velocity/Paper/Geyser/AntiCheat, Skript/WorldGuard/Economy anti-dupe, Bukkit/Spigot/`plugin.yml`, MythicMobs/MMOItems, HikariCP/MySQL pools, Spark/JFR flamegraphs, and GLSL 1.21+ shaders.
> - **Companion `mckit-bridge-plugin` (Paper/Folia Java 21, incl. `/api/v1/system` & `/api/v1/threads` deadlock detection, 11/11 contract tests) & `mckit-client-mod` (Fabric + Docker Xvfb, `/api/v1/gui-state`, `/api/v1/captures` & `/api/v1/render-metrics`, 8 authenticated endpoints)** for live telemetry and off-screen 3D shader/pack captures.
> - **41,887 offline bytecode-verified RPG APIs** (ModelEngine, MMOItems, MMOCore, MythicCrucible, MythicDungeons...) + **10 integrated SalyVn CLI tools** (`mcstage` 38-tool MCP, `foliascan`, `shadersmith`, `pluginscope`, `serverdoctor`, `packmigrate`, `packmerge`, `glyphsmith`, `rp-engine`, `texlab`).
>
> Interactive Showcase (with 12 Interactive Stage Presets, 1-Click Fleet RAM Presets, Copy MCP & Stage YAML Export, GO/NO-GO Scorecard Simulator & 10-Engine Diagnostics Lab): https://salyys1.github.io/minecraftkit/showcase.html
> Quick install: `npx minecraftkit install --target both && npx minecraftkit mcp --print-config`

### C. Bài Đăng Cộng Đồng Minecraft Dev & AI Việt Nam (Facebook / Discord)
> **Tiêu đề:** Chia sẻ bộ công cụ mã nguồn mở **MinecraftKit v10.3.0 GRAND FLAGSHIP** — 100 công cụ MCP giúp AI (Claude Code / Cursor / Codex) tự test server Minecraft bằng Bot 18–42MB không chiếm màn hình!
>
> Anh em dev plugin Paper/Folia/RPG chắc từng đau đầu cảnh mở 5–10 tab Minecraft test tính năng muốn nổ RAM? Mình vừa hoàn thiện **Salyyy Minecraft Kit (v10.3.0 GRAND FLAGSHIP — 100 MCP Tools)** hoàn toàn mã nguồn mở & chạy local 100%:
> - 🤖 **Bot tự động siêu nhẹ (~18–42 MB RAM/bot, không mở app Minecraft, không cướp chuột)**: tự join server (Java 1.20.4–26.3 + Bedrock/Geyser), tự nhận diện & gõ `/register` `/login` AuthMe/nLogin (mật khẩu luôn bị ẩn `[REDACTED]`), có sẵn **14 preset kịch bản** (Shop GUI, MythicMobs, MMOCore ActionBar HUD, Geyser Crossplay, Economy Anti-Dupe, Velocity Transfer...), kiểm tra cả ActionBar, GUI Title, XP Level & Item Lore, tự chụp **7 loại biểu đồ PNG**, **quay GIF/MP4 Timelapse & so sánh pixel Visual Diff** trả thẳng về khung chat AI!
> - 🐳 **Docker Xvfb Hardened Grid + Oracle Cloud Always-Free 24 GB ARM64 ($0/tháng)**: có `no-new-privileges`, `pids_limit` và RSS watchdog chống nổ máy tuyệt đối; cần test shader/resource pack 3D thì chạy 1 container Xvfb ngầm kết hợp N-1 bot protocol, tiết kiệm >90% RAM.
> - 🔐 **Tự kết nối Hosting/VPS có 2FA TOTP, RCON & SFTP không chiếm màn hình**: hỗ trợ Pterodactyl, Pelican, Crafty (`list_files`), đẩy file `.jar` an toàn qua file tạm + kiểm tra toàn vẹn SHA-256 (`verify_jar`) + kiểm tra world (`stat_world`) + tự rollback `.mckit.bak`.
> - 🧰 **Tích hợp sẵn trọn bộ 10 công cụ Minecraft** (`mcstage` 38 MCP tools, `foliascan`, `shadersmith`, `packmigrate`, `pluginscope`, `serverdoctor`, `glyphsmith`, `packmerge`, `rp-engine`, `texlab`) + **41.887 API plugin RPG offline** + **Phòng Lab Chẩn Đoán 10 Công Cụ chạy ngay trên trình duyệt (xuất JSON/SARIF 1-click)**!
>
> 🌐 Trải nghiệm trực tiếp trên web (hỗ trợ Tiếng Việt / English): https://salyys1.github.io/minecraftkit/showcase.html
> ⚡ Cài nhanh 1 dòng: `npx minecraftkit install --target both`

### D. 60-Second Short-Form Video Storyboard (TikTok / YouTube Shorts / Reels)
- **0:00–0:08 (Hook):** Split screen: Left shows Task Manager hitting 98% RAM with 8 desktop Minecraft windows freezing PC; Right shows `minecraftkit` spawning 10 headless bots at **420 MB total RAM** while the user keeps coding smoothly.
- **0:08–0:25 (Auto-Auth + Stages):** Terminal/Chat shows `mc_bot_run_stages` joining Paper 26.3, auto-completing `/register [REDACTED_PASSWORD]`, opening `/shop`, and clicking Slot #13.
- **0:25–0:42 (Visual Proof in Chat):** Inline 9x4 GUI PNG + red-highlighted `mc_bot_visual_diff` pops right inside Claude Code / Cursor; AI reads `mckit-bridge-plugin` error trace, patches the Java bug, and redeploys via atomic SFTP.
- **0:42–0:55 (Re-run PASS):** Bot re-joins automatically -> `6/6 PASSED`, TPS `20.0`, 0 SEVERE errors.
- **0:55–1:00 (CTA):** On-screen banner: `npx minecraftkit install --target both` · `salyys1.github.io/minecraftkit/showcase.html` (Free & Open Source!).
