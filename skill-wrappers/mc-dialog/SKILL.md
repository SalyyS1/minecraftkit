---
name: mc-dialog
description: "Create Minecraft dialogs, dialog registries, notice/confirmation/action lists, text/range/boolean/select inputs, server links, custom click payloads, Paper Dialog API flows, and safe client input handling. Use whenever dialog, custom menu input, action button, PlayerCustomClickEvent, or server links is mentioned."
---

# Minecraft Dialogs And Client Actions

Use native data-driven dialogs where supported; do not silently substitute inventory GUIs when semantics differ.

## Workflow

1. Record Minecraft/Paper version, connection phase, registration mode and fallback client range.
2. Locate the shared `minecraftkit` root: sibling `../minecraftkit` after install, or `../..` from source.
3. Load `<minecraftkit-root>/references/dialogs-and-client-actions.md` and the pinned Paper/vanilla source record.
4. Choose dynamic versus registry-backed dialog and define body, inputs, actions, after-action and close behavior.
5. Namespace action/input keys; validate payload types, permissions, lifetime, uses, replay and connection/player availability.
6. Mark the API experimental when upstream does; add an inventory/chat fallback when older clients matter.

## Scope And Security

This route handles native dialogs and their event flow. Treat all client input as untrusted, cap text/number values, authorize actions server-side and never run raw client-provided commands.
