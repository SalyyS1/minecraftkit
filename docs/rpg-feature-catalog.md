# RPG Feature Catalog

This is a capability map, not an assertion that every combination is already implemented. Query the exact symbol catalog before coding.

## Domain Matrix

| Domain | Primary owners | High-value primitives | New composition opportunities |
|---|---|---|---|
| Items and affixes | MMOItems, Crucible, Enchants, MMOInventory | types, templates, typed stats, modifiers, gems, sets, upgrades, enchant definitions, custom slots | evolving relics, provenance, seasonal equipment, market-driven affixes |
| Progression | MMOCore, MythicRPG | classes/archetypes, skill trees/talents, XP curves/sources, points, resources, spells | research trees, account legacy, adaptive encounter input |
| Profiles | MMOProfiles, MythicRPG, CoreTools | profile modules, snapshots, sessions, proxy transfer, variables | expedition profiles, seasonal boards, cross-server reward merge |
| Dungeons | MythicDungeons | instances, layouts, rooms, queues, parties, triggers, functions, conditions, rewards | raid direction, party-aware layouts, affixes, reward escrow |
| Models | ModelEngine | modeled entities, bones, animation state, behaviors, hitboxes, VFX, mounts, LOD | boss anatomy, equipment rigs, replay ghosts, accessible rendering |
| Furniture/world | Crucible, Dungeons, ModelEngine | furniture API/events, blocks, room doors/connectors, hitboxes, generators | spatial puzzles, strongholds, crafting altars, physical waystones |
| Crafting/stations | MMOItems, Crucible, CoreTools | recipe grammar, craft conditions/triggers, station events, multi-source items | research, rituals, provenance-aware crafting, economy balancing |
| Social | MMOCore, MythicRPG, Dungeons | party/guild providers, party DTOs, friends, shared XP/loot | synergy relics, loot contracts, group strongholds |
| Automation | CoreTools and Mythic family | context/queue, mechanics, conditions, targeters, placeholders, graph nodes | admin-authored orchestration over addon-owned state |
| Persistence/recovery | MMOProfiles, MythicRPG, CoreTools, ModelEngine | repositories, SQL migrations, profile modules, DataIO, variables | escrow, audit ledger, recovery hunts, replay snapshots |
| UI/resource packs | Crucible, ModelEngine, MMOCore, MythicRPG, CoreTools | pack pipeline, lore/tooltips/fonts, widgets, HUD, bindings | accessible casting, contextual HUD, living familiar, item evolution |
| Operations | all | scheduler adapters, tick phases, reload events, caches, diagnostics | performance governor, health panel, telemetry advisor |

## Item Feature Building Blocks

### MMOItems

- item type and template registries;
- stat parsing, validation, numeric formulas, random spread, modifiers, and history;
- builder pipeline before Bukkit `ItemStack` materialization;
- crafting ingredient/output/condition/trigger extension;
- gems, sets, tiers, upgrades, repair/reforge/durability lifecycle;
- external inventory supplier for equipment projection.

### MythicCrucible

- Mythic item traits and generated metadata;
- furniture, blocks, armor, equippables, augments, sets, recipes, bags, durability;
- lore/tooltips/fonts/sounds/paintings;
- item/resource-pack/world generation;
- furniture placement, rotation, removal, and tracking events.

### MythicEnchants

- custom/native enchant definitions and tags;
- builder fields for slots, filters, level ranges, conflicts, costs, options, and trigger skills;
- custom enchant-table offers, reagents, anvil and grindstone behavior;
- apply/remove/prepare/skill-trigger events;
- first-class addon context.

### MMOInventory

- data-defined inventories and slots;
- registration-time restriction grammar;
- compact/live provider representations;
- cancellable equip and interaction events;
- legacy RPGInventory compatibility surface.

## Character And Social Building Blocks

### MMOCore

- character class, profession, attribute, skill, resource, quest, and waypoint state;
- registered experience sources, objectives, triggers, drops, blocks, and conditions;
- party/guild/quest adapters;
- skill trees and scaling formulas;
- extensive pre/post transition events.

### MythicRPG

- active profile and archetype level/progress;
- talent and point mutations;
- spell metadata, learning, casting, binding, cooldown, resource, and quickcaster;
- waystone state/discovery/teleport;
- party, friend, shared XP/loot, and economy views;
- immutable DTO-heavy explicit API.

### MMOProfiles

- multiple character snapshots;
- plugin-owned data modules coordinated by a pending barrier;
- profile selection, unload, autosave, and proxy events;
- profile placeholder processing;
- cross-server request flow.

## Encounter Building Blocks

### MythicDungeons

- classic, continuous, and procedural instance types;
- weighted room connectors and layout bounds;
- queues, ready checks, internal/external party providers;
- trigger-condition-function graph with sequence, random, repeat, delay, and branching;
- difficulty, rewards, cooldowns, checkpoints, hotbar, spectators, moving blocks;
- dungeon, room, player, loot, trigger, and party event families.

### ModelEngine

- entity/model aggregate and blueprint registry;
- named bones and typed bone behaviors;
- priority and state-machine animation handlers;
- dynamic/sub-hitboxes and interaction tracking;
- mount controllers and leash/mount managers;
- viewer-specific glow, visibility, light, culling, and LOD;
- screen/widget and VFX systems;
- phased tick tasks and model lifecycle callbacks.

## Automation Building Blocks

### CoreTools

- event-normalized script context;
- factory conditions, mechanics, entity targeters, and location targeters;
- queue execution and return values;
- variables, stations, shop, auction, economy, and private drops;
- item creation across multiple providers;
- profile modules and MMOItems custom-stat attribution.

### Mythic DSL Surfaces

- Crucible: item/equipment/furniture/durability/upgrade mechanics and conditions;
- Dungeons: native graph plus Mythic mechanics, conditions, targeters, and placeholders;
- Enchants: 39 trigger families, mechanics, conditions, and targeting helpers;
- RPG: progression, casting, party, waystone mechanics, conditions, and targeters.

## Composition Rules

1. Select one authoritative owner per state field.
2. Carry stable IDs across plugin boundaries; resolve live objects at the edge.
3. Perform authorization before item/economy/reward side effects.
4. Persist one-time outcomes through an idempotent journal.
5. Coalesce inventory, stat, model, lore, and HUD projections.
6. Return Bukkit/Paper mutations to the owning scheduler.
7. Keep visuals and UI degradable.
8. Treat profile load/unload and dungeon dispose as hard lifecycle boundaries.
9. Test exact artifacts, especially snapshot/NMS/native-registry paths.
10. Label a new composition `ORIGINAL_DESIGN`; do not imply vendor ownership.
