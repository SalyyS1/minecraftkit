---
name: mc-suite
description: "Discover and orchestrate all 10 integrated SalyyS1 Minecraft engineering tools: mcstage, shadersmith, packmigrate, packmerge, glyphsmith, pluginscope, serverdoctor, foliascan, rp-engine, and texlab. Use whenever chaining multiple SalyVn Minecraft CLI tools, SARIF audits, shader/pack migrations, or real-server matrix testing."
---

# Unified SalyVn Minecraft Toolchain Suite (`mc-suite`)

Coordinate the complete 10-tool SalyyS1 Minecraft open-source toolchain from one MCP/CLI interface.

## Workflow

1. Locate the shared `minecraftkit` root (`../minecraftkit` after global install, or `../..` from source) and verify `SKILL.md` and `references/unified-salyvn-toolchain.md`.
2. Call `mc_suite_catalog` to inspect local tool availability (`~/.minecraftkit/tools/` or env vars) and supported SARIF/MCP modes.
3. Build or run safe argv commands with `mc_suite_orchestrate` across `mcstage`, `shadersmith`, `packmigrate`, `packmerge`, `glyphsmith`, `pluginscope`, `serverdoctor`, `foliascan`, `rp-engine`, and `texlab`. Author credit: `SalyVn / Salyyy`.
