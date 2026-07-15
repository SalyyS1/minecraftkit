# Upstream Source Catalog

MinecraftKit uses a reviewed allowlist, not open-ended GitHub search at answer time. This keeps repository identity, freshness, licensing and evidence reproducible.

## Pinned Snapshot

- observed: `2026-07-15T05:45:00+00:00`;
- reviewed GitHub repositories: `103`;
- catalog SHA-256: `711f48c324e8cec1b8f2e05d2420ec74ccfea9d23e1bf2be04f8f6c0fa2ff333`;
- immutable default-branch heads: `103/103`;
- GitHub license metadata present: `95/103`;
- archived historical sources: `2`, both intentionally lower-priority.

The source catalog and snapshot are `data/github-source-catalog.json` and `data/github-source-snapshot.json`. Mojang game history is separate in `data/minecraft-version-catalog.json` because Mojang metadata is not a GitHub repository.

## Coverage

Sources can belong to more than one route:

| Domain | Source records | Representative families |
|---|---:|---|
| `core` | 52 | Paper/Folia/Purpur, Fabric, Forge/NeoForge, Sponge, Minestom, proxies, commands, worlds, permissions |
| `client` | 33 | displays/projections, Polymer, Geyser, renderers, models, maps, NPCs, holograms |
| `rpg` | 26 | deep MMO/Mythic catalog plus public skill, quest, item, world and service ecosystems |
| `pack` | 25 | vanilla pack facts, pack builders, custom content, models, fonts, delivery and optimization |
| `nms` | 23 | paperweight, mappings, remappers, build tools, compatibility helpers |
| `protocol` | 23 | ProtocolLib, PacketEvents, Via family, MCProtocolLib, proxies and protocol-aware plugins |
| `model` | 18 | Blockbench, Animated Java, GeckoLib, AzureLib, client entity features and server model engines |
| `dialog` | 12 | Paper/Adventure dialogs, commands, conversations, NPCs and hologram actions |
| `shader` | 10 | vanilla/Fabric rendering evidence, Sodium, Iris, Veil and historical Canvas/FREX |

This is curated breadth, not a claim that every Minecraft repository or every version-specific API method has been mirrored.

## Priorities

- `P0`: authoritative or foundational for default routing and compatibility answers.
- `P1`: high-value enrichment, tooling, integration or specialized API.
- `P2`: historical, constrained, stale-release, narrow or optional evidence.

Priority never overrides source authority. A P0 implementation cannot override Mojang version identity or a platform's canonical artifact feed.

## Ingestion Policies

| Policy | MinecraftKit may store | It must not do |
|---|---|---|
| `index` | public symbols, artifacts, module names, documented contracts, metadata and original summaries | copy method bodies/assets or ignore license/NOTICE obligations |
| `derive` | original architectural/algorithmic synthesis tied to revision and evidence | present inferred behavior as a public API or reproduce implementation |
| `metadata-only` | identity, revision, release, license, topics and original description | analyze/mirror source structure without a separate permission review |
| `link-only` | canonical links, revision/checksum and a minimal routing note | mirror prose, code, mappings, generated data or assets |

Public visibility is not an ingestion policy. Custom/commercial, mixed-provenance, no-license, PolyForm and Mojang-derived sources are deliberately restricted.

## Notable License Gates

- Mojang binaries, assets and mappings are outside the GitHub catalog and never redistributed.
- Sodium is `metadata-only` because PolyForm Shield requires product-specific review.
- Fabric docs are `metadata-only` because their noncommercial ShareAlike terms may not match every MinecraftKit use.
- Towny and Oraxen remain `metadata-only` under restrictive/custom licenses.
- ItemsAdder and Nexo public API/docs repositories are `link-only`; paid runtime/default content is not ingested.
- minecraft-data and mcmeta stay `link-only` because repository-level labels do not settle every generated/derived file's provenance.
- GPL/LGPL/AGPL/OSL/EPL sources can support indexing/original synthesis, but copying or linking code into a product is a separate compliance decision.

## Repository Identity

Every snapshot record contains:

- requested and canonical `owner/repository` identity;
- project URL and default branch;
- exact default-branch commit SHA, timestamp and commit URL;
- latest GitHub release observation when present;
- archive/fork/activity/stars metadata;
- GitHub's observed license descriptor;
- original catalog domain, priority, policy and rationale.

The synchronizer rejects aliases/renames rather than silently following them. Mutable “latest” and branch names are discovery metadata; the commit SHA is the reproducible source coordinate.

## Query

Use the narrow offline query:

```text
python scripts/query_sources.py Paper dialog --domain dialog
python scripts/query_sources.py shader --domain shader --priority P0
python scripts/query_sources.py packet --domain protocol --json
python scripts/query_sources.py --policy metadata-only --include-archived --limit 200
```

All free-text terms must match the normalized record. Archived sources are hidden unless explicitly requested.

## Maintenance

Refresh is a reviewed action, not an agent's background browse:

```text
python scripts/sync_github_sources.py
python scripts/sync_github_sources.py --offline
```

The live refresh uses an optional `GITHUB_TOKEN` from the environment, performs concurrent allowlisted REST lookups, never serializes the token, resolves every branch to a commit and writes atomically. CI and normal skill use are offline.

Before adding a source, verify canonical identity, public status, activity or historical justification, unique coverage, exact docs, domain, priority, license and policy. Do not add a repository only because it is popular.

## Evidence Use

When answering:

1. Resolve the source by ID/domain.
2. Check exact commit/release and freshness warning.
3. Confirm the target Minecraft/platform version separately.
4. Use only the content permitted by the policy.
5. Cite canonical docs/source and label the claim.
6. Preserve contradictions instead of selecting whichever source is newer-looking.

Version, artifact, release, tested, supported and compatible remain separate assertions.
