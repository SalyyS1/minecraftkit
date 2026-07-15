---
description: Implement or debug Minecraft packets, codecs, and translation layers through mc:protocol.
argument-hint: "[packet flow, library, version, or bug]"
---

# /mc:protocol

Activate the installed `mc-protocol` skill for the `/mc:protocol` route:

<request>$ARGUMENTS</request>

Bind every claim to client/server version, protocol number, connection state, direction and library revision. Prefer typed wrappers/codecs over numeric IDs. Cover thread or event-loop ownership, ordering, registry dependencies, payload bounds, translation layers, disconnect behavior and cleanup; refuse exploit or credential-theft payloads.
