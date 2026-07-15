# Minecraft Ecosystem API Atlas

This atlas routes high-value public API families across MinecraftKit. The exact repository/revision is in the pinned source snapshot. The ten supplied RPG artifacts retain their exhaustive, class/member-level shards under [RPG API index](api/index.md).

The entries below are navigation surfaces, not copied source and not a promise of cross-version compatibility.

## Plugin Build And Shipping APIs

- Gradle Wrapper, Kotlin DSL, JVM toolchains, dependency configurations, locking, verification, test tasks, reproducible archives, and publishing tasks.
- Kotlin/JVM typed compiler options and deliberate Kotlin/Java mixed-source boundaries.
- Paper `plugin.yml`/`paper-plugin.yml`, runtime `libraries`, `compileOnly` APIs, paperweight-userdev, and exact-version development bundles.
- Configuration/data contracts for YAML/YML and JSON: schema validation, migrations, defaults, atomic writes, and operator-safe diagnostics.
- Storage contracts for external PostgreSQL/MySQL services or operator-owned SQLite files: pools, migrations, prepared statements, transactions, timeouts, backups, and scheduler handoff.
- GitHub Releases, Hangar, Modrinth, and Spigot publication surfaces with SemVer, immutable checksummed artifacts, compatibility matrices, notices, and secret-scoped CI.

Use [`/mc:build`](../commands/mc/build.md) and the [plugin engineering handbook](plugin-engineering-handbook.md) for the end-to-end workflow.

## Core Platforms

### Paper, Folia, Purpur, Bukkit and Spigot

- Bukkit/Paper entity, world, inventory, event, scheduler, services and plugin lifecycle APIs.
- Paper display entities: `Display`, `TextDisplay`, `ItemDisplay`, `BlockDisplay`, transformations and interpolation.
- Paper registries, data components, connection configuration, dialogs and Adventure-native audiences.
- Folia ownership schedulers: global-region, region, entity and async schedulers; compatibility is explicit.
- Purpur extends the Paper/Spigot/Bukkit surface; fork-only APIs are not portable upstream.
- NMS access routes through paperweight-userdev and exact dev bundles, not the ordinary API artifact.

### Fabric

- Loader entrypoints, metadata and mapping resolver.
- Fabric API modules for events, registries, networking, resources, screens, model loading and rendering.
- Client surfaces include model-loading plugins, entity renderer registration, world render events and renderer/mesh abstractions.
- Fabric Loom, mapping-io and Tiny Remapper are build/mapping tools, not gameplay APIs.

### NeoForge And Forge

- Loader lifecycle, events, registries, capabilities/attachments, networking, resources and data generation.
- Client model registration, custom unbaked models/loaders, codecs, baking data and renderer events.
- Bind every API to the exact Minecraft + NeoForge/Forge artifact and channel.

### Sponge, Minestom And Proxies

- SpongeAPI events, services, data, commands and platform-independent plugin contracts, paired with a concrete implementation target.
- Minestom instance/entity/event/command/inventory/scheduler and protocol-facing server-library APIs.
- Velocity and BungeeCord proxy events, backend connections, forwarding and plugin messaging; no backend gameplay world API.
- Adventure `Audience`, `Component`, keys, serializers, NBT, dialogs and resource-pack request contracts.

## RPG And Public Plugin APIs

### Deep Supplied Catalog

- MMOItems, MMOCore, MMOInventory, MMOProfiles, ModelEngine, MythicCrucible, MythicDungeons, MythicEnchants, MythicRPG and CoreTools.
- Query exact class/member/descriptor with `scripts/query_api.py`; use the 965 generated API shards for human browsing.
- Claims are labeled `VERIFIED_BYTECODE`, `DERIVED_SOURCE`, `ORIGINAL_DESIGN` or `UNVERIFIED`.

### Permissions, Economy And Placeholders

- LuckPerms: provider, users/groups, immutable nodes, tracks, contexts, query options, cached data and messaging.
- Vault: legacy economy, permission and chat service-provider interfaces and provider discovery.
- EssentialsX: user state, homes/warps/kits, teleports, economy, commands and integration events.
- PlaceholderAPI: expansion lifecycle, normal/relational parsing, cache expectations and discovery.

### Worlds, Regions And Editing

- WorldEdit: edit sessions, extents, operations, regions, clipboards/schematics, masks, patterns, transforms and history.
- FAWE: queue/chunk pipelines, parallel-safe extension points, history and memory/backpressure boundaries.
- WorldGuard: region containers/managers, protected regions, flags, queries, sessions and custom flags.
- Multiverse-Core: world lifecycle, generators, properties, destinations, access policy and events.

### NPC, Quest, Skills And Content

- Citizens: NPC registries, traits, navigation/goals, metadata, speech, selectors, lifecycle and persistence.
- AuraSkills: skills, stats, mana, abilities, XP, modifiers, rewards, profiles and events.
- BetonQuest/Quests: conversations, stages/objectives, conditions, events, variables, requirements, rewards and extension registration.
- Nova/Slimefun: custom items/blocks, tile entities/machines, behaviors, recipes, energy/storage, GUI, pack/model and addon registries.
- mcMMO: skills/XP/profiles, abilities, parties, gathering/combat events and persistence.
- Denizen/Skript: script object/syntax registration, parser, events, conditions/effects, queues and addon lifecycle.

## Shaders And Rendering

- Mojang client navigation metadata: `RenderPipeline`, `RenderPipelines` and version-pinned shader asset path families. These are internals, not a supported mod API.
- Fabric API rendering/model modules: renderer API, meshes/quads, model-loading plugins, render events and client registration.
- Iris public surface: `IrisApi`, configuration/program concepts and declared renderer integration.
- Sodium exposes only narrow public integration/configuration surfaces; internal renderer/mixins are not API and source ingestion is restricted.
- Veil exposes shader, framebuffer, post-processing, editor/debug and model/animation framework surfaces on its supported lines.
- Canvas/FREX exposes historical material/shader APIs and is never the default current Fabric recommendation.

## Dialogs, Commands And Client Actions

- Paper experimental dialog builders/base/input/type APIs, registry events and custom click events.
- Adventure dialog-like and audience show/close capabilities where supported by the platform.
- Inputs include boolean, text, number/range and selection families; exact builders are version-pinned.
- cloud: command managers, parsers, contexts, suggestions, annotations, execution coordinators and platform adapters.
- CommandAPI: Brigadier trees, native arguments, executors, suggestions, permissions and registration lifecycle.
- Dialog/command/action payloads remain client input; authorize semantic actions server-side.

## Client Projection

- Paper/Bukkit displays for real tracked text/item/block entities.
- ProtocolLib: `ProtocolLibrary`, `ProtocolManager`, `PacketAdapter`, `PacketContainer`, `StructureModifier` and packet listeners.
- PacketEvents: facade/event manager, protocol player and typed client/server wrapper families.
- Polymer: `PolymerItem`, `PolymerBlock`, `PolymerEntity`, resource-pack builder/utilities, virtual `ElementHolder` and display elements.
- Geyser extension/API and bridge metadata for Bedrock; treat Bedrock packs/models/UI as a separate client system.
- DecentHolograms `DHAPI`, Citizens NPCs, SkinsRestorer skin data/apply flow and map/marker APIs are specialized projections.

## Resource And Data Packs

- Adventure/Paper resource-pack information, requests, callbacks and audience delivery.
- Modern item-definition graphs, model geometry, CustomModelData typed channels, fonts, sounds, atlases, shaders and dialogs.
- Polymer pack builder, generated allocation and virtual content APIs for Fabric server + vanilla client.
- beet programmable pack model/build context; PackSquash optimizer; Spyglass language/schema tooling.
- ItemsAdder public `CustomStack`/registry concepts and readiness events; Nexo item/block/furniture and loaded/mechanics/pack-server lifecycle APIs.
- Oraxen is metadata-only under its custom license; public visibility is not permission to ingest implementation.

## Models And Animation

- Blockbench plugin lifecycle, `Codec`, `ModelFormat`, projects, cubes/meshes/groups, animations, keyframes and Molang authoring concepts.
- Animated Java exporter/function contract for display-entity data/resource-pack animation.
- GeckoLib 5 animatable/entity/item surfaces, controllers, raw animation, caches, loaders, render layers and keyframe events.
- AzureLib animator/controller/sequence APIs are a distinct, older game-line ecosystem, not GeckoLib 5 aliases.
- ModelEngine verified surfaces include `ModelEngineAPI`, modeled entities, active models, animation handlers, bones/behaviors/renderers and per-viewer projection.

## Packets And Protocols

- ProtocolLib and PacketEvents interception/synthesis APIs described above.
- ViaVersion public API, manager, connection, protocol pipeline and mappings; ViaBackwards/ViaRewind add directed translation edges.
- MCProtocolLib session, packet, encryption, compression, authentication and exact-game codec surfaces.
- minecraft-data/ProtoDef/node-minecraft-protocol are derived schema/tooling sources and cannot override maintained Java implementations.
- Velocity/Bungee proxy lifecycle and forwarding complete the connection topology.

Packet identity is edition + protocol + state + direction + wire ID + schema hash. Packet names/IDs alone are not stable APIs.

## NMS And Mappings

- paperweight-userdev exact dev bundles and mapping/remapping workflow.
- Paper Codebook and reflection-remapper for controlled mapping-aware build/runtime operations.
- Fabric mapping-io, Tiny Remapper, Loom, historical Yarn/intermediary.
- NeoForm, AutoRenamingTool, SRGUtils, ForgeGradle, MCPConfig and Parchment.
- Minecraft game name epoch is `obfuscated` through 1.21.11 and `original-name` from 26.1. Paper runtime namespace/remapping is a separate platform property.

Internals must live behind exact-version adapters and fail closed on unknown fingerprints.

## Professional Engineering Patterns

- Separate authoritative domain state from every client/render projection.
- Use provider/service/capability boundaries for optional integrations.
- Register after dependency readiness; unregister and clean idempotently.
- Model scheduler/object ownership, not merely “sync/async”.
- Treat version, release, artifact, tested, supported and compatible as separate evidence.
- Pin mutable sources to commits and preserve license/provenance with derived indexes.
- Validate all client input and bound network, pack, model, shader and animation resources.
- Design explicit fallback/degradation for missing plugins, unsupported clients and failed packs.

## Query Examples

```text
python scripts/query_sources.py quest --domain rpg --priority P0
python scripts/query_sources.py render --domain shader --limit 20
python scripts/query_sources.py packet --domain protocol --json
python scripts/query_api.py ActiveModel --plugin ModelEngine --limit 20
```

For exact versions and source revisions, use the machine-readable catalogs or the static ecosystem explorer.
