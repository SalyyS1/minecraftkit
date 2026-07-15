# RPG Feature Design

Use this workflow to compose a feature from two or more reviewed plugin contracts.

## Capability-First Design

Define the gameplay invariant before selecting APIs. Examples:

- a profile must never receive another character's equipment;
- a reward must be granted at most once per dungeon run;
- a visual limb state must match authoritative combat state;
- a crafting cost must survive restart and disconnect.

Then choose one authoritative owner for each state field. Other plugins receive projections through events, adapters, or derived caches.

## Composition Sequence

1. Identify trigger and cancellation point.
2. Read required state through the strongest service/API boundary.
3. Validate profile/session and plugin readiness.
4. Compute the transition without side effects where practical.
5. Apply mutations on the correct scheduler/thread.
6. Persist the authoritative state or enqueue an idempotent write.
7. Publish a post-event or refresh derived projections.
8. Record enough correlation data to retry or diagnose safely.
9. Dispose tasks/listeners/caches at player, entity, dungeon, profile, and plugin teardown.

## Cross-Plugin Rules

- Wrap every vendor dependency behind an addon-owned port or adapter.
- Store stable IDs, not Java object instances, across reloads.
- Never make lore, packets, model bones, or GUI state the source of truth.
- Coalesce equipment/stat/model refreshes when one action emits multiple events.
- Guard event loops with transaction/correlation IDs or scoped reentrancy flags.
- Fail closed for economy, item duplication, profile selection, and one-time rewards.
- Degrade visuals and optional integrations before disabling authoritative gameplay.

## Design Deliverable

Provide:

- player-facing behavior and explicit non-goals;
- plugin/version/API matrix with confidence labels;
- state model and ownership table;
- event sequence and scheduler context;
- persistence schema and migration strategy;
- disconnect/reload/retry/idempotency handling;
- compatibility and optional-dependency behavior;
- test matrix covering happy path, cancellation, race, restart, and missing dependency.

Use `docs/rpg-feature-catalog.md` for capability discovery and `docs/original-addon-blueprints.md` for worked compositions. The feature catalog is inspiration, not proof of an exact symbol; query the API index before implementation.
