# MinecraftKit Documentation

MinecraftKit separates upstream facts, bytecode facts, source-derived architecture, and original design ideas. Start with the smallest document that answers the task.

## Ecosystem Snapshot

- 103 reviewed GitHub sources pinned to canonical identity and commit SHA.
- 901 official Mojang Java Edition version records in manifest order.
- 10 focused routes across production builds, core, RPG, shaders, dialogs, clients, packs, models, protocols, and NMS.
- Static VI/EN command wiki, ecosystem/source/version atlas, and deep RPG API explorer.

## Catalog Snapshot

- 10 supplied plugin artifacts and 10 matching decompiled roots.
- 5,345 public/protected namespace types and 41,887 public/protected members.
- 4,947 types and 39,262 members classified as plugin-owned.
- 398 types and 2,625 members retained but labeled `bundled-third-party`.
- 965 generated Markdown API shards.
- Zero unexplained class parser errors.

## Research Map

| Need | Document |
|---|---|
| Build and ship a Kotlin/Java plugin | [Plugin engineering handbook](plugin-engineering-handbook.md) |
| Route public Minecraft platform/plugin APIs | [Minecraft ecosystem API atlas](minecraft-ecosystem-api-atlas.md) |
| Browse every extracted symbol | [Complete API catalog](api/index.md) |
| Understand architecture and logic | [Plugin architecture and logic](plugin-architecture-and-logic.md) |
| Reuse professional engineering patterns | [Professional engineering patterns](professional-engineering-patterns.md) |
| Map RPG capabilities across plugins | [RPG feature catalog](rpg-feature-catalog.md) |
| Design new addons | [Original addon blueprints](original-addon-blueprints.md) |
| Understand AgentKit research and skill shape | [AgentKit skill design](agentkit-skill-design.md) |
| Install for Codex and Claude | [Codex and Claude compatibility](codex-claude-compatibility.md) |
| Audit provenance and limitations | [Research methodology](research-methodology.md) |

For upstream lookup, run `python scripts/query_sources.py <terms> --domain <route>`. For exact supplied RPG symbols, run `python scripts/query_api.py <terms>`. Agents should not load the 40 MB RPG API index into context.

## Confidence Labels

- `VERIFIED_UPSTREAM`: exact pinned canonical project/source/document evidence.
- `VERIFIED_BYTECODE`: direct JVM metadata from the supplied artifact.
- `DERIVED_SOURCE`: behavior inferred from decompiled source and cited paths.
- `ORIGINAL_DESIGN`: a new composition produced by this kit.
- `UNVERIFIED`: runtime or version-sensitive claim that needs an empirical test.

The kit contains no Minecraft/plugin JAR, class file, decompiled method body, or proprietary asset.
