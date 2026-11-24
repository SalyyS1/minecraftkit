# Salyyy Minecraft Kit

[Tiếng Việt (README.vi.md)](README.vi.md) · [**Flagship Showcase**](https://salyys1.github.io/minecraftkit/showcase.html) · [RPG API Explorer](https://salyys1.github.io/minecraftkit/) · [Ecosystem Atlas](https://salyys1.github.io/minecraftkit/ecosystem.html) · [Diagnostics Lab](https://salyys1.github.io/minecraftkit/playground.html) · [Documentation Wiki](https://salyys1.github.io/minecraftkit/wiki.html) · [Growth Playbook](docs/GROWTH_STRATEGY.md) · [npm](https://www.npmjs.com/package/minecraftkit)

[![CI](https://github.com/SalyyS1/minecraftkit/actions/workflows/ci.yml/badge.svg)](https://github.com/SalyyS1/minecraftkit/actions/workflows/ci.yml)
[![Version: v3.5.0](https://img.shields.io/badge/version-v3.5.0-blue)](https://github.com/SalyyS1/minecraftkit/releases/tag/v3.5.0)
[![Glama MCP Score](https://glama.ai/mcp/servers/SalyyS1/minecraftkit/badges/score.svg)](https://glama.ai/mcp/servers/SalyyS1/minecraftkit)
[![Protocol: MCP JSON-RPC 2.0](https://img.shields.io/badge/MCP-JSON--RPC%202.0-1f6feb)](https://modelcontextprotocol.io)

All-in-one Minecraft plugin engineering, autonomous headless bot QA (Java SLP + Wire-Level Offline Login Probe + Bedrock/Geyser RakNet UDP), persistent freeform multi-turn bot sessions, off-screen PNG visual diff & MP4 timelapse capture, headless hosting/VPS/2FA/WebSocket & SFTP operations with a masked profile vault, companion Paper/Folia & Fabric testing bridges, 14 `/mc:*` agent skills, interactive GitHub Pages showcase, and a 45-tool stdio MCP server by **SalyVn / Salyyy**.

## What Salyyy Minecraft Kit Includes

- **Resource-Optimized Autonomous Test Bot Engine (`bot/`, `docker/`, `scripts/bot_engine.py`, `scripts/visual_capture.py`)**:
  - **Tier 1 Headless Protocol Bots (~42 MB RAM/bot, ZERO GUI, ZERO screen lock)**: Auto-joins servers, auto-completes `/register` and `/login` (AuthMe, nLogin, OpeNLogin, LimboAuth, VelocityAuth) with strict password redaction, accepts resource packs, runs stage-based or freeform gameplay assertions, and renders crisp off-screen PNG visual QA snapshots (HUD telemetry, 9×4 GUI/Chest slots, scoreboard, 2D entity minimap, redacted chat) returned directly inside MCP chat responses.
  - **Tier 2 Hybrid Docker/Xvfb Visual Client Grid (`docker/Dockerfile.visual-bot`, `docker/docker-compose.testgrid.yml`)**: Runs 1 containerized off-screen Fabric visual client (Xvfb + Mesa + ffmpeg) alongside N-1 lightweight protocol bots — saving **> 85% RAM** vs opening 10 desktop Minecraft tabs without ever stealing window focus!
- **Companion Testing Plugin & Client Mod (`bridge-plugin/`, `client-mod/`)**:
  - **`mckit-bridge-plugin`** (Paper/Folia Java 21): Token-authenticated loopback (`127.0.0.1:25590`) HTTP/JSON telemetry bridge exposing live TPS/MSPT, JVM heap, loaded chunks, online player GUI states, plugins, and a bounded ring buffer of grouped `SEVERE`/exception traces.
  - **`mckit-client-mod`** (Fabric 1.21.4+): Off-screen framebuffer capture & resource-pack/shader reload error bridge (`127.0.0.1:25591`) for Tier-2 Docker/Xvfb visual QA.
- **Headless Hosting / VPS Panel (with RFC 6238 TOTP 2FA) & SFTP Connector (`scripts/hosting_bridge.py`)**:
  - Connects headlessly to **Pterodactyl**, **Pelican**, **Crafty Controller**, **PufferPanel**, **Multicraft**, and generic web panels via domain, credentials/API key, and built-in pure-Python RFC 6238 TOTP 2FA — zero visible browser popups, strict secret redaction.
  - Full SFTP operations (`list`, `read`, `tail_log` with error highlighting, safe `.mckit.bak` config patching, atomic temp-file + SHA-256 plugin JAR deployment, crash report listing) with path-traversal protection.
- **Unified 10-Repo SalyyS1 Minecraft Toolchain (`scripts/toolchain_bridge.py`)**: Integrates `mcstage`, `shadersmith`, `packmigrate`, `packmerge`, `glyphsmith`, `pluginscope`, `serverdoctor`, `foliascan`, `rp-engine`, and `texlab` into a single `mc_run_qa_pipeline` end-to-end automated QA loop.
- **Offline RPG & Plugin Bytecode API Catalog**: 4,947 plugin-owned types and 41,887 bytecode-verified members across 10 major RPG and server plugins (`ModelEngine`, `MMOItems`, `MMOCore`, `MMOInventory`, `MMOProfiles`, `MythicCrucible`, `MythicDungeons`, `MythicEnchants`, `MythicRPG`, `CoreTools`), plus 103 curated GitHub sources and 901 Mojang release/snapshot records.
- **14 `/mc:*` Engineering Agent Skills**: Specialized routing skills and slash commands for Claude Code, Cursor, Windsurf, Antigravity, and OpenAI Codex covering `mc:bot`, `mc:build`, `mc:core`, `mc:rpg`, `mc:protocol`, `mc:nms`, `mc:ops`, `mc:pack`, `mc:model`, `mc:qa`, `mc:shader`, `mc:dialog`, `mc:client`, and `mc:suite`.
- **43-Tool Stdio MCP Server**: Pure Python 3.10+ JSON-RPC 2.0 MCP server (`scripts/mcp_server.py` and `minecraftkit mcp`) with native multimodal PNG image responses for live visual bot testing, Bedrock/Geyser RakNet UDP pings, plugin stage presets, synced `mcstage v0.9.0` suite generation, pixel-exact visual regression diffs, and ffmpeg MP4 timelapses.

## Quick Install

Install the canonical skill and all 10 `mc:*` domain wrappers for both Claude Code and Codex (works cross-platform on Windows, Linux, and macOS via PowerShell or the built-in Node.js SHA-256 verified installer):

```bash
npx minecraftkit install --target both
```

Install for a single agent target or install the CLI globally:

```bash
npx minecraftkit install --target claude
npx minecraftkit install --target codex

npm install -g minecraftkit
minecraftkit doctor
```

## Built-In MCP Server (Cursor / Windsurf / Claude Desktop / Claude Code)

Print a ready-to-paste configuration snippet tailored to your local environment:

```bash
npx minecraftkit mcp --print-config
```

Or add `minecraftkit` directly to `.cursor/mcp.json`, `.mcp.json`, or `claude_desktop_config.json`:

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

If you cloned this repository or installed the skill locally, you can also invoke `scripts/mcp_server.py` directly with zero npm startup overhead:

```json
{
  "mcpServers": {
    "minecraftkit": {
      "command": "python3",
      "args": ["-B", "/path/to/minecraftkit/scripts/mcp_server.py"]
    }
  }
}
```

### Exposed Read-Only MCP Tools

| Tool | Purpose |
| --- | --- |
| `mc_search_api` | Search 41,800+ offline classes, interfaces, methods, fields, and constructors by `terms`, `plugin`, `kind`, and `limit`. |
| `mc_list_plugins` | List all 10 indexed RPG plugins with versions, class-file targets, symbol counts, API boundaries, and integration risks. |
| `mc_search_sources` | Filter 103 curated upstream Minecraft, Paper, Folia, protocol, shader, and pack GitHub repositories with pinned commit SHAs. |
| `mc_version_capabilities` | Query Mojang version history (901 versions), Java requirements, protocol numbers, and resource/data pack formats (including `26.2`). |
| `mc_route_skill` | Recommend primary and secondary `/mc:*` engineering skills, reference handbooks, and verification checklists for a task. |
| `mc_folia_migration_advisor` | Audit Java/Kotlin snippets or Bukkit API symbols for Folia regionized threading hazards and output `RegionScheduler` / `EntityScheduler` / `teleportAsync` replacements. |
| `mc_diagnose_server_log` | Analyze Paper, Folia, Purpur, and Velocity crash logs, watchdog stalls, classloader/shading collisions, and JVM classfile mismatches. |
| `mc_inspect_type` | Inspect the full bytecode hierarchy of any indexed RPG plugin class, interface, enum, or record, including superclass, interfaces, indexed subtypes, constructors, methods, fields, and minimum Java version. |
| `mc_audit_gradle_build` | Audit `build.gradle.kts` / `build.gradle` and `paper-plugin.yml` / `plugin.yml` for bundled server APIs, un-relocated `shadowJar` packages, Paperweight mapping mismatches, Java toolchain gaps, and isolated classloader `join-classpath` issues. |
| `mc_audit_paper_plugin_yml` | Validate `paper-plugin.yml` (and optional dual `plugin.yml`) across Paper `1.19` through `26.3+` for YAML float truncation (`1.20` -> `1.2`), illegal legacy root keys (`commands`, `depend`, `libraries`), `bootstrapper` / `loader` / `main` class collisions, `bootstrap` vs `server` dependency graph ordering conflicts, isolated classloader `join-classpath` visibility, and Folia flags. |
| `mc_generate_pack_overlay` | Generate client- and server-validated `pack.mcmeta` files and `overlays.entries` manifests for resource packs and data packs spanning `1.20.1` through `26.3+` (enforcing `supported_formats` pre-minor clamping at `64`/`81`, `min_format`/`max_format` `[major, minor]` tuples, `OverlayMetadataSection` directory naming rules, and breaking-epoch splits). |
| `mc_audit_server_properties` | Audit `server.properties` alongside optional `config/paper-global.yml`, `spigot.yml`, and JVM flags for `network-compression-threshold` double-compression and sub-64-byte CPU burn hazards, Velocity/BungeeCord forwarding authentication mismatches, Netty EventLoop thread starvation or oversubscription, quadratic `(2d + 1)^2` simulation-distance chunk budgets, RCON plaintext exposure, resource-pack SHA-1/UUID contracts, Paper `26.3` schema drift, and Java 25 GC flags. |
| `mc_validate_item_components` | Validate Minecraft and Paper `1.20.5` through `26.3+` structured item data components, component patches, and companion client `assets/<namespace>/items/<id>.json` definitions (`custom_model_data` typed channels, `tooltip_display` vs removed `show_in_tooltip`, `food`/`consumable`/`use_remainder` splits, `equippable.asset_id` renames, `max_damage` + `max_stack_size` mutual exclusion, and client selector channel index bounds). |
| `mc_diagnose_crash_report` | Parse and triage Minecraft server and client crash reports (Vanilla, Paper, Folia, Fabric, Forge, NeoForge) for ticking entities (exact block coords and `/minecraft:kill` commands), ticking block entities (`/setblock air`), mixin application conflicts, classloader NoSuchMethodError/NoClassDefFoundError linkage faults, JVM OOM/Metaspace exhaustion, and corrupted chunk I/O boundaries with optional OASIS SARIF v2.1.0 output. |
| `mc_audit_datapack` | Audit Minecraft `1.20.5` through `26.3+` datapacks for `pack.mcmeta` format compliance (`pack_format` 41 through 97, integer or `[min, max]` range tuples), modern recipe component syntax (replacing legacy `result.item` and raw `tag` strings with structured component patches), recipe pattern bounds, cyclical tag reference graph loops, namespace validity, and `.mcfunction` command hygiene. |
| `mc_audit_spark_flamegraph` | Parse collapsed flamegraph stacks and indented Spark/JFR call-trees (`SPARK-001` through `SPARK-008`), compute deduplicated inclusive and child-subtracted exclusive self weights, demangle JDK 21+ hidden lambdas, attribute hotspots back to initiating plugins (including indexed RPG plugins), and separate genuine async worker pool starvation (`HikariPool`, socket stalls, lock convoys, nested future deadlocks) from benign idle worker parking, with optional OASIS SARIF v2.1.0 output. |
| `mc_analyze_folia_scheduler_trace` | Verify Folia 4-domain scheduler thread-affinity contracts (`REGION`, `ENTITY`, `GLOBAL`, `ASYNC`, plus `NETTY`) across stack traces and multi-thread dumps (`FOLIA-TRC-001` through `FOLIA-TRC-007`), catching `GlobalRegionScheduler` spatial escapes, async world/entity mutations, Netty packet-thread world access, blocking `CompletableFuture.join()` barrier deadlocks, synchronous teleports, and missing `EntityScheduler` retired callbacks, with optional OASIS SARIF v2.1.0 output. |
| `mc_audit_packet_codec` | Audit Minecraft `1.20.5` through `26.3+` `StreamCodec`, `CustomPacketPayload`, PacketEvents/ProtocolLib listeners, and Velocity plugin messaging channels (`NETTY-001` through `NETTY-008`), computing exact LEB128 VarInt and worst-case UTF-8/collection wire-byte budgets against `32,767 B` serverbound and `1,048,576 B` clientbound caps, catching unbounded decode DoS, asymmetric read/write order, `ByteBuf` ref-count leaks, invalid `ResourceLocation` channels, and plain `FriendlyByteBuf` registry-codec mismatches, with optional OASIS SARIF v2.1.0 output. |
| `mc_audit_sql_persistence` | Audit Paper, Folia, and Velocity plugin SQL persistence layers and HikariCP configurations (`SQL-001` through `SQL-007`), computing fleet MySQL connection budgets and `maxLifetime` vs `wait_timeout` safety margins, and catching synchronous tick-thread JDBC calls, SQLite multi-pool `SQLITE_BUSY` contention without WAL, unclosed JDBC resource leaks, SQL string interpolation, and direct Bukkit/Folia mutations inside async DB completion callbacks, with optional OASIS SARIF v2.1.0 output. |
| `mc_profile_chunk_io_barriers` | Profile Paper `1.21.4` through `26.3+` Moonrise and Folia async chunk I/O pipelines, plugin chunk tickets, and worldgen worker saturation (`CHUNK-IO-001` through `CHUNK-IO-008`), computing Sakasegawa M/M/c expected barrier latency, utilization `rho`, and resident chunk RAM budgets while catching synchronous tick-thread chunk loads, `CompletableFuture.join()` self-deadlocks, unbounded ticket leaks, `sync-chunk-writes` fsync stalls, and Folia `16x16` region-section escapes, with optional OASIS SARIF v2.1.0 output. |
| `mc_correlate_spark_jfr_traces` | Cross-correlate Spark CPU/wall/alloc flamegraphs with JDK Flight Recorder (JFR) event streams and unified HotSpot GC/safepoint/tick-spike logs (`CORR-001` through `CORR-007`), computing sweep-line interval overlap attribution, directed `JavaMonitorEnter` wait-for deadlock graphs, outside-TLAB allocation churn, JDK 21/25 virtual-thread pinning, and Folia region thread Gini skew, with optional OASIS SARIF v2.1.0 output. |
| `mc_bot_plan_resources` | Calculate optimal off-screen bot fleet architecture (Tier-1 Headless Protocol ~42 MB/bot vs Hybrid 1 Visual Docker/Xvfb + N-1 Protocol vs Cloud Grid), RAM savings vs desktop tabs, and anti-OOM governor caps. |
| `mc_bot_ping_server` | Native pure-Python Minecraft Java Edition Server List Ping (SLP) TCP handshake probe (version, protocol, online/max players, MOTD, latency) with zero client launch. |
| `mc_bot_run_stages` | Launch headless screen-lock-free test bots with auto-register/login (AuthMe/nLogin/LimboAuth, redacted passwords), stage assertions (`join`, `auth`, `accept_pack`, `command`, `move`, `click_slot`, `assert_chat`, `assert_gui`, `assert_scoreboard`, `assert_tps`), and off-screen PNG visual snapshots returned directly in chat. |
| `mc_bot_inspect_session` | Render an on-demand off-screen PNG visual QA card (HUD telemetry, 9×4 Chest/Inventory GUI grid, 2D entity minimap, scoreboard, redacted chat) directly as an MCP image block. |
| `mc_bot_generate_docker_grid` | Generate a resource-capped `docker-compose.testgrid.yml` for off-screen Tier-1 protocol bot pools and Tier-2 Xvfb visual Fabric containers. |
| `mc_hosting_connect_plan` | Validate headless hosting panel connections (Pterodactyl, Pelican, Crafty, PufferPanel, Multicraft, generic) with domain, credentials/API key, and built-in RFC 6238 TOTP 2FA generator (fully redacted, zero browser popups). |
| `mc_hosting_server_action` | Execute or dry-run headless hosting panel operations (`status`, `resources`, `start`, `stop`, `restart`, `kill`, `command`, `backups`). |
| `mc_sftp_operations` | Headless SFTP/SSH server operations (`list`, `read`, `tail_log`, safe `.mckit.bak` `patch_config`, atomic `deploy_jar`, `list_crashes`) with path-traversal guards and secret redaction. |
| `mc_suite_catalog` | Inspect all 10 integrated SalyyS1 Minecraft tools (`mcstage`, `shadersmith`, `packmigrate`, `packmerge`, `glyphsmith`, `pluginscope`, `serverdoctor`, `foliascan`, `rp-engine`, `texlab`), local availability, and recipes. |
| `mc_suite_orchestrate` | Construct or safely execute CLI commands across any integrated SalyyS1 Minecraft tool. |
| `mc_bridge_plugin_query` | Query the companion loopback token-authenticated `mckit-bridge-plugin` (TPS/MSPT, JVM heap, player GUI states via `/api/v1/gui`, loaded worlds via `/api/v1/worlds`, plugins, grouped SEVERE error ring buffer). |
| `mc_run_qa_pipeline` | Execute the complete 5-phase automated Minecraft QA loop: resource planning -> static plugin/pack/shader audits -> SFTP/Panel/mcstage deploy -> headless bot stage tests + visual PNG snapshot -> `serverdoctor` triage. |
| `mc_ops_profile_vault` | Manage masked reusable server/panel/SFTP/bot profiles (`list`, `get`, `save`, `delete`, `export_redacted`) stored with `chmod 0600` in `~/.minecraftkit/profiles.json` and `env:VAR` secret indirection. |
| `mc_bot_session_start` | Start a governed persistent freeform headless bot session with anti-OOM session cap, auto-auth, and immediate off-screen PNG visual snapshot. |
| `mc_bot_session_action` | Drive an active freeform bot session step-by-step (`command`, `chat`, `move`, `click_slot`, `look`, `accept_pack`, `wait`, `snapshot`) returning updated HUD/GUI/minimap PNG frames inline in chat. |
| `mc_bot_session_stop` | Stop a persistent bot session cleanly and return final session telemetry and recorded frame count. |
| `mc_bot_capture_timelapse` | Assemble recorded frames from a bot session into a real headless H.264 MP4 timelapse video via `ffmpeg` (gracefully degrades to indexed frame manifest if ffmpeg is absent). |
| `mc_bot_visual_diff` | Compute pixel-exact visual regression diffs between two base64 PNG bot snapshots, returning `diff_ratio`, `changed_pixels`, pass/fail verdict, and a highlighted visual diff PNG inline in chat. |
| `mc_bot_ping_bedrock` | Perform a pure-Python UDP RakNet Unconnected Ping (`0x01` -> `0x1C`) against Bedrock or GeyserMC/Floodgate crossplay servers (MOTD, version, protocol, online/max players, gamemode, latency). |
| `mc_bot_generate_stage_preset` | Generate customized autonomous bot QA stage presets for `authme_lobby`, `rpg_shop_gui`, `resource_pack_itemsadder_nexo`, `mythicmobs_dungeon`, and `folia_region_stress`. |
| `mc_hosting_console_stream_plan` | Build or live-fetch a screen-lock-free Pterodactyl/Pelican live console WebSocket handshake & command plan with strict JWT/API-key redaction. |
| `mc_suite_generate_mcstage_suite` | Generate a synced `mcstage.yml` (v0.9.0 `bot-probe` + `assert-bridge` TPS/GUI checks + Folia barrier checks) paired with a GitHub Actions QA workflow. |
| `mc_bot_login_handshake_probe` | Pure-Python wire-level Minecraft 1.20.2–1.21.4+ offline Login -> zlib SetCompression -> LoginSuccess -> Configuration probe (~18 MB RAM, zero Node/client install). |
| `mc_bot_export_stage_yaml` | Serialize a preset or custom bot QA stage list into a password-redacted `.mckit-stages.yml` recipe for CI or community sharing. |

### Exposed MCP Resources & Slash Prompts

- **MCP Resources (`resources/list` & `resources/read`)**: Exposes `minecraftkit://catalog/overview` (`application/json`), `minecraftkit://catalog/paper-26.3-item-components` (`application/json`), and 21 offline engineering handbooks (`minecraftkit://references/*.md`) covering Paper/Folia threading, Gradle/Shadow builds, Netty packets, Mojang mappings, GLSL shaders, dialogs, and RPG plugin boundaries.
- **MCP Prompts (`prompts/list` & `prompts/get`)**: Exposes all 10 `/mc:*` domain workflows (`mc-core`, `mc-build`, `mc-rpg`, `mc-protocol`, `mc-nms`, `mc-pack`, `mc-model`, `mc-shader`, `mc-dialog`, `mc-client`) as native parameterized MCP prompts.

## CLI Commands

```text
minecraftkit install [codex|claude|both] [--dry-run] [--version x.y.z]
minecraftkit update [codex|claude|both]
minecraftkit mcp [--print-config] [--root <dir>]
minecraftkit doctor [--json]
minecraftkit commands [--json]
minecraftkit wiki
minecraftkit version
```

### `/mc:*` Engineering Routes

| Route | Focus |
| --- | --- |
| `/mc:core` | Paper, Folia, Purpur, Velocity, Fabric, NeoForge runtime and version contracts |
| `/mc:build` | Kotlin/Java Gradle builds, Shadow relocation, HikariCP/SQLite/MySQL, CI publishing |
| `/mc:rpg` | RPG system architecture and verified bytecode integrations across 10 RPG plugins |
| `/mc:protocol` | Netty pipelines, StreamCodec, packet listeners, and version-safe wire contracts |
| `/mc:nms` | Mojang-mapped internals, Paperweight userdev, and multi-version adapter isolation |
| `/mc:bot` | Resource-optimized headless test bots, auto-auth, stage tests, and off-screen PNG/Docker Xvfb visual capture |
| `/mc:ops` | Headless hosting panels (Pterodactyl/Pelican/Crafty), RFC 6238 TOTP 2FA, and SFTP deployment/log ops |
| `/mc:qa` | End-to-end closed-loop Minecraft QA pipeline (audit -> deploy -> headless bot -> visual proof -> auto-fix) |
| `/mc:suite` | Unified orchestration across all 10 integrated SalyyS1 Minecraft open-source CLI/MCP tools |
| `/mc:pack` | Resource packs, data packs, custom fonts/glyphs, item models, and delivery contracts |
| `/mc:model` | Blockbench `.bbmodel` rigs, hitbox budgets, animations, and ModelEngine pipelines |
| `/mc:shader` | Vanilla core/post GLSL shaders, uniforms, render targets, and client boundaries |
| `/mc:dialog` | Server-driven dialogs, validated click actions, and form payload safety |
| `/mc:client` | Client mod boundaries vs vanilla-client display/entity/pack projections |

## Web Explorers

- **[RPG API Explorer](https://salyys1.github.io/minecraftkit/)**: Search indexed plugin classes, methods, fields, and architectural insights in the browser.
- **[Diagnostics Lab](https://salyys1.github.io/minecraftkit/playground.html)**: Run client-side Spark flamegraph hotspot classification (`SPARK-001`..`SPARK-008`), Folia 4-domain scheduler trace verification (`FOLIA-TRC-001`..`FOLIA-TRC-007`), Netty `StreamCodec` wire-byte budget and HikariCP/SQLite persistence audits (`NETTY-001`..`NETTY-008`, `SQL-001`..`SQL-007`), Moonrise chunk I/O barrier & Spark/JFR trace correlation (`CHUNK-IO-001`..`CHUNK-IO-008`, `CORR-001`..`CORR-007`), and SARIF v2.1.0 export with zero uploads.
- **[Minecraft Ecosystem Atlas](https://salyys1.github.io/minecraftkit/ecosystem.html)**: Browse 103 reviewed upstream repositories, Mojang version history, and release capability profiles.
- **[Bilingual Wiki (VI/EN)](https://salyys1.github.io/minecraftkit/wiki.html)**: Step-by-step installation guides, route overviews, and engineering checklists.

## Companion Minecraft Static Analysis & Resource Pack CLI Suite

| Tool | Purpose |
| --- | --- |
| [foliascan](https://github.com/SalyyS1/foliascan) | Static bytecode and taint-flow verifier for Folia regionized multithreading (`action.yml` + [browser JAR scanner](https://salyys1.github.io/foliascan/)). |
| [serverdoctor](https://github.com/SalyyS1/serverdoctor) | Offline post-mortem diagnostics across server logs, configs, JVM flags, crash reports, worlds, and access lists (`CLI` + `mcp`). |
| [pluginscope](https://github.com/SalyyS1/pluginscope) | Static plugin JAR packaging, Paper API compatibility, multi-plugin stack conflict, and resource pack auditor (`CLI` + `mcp`). |
| [mcstage](https://github.com/SalyyS1/mcstage) | Standalone integration runner that boots a real Paper, Folia, or Purpur server, installs your plugin, drives the console, and asserts on logs. |
| [glyphsmith](https://github.com/SalyyS1/glyphsmith) | Compiler that turns PNGs and pixel coordinates into exact Minecraft font glyphs, ascent/advance metrics, negative-space shifts, and resource packs. |

## Provenance & Notice

Review [NOTICE.md](NOTICE.md) before redistributing third-party-derived API metadata or catalog artifacts.
