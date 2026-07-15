# Research Methodology And Provenance

## Scope

The authorized local input contained ten plugin JARs and ten matching decompiled roots under the supplied RPG bundle. The review covered:

- 11,490 decompiled files;
- 10,661 `.java` files plus 829 resources/side artifacts;
- ten primary Bukkit/Paper descriptors and two proxy descriptors;
- plugin-owned source, API packages, lifecycle, registries, events, schedulers, persistence, configuration, and integrations;
- locally installed AgentKit skill architecture under allowlisted roots.

No input file was modified.

## Chain Of Custody

`scripts/inventory_sources.py` records relative path, byte size, and SHA-256 for all ten JARs and every decompiled file. The deterministic inventory has no run timestamp. Verification rebuilds the inventory, rejects symlinks/reparse points and boundary escape, and reports missing, added, size-changed, hash-changed, or metadata-changed records.

The source inventory contains hashes, not source content.

## API Extraction

`scripts/java_classfile.py` reads JVM class metadata directly, including modern constant-pool tags and Java class major versions through the supplied Java 25 artifacts. It strictly decodes JVM Modified UTF-8 and validates field/method descriptors.

`scripts/extract_api.py` publishes:

- public/protected type identity, kind, visibility, modifiers, inheritance, interfaces, generic signature when present, and Java class major;
- public/protected fields, constructors, methods, descriptors, decoded parameter/return types, generic signatures, declared exceptions, constants, bridge/synthetic flags, and deprecation marker;
- JAR hash, entry path, source correlation path, multi-release variant, stable ID, and origin label.

The claim is a **public/protected signature inventory**. Runtime annotations, parameter names/annotations, annotation defaults, record-component attributes, and permitted-subclass metadata are not part of schema version 1 unless also visible through ordinary declarations.

## Ownership Classification

Entrypoint namespaces select relevant class entries. Known relocated libraries inside those namespaces remain in the catalog but carry `bundled-third-party` rather than `plugin-owned`:

- CoreTools embedded libraries;
- MMOCore PaperLib;
- MMOProfiles relocated Gson;
- MythicCrucible and MythicRPG metrics;
- MythicDungeons AvN-GUI, bStats, and Objenesis.

This produces 4,947 plugin-owned types/39,262 members and 398 bundled types/2,625 members, for 5,345 types/41,887 members total. Zero entries failed parsing.

## Semantic Source Review

Reviewers enumerated the full corpus, then deep-read plugin descriptors, entrypoints, API packages, aggregate roots, managers, registries, providers, events, schedulers, persistence drivers, configuration loaders, proxy bridges, and representative call paths.

Three independent family reports were produced:

- CoreTools plus four MMO plugins;
- ModelEngine;
- four Mythic-family plugins.

Shaded/vendor packages were separated from design conclusions. Findings cite relative source paths and line locations. Method bodies and substantial excerpts were not copied into the kit.

## Evidence Classes

| Label | Meaning | Suitable use |
|---|---|---|
| `VERIFIED_BYTECODE` | direct metadata from supplied JAR | symbol lookup and consumer compile planning |
| `DERIVED_SOURCE` | behavior inferred from decompiled flow | architecture guidance with caveat/citation |
| `ORIGINAL_DESIGN` | independently designed composition | addon blueprint, never vendor attribution |
| `UNVERIFIED` | runtime/version ambiguity | explicit test requirement |

Decompiler output may distort local names, synthetic constructs, casts, annotations, nullability, text encoding, or control flow. Suspicious flows are recorded as risks and not silently corrected.

## Generated Documentation And Web

`scripts/render_docs.py` loads all required JSON before mutation, rejects input/output overlap, renders into staged sibling directories, checks shard counts, and promotes with rollback backups. Package/plugin filenames include stable hashes and collision preflight. Every JSON boundary rejects non-standard NaN/Infinity.

The web explorer uses generated JavaScript registration files because `fetch()` is unreliable from `file://`. It has no network dependency and lazily loads one plugin API shard at a time.

## AgentKit Research Boundary

Local AgentKit research used allowlisted directories and safe CLI inventory. It excluded dotenv, credentials, auth data, histories, sessions, logs, telemetry, caches, virtual environments, dependencies, and unrelated personal content. Reports retain structural counts and hashes, not private values.

Official Codex and Claude guidance was checked for skill roots, common frontmatter, and progressive disclosure.

## Reproducibility And Limits

Normalized extraction/render runs must produce identical outputs for identical inputs. Tests cover parsing, queries, path overlap, strict JSON, deterministic inventory, generated counts, direct references, offline web registration, and hard-copy installation.

The kit does not establish vendor API support policy, binary compatibility across versions, licensing rights, or runtime correctness. Production integrations still require official documentation where available, exact-artifact consumer compilation, and an authorized test server.
