# NMS And Mappings

Use this reference with `mc:nms`. NMS means version-bound Minecraft server internals; original class names do not make those internals a stable API.

## First Question

Prove the required capability is absent from a supported public surface before choosing NMS. Check Paper/platform APIs, Adventure, registries, data components, dialogs, resource packs and typed packet libraries first.

NMS is justified only when its exact capability and maintenance cost are explicit.

## Game Name Epochs And Platform Namespace

| Game name epoch | Game scope | Name behavior | Required treatment |
|---|---|---|---|
| Obfuscated | through 1.21.11 | Mojang game jars are obfuscated; official/Spigot/Yarn/intermediary/SRG/TSRG/Parchment namespaces may coexist | record development, artifact and runtime namespaces plus directed mapping artifacts |
| Original-name | 26.1 onward | Mojang jars ship original names; version metadata no longer publishes mapping entries; Paper reobfuscation ends | mark `original-name`; still pin exact game/build and adapter |

Mojang's [unobfuscation announcement](https://www.minecraft.net/en-us/article/removing-obfuscation-in-java-edition) establishes the policy boundary. Absence of a mapping URL alone is not enough to infer the epoch.

Platform namespace is a separate axis. Paper 1.20.5 through 1.21.11 runs a Mojang-mapped server even though those Minecraft game jars belong to the obfuscated game epoch; legacy Spigot-mapped plugin artifacts may be remapped at load. Paper also removed versioned CraftBukkit package relocation during that transition. Do not encode this Paper-only state on `GameVersion`.

Paper's [paperweight-userdev guide](https://docs.papermc.io/paper/dev/userdev/) is the supported Paper workflow. It documents dev bundles from 1.17.1, the Paper 1.20.5 runtime transition and the end of reobfuscation after 1.21.11.

## Adapter Architecture

Keep stable plugin behavior separate from internals:

```text
public plugin/API module
  -> mapping-neutral internal capability interface
  -> exact-version adapter module
  -> NMS/CraftBukkit/paperweight dependency
```

Each adapter declares:

- exact Minecraft and platform build range (prefer one exact version);
- Java level, game name epoch, development namespace, artifact namespace, platform runtime namespace and remapping policy;
- build/dev-bundle coordinates and immutable revision;
- capability flags, scheduler/ownership requirements and known hazards;
- fingerprint detection and fail-closed behavior;
- compile and runtime fixtures.

Never silently select the nearest adapter.

## Namespace Graph

Model namespace conversion as directed edges:

```text
namespace + game_version + game_name_epoch
  --artifact(format, hash, license, completeness)-->
namespace
```

Relevant historical namespaces include official obfuscated, Mojmap, Spigot, intermediary, Yarn, SRG, TSRG and Parchment. Completeness differs: classes, methods, fields, parameters and documentation are separate properties.

Useful canonical tools include:

- [paperweight](https://github.com/PaperMC/paperweight) and [Codebook](https://github.com/PaperMC/codebook);
- [mapping-io](https://github.com/FabricMC/mapping-io), [tiny-remapper](https://github.com/FabricMC/tiny-remapper) and [Fabric Loom](https://github.com/FabricMC/fabric-loom);
- [NeoForm](https://github.com/neoforged/NeoForm), [AutoRenamingTool](https://github.com/neoforged/AutoRenamingTool) and [SRGUtils](https://github.com/neoforged/SRGUtils);
- [ForgeGradle](https://github.com/MinecraftForge/ForgeGradle) and [MCPConfig](https://github.com/MinecraftForge/MCPConfig);
- [Parchment](https://github.com/ParchmentMC/Parchment) for historical parameter/documentation enrichment.

Tool availability does not grant redistribution rights over its inputs or outputs.

## Reflection

Prefer compile-time adapters. If reflection is unavoidable:

- constrain it to an allowlisted type/member set;
- resolve once, validate descriptors/owners, cache immutable handles and fail closed;
- use a mapping-aware mechanism on mapped Paper lines; raw string literals may not remap;
- never catch `Throwable` and continue with partially initialized state;
- expose a capability result rather than leaking reflective objects upward.

Paper documents [reflection-remapper](https://github.com/jpenilla/reflection-remapper) for mapping-aware reflection. It does not turn unknown internals into a stable contract.

## Lifecycle And Threading

Internal access does not bypass platform ownership:

- mutate entities/worlds only from their owning server/region context;
- do not hold internal entity/level references across unload, respawn or reload without revalidation;
- unregister listeners, packet hooks and injected handlers idempotently;
- clean partial initialization in `finally`/rollback paths;
- assume descriptors, registry bootstrap order and packet constructors can change even when names do not.

## Compatibility Gate

At startup:

1. Read exact game/platform build and mapping epoch.
2. Match an allowlisted adapter fingerprint.
3. Verify required types, owners, descriptors and capability probes.
4. Refuse the NMS-backed feature on unknown or partial matches.
5. Offer a public-API/packet/fallback mode when possible.
6. Log only safe build/capability identifiers, never local paths or secrets.

## Validation

For every supported target:

- compile against the exact dev bundle/artifact;
- start the exact server build and exercise capability probes;
- test enable, reload/disable, world unload, reconnect and failure rollback;
- test the appropriate scheduler model, including Folia when claimed;
- compare public behavior rather than copied implementation details;
- run linkage tests that fail on missing or changed descriptors.

## Redistribution Boundary

- Do not commit or publish Mojang client/server JARs, patched server JARs, proprietary assets or decompiled method bodies.
- Official mapping terms are not a generic open-source license; store URL/hash/statistics and review before distributing derived symbol rows.
- GitHub SPDX metadata for a fork may cover only its patches, not inherited Minecraft/Spigot/Paper material.
- Build caches and generated sources stay local/ephemeral unless their exact license permits publication.

## Output Checklist

An NMS recommendation must state exact target, why public APIs are insufficient, mapping epoch/namespaces, adapter boundary, scheduler owner, fallback, failure mode, redistribution constraints and the compile/runtime matrix.
