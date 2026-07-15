# Models And Animation

Use this reference with `mc:model`. Choose the runtime first; a Blockbench project or model JSON does not determine how Minecraft renders or animates it.

## Runtime Matrix

| Runtime | Client mod | Delivery | Main use |
|---|---:|---|---|
| vanilla item/block model | no | resource pack | static/custom item and block appearance |
| display-entity animation | no | data pack/functions plus optional resource pack | server-driven transforms and vanilla-client models |
| Animated Java | no runtime mod | generated data/resource packs | Blockbench-authored display animation |
| GeckoLib 5 | yes | loader mod + model/animation resources | client-rendered entity/item/block skeletal animation |
| AzureLib | yes | loader mod + resources | separate GeckoLib-4-derived animator ecosystem |
| playerAnimator | yes | client library | player pose layers |
| EMF/ETF | yes | client mods + compatible packs | OptiFine-style entity model/texture features |
| ModelEngine | no client mod, pack required | commercial server plugin + per-viewer projection | modeled server entities/bones/animations |

Do not describe GeckoLib/AzureLib as server-only resource packs. Do not describe display animation as client skeletal rendering.

## Blockbench Contract

Blockbench is an authoring and plugin host. Pin:

- Blockbench version and native bbmodel/project format;
- model format/codec and exporter/plugin version/checksum;
- Java/Bedrock/OptiFine/generic coordinate convention;
- target game, loader/runtime and resource/data-pack formats;
- texture sources/licenses and generated asset manifest.

Relevant extension surfaces include plugin lifecycle, `Codec`, `ModelFormat`, project, cube/mesh/group, animation/keyframe and Molang concepts. Blockbench plugins are executable JavaScript; never auto-install/execute registry entries during research. Inspect source, permissions, checksum, supported Blockbench range and license first.

## Authoring Worksheet

```text
edition/game/loader:
runtime and exact version:
Blockbench + exporter version:
coordinate axes, units and origin:
pivots and bone hierarchy:
texture atlas/resolution/UV rules:
animations, loops, controllers, transitions and keyframes:
events: sound, particle, function/custom callback:
runtime identifier map:
hitbox/collision authority:
LOD/culling/update budget:
fallback visual:
```

Normalize and validate model, bone, locator, variant and animation IDs. Keep stable gameplay IDs separate from authored/render identifiers.

## Animated Java

Animated Java exports Blockbench work into Minecraft data/resource-pack behavior using display entities. Pin the exporter and required Blockbench version. Function/script keyframes execute within server/data-pack permission context and need review.

Budget display count, summon/removal, transform update rate and per-viewer visibility. Test reload, interrupted animation and cleanup. Custom textures/models still require a pack even if some vanilla assets do not.

## GeckoLib 5

GeckoLib 5 provides loader-specific client animation/rendering for entities, items and blocks. Pin GeckoLib major, Minecraft, loader and Java; GeckoLib 4 examples are not interchangeable.

Design per-instance animatable identity, cache lifecycle, controller concurrency/priorities, network synchronization and keyframe side effects. Sound/particle/custom callbacks must run on the correct side and be deduplicated against prediction/replay.

## AzureLib And Player/Entity Features

AzureLib is a separate GeckoLib-4-derived system with its own animator/controllers; use only on its exact supported line. playerAnimator, EMF and ETF inject into sensitive client render paths and may conflict with cosmetics, armor, first-person, shaders and renderer replacements. Test the whole client mod stack.

## ModelEngine Integration

For the authorized ModelEngine R4.1.0 artifact, use the verified API catalog rather than implementation bodies. Prefer the public facade/provider, modeled entity/active model, animation handler, bone/behavior/render and viewer APIs. Bind through an owned adapter so plugin readiness, reload and absence do not leak across gameplay code.

ModelEngine bones/viewer entities are projections. Rebuild them from stable server state after reload; clean forced viewers; profile packet volume, bones, culling and LOD. Match the paid artifact with its generated resource pack.

## Budgets

Define caps for texture bytes/dimensions, cubes/meshes, bones, keyframes, animation duration, concurrent controllers, display elements, particles/sounds and per-viewer update bandwidth. Use culling, visibility range, LOD/update tiers and shared immutable frames.

## Security And Provenance

- Do not copy commercial models, default vendor packs or marketplace assets.
- Treat bbmodel/JSON/textures/plugins/exporters as untrusted input.
- Reject path traversal, oversized/recursive structures, non-finite transforms and invalid identifiers.
- Pin every tool/runtime dependency and retain asset author/license/checksum.
- Do not let model/function keyframes execute arbitrary commands without an allowlist and server authorization.

## Validation

Test static format validation, exporter reproducibility, exact runtime load, resource reload, animation transitions/interruptions, culling, transforms/pivots, hitbox separation, join/respawn/world change, unload/disable cleanup and fallback. For client mods, include renderer/shader/cosmetic compatibility.

## Primary References

- [Blockbench formats](https://www.blockbench.net/wiki/blockbench/formats/)
- [Blockbench plugin development](https://www.blockbench.net/wiki/docs/plugin/)
- [Animated Java](https://github.com/Animated-Java/animated-java)
- [GeckoLib](https://github.com/bernie-g/geckolib)
- [AzureLib](https://github.com/AzureDoom/AzureLib)
