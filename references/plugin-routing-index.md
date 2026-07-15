# Plugin Routing Index

Choose the plugin that already owns the requested domain, then integrate through its strongest boundary.

| Domain | Primary plugin | Strongest reviewed boundaries |
|---|---|---|
| Item types, templates, stats, generation, crafting, upgrades, gems, sets | MMOItems | stat/type/template/crafting registries, builders, lifecycle events |
| Classes, skills, attributes, professions, quests, parties, guilds, XP, resources | MMOCore | `MMOCoreAPI`, loader SPI, registries, `PlayerData`, events |
| Custom equipment layout and slot restrictions | MMOInventory | inventory/restriction managers, provider/data models, equip/update events |
| Multiple character profiles and proxy handoff | MMOProfiles | Bukkit `ProfileProvider` service, profile modules, lifecycle events |
| Models, bones, animations, VFX, hitboxes, mounts, model screens | ModelEngine | `ModelEngineAPI`, model interfaces, behavior/animation registries, events |
| Mythic item mechanics, equipment skills, furniture, recipes | MythicCrucible | item/recipe registries, mechanics/conditions/targeters, Bukkit/Mythic events |
| Instanced dungeons, rooms, checkpoints, objectives, matchmaking | MythicDungeons | dungeon/session/instance managers, registries, lifecycle events |
| Enchant definitions, levels, triggers, mechanics | MythicEnchants | enchant registry/config loaders, Mythic skill hooks, enchant events |
| Mythic-centric RPG profiles, stats, classes, quests, storage | MythicRPG | managers/registries, player aggregate, storage providers, events |
| Config scripting, variables, stations, shops, auction, economy, multi-source items | CoreTools | script context/factories, variables/station events, item-source registration |

## Boundary Rules

- Prefer service/API/event/registry contracts over direct manager fields.
- When two plugins can own the same state, pick one authority and project derived state into the other.
- ModelEngine owns presentation geometry; combat/progression plugins own gameplay truth.
- Inventory contents are not automatically profile-safe; bind them to a profile lifecycle module or synchronized holder.
- CoreTools and Mythic skill systems are orchestration layers. Avoid making script context the durable source of truth.
- Use adapters for optional dependencies and return a clear disabled/degraded status when absent.

Aliases used in requests may omit pluralization: MythicDungeon maps to the catalog name `MythicDungeons`; MythicEnchant maps to `MythicEnchants`.
