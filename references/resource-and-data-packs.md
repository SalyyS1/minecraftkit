# Resource And Data Packs

Use this reference with `mc:pack`. Resolve exact Minecraft version and pack kind first: resource-pack and data-pack formats evolve independently.

## Pinned 26.2 Snapshot

The Mojang 26.2 artifact inventory observed on 2026-07-15 reports:

- resource-pack format `88.0`;
- data-pack format `107.1`;
- separate item-definition graphs under `assets/minecraft/items` and model geometry under `assets/minecraft/models/item`;
- built-in dialog data and font definitions.

These are exact-artifact `VERIFIED_UPSTREAM` facts. Refresh through pinned Mojang metadata when targeting another version; never guess pack formats from a plugin version.

## Asset Layers

| Layer | Purpose | Typical hazards |
|---|---|---|
| `pack.mcmeta` | pack identity and compatibility | wrong resource/data format; unbounded compatibility claims |
| item definitions | recursive selection/condition/range/composite/special-render graph | cycles, missing model references, legacy override assumptions |
| model JSON | geometry, parents, textures, transforms | case/path mismatch, parent cycles, texture collisions |
| textures/atlases | images and stitching rules | size/memory, atlas conflicts, unauthorized assets |
| fonts | providers, glyphs, spacing/references | private-use collisions, UI spoofing, missing fallback |
| sounds | sound events and media | namespace collisions, codec/channel/size issues |
| shaders | core/include/post overrides | volatile internal interface and pack conflicts |
| dialogs/data | registry-driven UI and gameplay data | exact data format, action/input validation |

Modern CustomModelData is not safely represented as one global integer. Current ecosystems expose typed indexed channels such as flags, floats, strings and colors/tints. Allocate channels with owner, type, index/range, target versions and collision diagnostics.

## Source And Build Layout

Keep an authored source tree separate from generated/optimized artifacts:

```text
pack-source/
  assets/<namespace>/...
  data/<namespace>/...
  allocation-registry.json
  provenance.json
build/
  staged merged tree
  validation report
  final content-addressed ZIP
```

Build to staging, validate, hash and publish atomically. Retain the canonical unoptimized source pack; optimizer output is a derivative artifact.

## Merge Rules

Pack priority is order-sensitive. Detect before promotion:

- duplicate paths and incompatible file types;
- item-definition/model/parent replacements;
- atlas sources, language keys and sound-event merges;
- font provider/glyph and CustomModelData allocation collisions;
- shader program/include overrides;
- vendor-generated file ownership and stale removed files.

Never default to silent last-writer-wins. Record owner and resolution for each intentional override.

## Delivery

For server delivery:

1. Build immutable ZIP bytes and compute the exact requested hash.
2. Host over HTTPS at an allowlisted stable URL with bounded size/content type.
3. Use a new content identity/UUID when bytes change.
4. Select a variant from the actual client capability/protocol, not only server version.
5. Handle accepted, downloaded, loaded, declined, failed, timeout and disconnect states.
6. Gate pack-required gameplay through server-owned state; client success status is not authorization proof.

ViaVersion translates protocol packets, not resource-pack JSON schemas. Generate per-client variants when formats/features differ. Geyser/Bedrock needs a separate pack/fallback pipeline.

## Tooling

- [beet](https://github.com/mcbeet/beet): programmable Python build/merge pipeline; plugins execute code, so pin and audit them.
- [PackSquash](https://github.com/ComunidadAylas/PackSquash): optimization; validate transformed images/audio/JSON/GLSL on every target.
- [Spyglass](https://github.com/SpyglassMC/Spyglass): language-server/schema diagnostics; tooling acceptance is not runtime proof.
- [Blockbench](https://github.com/JannisX11/blockbench): authoring/export hub; exporter version is part of the build contract.
- [Animated Java](https://github.com/Animated-Java/animated-java): generates data/resource packs for display animation; pin Blockbench/exporter/game formats.

Vendor generators (ItemsAdder, Nexo, Oraxen, MythicCrucible and similar) own lifecycle and merge conventions. Treat their output as generated, not source of truth; use public APIs/readiness events and comply with commercial/custom licenses.

## Untrusted Input

Treat ZIP, JSON, PNG, OGG, GLSL, bbmodel and fonts as untrusted:

- reject path traversal, absolute paths, symlinks and case-collision tricks;
- cap compressed/uncompressed size, entry count, nesting, dimensions and parser depth;
- never execute Blockbench/beet plugins or downloaded converters during indexing;
- statically validate JSON/resource locations and media headers;
- record origin, author, license, checksum and redistribution scope for every asset;
- exclude secrets, local paths and tracking identifiers.

## Validation

Validate JSON/schema/references, case-sensitive paths, cycles, allocation conflicts, pack formats, ZIP safety, exact hash and clean-client load. Test pack rejection/failure, cache invalidation, reload, proxy transfer and every declared client variant.

## Original Addon Pattern

`ORIGINAL_DESIGN`: a capability-aware pack compiler can combine owned RPG/item/model sources, allocate typed item/glyph channels, emit version-specific Java variants plus a Geyser fallback, then publish an immutable provenance manifest. The original composition is the conflict-aware multi-client build graph; no vendor is claimed to provide the whole pipeline.
