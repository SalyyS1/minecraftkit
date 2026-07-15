# Original Addon Blueprints

Every concept here is `ORIGINAL_DESIGN`. The reviewed plugins provide the listed primitives, but the end-to-end feature was not identified in the supplied artifacts. Exact symbols must be re-queried before implementation.

## Idea Catalog

| # | Addon | Plugin composition | New behavior |
|---:|---|---|---|
| 1 | Adaptive Raid Director | Dungeons + MMOCore + MythicRPG + MMOItems + Enchants | Locks a bounded party-power plan and learns from failures without changing difficulty mid-run |
| 2 | Profile-bound Seasonal Relic Board | MMOProfiles + MMOInventory + MMOItems + MMOCore | Versioned relic slots isolated per character and season |
| 3 | Reward Escrow And Recovery | Dungeons + Profiles + MMOItems + Enchants + CoreTools | Exactly-once dungeon rewards that survive crash, death, and profile switch |
| 4 | Reactive Anatomy Boss | ModelEngine + Dungeons + Crucible + MMOCore | Limb health changes attacks, animation, equipment, and room routes |
| 5 | Item Provenance Ledger | MMOItems + Crucible + Enchants + CoreTools + Profiles | Append-only lifecycle identity for high-value items |
| 6 | Crafting Research Tree | MMOItems + Crucible + MMOCore + MythicRPG | Recipe families unlock through experimentation and research |
| 7 | Dynamic Affix Economy | MMOItems + CoreTools | Market demand influences reforge cost and future affix supply inside bounds |
| 8 | Party Synergy Relics | MMOCore + MythicRPG + MMOItems + MMOInventory | Relics activate bonuses from nearby party-role composition |
| 9 | Waypoint Caravan Contracts | MMOCore + MythicRPG + CoreTools | Timed trade routes respond to traffic, risk, and destination demand |
| 10 | Cross-server Expedition Character | MMOProfiles + MMOCore + Inventory + Items | Temporary character travels across a cluster and merges whitelisted rewards home |
| 11 | Death Insurance And Recovery Hunt | Inventory + MMOCore + CoreTools + Dungeons | Uninsured gear becomes an owner-bound recovery encounter |
| 12 | Balance Telemetry Advisor | MMOCore + Items + Dungeons + RPG | Privacy-light signals produce review suggestions without auto-editing configs |
| 13 | Contextual Resource HUD | MMOCore + RPG + CoreTools + ModelEngine | Accessible panels change with class, combat, item, station, and objective |
| 14 | Account Legacy, Character Mastery | Profiles + MMOCore + RPG + CoreTools | Explicit account inheritance with profile-local mastery and migrations |
| 15 | Relic Evolution | Crucible + Enchants + RPG + ModelEngine | Relics branch from feats and change abilities, lore, and visual form |
| 16 | Furniture Puzzle Runtime | Crucible + Dungeons + ModelEngine | Instance-scoped furniture state becomes a validated room puzzle graph |
| 17 | Waystone Conquest Network | RPG + Dungeons + Crucible | Dungeon clears activate physical, contestable travel nodes |
| 18 | Enchantment Trials | Enchants + Dungeons + RPG | Room constraints alter the next bounded enchant offer or talent path |
| 19 | Spellbound Enchants | Enchants + RPG | Enchant triggers a learned spell through one cooldown/reagent transaction |
| 20 | Procedural Party-synergy Layout | Dungeons + MMOCore + RPG | Room connector weights adapt to role coverage and missing capabilities |
| 21 | Party Loot Contract | RPG + Dungeons + Enchants + Items | Per-run typed loot rules route rewards through an audit ledger |
| 22 | Living Strongholds | Crucible + Dungeons + RPG + ModelEngine | Persistent player structures instantiate as attackable evolving dungeons |
| 23 | Seasonal Affix Engine | Dungeons + Enchants + Mythic skills | Deterministic weekly encounter and loot affixes with preview and rollback |
| 24 | Accessibility Casting Layer | RPG + Crucible + Enchants + ModelEngine | Alternate input, high contrast, readable cooldown, and one-handed layouts |
| 25 | Audience-specific Phase Skins | ModelEngine + Profiles + MMOCore | Parties see different visual quest/boss phases on one authoritative entity |
| 26 | Root-motion Dungeon Traversal | ModelEngine + Dungeons | Server-validated animation drives vaulting, finishers, and traps |
| 27 | Living UI Familiar | ModelEngine + Profiles + MMOCore + RPG | Companion model becomes a quest/profile/progression navigator |
| 28 | Adaptive Model Detail Governor | ModelEngine | Per-viewer visual budgets preserve gameplay while reducing load |
| 29 | Spectral Replay Ghosts | ModelEngine + Dungeons | Privacy-safe transform streams replay prior runs as coaching ghosts |
| 30 | Mount Talent System | ModelEngine + MMOCore + RPG | Character progression unlocks versioned mount controllers and abilities |

## Blueprint 1: Adaptive Raid Director

### Player contract

A party receives an encounter tuned once at queue lock. The server shows a transparent difficulty band and never raises it during the run. Failure streaks may lower future pressure; reward ceilings remain admin-defined.

### API composition

| Need | Preferred boundary |
|---|---|
| queue/instance lifecycle | `MythicDungeonsService` plus queue/start/end/dispose events |
| class/level/party snapshot | MMOCore API/player aggregate or MythicRPG immutable session views |
| equipment score | MMOItems template/type/stat history through an adapter |
| enchant contribution | MythicEnchants query API |
| instance projection | Dungeon variables, difficulty, Mythic mechanics, and loot events |

### State

`RaidPlan(runId, rosterProfileIds, inputHash, powerBand, roleCoverage, failureBand, encounterBudget, rewardBudget, revision)` is addon-owned and immutable after instance creation.

### Sequence

1. Queue ready event locks roster and stable profile IDs.
2. Server-thread adapters read live progression/equipment; pure normalization may run async on copied values.
3. Deterministic scoring selects a plan inside configured minimum/maximum bounds.
4. Revalidate roster and create the dungeon instance.
5. Project plan values into difficulty, variables, mob override, and reward policy.
6. Journal one terminal result and update a bounded future-run signal.

### Failure policy

- missing optional input uses baseline, never a harsher inferred value;
- roster change invalidates the pre-instance plan;
- unknown service return in the reviewed Dungeons snapshot is confirmed through instance/event state;
- reward journal makes repeated end/dispose callbacks harmless.

### Validation

Golden scoring vectors, role edge cases, roster race, missing dependencies, exact-artifact consumer compile, restart between end and reward, and simultaneous queue load.

## Blueprint 2: Profile-bound Seasonal Relic Board

### Player contract

Each character has a separate seasonal board. Rollover rules explain what archives, carries, converts, or returns. A profile switch can never expose another character's relics.

### State

The addon repository owns `(accountUuid, profileUuid, seasonId, layoutVersion, revision, slots[])`. MMOInventory displays a projection; MMOItems/skills consume one derived bonus snapshot.

### Sequence

1. Register a `ProfileDataModule` and current layout schema.
2. Pending profile load reads and migrates stable relic IDs.
3. Unknown definitions or removed slots enter recovery escrow.
4. Populate the custom layout after migration succeeds.
5. Buffer equip changes and publish one new bonus revision.
6. Persist by compare-and-set revision; validate the profile module in `finally`.
7. Unload clears inventory/stat/model projections before the next profile applies.

### Failure policy

Timeout produces an empty degraded board plus staff diagnostic, not a stuck profile. Stale async writes lose by revision. Missing MMOItems preserves the record but disables item projection. Layout migration never silently deletes a relic.

### Validation

Two-character isolation, disconnect during pending load, old slot migration, duplicate equip events, season rollover, full recovery inventory, and restart while a write is pending.

## Blueprint 3: Dungeon Reward Escrow And Recovery

### Player contract

Rewards are visible at completion but become claimable only after the run reaches a final state. If the server stops, the player can recover the same reward once after restart.

### State machine

```text
PENDING -> COMMITTED -> CLAIMED
    |          |
    +-> VOID   +-> RECOVERY_REQUIRED -> CLAIMED
```

Each reward has run UUID, reward UUID, profile UUID, safe item/currency descriptor, schema version, transition sequence, and idempotency key.

### Sequence

1. Replace direct loot grant with an escrow descriptor during loot generation.
2. Commit when the authoritative dungeon outcome becomes final.
3. On clean disposal, claim through inventory, profile-aware mailbox/private drop, or economy adapter.
4. On startup, reconcile committed/unclaimed entries.
5. Append an audit fact for every transition.

### Failure policy

Storage outage blocks final delivery but never drops the descriptor. Full inventory uses recovery. Profile mismatch defers. Duplicate lifecycle callbacks see the existing transition. Economy/item grant and ledger commit use a compensating recovery state when no shared transaction exists.

### Validation

Terminate the server at every transition, emit duplicate end/dispose, switch profile, fill inventory, disable an optional provider, and reconcile after database retry.

## Blueprint 4: Reactive Anatomy Boss

### Player contract

Players can target readable limbs. A broken limb predictably removes or changes an attack, movement option, armor piece, or route. Accessibility mode exposes the same state without relying only on color/effects.

### State

`BossAnatomy` owns logical limb IDs, health, state, sequence, associated skill IDs, and room actions. Model bones and hitboxes are visual/interaction projections.

### Sequence

1. At encounter spawn, validate logical limbs against ModelEngine bone IDs.
2. Map sub-hitbox damage into one guarded limb transaction.
3. Publish a cancellable pre-break transition, commit health, then a post-break event.
4. Switch animation state, disable mapped Mythic skills, detach visuals, and update dungeon variables/doors.
5. Dispose hitbox mappings, tick tasks, callbacks, and models with the instance.

### Failure policy

A missing bone disables that limb mechanic, not the boss. Model unload cannot delete authoritative combat state. Duplicate damage is rejected by sequence. Unsupported rendering degrades to a normal entity hitbox and textual/audio cues.

### Validation

Bone-map lint, simultaneous lethal hits, model reload, instance disposal, low-effects mode, absent ModelEngine adapter, and performance under many viewers.

## Blueprint 5: Item Provenance Ledger

### Player/admin contract

High-value items have a traceable origin and revision history. The system detects impossible transitions but quarantines evidence instead of deleting an item automatically.

### State

The append-only ledger owns item UUID, revision, parent item UUIDs, template/type, profile UUID, event UUID, transition kind, station/run reference, safe property hash, and previous-entry hash. Item metadata stores only opaque UUID and revision.

### Sequence

1. Issue identity during an authorized build/craft/reward event.
2. Append parentage and origin context.
3. For reforge, upgrade, enchant, or soulbind, compare expected revision and append once.
4. At inventory/profile/server boundaries, reconcile metadata with the ledger.
5. Quarantine conflicts into a staff-visible recovery queue.

### Failure policy

High-value tiers may fail closed during ledger outage; ordinary items can be configured fail-open. Legacy items use an explicit adoption flow. Duplicate event UUIDs are idempotent. Stripped metadata is evidence, not an instruction to destroy inventory state.

### Validation

Clone simulation, concurrent upgrade, profile transfer, cross-server merge, legacy adoption, metadata stripping, ledger restore, key rotation, and staff reconciliation permissions.

## Blueprint Quality Gate

Before implementation, every blueprint must name exact plugin versions and queried symbols, authoritative state, lifecycle/thread context, idempotency model, optional-dependency behavior, persistence migration, teardown, and exact-artifact test plan. If one is absent, classify the design as a concept rather than build-ready.
