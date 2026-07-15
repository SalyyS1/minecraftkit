# MinecraftRPG Kit

MinecraftRPG Kit is an offline research and design skill for Codex and Claude. It catalogs the public/protected JVM surface of ten Minecraft RPG plugins, summarizes their architecture and extension patterns, and turns those primitives into safe integration guidance and original addon blueprints.

- Live API explorer: <https://salyys1.github.io/minecraft-rpg-kit/>
- Public repository: <https://github.com/SalyyS1/minecraft-rpg-kit>

## What Is Included

- **4,947 plugin-owned types** and **39,262 plugin-owned members**. The full namespace catalog retains 5,345 types and 41,887 members, with bundled third-party records labeled separately.
- 965 human-readable Markdown API shards grouped by plugin and package.
- Architecture, lifecycle, persistence, scheduler, event, registry, and compatibility research.
- RPG capability map and original cross-plugin addon blueprints.
- An offline HTML/CSS/JS explorer that works from `file://` without a server or network.
- Deterministic extraction, query, rendering, validation, inventory, packaging, and installation tooling.

No plugin JAR, decompiled source body, proprietary asset, or credential is included.

## Quick Start

Open `web/index.html` for the visual explorer, or query the compact catalog from a terminal:

```powershell
python .\scripts\query_api.py ActiveModel --plugin ModelEngine --limit 20
python .\scripts\query_api.py ItemEquipEvent --json
```

Start with `docs/index.md` for the research map and `docs/api/index.md` for the generated API catalog. Agents should follow `SKILL.md` and load only the one reference needed for the current task.

## Validate

```powershell
python .\scripts\validate_kit.py .
python -B -m unittest discover -s .\tests -v
```

## Regenerate From Authorized Local Inputs

Only run this against artifacts you are authorized to analyze. The supplied input is treated as read-only.

```powershell
python .\scripts\inventory_sources.py --bundle 'D:\path\to\RPG BUNDLE' --output .\data\source-inventory.json --verify
python .\scripts\extract_api.py --jars 'D:\path\to\RPG BUNDLE' --sources 'D:\path\to\RPG BUNDLE\decompiled' --output .\data
python .\scripts\render_docs.py --data .\data --docs .\docs --web .\web
python .\scripts\build_manifest.py .
python .\scripts\inventory_sources.py --bundle 'D:\path\to\RPG BUNDLE' --output .\data\source-inventory.json --verify
```

## Package And Install

Create the deterministic project package:

```powershell
python .\scripts\package_kit.py .
```

Install independent physical copies for both clients:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\install-global.ps1
```

Targets are `$HOME/.agents/skills/minecraft-rpg-kit` for Codex and `$HOME/.claude/skills/minecraft-rpg-kit` for Claude. Existing targets are moved to timestamped sibling backups before promotion.

## Layout

- `SKILL.md`: shared Codex/Claude workflow router.
- `references/`: focused operational instructions loaded on demand.
- `data/`: machine-readable API, coverage, provenance, and insight records.
- `docs/`: human-readable research and generated API shards.
- `scripts/`: deterministic local tooling.
- `tests/`: contract and regression tests.
- `web/`: offline explorer.
- `dist/`: release package and checksum, excluded from global installs.

See `NOTICE.md` before redistributing any derived material.
