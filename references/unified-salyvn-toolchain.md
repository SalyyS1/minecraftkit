# Unified SalyVn / SalyyS1 Minecraft Toolchain Suite (`mc:suite`)

MinecraftKit unifies all 10 open-source SalyyS1 Minecraft engineering tools behind `mc_suite_catalog`, `mc_suite_orchestrate`, and `mc_run_qa_pipeline`.

## Integrated Repositories

| Tool | Role | Category |
| --- | --- | --- |
| `mcstage` | Real Paper/Folia/Purpur integration runner with crash-guard MCS001-MCS017, Folia lag/recovery, RCON fault injection, JUnit & SARIF | `runtime-testing` |
| `shadersmith` | GLSL core/post-effect validator, std140 UBO layout checker & 26.3 migrator | `shaders` |
| `packmigrate` | Deterministic 1.20..26.3 CustomModelData & overlay migrator with perceptual dedup | `resource-pack` |
| `packmerge` | Deterministic resource pack union compiler (item models, fonts, sounds, lang, atlases) | `resource-pack` |
| `glyphsmith` | Bitmap font glyph solver, negative-space shift compiler & lockfile auditor | `resource-pack` |
| `pluginscope` | Static plugin JAR packaging, Paper API compatibility & stack conflict auditor + MCP | `static-audit` |
| `serverdoctor` | Offline server log, config, JVM flags, GC, crash & Spark diagnostics + MCP | `diagnostics` |
| `foliascan` | Folia regionized multithreading bytecode taint-flow scanner + browser JAR scanner | `static-audit` |
| `rp-engine` | Resource pack build delivery, custom models, emotes & animations runtime engine | `resource-pack` |
| `texlab` | Pixel art Minecraft resource pack texture editor with AI MCP integration | `textures` |

Place downloaded release JARs in `~/.minecraftkit/tools/<tool>.jar` or set `<TOOL>_JAR` env vars for instant local execution via `mc_suite_orchestrate`.
