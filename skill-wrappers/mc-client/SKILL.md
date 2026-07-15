---
name: mc-client
description: "Design Minecraft client-side mods and server-driven client projections: fake entities/blocks, display entities, holograms, camera/input flows, Polymer, Geyser/Floodgate, per-viewer state, and packet-backed visuals. Use for client-side, fake object, projection, camera, hologram, or Bedrock bridge requests."
---

# Minecraft Client And Projection

Distinguish an installed client mod from a vanilla-client projection produced by packets/resource packs. State that requirement before designing the feature.

## Workflow

1. Record Java/Bedrock clients, loader/mod requirements, server fork, versions and per-viewer isolation.
2. Locate the shared `minecraftkit` root: sibling `../minecraftkit` after install, or `../..` from source.
3. Load `<minecraftkit-root>/references/client-and-projection.md`; add pack/protocol references only when needed.
4. Define authoritative server state separately from projected entity/block/UI state.
5. Design viewer join/respawn/world-change/teleport/reload cleanup and entity-ID lifecycle.
6. Validate interaction routing, packet order, tracking range, bandwidth, anti-cheat and Bedrock degradation.

## Scope And Security

This route handles legitimate client mods and server visuals. Do not create stealth clients, credential/session theft, anti-cheat bypass, remote code execution, or deceptive UI that captures sensitive data.
