# Architecture Review Workflow

Use this workflow to explain how a reviewed plugin is built or to transfer its engineering patterns into a new addon.

## Review Lenses

Apply each lens and explicitly mark missing evidence:

1. **Composition root:** load/enable/disable order, manager construction, dependency discovery.
2. **Domain ownership:** aggregate roots, immutable value objects, caches, derived state.
3. **Extension model:** services, facades, registries, loaders, providers, events, adapters.
4. **Data flow:** inputs, validation, transformation, persistence, events, outputs.
5. **Thread model:** sync/async/Folia scheduler boundaries and callback context.
6. **Persistence:** source of truth, serialization, migration, flush/close, failure recovery.
7. **Compatibility:** optional plugins, version dispatch, NMS/protocol boundary, fallbacks.
8. **Lifecycle cleanup:** listener/task disposal, cache invalidation, entity/player unload.

## Evidence Order

Use the curated architecture documents first, then query exact API records. Only inspect authorized decompiled source when the existing summary cannot answer the question.

Classify evidence:

- `VERIFIED_BYTECODE` for structure and signatures;
- `DERIVED_SOURCE` for behavior traced through decompiled control flow;
- `UNVERIFIED` for runtime timing, undocumented ordering, or suspicious decompiler output.

Do not convert a repeated pattern into a guarantee unless an interface, event contract, or empirical test supports it.

## Professional Patterns Worth Reusing

- stable IDs and typed registries;
- two-phase registration then reference resolution;
- provider/adapter boundaries for storage and optional dependencies;
- cancellable pre-events plus factual post-events;
- aggregate roots for player, item, profile, dungeon, and model state;
- buffered recomputation for equipment and stats;
- explicit scheduler abstraction and tick phases;
- idempotent teardown with owned task/listener/resource tracking;
- config loaders that report object ID and source path on failure;
- narrow compatibility modules instead of optional-plugin checks everywhere.

## Review Output

Return a short architecture statement, a state/data flow, extension points ranked by stability, transferable engineering patterns, concrete risks, and a validation plan. Cite evidence by relative decompiled path and line when using source-derived conclusions.

Keep design advice original. Do not transplant proprietary method bodies or reproduce internal algorithms line for line.
