# MinecraftKit Community Growth, Promotion & Issue-Driven Adoption Playbook

**Goal:** Grow `SalyyS1/minecraftkit` into the #1 open-source AI Engineering, MCP Server, Autonomous Bot QA & Server Ops toolkit for Paper, Folia, Purpur, Fabric, and RPG Minecraft developers worldwide and in Vietnam.

---

## 1. Core Positioning & Viral Hook ("Why Developers Star Immediately")

Don't pitch "just another docs repo." Lead with the **3 unmistakable painkillers**:
1. **"Stop opening 10 Minecraft windows that melt your 16 GB laptop."**
   - Show the visual benchmark: **10 Headless Protocol Bots = 420 MB RAM (0 desktop focus lock)** vs **10 Desktop Minecraft Clients = 26 GB RAM**.
2. **"Your AI coding agent can now join your server, `/login`, open `/shop`, take a screenshot, read the console crash, and fix the Java bug automatically."**
   - Record a 45-second screen recording showing Claude Code / Cursor calling `mc_run_qa_pipeline`, receiving an inline PNG GUI snapshot in chat, spotting a broken MythicMobs/MMOItems slot, patching the plugin, deploying via SFTP, and passing on the second run.
3. **"One MCP install unlocks 33 tools, 14 `/mc:*` skills, 41,887 bytecode-verified RPG APIs, and 10 specialized SalyVn CLI tools (`mcstage`, `foliascan`, `shadersmith`, `pluginscope`, `serverdoctor`, ...)."**

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
- **Glama MCP Directory** (`glama.json` already present — verify score badge is updated for v3.1.0!)
- **Smithery.ai** (`smithery.yaml` already present — publish v3.1.0 with 33 tools!)
- **Official MCP Registry** (`server.json` already aligned with schema!)
- **Awesome MCP Servers** (`punkpeye/awesome-mcp-servers`, `wong2/awesome-mcp-servers`, `appcypher/awesome-mcp-servers`) — 1 concise bullet highlighting *33 Minecraft engineering + headless QA bot + SFTP/hosting tools*.

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
| **Week 1** | Polish & Proof | Tag `v3.1.0`, publish GitHub Release with demo GIF + SHA-256 checksums, deploy updated GitHub Pages Showcase, open the 4 pinned community issues on `SalyyS1/minecraftkit`. |
| **Week 2** | MCP Registries & Dev Socials | Update Glama, Smithery, npm (`minecraftkit@3.1.0`), submit Awesome-MCP PRs, publish `r/admincraft` + `r/MinecraftPlugins` deep-dive post. |
| **Week 3** | Video Proof & Companion Plugin | Publish 60s YouTube Short / TikTok showing live bot stage QA + auto-fix; publish `mckit-bridge-plugin` on Hangar/Modrinth linking to MinecraftKit. |
| **Week 4** | Ecosystem Cross-Linking | Cross-link all 10 SalyyS1 Minecraft repos (`mcstage`, `foliascan`, `shadersmith`, `pluginscope`, `serverdoctor`, `packmigrate`, `packmerge`, `glyphsmith`, `rp-engine`, `texlab`) with a unified footer banner pointing to MinecraftKit Showcase. |
