---
name: mc-protocol
description: "Implement and debug Minecraft packets, protocol states/codecs, ProtocolLib, PacketEvents, ViaVersion/ViaBackwards/ViaRewind, MCProtocolLib, proxy translation, custom payloads, packet order, fake entities, and version-safe networking. Use whenever packet, protocol, codec, ProtocolLib, PacketEvents, ViaVersion, custom payload, or wire format is mentioned."
---

# Minecraft Packets And Protocols

Bind every packet claim to protocol version, connection state, direction and library mapping. Packet names alone are not stable identifiers.

## Workflow

1. Record client/server versions, protocol number, state, direction, proxy/translation layer and packet library version.
2. Locate the shared `minecraftkit` root: sibling `../minecraftkit` after install, or `../..` from source.
3. Load `<minecraftkit-root>/references/packets-and-protocols.md` and exact source/version records.
4. Prefer wrapper types/codecs over numeric IDs and reflection; define thread/event-loop ownership.
5. Validate packet order, entity IDs, registry/data dependencies, cancellation side effects, payload bounds and disconnect behavior.
6. Test native, translated and unsupported client paths; include cleanup and graceful disable behavior.

## Scope And Security

This route supports legitimate interoperability and debugging. Refuse credential/session theft, unauthorized traffic interception, crash/exploit payloads, anti-cheat bypass or covert surveillance. Never log secrets or full sensitive packet payloads.
