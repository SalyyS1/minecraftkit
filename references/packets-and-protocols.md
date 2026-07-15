# Packets And Protocols

Use this reference with `mc:protocol`. A packet claim is valid only for an exact edition, protocol, connection state, direction, codec schema and library revision.

## Escalation Rule

Prefer the highest semantic layer that can implement the feature:

1. public platform API and events;
2. Adventure, registry, data-component or resource/data-pack surface;
3. a typed packet-library wrapper;
4. a version-pinned protocol codec;
5. isolated NMS/network internals as a last resort.

Packets expose representation and timing, not stable gameplay semantics. Sending bytes successfully does not prove the client reached a valid state.

## Packet Identity

Do not key by packet display name or numeric ID alone. Use at least:

```text
edition + protocol_id + connection_state + direction + wire_id + codec_schema_hash
```

Keep symbolic aliases per source because ProtocolLib, PacketEvents, ViaVersion, MCProtocolLib and Prismarine datasets can name the same wire structure differently. One protocol ID may map to multiple launcher-visible game versions.

States commonly include handshake, status, login, configuration and play. Never decode a play packet under a login/configuration schema.

## Surface Selection

| Need | Preferred source | Important boundary |
|---|---|---|
| Bukkit/Paper interception | ProtocolLib | pin release/build; structure indices are not semantic contracts |
| Cross-platform wrapper/interception | PacketEvents | pin module/platform and protocol coverage; callback ownership differs |
| Newer clients to older servers | ViaVersion | directed translator; feature fidelity is not guaranteed |
| Older clients to newer servers | ViaBackwards | directed, often lossy transformations |
| 1.7/1.8 bridge | ViaRewind plus required Via projects | legacy behavior and extra security/dependency surface |
| Standalone Java client/server | MCProtocolLib | one concrete game line; current work may be snapshot-first |
| Generated/community schemas | minecraft-data + ProtoDef | derived, potentially lagging and mixed-provenance data |
| Proxy topology | Velocity or BungeeCord API | forwarding/auth and backend trust boundary matter |

Use pinned repository records for exact current releases. Do not derive “supports every version between A and B” from an enum endpoint.

## Protocol Graph

Model game and protocol as many-to-many assertions:

```text
GameVersion --USES_PROTOCOL--> ProtocolVersion
LibraryRelease --UNDERSTANDS--> ProtocolVersion
TranslatorRelease --TRANSLATES--> TranslationEdge
PacketSchema --BELONGS_TO--> ProtocolVersion + state + direction
```

When Mojang does not publish a protocol number, corroborate it with two maintained implementations where practical. Otherwise label the single-source assertion `DERIVED_SOURCE`.

## Translation Edges

Store Via-style support as a directed edge, never a badge:

- translator release and dependency chain;
- source and destination protocols;
- serverbound/clientbound behavior;
- affected registries, entities, items, sounds, UI and world geometry;
- fidelity: exact, substituted, dropped, unsupported or unknown;
- immutable evidence and observed timestamp.

ViaVersion, ViaBackwards and ViaRewind solve different directions/scopes. Do not reverse an edge automatically.

## Wrapper Design

A packet adapter should expose domain meaning and hide library/version layout:

```text
Feature service
  -> semantic operation (show projection, receive action, update camera)
  -> version/library adapter
  -> typed packet(s) and ordering
  -> per-viewer session/cleanup registry
```

The adapter owns:

- protocol/version gate;
- packet order and required registry/entity dependencies;
- entity/window/transaction ID allocation;
- conversion from network callbacks to platform ownership context;
- teardown on disconnect, respawn, world change, plugin reload and failed partial send;
- fallback or explicit unsupported result.

Never expose raw numeric field positions as the feature-level API.

## Thread And Lifecycle Rules

- Decode on the library's allowed context; move gameplay mutation to the owning platform scheduler.
- Under Folia, schedule by region/entity ownership rather than a fictional global main thread.
- Keep per-connection state bounded and remove it on every terminal path.
- Define packet ordering around spawn, metadata, passengers, equipment, teleport and removal.
- Treat cancellation as a state transition: downstream packets/server state may still require repair.
- Register and unregister listeners idempotently across reload/disable.

## Defensive Decoding

Treat every client field as untrusted:

- cap byte arrays, strings, lists, NBT depth/size and decompressed output;
- validate enum IDs, resource locations, registry references and state;
- reject non-finite coordinates/rotations and invalid VarInt/length combinations;
- authorize semantic actions server-side after parsing;
- keep raw capture opt-in, bounded, redacted and short-lived;
- never log session/auth tokens or complete sensitive login/custom payloads.

Version detection and client brand are not authorization.

## Projection Example

A safe fake-entity/hologram feature needs more than a spawn packet:

1. Allocate a collision-safe per-viewer entity ID and UUID.
2. Send spawn and metadata in the target protocol's required order.
3. Keep authoritative hit/action routing on the server.
4. Recreate on respawn/world/translation-boundary changes as needed.
5. Remove on range exit, disconnect, disable and error rollback.
6. Provide a display/entity/chat fallback when the client/protocol cannot represent the feature.

CursorCs demonstrated this composition through a clean-room review: a server-owned session, per-player fake display packets, Java camera packets, a Geyser camera path and explicit lifecycle cleanup. This is `DERIVED_SOURCE`; MinecraftKit does not redistribute its proprietary implementation.

## Testing Matrix

Test at least:

- exact native client/server pair;
- every declared translated client edge;
- join, login/configuration/play transitions;
- reconnect, respawn, dimension/world change and proxy transfer;
- missing registry/data dependency and malformed/boundary payloads;
- listener cancellation and partial-send rollback;
- Folia or other alternate scheduler model when claimed;
- bandwidth/allocation pressure and cleanup leak checks.

Codec implementations should have fixture round trips. Cross-source schema conflicts must remain visible rather than silently picking one.

## Primary References

- [ProtocolLib](https://github.com/dmulloy2/ProtocolLib)
- [PacketEvents](https://github.com/retrooper/packetevents)
- [ViaVersion](https://github.com/ViaVersion/ViaVersion)
- [ViaBackwards](https://github.com/ViaVersion/ViaBackwards)
- [ViaRewind](https://github.com/ViaVersion/ViaRewind)
- [MCProtocolLib](https://github.com/GeyserMC/MCProtocolLib)
- [minecraft-data](https://github.com/PrismarineJS/minecraft-data)
