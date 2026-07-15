---
name: mc-pack
description: "Build and troubleshoot Minecraft resource packs and data packs: pack formats, assets/data namespaces, textures, item models, custom model data/components, fonts, sounds, atlases, predicates, delivery, merging, and version migration. Use whenever resource pack, data pack, texture, font, sound, model JSON, pack.mcmeta, or custom model data is mentioned."
---

# Minecraft Resource And Data Packs

Resolve the exact Minecraft version and pack kind first. Resource-pack and data-pack formats evolve independently and cannot be guessed from a plugin version.

## Workflow

1. Record edition/version, resource or data pack, namespace, server delivery path and client requirements.
2. Locate the shared `minecraftkit` root: sibling `../minecraftkit` after install, or `../..` from source.
3. Load `<minecraftkit-root>/references/resource-and-data-packs.md`; add model/shader references only when needed.
4. Validate `pack.mcmeta`, paths, identifiers, case, JSON schemas, parent/model references and asset conflicts.
5. Model merge priority, hash/URL delivery, acceptance status, reload behavior and older-client fallback.
6. Test with clean client cache and exact target version; report pack/data format and migration boundary.

## Scope And Security

This route handles authored or authorized assets and data. Never redistribute Mojang/vendor assets or unknown copyrighted packs, embed trackers, leak local paths, or serve untrusted executable content.
