# Salyyy Minecraft Kit

[Tiếng Việt (README.vi.md)](README.vi.md) · [RPG API Explorer](https://salyys1.github.io/minecraftkit/) · [Ecosystem Atlas](https://salyys1.github.io/minecraftkit/ecosystem.html) · [Documentation Wiki](https://salyys1.github.io/minecraftkit/wiki.html) · [npm](https://www.npmjs.com/package/minecraftkit)

[![CI](https://github.com/SalyyS1/minecraftkit/actions/workflows/ci.yml/badge.svg)](https://github.com/SalyyS1/minecraftkit/actions/workflows/ci.yml)
[![Version: v2.5.0](https://img.shields.io/badge/version-v2.5.0-blue)](https://github.com/SalyyS1/minecraftkit/releases/tag/v2.5.0)
[![Glama MCP Score](https://glama.ai/mcp/servers/SalyyS1/minecraftkit/badges/score.svg)](https://glama.ai/mcp/servers/SalyyS1/minecraftkit)
[![Protocol: MCP JSON-RPC 2.0](https://img.shields.io/badge/MCP-JSON--RPC%202.0-1f6feb)](https://modelcontextprotocol.io)

Offline Minecraft plugin engineering catalog, 10 `/mc:*` agent skills for Claude Code and Codex, interactive web explorers, and a zero-dependency stdio MCP server by **SalyVn / Salyyy**.

## What Salyyy Minecraft Kit Includes

- **Offline RPG & Plugin Bytecode API Catalog**: 4,947 plugin-owned types and 41,887 bytecode-verified members across 10 major RPG and server plugins (`ModelEngine`, `MMOItems`, `MMOCore`, `MMOInventory`, `MMOProfiles`, `MythicCrucible`, `MythicDungeons`, `MythicEnchants`, `MythicRPG`, `CoreTools`), plus 103 curated Paper/Folia/Fabric/NeoForge/Velocity/pack GitHub sources and 901 Mojang release/snapshot version records.
- **10 `/mc:*` Engineering Agent Skills**: Specialized routing skills and slash commands for Claude Code and OpenAI Codex covering Paper/Folia runtime contracts (`mc:core`), Gradle/Kotlin builds (`mc:build`), RPG integrations (`mc:rpg`), packets (`mc:protocol`), NMS adapters (`mc:nms`), resource/data packs (`mc:pack`), Blockbench rigs (`mc:model`), shaders (`mc:shader`), dialogs (`mc:dialog`), and client projections (`mc:client`).
- **Interactive Web Explorers**: Zero-backend browser tools for instant symbol lookup, version capability inspection, and workflow search.
- **Built-In Stdio MCP Server**: Pure Python 3.10+ JSON-RPC 2.0 Model Context Protocol server (`scripts/mcp_server.py` and `minecraftkit mcp`) for Cursor, Windsurf, Claude Desktop, and Claude Code.

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

### Exposed MCP Resources & Slash Prompts

- **MCP Resources (`resources/list` & `resources/read`)**: Exposes `minecraftkit://catalog/overview` (`application/json`) plus 21 offline engineering handbooks (`minecraftkit://references/*.md`) covering Paper/Folia threading, Gradle/Shadow builds, Netty packets, Mojang mappings, GLSL shaders, dialogs, and RPG plugin boundaries.
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
| `/mc:pack` | Resource packs, data packs, custom fonts/glyphs, item models, and delivery contracts |
| `/mc:model` | Blockbench `.bbmodel` rigs, hitbox budgets, animations, and ModelEngine pipelines |
| `/mc:shader` | Vanilla core/post GLSL shaders, uniforms, render targets, and client boundaries |
| `/mc:dialog` | Server-driven dialogs, validated click actions, and form payload safety |
| `/mc:client` | Client mod boundaries vs vanilla-client display/entity/pack projections |

## Web Explorers

- **[RPG API Explorer](https://salyys1.github.io/minecraftkit/)**: Search indexed plugin classes, methods, fields, and architectural insights in the browser.
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
