---
name: mc-model
description: "Design Minecraft 2D/3D model and animation pipelines with Blockbench, bbmodel, Java/Bedrock model formats, GeckoLib, AzureLib, Animated Java, bones, rigs, keyframes, display entities, and server model engines. Use whenever Blockbench, model, animation, rig, bone, GeckoLib, AzureLib, or Animated Java is mentioned."
---

# Minecraft Models And Animation

Choose the runtime before the authoring format. A Blockbench project is not itself a Minecraft runtime contract.

## Workflow

1. Record Java/Bedrock edition, loader/server-only target, model runtime, Minecraft version and export format.
2. Locate the shared `minecraftkit` root: sibling `../minecraftkit` after install, or `../..` from source.
3. Load `<minecraftkit-root>/references/models-and-animation.md` and exact tool/runtime source records.
4. Define coordinate system, pivots, bone hierarchy, texture atlas, animation controllers/keyframes and export constraints.
5. Map authored identifiers to runtime assets/code; version and validate both sides together.
6. Test culling, interpolation, transforms, hitboxes, LOD/viewer cleanup and fallback visuals.

## Scope And Security

This route handles authorized model/animation workflows. Do not copy commercial models, bypass marketplace licensing, execute untrusted Blockbench plugins, or imply format compatibility without an exporter/runtime match.
