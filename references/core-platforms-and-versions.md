# Core Platforms And Versions

Use this reference with `mc:core`. It describes how MinecraftKit resolves versions and platform contracts; it is not a timeless “latest version” page.

## Source Precedence

Resolve unstable facts from pinned records in this order:

1. Mojang launcher version metadata for Java Edition version identity, ordering, release time, runtime metadata and artifact hashes.
2. A platform's canonical release/build/Maven feed for released artifacts and game targets.
3. The platform's immutable source revision for API modules, build configuration and implementation evidence.
4. Canonical project documentation for supported workflows and policy.
5. Maintained implementations for facts Mojang does not publish, such as many protocol-number mappings.
6. Community datasets only as corroboration or when the answer is explicitly labeled derived.

Never let GitHub search rank, repository stars, a default branch, or a “latest release” badge override a project-specific artifact feed.

## Pinned Baseline

The bundled `data/minecraft-version-catalog.json` was observed on 2026-07-15 from Mojang's [version manifest v2](https://piston-meta.mojang.com/mc/game/version_manifest_v2.json). At that observation:

- latest release: `26.2`;
- latest snapshot: `26.3-snapshot-3`;
- both hydrated current records require Java 25;
- the catalog contains the complete ordered manifest history, including release, snapshot, old beta and old alpha entries.

These are `VERIFIED_UPSTREAM` snapshot facts, not permanent claims. Query the bundled catalog for reproducible answers; refresh only through `scripts/sync_minecraft_versions.py` when current data is explicitly needed.

Exact 26.2 protocol/pack-format and safe client path/count observations are separated in `data/minecraft-release-capabilities.json` and tied to the hydrated client SHA-1. They are not inferred from the version string.

Do not sort Minecraft version IDs as SemVer or plain strings. Preserve Mojang manifest ordering: historical `1.x`, calendar-style `26.x`, snapshots, previews and old versions do not share one safe numeric grammar.

## Relationship Model

Treat the ecosystem as a graph:

```text
GameVersion
  -> ProtocolVersion, JavaRuntime, AssetIndex, PackFormats, GameNameEpoch
  <- TARGETS_GAME <- PlatformRelease
  <- UNDERSTANDS  <- ProtocolLibraryRelease

PlatformRelease
  -> EXPOSES_API -> ApiSurface
  -> FORKS / IMPLEMENTS / REQUIRES -> other concrete releases
  -> SchedulerModel, RuntimeNamespace, ArtifactNamespace, RemappingPolicy

CompatibilityAssertion
  -> subject, relation, object, scope, evidence, confidence, observed_at, caveat
```

A fork edge does not imply drop-in compatibility. A downloadable artifact does not imply active support. A protocol translation edge does not imply feature fidelity.

## Keep Support Labels Separate

Use explicit labels:

- `available`: an artifact/history entry exists;
- `current`: an upstream feed presently names it;
- `stable`: upstream marks it non-preview;
- `tested`: upstream CI/source enumerates it;
- `supported`: upstream promises support;
- `compatible`: evidence connects two concrete releases;
- `inferred`: MinecraftKit derived the relation;
- `end_of_life`: upstream ended maintenance;
- `unknown`: no trustworthy assertion exists.

Never turn a version range in a download API into a support promise.

## Platform Topology

| Platform | Kind and relationship | Contract to record | Primary hazard |
|---|---|---|---|
| Bukkit / CraftBukkit / Spigot | API, implementation and server lineage | exact Spigot API snapshot plus game target | Stash/Maven history and NMS namespaces differ |
| Paper | Spigot/Bukkit-compatible fork with richer API | Paper build, game version, Java, API and scheduler | available old builds are not current support |
| Folia | region-threaded Paper fork | exact Folia build, region ownership and `folia-supported` declaration | compatibility starts as unknown/conditional |
| Purpur | configurable Paper fork | Purpur build plus inherited Paper/Spigot/Bukkit surfaces | patch license does not replace inherited licenses |
| Fabric Loader + Fabric API | loader plus game-bound modular API | loader, Fabric API and exact game version separately | loader compatibility is not mod/API compatibility |
| Forge | independent mod loader/API | exact `minecraft-forge` pair and channel | major numbers alone are ambiguous |
| NeoForge | separate modern loader/API with Forge ancestry | exact NeoForge artifact, channel and target | similarity does not create Forge compatibility |
| SpongeAPI + Sponge implementations | API implemented by Vanilla/Forge/Neo runtimes | API version and concrete implementation/game target | default branch may differ from newest release line |
| Minestom | from-scratch server library | exact release and one targeted game/data revision | not Bukkit/NMS or drop-in vanilla |
| Velocity / BungeeCord | proxies | proxy/API version, forwarding mode and backend graph | no gameplay API; forwarding security is material |
| Adventure | UI/component abstraction | module/platform adapter plus client feature availability | native and legacy adapter behavior differs |

Canonical repository identities and immutable observations live in `data/github-source-catalog.json` and `data/github-source-snapshot.json`.

## Thread And Ownership Models

Do not reduce execution to “sync versus async”:

- Bukkit/Spigot/Paper: most world/entity mutation belongs to the server thread or the platform scheduler contract.
- Folia: regions and entities have owners; use the appropriate region, entity, global-region or async scheduler. There is no universal main thread for gameplay state.
- Proxies: callbacks may run on event-loop or library-managed threads; backend world state is not locally owned.
- Packet libraries: decode/intercept callbacks may run outside a platform mutation context.
- Client mods: render thread, networking thread and logical game thread are distinct.

Record the owner for every mutable object and define how work crosses ownership boundaries.

## Selection Workflow

1. Resolve edition and exact game version through the Mojang catalog.
2. Resolve Java runtime and the game's obfuscated/original-name epoch.
3. Choose server, mod loader, proxy or standalone server-library topology.
4. Resolve a concrete release from the project's authoritative feed, then pin its immutable source revision.
5. Identify public API surface and scheduler model.
6. Add client requirements, protocol translators and optional integrations.
7. State support labels and missing evidence independently.
8. Compile and runtime-test the exact matrix; fail closed on unknown versions.

## Compatibility Matrix Template

```text
game: exact Mojang ID
java: major + vendor constraints if relevant
runtime: project + release/build + immutable revision
api: artifact coordinates + API surface
game_name_epoch: obfuscated | original-name
platform_runtime_namespace: exact namespace for this platform release
artifact_namespace: exact namespace produced by the build
remapping_policy: none | platform-load-remap | build-remap | other evidenced rule
scheduler: ownership model
client: vanilla | loader/mod/version | Bedrock bridge
proxy/translators: concrete releases + directed edges
status: available/current/stable/tested/supported/compatible/unknown
evidence: source ID + locator + observed_at
fallback: disable, substitute, or reject
```

## Refresh And Validation

Network refresh is an explicit maintenance action:

```text
python scripts/sync_minecraft_versions.py --detail <release> --detail <snapshot>
python scripts/sync_github_sources.py
python scripts/sync_github_sources.py --offline
```

CI should validate pinned files offline. A refresh must preserve repository identity, resolve mutable branches to commit SHAs, retain license metadata and never download Minecraft binaries.

## Primary References

- [Paper developer documentation](https://docs.papermc.io/paper/dev/)
- [Folia support guide](https://docs.papermc.io/paper/dev/folia-support/)
- [Fabric documentation](https://docs.fabricmc.net/)
- [NeoForge documentation](https://docs.neoforged.net/)
- [SpongeAPI](https://github.com/SpongePowered/SpongeAPI)
- [Minestom unsupported-version policy](https://minestom.net/docs/compatibility/unsupported-versions)
- [Velocity documentation](https://docs.papermc.io/velocity/)
