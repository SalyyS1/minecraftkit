# Salyyy Minecraft Kit

**Version 2.2.0 · Author/nametag: SalyVn / Salyyy**

Salyyy Minecraft Kit is an evidence-backed Minecraft engineering skill system for Codex and Claude. It routes ten focused domains across production plugin builds, game/platform versions, packets, NMS, client rendering, shaders, dialogs, packs, models/animation, and RPG systems.

RPG remains the deepest symbol catalog, not the limit of the project.

- VI/EN command and engineering wiki: <https://salyys1.github.io/minecraftkit/wiki.html>
- Unified VI/EN Kit Wiki: <https://salyys1.github.io/minecraftkit/wiki.html>
- RPG API Explorer and Ecosystem Atlas: linked from the wiki with one aqua visual system.
- Public repository: <https://github.com/SalyyS1/minecraftkit>

## What Is Included

- **103 reviewed public GitHub sources**, each pinned to its canonical repository and a 40-character default-branch commit SHA.
- **901 Mojang Java Edition version records** from the official manifest snapshot, including hydrated 26.2 and 26.3-snapshot-3 metadata.
- Ten auto-routing sibling skills, including `mc-build`, plus matching Claude slash commands from `/mc:build` through the other focused routes.
- A human API atlas for major public platform/plugin families and focused engineering references for every domain.
- A production plugin handbook for Kotlin/Java, Gradle, descriptors, YAML/JSON, Paper/Purpur/Folia, SQL, SemVer, testing, security, performance, and marketplace publishing.
- A deep authorized RPG catalog: **4,947 plugin-owned types**, **39,262 plugin-owned members**, and 965 Markdown API shards across ten supplied plugins. The full namespace index contains 5,345 types and 41,887 members.
- Static offline web explorers for the ecosystem/source/version atlas and the original RPG symbol catalog.
- Deterministic query, sync, rendering, validation, packaging, and transactional global-install tooling.

No Minecraft/plugin JAR, decompiled method body, proprietary asset, marketplace token, credential, or raw CursorCs implementation is included.

## Quick Start

Open `web/wiki.html` for the unified bilingual command/engineering wiki. Its command-center navigation opens the Minecraft ecosystem atlas and the deep RPG API explorer within the same aqua visual system. All views run from local files without a server, CDN, or background request.

Query reviewed sources and exact RPG symbols locally:

```powershell
python .\scripts\query_sources.py shader --domain shader --priority P0
python .\scripts\query_sources.py packet --domain protocol --json
python .\scripts\query_api.py ActiveModel --plugin ModelEngine --limit 20
python .\scripts\query_api.py ItemEquipEvent --json
```

Start with `docs/minecraft-ecosystem-api-atlas.md`. Agents use `SKILL.md` as the router and load only the focused reference required for the task.

## Commands And Skills

Claude exposes these as slash commands. Codex automatically selects the matching installed `mc-*` skill from the task wording.

| Command | What it does |
|---|---|
| `/mc:build` | Designs, builds, tests, versions, and ships Kotlin/Java plugins with Gradle, safe dependencies, storage, CI, and marketplace release gates. |
| `/mc:core` | Resolves exact Minecraft, Java, server fork, proxy, loader, and API compatibility contracts. |
| `/mc:rpg` | Designs stats, combat, skills, items, loot, classes, quests, dungeons, and integrations using the deep RPG catalog. |
| `/mc:shader` | Works with vanilla core shaders, GLSL, render pipelines, Iris, Sodium, Canvas, and Veil boundaries. |
| `/mc:dialog` | Builds native dialogs, inputs, client actions, click payloads, validation, and version fallbacks. |
| `/mc:client` | Designs client mods or vanilla-client projections such as fake entities, blocks, cameras, holograms, and Geyser paths. |
| `/mc:pack` | Builds and validates resource/data packs, textures, fonts, sounds, models, atlases, metadata, and delivery. |
| `/mc:model` | Plans Blockbench 2D/3D models, bones, rigs, animations, exporters, and runtime integration. |
| `/mc:protocol` | Handles packet state/direction, codecs, ProtocolLib, PacketEvents, ViaVersion, and wire-version safety. |
| `/mc:nms` | Isolates mapped internals through paperweight, adapters, reflection gates, and exact-version tests. |

The wiki documents inputs, workflow, outputs, guardrails, examples, and cross-route combinations for every command in Vietnamese and English.

## Production Plugin Baseline

- Choose Kotlin, Java, or a deliberate mixed boundary; configure a Gradle Wrapper, Kotlin DSL, and an explicit target-compatible JVM toolchain.
- Keep server APIs `compileOnly`. Prefer runtime library loading where supported; shade/relocate only when necessary and after license/collision review.
- Keep database servers and mutable database files outside the plugin artifact. Use a bounded pool, migrations, prepared statements, timeouts, backups, async I/O, and correct scheduler handoff before touching game state.
- Treat YAML as operator configuration and JSON as strict machine/pack data. Validate schemas, preserve defaults, migrate versions, and write atomically.
- Paper compatibility does not prove Folia compatibility. Use global, region, entity, and async schedulers by ownership; enable `folia-supported` only after representative runtime tests.
- Use SemVer: `1.0.0 → 1.0.1` for a compatible fix, `1.0.0 → 1.1.0` for compatible functionality, and `1.0.0 → 2.0.0` for an incompatible public contract.
- Build once, test that exact checksum, and publish the same immutable bytes with changelog, license/notice, dependency report, compatibility matrix, and rollback notes.

See `docs/plugin-engineering-handbook.md` and route through `/mc:build` for a project-specific build contract.

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
python .\scripts\render_wiki_web.py
python .\scripts\build_manifest.py .
python .\scripts\validate_kit.py .
```

`render_docs.py` transactionally replaces `web/data`; therefore both `render_ecosystem_web.py` and `render_wiki_web.py` must run immediately afterward and before the release manifest is built.

## Package And Install

### One-command install from GitHub

Run exactly one of these in PowerShell. The bootstrap downloads the release ZIP plus its `.sha256` sidecar, verifies SHA-256, safely extracts it, and then uses the transactional installer.

Codex only:

```powershell
& ([scriptblock]::Create((Invoke-RestMethod 'https://raw.githubusercontent.com/SalyyS1/minecraftkit/main/scripts/install-from-github.ps1'))) -Target codex
```

Claude only:

```powershell
& ([scriptblock]::Create((Invoke-RestMethod 'https://raw.githubusercontent.com/SalyyS1/minecraftkit/main/scripts/install-from-github.ps1'))) -Target claude
```

Codex + Claude:

```powershell
& ([scriptblock]::Create((Invoke-RestMethod 'https://raw.githubusercontent.com/SalyyS1/minecraftkit/main/scripts/install-from-github.ps1'))) -Target both
```

The command intentionally names the public repository and target. Review the [bootstrap source](https://github.com/SalyyS1/minecraftkit/blob/main/scripts/install-from-github.ps1) before executing remote code in a sensitive environment.

### npm CLI

The dependency-free [`minecraftkit` package on npm](https://www.npmjs.com/package/minecraftkit) packages a local copy of the same reviewed bootstrap; it does not evaluate a raw GitHub script.

```powershell
npx minecraftkit install --target both

# Or add it to a project, then run it with npx
npm install minecraftkit
npx minecraftkit doctor

# Or install the CLI globally
npm install -g minecraftkit
minecraftkit doctor
minecraftkit install --target codex
```

Available commands are `install`, `update`, `doctor`, `commands`, `wiki`, and `version`. The PowerShell installer above remains a supported public fallback.

### Package or install a local checkout

Create the deterministic package:

```powershell
python .\scripts\package_kit.py .
```

Preview global installation without writes:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\install-global.ps1 -Target both -PlanOnly
```

Install validated physical copies:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\install-global.ps1 -Target both
```

The transaction installs:

- Codex core: `$HOME/.agents/skills/minecraftkit`;
- Codex routes: `$HOME/.agents/skills/mc-*`;
- Claude core: `$HOME/.claude/skills/minecraftkit`;
- Claude routes: `$HOME/.claude/skills/mc-*`;
- Claude commands: `$HOME/.claude/commands/mc` for `/mc:build`, `/mc:core`, `/mc:rpg`, and the other routes.

Every payload is staged, validated and hash-compared before promotion. Existing targets become collision-safe timestamped backups and the legacy `minecraft-rpg-kit` target is preserved.

## Layout

- `SKILL.md`: shared auto-router and evidence/safety contract.
- `skill-wrappers/`: ten focused sibling skills.
- `commands/mc/`: Claude `/mc:*` command wrappers.
- `references/`: operational domain guidance loaded on demand.
- `data/`: source, version, domain, RPG API, provenance and design catalogs.
- `docs/`: ecosystem atlas, research, and generated RPG API shards.
- `scripts/`: deterministic offline and reviewed-sync tooling.
- `tests/`: contract, safety and regression tests.
- `web/`: static VI/EN wiki, ecosystem atlas, and RPG explorer.
- `dist/`: deterministic release ZIP/checksum, excluded from global installs.

Read `NOTICE.md` before redistributing derived material.
