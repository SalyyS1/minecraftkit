# Shaders And Rendering

Use this reference with `mc:shader`. “Minecraft shader” can mean several incompatible systems; identify the pipeline before proposing files or code.

## Pipeline Taxonomy

| Pipeline | Owner | Client requirement | Contract |
|---|---|---|---|
| Vanilla core/include/post shaders | Mojang client + active resource packs | vanilla client can load an overriding pack | volatile asset paths, shader interfaces and render state |
| Iris shader packs | Iris + compatible renderer/client | Fabric client mod and matching game build | OptiFine-style shader-pack ecosystem plus Iris API |
| Sodium | renderer replacement | matching Fabric/NeoForge client artifact | performance renderer and narrow public integration APIs, not a shader-pack API |
| Veil | mod-developer rendering framework | matching Fabric/NeoForge client mod | shaders, framebuffers, post processing and render tooling |
| Canvas/FREX | alternate historical Fabric renderer/material system | old matching Fabric client | separate material pipeline; not Iris-compatible and not current default |

A server cannot install client rendering code. Without a client mod it can deliver a resource pack, use display entities or project packets; that is not equivalent to a renderer framework.

## Pinned Vanilla Baseline

The 2026-07-15 clean inventory of the Mojang 26.2 client found:

- resource-pack format `88.0`;
- 61 entries under the core shader area, 9 include files and 10 post shader files;
- named client navigation points including `RenderPipeline` and `RenderPipelines`.

These counts are `VERIFIED_UPSTREAM` for the SHA-addressed 26.2 artifact referenced by Mojang metadata. MinecraftKit stores counts/paths and original analysis only; it does not publish Mojang shader bodies.

Core shaders are implementation internals. Pin every filename, attribute, uniform, sampler, matrix, blend/depth/cull assumption and render target to the exact client artifact. A pack that compiles on one version may render incorrectly or fail on the next.

## Shader Contract Worksheet

Before editing:

```text
game/client artifact:
loader + renderer + shader framework:
pack stack and precedence:
stage/program/path:
vertex attributes and formats:
uniforms/matrices/time inputs:
samplers and texture ownership:
render target/framebuffer:
blend/depth/cull/write state:
color space and alpha convention:
fallback when compile/link/runtime support fails:
```

Do not copy a variable name from another version or renderer and assume it exists.

## Vanilla Core-Shader Override

Use only when the target is a controlled client/pack matrix and a public gameplay API cannot provide the visual. Treat the override as a whole-pack compatibility surface:

1. Resolve the exact vanilla shader path and paired vertex/fragment interface from the target client.
2. Author the smallest independent change; do not paste Mojang/vendor bodies into documentation.
3. Preserve attribute locations, varying types, sampler bindings and expected output semantics.
4. Compile/link every program in the pack, not only the edited one.
5. Test pack precedence against other server/resource packs and accessibility settings.
6. Provide a no-effect or normal-render fallback.

CursorCs supplied one `DERIVED_SOURCE` example: its pack tests a negative game-time signal while a server packet adapter sends a special world-age value, producing a per-session FOV effect. This is an inventive composition, not a stable Mojang API. It can collide with other core-shader packs, protocol translators and future uniform behavior; implement equivalent ideas behind exact-version capability gates and an explicit fallback.

## Iris And Renderer Stack

Iris loads shader packs and integrates closely with Sodium. Resolve a publisher artifact for the exact Minecraft version; do not install a 26.1.x artifact on 26.2 merely because the version is nearby.

Test at least:

- Iris and Sodium declared-compatible pair;
- target shader pack with optional features both enabled and disabled;
- integrated graphics and representative discrete GPU/driver families;
- other rendering/model mods in the actual client pack;
- world/dimension transitions, reload, resize and resource reload;
- fallback with shaders disabled.

Sodium internals are not its API. Its current license is metadata/link-sensitive for MinecraftKit; use the catalog's `metadata-only` policy unless a separate review permits more.

## Mod Rendering Frameworks

For Fabric's current line, use versioned Fabric rendering/model/resource modules and current render-state/extraction guidance. Keep client-only registrations in client source sets.

For NeoForge/Forge, bind model loaders, codecs, baking events and render registration to the exact documented game branch. A Forge 1.21.x geometry-loader recipe is not evidence for 26.2.

Veil provides powerful framebuffers/post-processing/editor surfaces but its observed public artifact targets an older game line. Canvas/FREX is historical and a separate pipeline. Return them only when their exact target matches the request.

## Performance And Safety

- Bound render targets, texture dimensions, passes, samples, lights and per-frame allocations.
- Avoid unbounded loops, NaN/Infinity propagation and data-dependent shader work from untrusted pack values.
- Treat shader packs as untrusted input; never auto-enable downloaded content or execute bundled scripts/tools.
- Record GPU/driver crashes and compile errors without leaking user paths or identifiers.
- Avoid visual spoofing that imitates trusted UI or captures sensitive input.
- Test photosensitivity/accessibility and offer reduced-effects controls.

## Validation Output

Report exact game/client, renderer/framework versions, pipeline kind, shader contract, pack conflicts, client requirement, compile/runtime matrix, performance budget and fallback. Label any inferred vanilla interface `UNVERIFIED` until checked against the exact client artifact.

## Primary References

- [Fabric rendering concepts](https://docs.fabricmc.net/develop/rendering/basic-concepts)
- [Sodium](https://github.com/CaffeineMC/sodium)
- [Iris](https://github.com/IrisShaders/Iris)
- [Veil](https://github.com/FoundryMC/Veil)
- [Canvas](https://github.com/vram-guild/canvas)
