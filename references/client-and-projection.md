# Client And Projection

Use this reference with `mc:client`. Begin by stating whether the feature requires an installed client mod or must work on an unmodified Java/Bedrock client.

## Four Different Systems

| System | Exists on server | Installed client code | Typical tools |
|---|---:|---:|---|
| real entity/display | yes | no | Paper/Bukkit display APIs |
| fake/virtual per-viewer object | no authoritative vanilla entity | no | PacketEvents, ProtocolLib, Polymer virtual entities |
| resource-pack projection | server selects/delivers assets; client renders | no mod, pack required | Adventure/Paper pack requests, generated packs |
| client mod | server may synchronize state | yes | Fabric/NeoForge/Forge APIs, GeckoLib, render mods |

Do not return client-mod code for a vanilla-client server request. Do not describe a fake packet entity as a persistent server entity.

## Authority Boundary

Server state owns gameplay identity, authorization, collision/hit decisions, inventory/economy changes and persistence. Client projections own presentation such as display IDs, bones, interpolated transforms, camera pose, shader state, glyphs and model paths.

Never use an entity packet ID, display UUID, bone name, glyph or CustomModelData slot as durable gameplay identity.

## Real Displays

Paper/Bukkit display entities are useful for text, items and blocks with client-side transform interpolation. Design:

- persistence policy and explicit removal for temporary displays;
- transformation/pivot/interpolation timing;
- tracking distance, culling and per-viewer visibility;
- world/chunk unload and plugin disable cleanup;
- authoritative interaction target separate from visual transforms;
- update coalescing and packet/entity budgets.

Client interpolation is visual only; combat, collision and timing use server state.

## Fake And Virtual Entities

A per-viewer projection needs:

1. collision-safe entity ID and UUID allocation;
2. exact protocol spawn/metadata/equipment/passenger/move/remove ordering;
3. viewer session ownership and visibility policy;
4. join, respawn, world/dimension change, teleport, range and proxy-transfer resynchronization;
5. interaction mapping back to a current server-owned target plus range/permission/state checks;
6. teardown on disconnect, disable and partial-send failure.

Packet callbacks may run on network/library threads. Move gameplay work to the correct platform owner; under Folia, use region/entity ownership.

Polymer provides a Fabric-server ecosystem for vanilla-client custom content and virtual entities. It is not a Paper plugin. PacketEvents and ProtocolLib are lower-level Paper/proxy choices when public display APIs cannot express the feature.

## Camera And Per-Viewer Effects

Treat camera state as a session with explicit enter/exit and recovery:

```text
idle -> requesting -> active -> restoring -> closed
                  \-> failed -> restoring
```

Restore on death, respawn, teleport, world change, disconnect, plugin disable, timeout and unexpected target removal. Provide an escape/timeout and avoid trapping input.

The clean-room CursorCs review found two version-sensitive paths: reflected Java camera packets and a Geyser camera-position flow, plus fake per-player text displays. It exposes a small `CursorCsApi` service rather than requiring consumers to know the transport. This is a useful `DERIVED_SOURCE` architecture pattern, but the proprietary method bodies/resources are excluded.

## Geyser And Bedrock

Bedrock is a separate client capability class, not another Java protocol number. Java resource packs, item models, dialogs, display behavior, fonts and shaders may not translate. Resolve Geyser/Floodgate session state through supported APIs and define a Bedrock-native or simple text/entity fallback.

Never infer account authorization from brand or edition alone.

## Client Mod Design

For a required client mod, pin game, loader, mod/API, Java and server handshake versions. Separate:

- logical server state and validation;
- network schema with bounded payloads;
- client game-thread state;
- render-thread resources and cleanup;
- reloadable resource/model state;
- optional renderer compatibility.

Fail gracefully when the mod/version is missing. Never make a stealth client, session/token extractor, anti-cheat bypass or remote-code loader.

## Performance Budget

Track per-viewer spawned projections, metadata/transform updates per second, bytes per second, model/display elements, view distance and cleanup lag. Use visibility culling, LOD/update tiers and shared immutable frames. Avoid per-bone per-tick updates for every viewer.

## Validation Matrix

Test exact native Java client, each translated Java protocol, clean client cache/pack rejection, separate Bedrock client, join/reconnect, respawn, world change, teleport, tracking enter/leave, reload/disable and malformed interactions. Assert session/entity-ID cleanup after every case.

## Primary References

- [Paper display entities](https://docs.papermc.io/paper/dev/display-entities/)
- [Polymer](https://github.com/Patbox/polymer)
- [PacketEvents](https://github.com/retrooper/packetevents)
- [ProtocolLib](https://github.com/dmulloy2/ProtocolLib)
- [Geyser](https://github.com/GeyserMC/Geyser)
