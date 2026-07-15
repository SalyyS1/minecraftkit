---
name: mc-nms
description: "Work safely with Minecraft server internals, NMS, Mojang/Spigot/Yarn/Parchment mappings, paperweight-userdev, remapping, reflection, version modules, CraftBukkit and internals migration. Use whenever NMS, internals, mapping, Mojmap, Yarn, Parchment, paperweight, reflection, or remap is mentioned."
---

# Minecraft NMS And Mappings

Use internals only after proving the required capability is absent from a stable API. Bind code to an exact runtime and mapping namespace.

## Workflow

1. Record Minecraft/Paper version, Java version, mapping namespace, build tool and deployment targets.
2. Locate the shared `minecraftkit` root: sibling `../minecraftkit` after install, or `../..` from source.
3. Load `<minecraftkit-root>/references/nms-and-mappings.md` and the pinned version/source record.
4. Prefer Paper API, Adventure, registry/data-component APIs or packets before NMS.
5. When unavoidable, use supported paperweight-userdev/version-module boundaries and isolate internal symbols behind an adapter.
6. Compile and runtime-test every supported version; fail closed on unknown mappings/signatures.

## Scope And Security

This route handles legitimate server internals. Do not redistribute Minecraft server/client JARs, proprietary mappings/assets, bypass licensing, or fabricate cross-version stability. Avoid unconstrained reflection and never swallow linkage errors silently.
