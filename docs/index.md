# MinecraftRPG Kit Documentation

This kit separates bytecode facts, source-derived architecture, and original design ideas. Start with the smallest document that answers the task.

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
| Browse every extracted symbol | [Complete API catalog](api/index.md) |
| Understand architecture and logic | [Plugin architecture and logic](plugin-architecture-and-logic.md) |
| Reuse professional engineering patterns | [Professional engineering patterns](professional-engineering-patterns.md) |
| Map RPG capabilities across plugins | [RPG feature catalog](rpg-feature-catalog.md) |
| Design new addons | [Original addon blueprints](original-addon-blueprints.md) |
| Understand AgentKit research and skill shape | [AgentKit skill design](agentkit-skill-design.md) |
| Install for Codex and Claude | [Codex and Claude compatibility](codex-claude-compatibility.md) |
| Audit provenance and limitations | [Research methodology](research-methodology.md) |

For fast symbol lookup, run `python scripts/query_api.py <terms>`. Agents should not load the 40 MB API index into context.

## Confidence Labels

- `VERIFIED_BYTECODE`: direct JVM metadata from the supplied artifact.
- `DERIVED_SOURCE`: behavior inferred from decompiled source and cited paths.
- `ORIGINAL_DESIGN`: a new composition produced by this kit.
- `UNVERIFIED`: runtime or version-sensitive claim that needs an empirical test.

The kit contains no plugin JAR, class file, method body, or proprietary asset.
