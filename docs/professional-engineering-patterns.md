# Professional Engineering Patterns

These patterns recur across the reviewed plugins. They are valuable because they make large, configurable RPG systems operable under reloads, optional dependencies, persistence, and high event volume. Reuse the pattern, not the proprietary implementation.

## 1. Stable IDs And Typed Registries

MMOCore, MMOItems, ModelEngine, MythicDungeons, MythicEnchants, and MythicRPG turn configuration strings into typed domain objects through registries.

Use:

- lowercase namespaced IDs such as `myaddon:relic_power`;
- duplicate rejection with source-path diagnostics;
- immutable read views;
- explicit unregister/deindex on supported reload;
- schema/version metadata for persisted IDs.

Avoid storing Java object references across reloads. Resolve stable IDs again after registries publish.

## 2. Two-phase Load And Reference Resolution

Definitions often refer to other definitions whose file order is not meaningful. MMOItems/MMOCore register schemas early; Crucible performs a second pass; ModelEngine publishes parser/behavior registration seams.

Recommended transaction:

1. parse raw definitions;
2. validate local fields;
3. register identities without publishing live behavior;
4. resolve cross-references;
5. reject or quarantine incomplete definitions;
6. atomically publish immutable views;
7. emit a factual loaded event.

## 3. Aggregate Roots Own Invariants

Examples include MMOCore `PlayerData`, MMOItems `MMOItem`, MMOProfiles `PlayerProfile`, ModelEngine `ModeledEntity`, MythicDungeons instances, and MythicRPG profile sessions.

A new addon should mutate state through one aggregate transition rather than several unrelated listeners. This provides one place for validation, revision numbers, event ordering, and idempotency.

## 4. Provider And Adapter Boundaries

Strong boundaries include Bukkit services, explicit API providers, party/guild modules, storage drivers, inventory suppliers, scheduler abstractions, NMS handlers, and optional-plugin compatibility managers.

An addon should define its own small ports:

```text
ProgressionReader
EquipmentSnapshotProvider
ProfileIdentityProvider
DungeonRunGateway
ModelProjection
RewardLedger
```

Vendor-specific adapters implement them. Core business logic then remains testable and degrades cleanly when an optional plugin is absent.

## 5. Event-first Extensibility

Good transition design has:

- cancellable pre-event before side effects;
- only intentionally mutable fields;
- committed transition with stable correlation ID;
- factual post-event after authoritative state changes;
- no silent cancellation after irreversible writes.

Guard recursive event loops. One equip change can trigger item, inventory, stat, model, lore, and profile listeners.

## 6. Config Factories And DSL Components

CoreTools script factories and the Mythic mechanics/conditions/targeters model let content authors extend behavior without Java changes. MythicDungeons adds a trigger-condition-function graph.

Treat configuration as a public product API:

- validate at load with exact object ID and source path;
- version and migrate keys;
- document aliases from actual registration metadata;
- bound loops, delay, recursion, and target counts;
- never make transient script context the durable source of truth.

## 7. Buffered Derived-state Updates

MMOItems coalesces inventory resolver updates before recalculating abilities, effects, permissions, and set bonuses. The same technique applies to party synergy, model equipment, HUDs, and relic boards.

Collect changes inside a transaction, update authoritative state once, then produce one derived snapshot. This avoids event storms and inconsistent intermediate states.

## 8. Explicit Scheduler And Tick Phases

ModelEngine provides phased tick tasks and a scheduler adapter. Mythic plugins select Bukkit/Folia schedulers. Storage often completes asynchronously.

Rules:

- entity, inventory, and world mutations execute on the owning main/region scheduler;
- pure calculation and storage I/O may run async;
- completion returns through an explicit scheduler boundary;
- task ownership is recorded for teardown;
- callbacks re-check entity/player/profile/run validity.

## 9. Immutable Public Views

MythicRPG's `Optional` results and copied DTO collections are safer than leaking mutable managers. Public contracts should return immutable snapshots or narrow commands. Mutable collections make registry corruption and cross-thread races too easy.

## 10. Lifecycle-owned Cleanup

Every created resource needs an owner:

| Resource | Typical owner | Required cleanup |
|---|---|---|
| listener/task | plugin module | unregister/cancel on disable or module unload |
| player/profile cache | session | invalidate on switch, quit, unload |
| dungeon world/container | run manager | restore players, close handles, verify path, dispose |
| modeled entity/VFX | encounter/entity | remove ticker/network/render state |
| addon classloader | addon manager | unregister callbacks then close loader |
| pending write | repository unit of work | finish/retry/cancel by revision |

Teardown should be idempotent. Unsupported hot reload is not solved by ignoring leaks; choose restart deployment when the vendor lifecycle cannot safely reset.

## 11. Repository, Journal, And Migration

MythicRPG demonstrates driver isolation and SQL migrations; MMOProfiles demonstrates modular profile state. Economy, item provenance, and one-time rewards need stronger journaling than a mutable YAML value.

Persist:

- stable domain ID;
- schema version;
- aggregate revision;
- idempotency/correlation key;
- state transition and timestamp;
- minimal recovery payload.

Do not infer “all persisted players” from an online cache API.

## 12. Graceful Optional Integrations

Detect an integration once at startup and bind one adapter. Core logic should receive `available`, `degraded`, or `disabled` capability state, not scatter plugin-manager checks everywhere.

Prefer losing visuals, HUD, or bonus composition before losing authoritative identity, reward, or economy correctness.

## 13. Observability As A Feature

Useful reviewed practices include load counts, explicit placement result enums, generation summaries, diagnostic retries, and lifecycle events.

For every addon transition, log structured identifiers without personal content: feature, definition ID, profile/run/item correlation ID, old/new revision, outcome, elapsed time, and failure class. Keep player-facing messages separate from staff diagnostics.

## 14. Failure Modes Worth Designing First

- profile module never completes;
- server stops between reward commit and delivery;
- dependency disables/reloads;
- definition disappears after migration;
- duplicate listener callback;
- player leaves during async work;
- generated world path is misconfigured;
- model bone or native enchant registry entry is absent;
- inventory is full;
- storage is slow or temporarily unavailable.

If the design cannot explain these cases, it is not build-ready.

## Pattern Selection Checklist

- What is authoritative state?
- Which stable IDs cross boundaries?
- Which lifecycle phase registers and resolves definitions?
- Which thread owns each transition?
- What is the pre-event and post-event contract?
- How are duplicate callbacks made harmless?
- What survives restart?
- Which optional integration can degrade?
- How does teardown prove every owned resource is released?
- Which claims are `VERIFIED_BYTECODE`, `DERIVED_SOURCE`, or still `UNVERIFIED`?
