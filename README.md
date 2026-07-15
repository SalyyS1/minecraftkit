# MinecraftKit

MinecraftKit is an evidence-backed Minecraft engineering skill system for Codex and Claude. It routes nine focused domains across game/platform versions, packets, NMS, client rendering, shaders, dialogs, packs, models/animation, and RPG systems.

RPG remains the deepest symbol catalog, not the limit of the project.

- Live atlas: <https://salyys1.github.io/minecraftkit/>
- Public repository: <https://github.com/SalyyS1/minecraftkit>

## What Is Included

- **103 reviewed public GitHub sources**, each pinned to its canonical repository and a 40-character default-branch commit SHA.
- **901 Mojang Java Edition version records** from the official manifest snapshot, including hydrated 26.2 and 26.3-snapshot-3 metadata.
- Nine auto-routing sibling skills (`mc-core` through `mc-nms`) plus matching Claude slash commands (`/mc:core` through `/mc:nms`).
- A human API atlas for major public platform/plugin families and focused engineering references for every domain.
- A deep authorized RPG catalog: **4,947 plugin-owned types**, **39,262 plugin-owned members**, and 965 Markdown API shards across ten supplied plugins. The full namespace index contains 5,345 types and 41,887 members.
- Static offline web explorers for the ecosystem/source/version atlas and the original RPG symbol catalog.
- Deterministic query, sync, rendering, validation, packaging, and transactional global-install tooling.

No Minecraft/plugin JAR, decompiled method body, proprietary asset, marketplace token, credential, or raw CursorCs implementation is included.

## Quick Start

Open `web/ecosystem.html` for the Minecraft ecosystem atlas or `web/index.html` for the deep RPG API explorer.

Query reviewed sources and exact RPG symbols locally:

```powershell
python .\scripts\query_sources.py shader --domain shader --priority P0
python .\scripts\query_sources.py packet --domain protocol --json
python .\scripts\query_api.py ActiveModel --plugin ModelEngine --limit 20
python .\scripts\query_api.py ItemEquipEvent --json
```

Start with `docs/minecraft-ecosystem-api-atlas.md`. Agents use `SKILL.md` as the router and load only the focused reference required for the task.

## Evidence Contract

MinecraftKit separates:

- `VERIFIED_UPSTREAM`: exact pinned official project/source/doc evidence;
- `VERIFIED_BYTECODE`: public/protected JVM facts extracted from an authorized supplied artifact;
- `DERIVED_SOURCE`: original inference from reviewed source/decompiled evidence;
- `ORIGINAL_DESIGN`: a new composition proposed by the kit;
- `UNVERIFIED`: version-sensitive or runtime behavior still requiring a target test.

Version, artifact, release, tested, supported, and compatible are separate facts.

## Validate

```powershell
python .\scripts\validate_kit.py .
python -B -m unittest discover -s .\tests -v
```

Validation reconciles route/skill/command/reference contracts, all version counts, source identities, commit pins, generated web data, deep RPG counts, release hashes, Python syntax, and copyright-safe payload policy.

## Refresh Reviewed Metadata

Normal skill use and tests are offline. Network refresh is an explicit maintainer action:

```powershell
python .\scripts\sync_minecraft_versions.py --detail 26.2 --detail 26.3-snapshot-3
$env:GITHUB_TOKEN = gh auth token
try { python .\scripts\sync_github_sources.py } finally { Remove-Item Env:GITHUB_TOKEN -ErrorAction SilentlyContinue }
python .\scripts\sync_github_sources.py --offline
```

The GitHub synchronizer reads only the allowlisted catalog, rejects aliases, resolves mutable branches to commits, redacts credentials by construction, and writes atomically. Offline validation rechecks the catalog hash, ordered identities, catalog fields, canonical repositories and immutable commit URLs. Mojang detail bytes must match the manifest SHA-1 before normalization; game binaries are never downloaded or redistributed.

## Regenerate The Authorized RPG Catalog

Only run this against artifacts you are authorized to analyze. Inputs remain read-only.

```powershell
python .\scripts\inventory_sources.py --bundle 'D:\path\to\RPG BUNDLE' --output .\data\source-inventory.json --verify
python .\scripts\extract_api.py --jars 'D:\path\to\RPG BUNDLE' --sources 'D:\path\to\RPG BUNDLE\decompiled' --output .\data
python .\scripts\render_docs.py --data .\data --docs .\docs --web .\web
python .\scripts\render_ecosystem_web.py
python .\scripts\build_manifest.py .
python .\scripts\validate_kit.py .
```

`render_docs.py` transactionally replaces `web/data`; therefore `render_ecosystem_web.py` must run immediately afterward and before the release manifest is built.

## Package And Install

Create the deterministic package:

```powershell
python .\scripts\package_kit.py .
```

Preview global installation without writes:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\install-global.ps1 -PlanOnly
```

Install validated physical copies:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\install-global.ps1
```

The transaction installs:

- Codex core: `$HOME/.agents/skills/minecraftkit`;
- Codex routes: `$HOME/.agents/skills/mc-*`;
- Claude core: `$HOME/.claude/skills/minecraftkit`;
- Claude routes: `$HOME/.claude/skills/mc-*`;
- Claude commands: `$HOME/.claude/commands/mc` for `/mc:core`, `/mc:rpg`, and the other routes.

Every payload is staged, validated and hash-compared before promotion. Existing targets become collision-safe timestamped backups and the legacy `minecraft-rpg-kit` target is preserved.

## Layout

- `SKILL.md`: shared auto-router and evidence/safety contract.
- `skill-wrappers/`: nine focused sibling skills.
- `commands/mc/`: Claude `/mc:*` command wrappers.
- `references/`: operational domain guidance loaded on demand.
- `data/`: source, version, domain, RPG API, provenance and design catalogs.
- `docs/`: ecosystem atlas, research, and generated RPG API shards.
- `scripts/`: deterministic offline and reviewed-sync tooling.
- `tests/`: contract, safety and regression tests.
- `web/`: static ecosystem and RPG explorers.
- `dist/`: deterministic release ZIP/checksum, excluded from global installs.

Read `NOTICE.md` before redistributing derived material.
