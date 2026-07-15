# Dialogs And Client Actions

Use this reference with `mc:dialog`. Native Minecraft dialogs are data-driven client UI controlled by server definitions; responses remain untrusted client input.

## Compatibility Contract

Record exact Minecraft client/protocol, Paper API/build, data-pack format, registration mode and fallback clients. Dialogs arrived in modern Minecraft and Paper's Dialog API remains experimental; do not advertise it as a stable cross-version Bukkit contract.

Use [Paper's versioned Dialog API documentation](https://docs.papermc.io/paper/dev/dialogs/) as the primary developer source and pin the project snapshot through the source catalog.

## Modes

| Mode | Good for | Lifecycle boundary |
|---|---|---|
| data-pack/registry definition | stable named UI shipped with server data | pack reload/bootstrap and exact data format |
| Paper registry-backed dialog | plugin-defined keyed UI discoverable through registry | registration event/bootstrap, not arbitrary late mutation |
| dynamic Paper dialog | per-player/session UI assembled at runtime | player/connection lifetime and experimental API |
| legacy fallback | inventory, book, chat or form plugin | different semantics; disclose the substitution |

Do not silently call an inventory GUI “the same dialog” when it lacks inputs, actions or client behavior.

## Composition

A dialog design should explicitly define:

- namespaced dialog key and optional session/nonce binding;
- base title/body, exit behavior and after-action policy;
- input keys and types: boolean, text, number/range or selection;
- type: notice, confirmation, list/multi-action, server links or other supported variant;
- action buttons and namespaced custom click identifiers;
- server-side authorization and semantic handler;
- timeout, close, disconnect, duplicate and late-response behavior;
- fallback for unsupported clients.

Treat exact builders/types as versioned Paper API. Query the pinned source/API rather than copying an example from a moving docs page.

## Input Validation

For every response:

1. Resolve the player/connection and active server-owned dialog session.
2. Match dialog key, action key and single-use nonce/sequence where available.
3. Check permission, current state, world/range/context and rate limits.
4. Validate field type, string length/content, selection allowlist, number bounds/step and NBT/custom payload limits.
5. Apply the semantic action idempotently.
6. Invalidate the session and clean it on every terminal path.

Never interpolate raw client text into console/player commands. Map allowlisted action IDs to server functions.

## Connection-Phase Flow

Some UI/pack decisions can occur while a connection is being configured rather than during normal play. Model this as a bounded state machine:

```text
connected
  -> capability/version resolved
  -> pack/dialog definitions prepared
  -> request shown/sent
  -> response | timeout | disconnect | server switch
  -> validate and continue, reject, or fall back
  -> finally remove pending state
```

Do not block the server thread. Futures/tasks need timeouts, cancellation and `finally` cleanup. A player object may not yet be available in every connection phase.

## Security And UX

- Client response/status is a claim, not proof of authorization or pack integrity.
- Do not embed secrets, trust tokens or hidden authorization state in dialog definitions.
- Rate-limit reopen/custom-click loops and cap concurrent pending dialogs.
- Keep accessibility text and a non-pixel-perfect fallback; fonts/packs may fail.
- Make destructive actions explicit and require confirmation where appropriate.
- Do not create deceptive screens that imitate account, launcher or payment credential prompts.

## Testing

Test native supported client, oldest declared client, Via-translated paths and a separate Geyser/Bedrock fallback. Exercise duplicate response, unsolicited key, invalid field values, close, timeout, disconnect, proxy switch, reload and permission/state changes while open.

## Original Addon Pattern

`ORIGINAL_DESIGN`: a context-aware quest contract dialog can compose RPG state with a native confirmation/list dialog. The dialog shows only a projection; the server re-resolves the quest/version/party state on click, reserves the encounter idempotently, then opens the encounter. Older clients receive a book/inventory summary and explicit command. This uses verified dialog and RPG primitives but is not claimed as a vendor feature.
