---
name: mc-shader
description: "Build, debug, or review Minecraft vanilla core shaders, GLSL vertex/fragment programs, render types, Iris shader packs, Sodium/Canvas/Veil rendering, uniforms, FOV/depth effects, and shader-based server visuals. Use whenever shader, GLSL, rendering, core shader, Iris, Sodium, Canvas, or Veil is mentioned."
---

# Minecraft Shaders And Rendering

Separate vanilla resource-pack core-shader overrides, mod-loader render APIs and Iris-style shader packs. They have different pipelines, loaders and conflict surfaces.

## Workflow

1. Record Minecraft version, renderer/loader, target render stage, resource-pack stack and client mod requirements.
2. Locate the shared `minecraftkit` root: sibling `../minecraftkit` after install, or `../..` from source.
3. Load `<minecraftkit-root>/references/shaders-and-rendering.md` and the exact pinned upstream source records.
4. Identify shader program, attributes, uniforms, matrices, samplers, blend/depth/cull state and fallback path.
5. Treat vanilla core-shader filenames/uniforms as version-specific internals; diff against the exact client artifact.
6. Validate compile/link logs, GPU state, pack conflicts, reduced-effects fallback and representative hardware.

## Scope And Security

This route handles rendering and shader design, not arbitrary native graphics injection or anti-cheat bypass. Do not copy proprietary shader bodies, download unknown packs, execute embedded scripts, or claim compatibility outside the tested client/loader matrix.
