"""Zero-dependency JSON-RPC 2.0 stdio MCP server for Salyyy Minecraft Kit."""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, BinaryIO

SCRIPTS_DIR = Path(__file__).resolve().parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from catalog_io import strict_json_file  # noqa: E402
import query_api  # noqa: E402
import query_sources  # noqa: E402


PROTOCOL_VERSION = "2025-11-25"
SUPPORTED_PROTOCOL_VERSIONS = frozenset({
    "2025-11-25",
    "2025-06-18",
    "2025-03-26",
    "2024-11-05",
})

PARSE_ERROR = -32700
INVALID_REQUEST = -32600
METHOD_NOT_FOUND = -32601
INVALID_PARAMS = -32602
INTERNAL_ERROR = -32603

MAX_MESSAGE_BYTES = 16 * 1024 * 1024

DOMAIN_SYNONYM_HINTS: dict[str, tuple[str, ...]] = {
    "build": (
        "gradle", "gradlew", "maven", "shadowjar", "relocate", "relocation", "hikari",
        "sqlite", "mysql", "postgres", "mariadb", "semver", "github actions", "jar",
    ),
    "client": (
        "hud", "actionbar", "bossbar", "scoreboard", "camera", "bedrock", "floodgate",
        "text display", "item display", "block display",
    ),
    "core": (
        "folia", "region scheduler", "globalregionscheduler", "entityscheduler",
        "asyncscheduler", "teleportasync", "bukkitrunnable", "bukkitscheduler",
        "tick", "server", "proxy", "bungeecord", "waterfall", "server.properties",
        "paper-global.yml", "simulation-distance", "view-distance",
    ),
    "dialog": (
        "dialog", "modal", "form", "custom click", "click action", "prompt",
    ),
    "model": (
        "bbmodel", "model engine", "activemodel", "blueprint", "keyframe", "emote", "hitbox",
    ),
    "nms": (
        "craftbukkit", "net.minecraft", "serverplayer", "serverlevel", "mojang mappings",
        "reobf", "mixin", "access widener", "byte buddy",
    ),
    "pack": (
        "pack_format", "glyph", "negative space", "unicode", "blockstate", "sounds.json",
        "lang", "custom_model_data", "item_model", "datapack", "resourcepack", "predicate",
        "tooltip_display", "equippable", "consumable", "blocks_attacks",
    ),
    "protocol": (
        "netty", "bytebuf", "friendlybytebuf", "registryfriendlybytebuf", "streamcodec",
        "channel", "play state", "configuration state", "handshake", "packetlistener",
        "network-compression-threshold", "eventloopthreads", "netty-threads",
    ),
    "rpg": (
        "coretools", "mmoinventory", "mmoprofiles", "mythiccrucible", "mythicdungeons",
        "mythicenchants", "mythicrpg", "mana", "stamina", "cooldown", "attribute", "party",
        "guild", "boss", "profession", "crafting",
    ),
    "shader": (
        "fsh", "vsh", "post-processing", "post shader", "rendertype", "uniform", "framebuffer",
        "optifine",
    ),
}


@dataclass(frozen=True)
class ToolOutcome:
    text: str
    is_error: bool = False


def _strict_loads(raw: str) -> Any:
    return json.loads(
        raw,
        parse_constant=lambda value: (_ for _ in ()).throw(
            ValueError(f"Non-standard JSON constant: {value}")
        ),
    )


def _compact_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, allow_nan=False, separators=(",", ":"))


def _pretty_json(value: Any) -> str:
    return json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False)


def _normalize_terms(raw: Any, field_name: str = "terms") -> list[str]:
    if raw is None:
        return []
    if isinstance(raw, str):
        return [part for part in raw.strip().split() if part]
    if isinstance(raw, list) and all(isinstance(item, str) for item in raw):
        out: list[str] = []
        for item in raw:
            stripped = item.strip()
            if stripped:
                out.append(stripped)
        return out
    raise ValueError(f"'{field_name}' must be a string or an array of strings.")


def _parse_bounded_int(raw: Any, *, field: str, default: int, minimum: int, maximum: int) -> int:
    if raw is None:
        return default
    if isinstance(raw, bool) or not isinstance(raw, int):
        raise ValueError(f"'{field}' must be an integer between {minimum} and {maximum}.")
    if not minimum <= raw <= maximum:
        raise ValueError(f"'{field}' must be between {minimum} and {maximum}; got {raw}.")
    return raw


class CatalogStore:
    """Lazy-loaded, read-only in-memory cache over MinecraftKit's offline JSON catalogs."""

    def __init__(self, root: Path) -> None:
        self.root = root.resolve()
        self._cache: dict[str, Any] = {}

    def _load_json(self, relative: str) -> Any:
        if relative not in self._cache:
            self._cache[relative] = strict_json_file(self.root / relative)
        return self._cache[relative]

    def kit_version(self) -> str:
        manifest_path = self.root / "manifest.json"
        if manifest_path.is_file():
            manifest = self._load_json("manifest.json")
            version = manifest.get("version") if isinstance(manifest, dict) else None
            if isinstance(version, str) and version:
                return version
        return "2.7.0"

    def api_index(self) -> dict[str, Any]:
        return self._load_json("data/api-index.json")

    def class_graph(self) -> dict[str, Any]:
        key = "__class_graph__"
        if key not in self._cache:
            by_fqcn_lower: dict[str, list[dict[str, Any]]] = {}
            by_simple_lower: dict[str, list[dict[str, Any]]] = {}
            subtypes: dict[str, list[dict[str, str]]] = {}
            all_classes: list[dict[str, Any]] = []

            for plugin in self.api_index().get("plugins", []):
                plugin_name = str(plugin.get("name", ""))
                for cls in plugin.get("classes", []):
                    fqcn = str(cls.get("name", ""))
                    simple = str(cls.get("simple_name") or fqcn.rsplit(".", 1)[-1])
                    origin = str(cls.get("origin", "plugin-owned"))
                    enriched = cls if cls.get("plugin") else {**cls, "plugin": plugin_name}
                    all_classes.append(enriched)
                    by_fqcn_lower.setdefault(fqcn.casefold(), []).append(enriched)
                    by_simple_lower.setdefault(simple.casefold(), []).append(enriched)

                    parents: list[str] = []
                    sup = cls.get("super")
                    if isinstance(sup, str) and sup and sup != "java.lang.Object":
                        parents.append(sup.replace("/", "."))
                    for iface in cls.get("interfaces") or ():
                        if isinstance(iface, str) and iface:
                            parents.append(iface.replace("/", "."))
                    for parent in parents:
                        subtypes.setdefault(parent.casefold(), []).append({
                            "plugin": plugin_name,
                            "name": fqcn,
                            "kind": str(cls.get("kind", "class")),
                            "origin": origin,
                        })

            self._cache[key] = {
                "all_classes": all_classes,
                "by_fqcn_lower": by_fqcn_lower,
                "by_simple_lower": by_simple_lower,
                "subtypes": subtypes,
            }
        return self._cache[key]

    def reference_files(self) -> tuple[Path, ...]:
        key = "__reference_files__"
        if key not in self._cache:
            ref_dir = self.root / "references"
            if ref_dir.is_dir():
                files = sorted(
                    p.resolve()
                    for p in ref_dir.glob("*.md")
                    if p.is_file() and not p.is_symlink()
                )
            else:
                files = []
            self._cache[key] = tuple(files)
        return self._cache[key]

    def api_records(self) -> tuple[dict[str, Any], ...]:
        key = "__flattened_api_records__"
        if key not in self._cache:
            index = self._load_json("data/api-index.json")
            self._cache[key] = tuple(query_api.iter_records(index))
        return self._cache[key]

    def coverage(self) -> dict[str, Any]:
        return self._load_json("data/api-coverage.json")

    def plugin_insights(self) -> dict[str, Any]:
        return self._load_json("data/plugin-insights.json")

    def upstream_sources(self) -> list[dict[str, Any]]:
        key = "__upstream_sources__"
        if key not in self._cache:
            catalog_path = self.root / "data" / "github-source-catalog.json"
            snapshot_path = self.root / "data" / "github-source-snapshot.json"
            self._cache[key] = query_sources.load_records(catalog_path, snapshot_path)
        return self._cache[key]

    def version_catalog(self) -> dict[str, Any]:
        return self._load_json("data/minecraft-version-catalog.json")

    def release_capabilities(self) -> dict[str, Any]:
        return self._load_json("data/minecraft-release-capabilities.json")

    def domain_catalog(self) -> dict[str, Any]:
        return self._load_json("data/minecraft-domain-catalog.json")

    def extract_route_workflow(self, skill_directory: str) -> list[str]:
        candidates = (
            self.root / "skill-wrappers" / skill_directory / "SKILL.md",
            self.root.parent / skill_directory / "SKILL.md",
        )
        for candidate in candidates:
            if not candidate.is_file():
                continue
            lines = candidate.read_text(encoding="utf-8").splitlines()
            steps: list[str] = []
            in_workflow = False
            for line in lines:
                stripped = line.strip()
                if stripped.startswith("## "):
                    in_workflow = stripped.lower() == "## workflow"
                    continue
                if in_workflow and re.match(r"^\d+\.\s+", stripped):
                    steps.append(re.sub(r"^\d+\.\s+", "", stripped))
            if steps:
                return steps
        return []


TOOL_DEFINITIONS: tuple[dict[str, Any], ...] = (
    {
        "name": "mc_search_api",
        "title": "Search Minecraft & RPG Plugin APIs",
        "description": (
            "Search 41,800+ offline classes, interfaces, enums, methods, fields, and constructors "
            "across indexed Minecraft RPG and utility plugins (ModelEngine, MMOItems, MMOCore, "
            "MMOInventory, MMOProfiles, MythicCrucible, MythicDungeons, MythicEnchants, MythicRPG, CoreTools)."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "terms": {
                    "oneOf": [
                        {"type": "string"},
                        {"type": "array", "items": {"type": "string"}},
                    ],
                    "description": "Case-insensitive search term(s); every term must match.",
                },
                "plugin": {
                    "type": "string",
                    "description": "Optional plugin filter (for example: ModelEngine, MMOItems, MMOCore).",
                },
                "kind": {
                    "type": "string",
                    "enum": ["class", "interface", "enum", "annotation", "record", "field", "method", "constructor"],
                    "description": "Optional symbol kind filter.",
                },
                "origin": {
                    "type": "string",
                    "enum": ["plugin-owned", "bundled-third-party", "all"],
                    "description": "Symbol ownership filter (defaults to plugin-owned).",
                },
                "limit": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 200,
                    "description": "Maximum records to return (1..200, default 25).",
                },
            },
            "additionalProperties": False,
        },
        "annotations": {"readOnlyHint": True},
    },
    {
        "name": "mc_list_plugins",
        "title": "List Indexed Plugins & Architecture Insights",
        "description": (
            "List the 10 indexed Minecraft RPG plugins with exact versions, bytecode class-file "
            "targets, type/member counts, API boundaries, architectural patterns, and integration risks."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "plugin": {
                    "type": "string",
                    "description": "Optional plugin name or ID to inspect a single plugin.",
                },
                "include_insights": {
                    "type": "boolean",
                    "description": "Include architectural summary, API boundaries, and risks (default true).",
                },
            },
            "additionalProperties": False,
        },
        "annotations": {"readOnlyHint": True},
    },
    {
        "name": "mc_search_sources",
        "title": "Search Curated Upstream Minecraft GitHub Sources",
        "description": (
            "Search 103 reviewed upstream Minecraft, Paper, Folia, Fabric, NeoForge, Velocity, "
            "protocol, shader, model, and pack GitHub repositories with pinned commit SHAs and licenses."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "terms": {
                    "oneOf": [
                        {"type": "string"},
                        {"type": "array", "items": {"type": "string"}},
                    ],
                    "description": "Case-insensitive search term(s) matched against repository, domain, and rationale.",
                },
                "domain": {
                    "type": "string",
                    "enum": ["build", "client", "core", "dialog", "model", "nms", "pack", "protocol", "rpg", "shader"],
                    "description": "Optional mc:* domain filter.",
                },
                "priority": {
                    "type": "string",
                    "enum": ["P0", "P1", "P2"],
                    "description": "Optional source priority tier.",
                },
                "policy": {
                    "type": "string",
                    "enum": ["derive", "index", "link-only", "metadata-only"],
                    "description": "Optional catalog ingestion policy filter.",
                },
                "include_archived": {
                    "type": "boolean",
                    "description": "Include archived GitHub repositories (default false).",
                },
                "limit": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 200,
                    "description": "Maximum sources to return (1..200, default 20).",
                },
            },
            "additionalProperties": False,
        },
        "annotations": {"readOnlyHint": True},
    },
    {
        "name": "mc_version_capabilities",
        "title": "Query Minecraft Version & Protocol/Pack Capabilities",
        "description": (
            "Query Mojang version history (901 releases and snapshots), Java runtime requirements, "
            "and profiled protocol numbers, resource-pack formats, data-pack formats, and shader/dialog counts."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "version": {
                    "type": "string",
                    "description": "Specific version ID (for example: '26.2', '1.21.4', 'latest', or 'latest-snapshot').",
                },
                "type": {
                    "type": "string",
                    "enum": ["release", "snapshot", "old_beta", "old_alpha"],
                    "description": "Optional version type filter when listing recent versions.",
                },
                "limit": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 100,
                    "description": "Maximum recent versions to list when 'version' is omitted (default 15).",
                },
            },
            "additionalProperties": False,
        },
        "annotations": {"readOnlyHint": True},
    },
    {
        "name": "mc_route_skill",
        "title": "Route Task to /mc:* Engineering Skill & Checklist",
        "description": (
            "Recommend the primary and secondary /mc:* engineering routes, reference handbooks, "
            "and verification checklist for a Minecraft development task."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "task": {
                    "type": "string",
                    "description": "Natural-language description of the Minecraft engineering task.",
                },
                "include_checklist": {
                    "type": "boolean",
                    "description": "Include concrete workflow and contract checklist items (default true).",
                },
            },
            "required": ["task"],
            "additionalProperties": False,
        },
        "annotations": {"readOnlyHint": True},
    },
    {
        "name": "mc_folia_migration_advisor",
        "title": "Folia Region-Threading Migration Advisor",
        "description": (
            "Audit a Java/Kotlin plugin snippet or Bukkit/Paper API symbol for Folia "
            "regionized multithreading incompatibilities and return exact EntityScheduler, "
            "RegionScheduler, GlobalRegionScheduler, AsyncScheduler, and teleportAsync replacements."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "code_or_symbol": {
                    "type": "string",
                    "description": "Java/Kotlin code snippet or Bukkit/Paper API class/method name to audit for Folia safety.",
                },
            },
            "required": ["code_or_symbol"],
            "additionalProperties": False,
        },
        "annotations": {"readOnlyHint": True},
    },
    {
        "name": "mc_diagnose_server_log",
        "title": "Diagnose Paper/Folia Server Crash & Watchdog Logs",
        "description": (
            "Analyze Minecraft Paper, Folia, Purpur, or Velocity console logs and stack traces "
            "to pinpoint off-region thread violations, Java classfile version mismatches, "
            "paper-plugin.yml classloader/shading conflicts, and tick-thread stalls."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "log_text": {
                    "type": "string",
                    "description": "Server log output, watchdog dump, or Java exception stack trace.",
                },
            },
            "required": ["log_text"],
            "additionalProperties": False,
        },
        "annotations": {"readOnlyHint": True},
    },
    {
        "name": "mc_inspect_type",
        "title": "Inspect Indexed Plugin Class Hierarchy & Bytecode Contract",
        "description": (
            "Inspect the complete bytecode contract of an indexed Minecraft RPG plugin class, "
            "interface, enum, or record, returning its superclass, implemented interfaces, "
            "indexed subtypes, constructors, methods, fields, and minimum Java runtime."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "type_name": {
                    "type": "string",
                    "description": "Fully-qualified class name (e.g. 'net.Indyuce.mmoitems.MMOItems'), 'Plugin:FQCN', or simple name (e.g. 'ActiveModel').",
                },
                "plugin": {
                    "type": "string",
                    "description": "Optional plugin filter when disambiguating simple type names.",
                },
                "member_filter": {
                    "type": "string",
                    "description": "Optional case-insensitive substring filter applied to constructor, method, and field signatures.",
                },
                "public_only": {
                    "type": "boolean",
                    "description": "Include only public and protected members (default true).",
                },
                "include_synthetic": {
                    "type": "boolean",
                    "description": "Include compiler-generated synthetic or bridge members (default false).",
                },
                "member_limit": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 500,
                    "description": "Maximum members returned per category (1..500, default 100).",
                },
            },
            "required": ["type_name"],
            "additionalProperties": False,
        },
        "annotations": {"readOnlyHint": True},
    },
    {
        "name": "mc_audit_gradle_build",
        "title": "Audit Minecraft Gradle Build & Plugin Descriptor",
        "description": (
            "Audit a Gradle build script (build.gradle.kts / build.gradle) and optional "
            "paper-plugin.yml or plugin.yml descriptor for accidental server/plugin API bundling, "
            "un-relocated shadowJar dependencies, Paperweight mapping era mismatches, Java toolchain "
            "incompatibilities, and isolated classloader join-classpath hazards."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "build_script": {
                    "type": "string",
                    "description": "Contents of build.gradle.kts or build.gradle.",
                },
                "descriptor_yaml": {
                    "type": "string",
                    "description": "Optional contents of paper-plugin.yml or plugin.yml.",
                },
                "target_mc_version": {
                    "type": "string",
                    "description": "Optional target Minecraft version (e.g. '1.21.4' or '26.2').",
                },
            },
            "required": ["build_script"],
            "additionalProperties": False,
        },
        "annotations": {"readOnlyHint": True},
    },
    {
        "name": "mc_audit_paper_plugin_yml",
        "title": "Audit Paper Plugin Descriptor & Dependency Graph",
        "description": (
            "Validate paper-plugin.yml (and optional dual plugin.yml) across Paper 1.19 through 26.3+ "
            "for unquoted YAML float truncation (e.g. 1.20 parsed as 1.2), illegal legacy plugin.yml root keys "
            "(commands, depend, softdepend, loadbefore, libraries), bootstrapper/loader/main class collisions, "
            "bootstrap vs server dependency graph ordering conflicts, isolated ConfiguredPluginClassLoader "
            "join-classpath hazards, and Folia region-threading declarations."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "paper_plugin_yaml": {
                    "type": "string",
                    "description": "Contents of paper-plugin.yml.",
                },
                "legacy_plugin_yaml": {
                    "type": "string",
                    "description": "Optional companion plugin.yml contents when shipping dual descriptors.",
                },
                "require_folia": {
                    "type": "boolean",
                    "description": "Require folia-supported: true for Folia deployments (default false).",
                },
            },
            "required": ["paper_plugin_yaml"],
            "additionalProperties": False,
        },
        "annotations": {"readOnlyHint": True},
    },
    {
        "name": "mc_generate_pack_overlay",
        "title": "Generate Multi-Version pack.mcmeta & Overlays Manifest",
        "description": (
            "Generate a client- and server-validated pack.mcmeta JSON and overlays.entries layout for "
            "Minecraft resource packs and data packs spanning 1.20.1 through 26.3+ (enforcing pre-minor "
            "supported_formats clamping at 64/81, 1.21.9+ and 26.x min_format/max_format [major, minor] "
            "tuples, OverlayMetadataSection directory naming rules, and optional breaking-epoch splits)."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "pack_type": {
                    "type": "string",
                    "enum": ["resource", "data"],
                    "description": "Pack kind: 'resource' (client assets) or 'data' (server data pack). Defaults to 'resource'.",
                },
                "min_version": {
                    "type": "string",
                    "description": "Minimum supported Minecraft release or pack format (e.g. '1.20.1', '1.21.4', '26.2', '88.0').",
                },
                "max_version": {
                    "type": "string",
                    "description": "Maximum supported Minecraft release or pack format (defaults to min_version; e.g. '26.2', '26.3', '97.1').",
                },
                "description": {
                    "type": "string",
                    "description": "Pack description string written into pack.description.",
                },
                "overlays": {
                    "type": "array",
                    "description": "Optional explicit overlay layers ordered from lowest priority to highest priority.",
                    "items": {
                        "type": "object",
                        "properties": {
                            "directory": {"type": "string"},
                            "min_version": {"type": "string"},
                            "max_version": {"type": "string"},
                        },
                        "required": ["directory", "min_version"],
                        "additionalProperties": False,
                    },
                },
                "auto_split_epochs": {
                    "type": "boolean",
                    "description": "Automatically emit recommended overlay entries at breaking vanilla pack-format boundaries when 'overlays' is omitted (default false).",
                },
            },
            "required": ["min_version"],
            "additionalProperties": False,
        },
        "annotations": {"readOnlyHint": True},
    },
    {
        "name": "mc_audit_server_properties",
        "title": "Audit server.properties, Netty Threads & Packet Compression",
        "description": (
            "Audit Minecraft server.properties alongside optional config/paper-global.yml, spigot.yml, "
            "and JVM flags for network-compression-threshold CPU/bandwidth hazards, Velocity/BungeeCord "
            "forwarding & online-mode authentication mismatches, Netty EventLoop thread starvation or "
            "oversubscription, quadratic view/simulation-distance chunk budgets, RCON plaintext exposure, "
            "resource-pack SHA-1/UUID contracts, Paper 26.3 schema drift, and JVM GC flags."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "server_properties": {
                    "type": "string",
                    "description": "Contents of server.properties.",
                },
                "paper_global_yaml": {
                    "type": "string",
                    "description": "Optional contents of config/paper-global.yml.",
                },
                "spigot_yaml": {
                    "type": "string",
                    "description": "Optional contents of spigot.yml.",
                },
                "jvm_args": {
                    "type": "string",
                    "description": "Optional JVM startup flags (e.g. '-Xms8G -Xmx8G -Dio.netty.eventLoopThreads=8').",
                },
                "behind_proxy": {
                    "type": "string",
                    "enum": ["none", "velocity", "bungeecord"],
                    "description": "Proxy topology in front of this backend server (default 'none').",
                },
                "expected_players": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 5000,
                    "description": "Expected peak concurrent players for Netty, bandwidth, and chunk-budget sizing (default 50).",
                },
                "cpu_cores": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 512,
                    "description": "Available host vCPUs/hardware threads for Netty and Moonrise worker sizing (default 4).",
                },
            },
            "required": ["server_properties"],
            "additionalProperties": False,
        },
        "annotations": {"readOnlyHint": True},
    },
    {
        "name": "mc_validate_item_components",
        "title": "Validate Paper 1.20.5-26.3+ Item Data Components & Client Item Definitions",
        "description": (
            "Validate Minecraft and Paper 1.20.5 through 26.3+ structured item data components, component "
            "patches, and optional client assets/<namespace>/items/<id>.json definitions. Detects legacy pre-1.20.5 "
            "NBT tags, 1.21.4+ typed custom_model_data channel mismatches, 1.21.5+/26.3 tooltip_display vs removed "
            "show_in_tooltip fields, food/consumable/use_remainder splits, equippable.asset_id renames, "
            "max_damage + max_stack_size mutual exclusion, JSON-escaped text strings, and out-of-bounds client "
            "custom_model_data selector indices."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "payload": {
                    "oneOf": [
                        {"type": "string"},
                        {"type": "object"},
                    ],
                    "description": "JSON string or object representing an item stack ({id, count, components}), a direct component map/patch, or a client items/<id>.json definition.",
                },
                "target_version": {
                    "type": "string",
                    "description": "Target Minecraft/Paper version (e.g. '26.3', '26.2', '1.21.5', '1.21.4', '1.20.5'; default '26.3').",
                },
                "client_item_definition": {
                    "oneOf": [
                        {"type": "string"},
                        {"type": "object"},
                    ],
                    "description": "Optional companion client item model definition (assets/<namespace>/items/<id>.json) to cross-check item_model and custom_model_data channel indices.",
                },
            },
            "required": ["payload"],
            "additionalProperties": False,
        },
        "annotations": {"readOnlyHint": True},
    },
    {
        "name": "mc_diagnose_crash_report",
        "title": "Diagnose Minecraft Server & Client Crash Reports",
        "description": (
            "Parse and triage Minecraft server and client crash reports (Vanilla, Paper, Folia, Fabric, "
            "Forge, NeoForge). Analyzes crash headers, thread stacks, ticking entities (coordinates, NBT, "
            "type), ticking block entities (tile location, container state), mixin application conflicts, "
            "classloader NoSuchMethodError/NoClassDefFoundError linkage faults, JVM OOM/Metaspace exhaustion, "
            "and corrupted chunk I/O boundaries. Returns structured root cause categorization, offending "
            "mod/plugin attribution, stack trace origin, remediation steps, and optional OASIS SARIF v2.1.0 output."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "crash_report": {
                    "type": "string",
                    "description": "Full text of the crash report (e.g. crash-YYYY-MM-DD_HH.MM.SS-server.txt) or stack trace snippet.",
                },
                "server_flavor": {
                    "type": "string",
                    "enum": ["auto", "paper", "folia", "fabric", "neoforge", "forge", "vanilla"],
                    "description": "Server or client platform flavor (default 'auto').",
                },
                "sarif": {
                    "type": "boolean",
                    "description": "Whether to include an OASIS SARIF v2.1.0 report in the response (default false).",
                },
            },
            "required": ["crash_report"],
            "additionalProperties": False,
        },
        "annotations": {"readOnlyHint": True},
    },
    {
        "name": "mc_audit_datapack",
        "title": "Audit Minecraft 1.20.5-26.3+ Datapack Structure & Components",
        "description": (
            "Audit Minecraft 1.20.5 through 26.3+ datapacks for pack.mcmeta format compliance (supporting single "
            "int or [min, max] range format), recipe item data components syntax (replacing legacy result count/item "
            "pairs with components patches), predicate & loot table damage type / item sub-predicate migrations, "
            "cyclical tag references, namespace naming collisions, and function command syntax."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "pack_mcmeta": {
                    "oneOf": [
                        {"type": "string"},
                        {"type": "object"},
                    ],
                    "description": "Content of pack.mcmeta as JSON string or object.",
                },
                "files": {
                    "type": "object",
                    "description": "Optional mapping of virtual datapack file paths to their string contents (e.g. {'data/custom/recipe/magic_wand.json': '...'}).",
                    "additionalProperties": {"type": "string"},
                },
                "target_version": {
                    "type": "string",
                    "description": "Target Minecraft version (e.g. '26.3', '1.21.4', '1.20.5'; default '26.3').",
                },
            },
            "required": ["pack_mcmeta"],
            "additionalProperties": False,
        },
        "annotations": {"readOnlyHint": True},
    },
    {
        "name": "mc_audit_spark_flamegraph",
        "title": "Audit Spark & JFR Flamegraph Stacks and Async Pool Starvation",
        "description": (
            "Parse and classify Minecraft Spark and JFR CPU/wall-clock profiles in either collapsed "
            "flamegraph format ('frame1;frame2;leaf 120') or indented call-tree format ('|-- 42.5% pkg.Class.method()'). "
            "Computes deduplicated inclusive and exclusive (self) frame weights, demangles JDK 21+ hidden lambdas, "
            "attributes hotspots back to initiating plugins (including indexed RPG plugins such as ModelEngine, "
            "MMOItems, MMOCore, and MythicDungeons), classifies 7 tick bottleneck categories (sync chunk I/O, "
            "sync JDBC/HTTP I/O, entity AI/collision, hopper/block-entity ticks, Netty codecs, worldgen structure "
            "search, and plugin reflection), and distinguishes genuine async worker pool starvation (HikariCP pool "
            "exhaustion, socket stalls, lock convoys, nested future deadlocks) from benign idle worker parking. "
            "Supports optional OASIS SARIF v2.1.0 output."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "profile": {
                    "type": "string",
                    "description": "Collapsed flamegraph stack lines ('frame1;frame2 45') or indented Spark/JFR call-tree text.",
                },
                "hotspot_threshold_pct": {
                    "type": "number",
                    "minimum": 0.1,
                    "maximum": 100.0,
                    "description": "Minimum inclusive or self sample percentage required to report a hotspot (default 5.0).",
                },
                "sarif": {
                    "type": "boolean",
                    "description": "Whether to include an OASIS SARIF v2.1.0 report under sarif_report (default false).",
                },
            },
            "required": ["profile"],
            "additionalProperties": False,
        },
        "annotations": {"readOnlyHint": True},
    },
    {
        "name": "mc_analyze_folia_scheduler_trace",
        "title": "Verify 4-Domain Folia Scheduler Thread Affinity & Trace Safety",
        "description": (
            "Verify Folia regionized multithreading contracts across single stack traces, multi-thread JVM dumps, "
            "or scheduled execution traces. Classifies each trace into Folia's 4 scheduler domains (REGION, ENTITY, "
            "GLOBAL, ASYNC) plus NETTY network I/O and evaluates the state-ownership matrix to catch off-region "
            "world/entity/inventory mutations (FOLIA-TRC-001), GlobalRegionScheduler chunk/block/entity escapes "
            "(FOLIA-TRC-002), cross-region player/entity iteration and synchronous teleport calls (FOLIA-TRC-003), "
            "Netty packet-thread world access (FOLIA-TRC-004), blocking CompletableFuture.join/get deadlocks on "
            "tick threads (FOLIA-TRC-005), legacy BukkitScheduler calls (FOLIA-TRC-006), and missing EntityScheduler "
            "retired callbacks (FOLIA-TRC-007). Returns remediation snippets and optional OASIS SARIF v2.1.0 output."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "trace": {
                    "type": "string",
                    "description": "Stack trace, multi-thread JVM dump, or Folia TickThread crash snippet.",
                },
                "declared_domain": {
                    "type": "string",
                    "enum": ["auto", "region", "entity", "global", "async", "netty"],
                    "description": "Explicit scheduler domain override when analyzing an isolated snippet without thread headers (default 'auto').",
                },
                "sarif": {
                    "type": "boolean",
                    "description": "Whether to include an OASIS SARIF v2.1.0 report under sarif_report (default false).",
                },
            },
            "required": ["trace"],
            "additionalProperties": False,
        },
        "annotations": {"readOnlyHint": True},
    },
)


def _strip_gradle_comments(script: str) -> str:
    without_block = re.sub(r"/\*.*?\*/", "", script, flags=re.DOTALL)
    out_lines: list[str] = []
    for line in without_block.splitlines():
        # Strip // comments that are not preceded by ':' (preserving https:// URLs)
        cleaned = re.sub(r"(?<!:)//.*$", "", line)
        out_lines.append(cleaned)
    return "\n".join(out_lines)


def _parse_mc_version_tuple(raw: str) -> tuple[int, int, int] | None:
    match = re.search(r"(\d+)\.(\d+)(?:\.(\d+))?", raw.strip())
    if not match:
        return None
    major = int(match.group(1))
    minor = int(match.group(2))
    patch = int(match.group(3) or 0)
    return (major, minor, patch)


def _required_java_for_mc(mc_tuple: tuple[int, int, int]) -> int:
    major, minor, patch = mc_tuple
    if major >= 26:
        return 25
    if major > 1:
        return 21
    if minor > 20 or (minor == 20 and patch >= 5):
        return 21
    if minor >= 18:
        return 17
    if minor >= 17:
        return 16
    return 8


def _strip_yaml_inline_comment(line: str) -> str:
    in_single = False
    in_double = False
    escaped = False
    for idx, ch in enumerate(line):
        if escaped:
            escaped = False
            continue
        if ch == "\\" and in_double:
            escaped = True
            continue
        if ch == "'" and not in_double:
            in_single = not in_single
        elif ch == '"' and not in_single:
            in_double = not in_double
        elif ch == "#" and not in_single and not in_double:
            if idx == 0 or line[idx - 1].isspace():
                return line[:idx].rstrip()
    return line.rstrip()


def _unquote_yaml_scalar(raw: str) -> tuple[str, bool]:
    val = raw.strip()
    if len(val) >= 2 and ((val[0] == "'" and val[-1] == "'") or (val[0] == '"' and val[-1] == '"')):
        return val[1:-1], True
    return val, False


def _parse_paper_plugin_yaml(text: str) -> dict[str, Any]:
    scalars: dict[str, str] = {}
    raw_scalars: dict[str, str] = {}
    quoted_flags: dict[str, bool] = {}
    root_keys: list[str] = []
    dependencies: dict[str, dict[str, dict[str, Any]]] = {"bootstrap": {}, "server": {}}
    has_tab_indentation = False

    in_deps = False
    deps_indent = 0
    current_section: str | None = None
    section_indent: int | None = None
    current_dep: str | None = None
    dep_indent: int | None = None

    for raw_line in text.splitlines():
        if raw_line and raw_line[0] in (" ", "\t"):
            leading = raw_line[: len(raw_line) - len(raw_line.lstrip(" \t"))]
            if "\t" in leading and raw_line.strip() and not raw_line.lstrip().startswith("#"):
                has_tab_indentation = True

        cleaned = _strip_yaml_inline_comment(raw_line.replace("\t", "  "))
        if not cleaned.strip() or cleaned.strip() == "---":
            continue

        indent = len(cleaned) - len(cleaned.lstrip(" "))
        content = cleaned.strip()

        if indent == 0:
            in_deps = False
            current_section = None
            section_indent = None
            current_dep = None
            dep_indent = None

            if ":" in content:
                key_part, _, rest_part = content.partition(":")
                key = key_part.strip()
                if key and key not in root_keys:
                    root_keys.append(key)
                rest = rest_part.strip()
                if key == "dependencies" and rest in ("", "{}"):
                    in_deps = rest == ""
                    deps_indent = 0
                elif rest and rest not in ("|", ">"):
                    unq, was_q = _unquote_yaml_scalar(rest)
                    scalars[key] = unq
                    raw_scalars[key] = rest
                    quoted_flags[key] = was_q
            continue

        if not in_deps:
            continue

        if section_indent is not None and indent <= section_indent:
            current_section = None
            section_indent = None
            current_dep = None
            dep_indent = None

        if current_section is None:
            if ":" in content and indent > deps_indent:
                sec_key, _, sec_rest = content.partition(":")
                sec_key = sec_key.strip()
                sec_rest = sec_rest.strip()
                if sec_key in ("bootstrap", "server") and sec_rest in ("", "{}"):
                    if sec_rest == "":
                        current_section = sec_key
                        section_indent = indent
            continue

        if dep_indent is not None and indent <= dep_indent:
            current_dep = None
            dep_indent = None

        if current_dep is None:
            if ":" in content and section_indent is not None and indent > section_indent:
                d_key, _, d_rest = content.partition(":")
                d_name, _ = _unquote_yaml_scalar(d_key.strip())
                d_rest = d_rest.strip()
                if d_name:
                    dependencies[current_section][d_name] = {
                        "load": "OMIT",
                        "raw_load": "OMIT",
                        "required": True,
                        "join_classpath": True,
                        "invalid_bool_fields": [],
                    }
                    if d_rest == "":
                        current_dep = d_name
                        dep_indent = indent
            continue

        if ":" in content and dep_indent is not None and indent > dep_indent:
            p_key, _, p_rest = content.partition(":")
            p_key = p_key.strip()
            p_val, _ = _unquote_yaml_scalar(p_rest.strip())
            cfg = dependencies[current_section][current_dep]
            if p_key == "load":
                cfg["raw_load"] = p_val
                if p_val in {"BEFORE", "AFTER", "OMIT"}:
                    cfg["load"] = p_val
            elif p_key == "required":
                if p_val.lower() == "true":
                    cfg["required"] = True
                elif p_val.lower() == "false":
                    cfg["required"] = False
                else:
                    cfg["invalid_bool_fields"].append("required")
            elif p_key == "join-classpath":
                if p_val.lower() == "true":
                    cfg["join_classpath"] = True
                elif p_val.lower() == "false":
                    cfg["join_classpath"] = False
                else:
                    cfg["invalid_bool_fields"].append("join-classpath")

    return {
        "scalars": scalars,
        "raw_scalars": raw_scalars,
        "quoted_flags": quoted_flags,
        "root_keys": root_keys,
        "dependencies": dependencies,
        "has_tab_indentation": has_tab_indentation,
    }


def _parse_legacy_plugin_yaml(text: str) -> dict[str, Any]:
    lists: dict[str, list[str]] = {"depend": [], "softdepend": [], "loadbefore": []}
    scalars: dict[str, str] = {}
    active_list_key: str | None = None

    for raw_line in text.splitlines():
        cleaned = _strip_yaml_inline_comment(raw_line.replace("\t", "  "))
        if not cleaned.strip() or cleaned.strip() == "---":
            continue
        indent = len(cleaned) - len(cleaned.lstrip(" "))
        content = cleaned.strip()

        if indent == 0:
            active_list_key = None
            if ":" in content:
                k_part, _, r_part = content.partition(":")
                key = k_part.strip()
                rest = r_part.strip()
                if key in lists:
                    if rest.startswith("[") and rest.endswith("]"):
                        inner = rest[1:-1].strip()
                        if inner:
                            for item in inner.split(","):
                                val, _ = _unquote_yaml_scalar(item.strip())
                                if val:
                                    lists[key].append(val)
                    elif rest == "":
                        active_list_key = key
                elif rest:
                    val, _ = _unquote_yaml_scalar(rest)
                    scalars[key] = val
        elif active_list_key is not None and content.startswith("-"):
            item_raw = content[1:].strip()
            val, _ = _unquote_yaml_scalar(item_raw)
            if val:
                lists[active_list_key].append(val)

    return {
        "scalars": scalars,
        "depend": lists["depend"],
        "softdepend": lists["softdepend"],
        "loadbefore": lists["loadbefore"],
    }


_RESOURCE_PACK_FORMATS: dict[str, tuple[int, int | None]] = {
    "1.20": (15, None),
    "1.20.1": (15, None),
    "1.20.2": (18, None),
    "1.20.3": (22, None),
    "1.20.4": (22, None),
    "1.20.5": (32, None),
    "1.20.6": (32, None),
    "1.21": (34, None),
    "1.21.1": (34, None),
    "1.21.2": (42, None),
    "1.21.3": (42, None),
    "1.21.4": (46, None),
    "1.21.5": (55, None),
    "1.21.6": (63, None),
    "1.21.7": (64, None),
    "1.21.8": (64, None),
    "1.21.9": (69, None),
    "1.21.10": (69, None),
    "1.21.11": (75, None),
    "26.1": (84, None),
    "26.1.1": (84, None),
    "26.1.2": (84, None),
    "26.2": (88, 0),
    "26.3": (97, 1),
}

_DATA_PACK_FORMATS: dict[str, tuple[int, int | None]] = {
    "1.20": (15, None),
    "1.20.1": (15, None),
    "1.20.2": (18, None),
    "1.20.3": (26, None),
    "1.20.4": (26, None),
    "1.20.5": (41, None),
    "1.20.6": (41, None),
    "1.21": (48, None),
    "1.21.1": (48, None),
    "1.21.2": (57, None),
    "1.21.3": (57, None),
    "1.21.4": (61, None),
    "1.21.5": (71, None),
    "1.21.6": (80, None),
    "1.21.7": (81, None),
    "1.21.8": (81, None),
    "1.21.9": (88, 0),
    "1.21.10": (88, 0),
    "1.21.11": (94, 1),
    "26.1": (101, 1),
    "26.1.1": (101, 1),
    "26.1.2": (101, 1),
    "26.2": (107, 1),
    "26.3": (121, 0),
}

_RESOURCE_BREAKING_EPOCHS: tuple[tuple[str, str, str], ...] = (
    ("overlay_1_21_2_equipment", "1.21.2", "Armor and elytra rendering moved to assets/<namespace>/equipment/ definitions."),
    ("overlay_1_21_4_items", "1.21.4", "Client item definitions under assets/<namespace>/items/<id>.json replaced legacy model overrides predicates."),
    ("overlay_1_21_6_dialogs", "1.21.6", "Built-in dialog UI definitions and updated core/post shader uniform layouts."),
    ("overlay_26_1_modern", "26.1", "Year-based 26.x resource pipeline and updated shader/atlas format contracts."),
    ("overlay_26_3_components", "26.3", "Resource pack format [97, 1]: updated item model selection properties, oversized GUI item rendering, and core shader uniform bindings."),
)

_DATA_BREAKING_EPOCHS: tuple[tuple[str, str, str], ...] = (
    ("overlay_1_20_5_components", "1.20.5", "Structured item data components replaced raw NBT tags across recipes, loot tables, and predicates."),
    ("overlay_1_21_singular_dirs", "1.21", "Registry folders renamed from plural to singular (loot_table, recipe, tags/item, tags/block) plus data-driven enchantments."),
    ("overlay_1_21_5_predicates", "1.21.5", "Updated entity/item component predicates, tooltip_display migration, and dialog data definitions."),
    ("overlay_26_1_modern", "26.1", "Year-based 26.x data pack registry schema updates."),
    ("overlay_26_3_components", "26.3", "Data pack format [121, 0]: Paper/Minecraft 26.3 strict typed item component codecs, tooltip_display enforcement, and weapon/blocks_attacks predicates."),
)

PAPER_26_3_ITEM_COMPONENT_SCHEMAS: dict[str, dict[str, Any]] = {
    "minecraft:custom_model_data": {
        "introduced_in": "1.20.5",
        "modern_schema_since": "1.21.4",
        "value_type": "object",
        "allowed_keys": ["floats", "flags", "strings", "colors"],
        "notes": "Integer prior to 1.21.4; typed channel object {floats: number[], flags: boolean[], strings: string[], colors: (int|number[3])[]} in 1.21.4 through 26.3+.",
    },
    "minecraft:item_model": {
        "introduced_in": "1.21.2",
        "value_type": "resource_location",
        "notes": "Namespaced ID resolving assets/<namespace>/items/<path>.json.",
    },
    "minecraft:item_name": {
        "introduced_in": "1.20.5",
        "modern_schema_since": "1.21.5",
        "value_type": "text_component",
        "notes": "Default non-italic item name; native text component object/string in 1.21.5 through 26.3+ (do not JSON-escape objects inside strings).",
    },
    "minecraft:custom_name": {
        "introduced_in": "1.20.5",
        "modern_schema_since": "1.21.5",
        "value_type": "text_component",
        "notes": "Anvil/custom display name; native text component object/string in 1.21.5 through 26.3+.",
    },
    "minecraft:lore": {
        "introduced_in": "1.20.5",
        "modern_schema_since": "1.21.5",
        "value_type": "array",
        "max_items": 256,
        "notes": "Array of up to 256 native text component entries.",
    },
    "minecraft:tooltip_display": {
        "introduced_in": "1.21.5",
        "value_type": "object",
        "allowed_keys": ["hide_tooltip", "hidden_components"],
        "notes": "Replaces removed minecraft:hide_tooltip, minecraft:hide_additional_tooltip, and per-component show_in_tooltip flags.",
    },
    "minecraft:tooltip_style": {
        "introduced_in": "1.21.2",
        "value_type": "resource_location",
        "notes": "Namespaced tooltip frame/background sprite prefix under textures/gui/sprites/tooltip/.",
    },
    "minecraft:equippable": {
        "introduced_in": "1.21.2",
        "modern_schema_since": "1.21.5",
        "value_type": "object",
        "required_keys": ["slot"],
        "allowed_keys": [
            "slot", "equip_sound", "asset_id", "camera_overlay", "allowed_entities",
            "dispensable", "swappable", "damage_on_hurt", "equip_on_interact", "can_be_sheared", "shearing_sound",
        ],
        "deprecated_keys": {
            "model": "Renamed to 'asset_id' in 1.21.4+ (referencing assets/<namespace>/equipment/<id>.json).",
        },
        "notes": "Controls armor, elytra, saddle, and custom equipment slot behaviour.",
    },
    "minecraft:consumable": {
        "introduced_in": "1.21.2",
        "value_type": "object",
        "allowed_keys": ["consume_seconds", "animation", "sound", "has_consume_particles", "on_consume_effects"],
        "notes": "Extracted from minecraft:food in 1.21.2; enables consumable animations and effects on any item.",
    },
    "minecraft:food": {
        "introduced_in": "1.20.5",
        "modern_schema_since": "1.21.2",
        "value_type": "object",
        "required_keys": ["nutrition", "saturation"],
        "allowed_keys": ["nutrition", "saturation", "can_always_eat"],
        "deprecated_keys": {
            "eat_seconds": "Moved to minecraft:consumable.consume_seconds in 1.21.2+.",
            "using_converts_to": "Moved to minecraft:use_remainder in 1.21.2+.",
            "effects": "Moved to minecraft:consumable.on_consume_effects in 1.21.2+.",
        },
        "notes": "Pure hunger/saturation stats when paired with minecraft:consumable.",
    },
    "minecraft:use_remainder": {
        "introduced_in": "1.21.2",
        "value_type": "object",
        "required_keys": ["id"],
        "notes": "Item stack returned after consuming an item.",
    },
    "minecraft:use_cooldown": {
        "introduced_in": "1.21.2",
        "value_type": "object",
        "required_keys": ["seconds"],
        "allowed_keys": ["seconds", "cooldown_group"],
        "notes": "Applies a shared namespaced cooldown group (seconds > 0) after item use.",
    },
    "minecraft:weapon": {
        "introduced_in": "1.21.5",
        "value_type": "object",
        "allowed_keys": ["item_damage_per_attack", "disable_blocking_for_seconds"],
        "notes": "Controls durability cost per melee hit and shield-disable duration in seconds.",
    },
    "minecraft:blocks_attacks": {
        "introduced_in": "1.21.5",
        "value_type": "object",
        "allowed_keys": [
            "block_delay_seconds", "disable_cooldown_scale", "damage_reductions",
            "item_damage", "block_sound", "disabled_sound", "bypassed_by",
        ],
        "notes": "Data-driven shield/parry component on 1.21.5 through 26.3+.",
    },
    "minecraft:break_sound": {
        "introduced_in": "1.21.5",
        "value_type": "sound_event",
        "notes": "Sound event triggered when item durability reaches zero.",
    },
    "minecraft:attribute_modifiers": {
        "introduced_in": "1.20.5",
        "modern_schema_since": "1.21.5",
        "value_type": "array",
        "notes": "Direct array of {type, id, amount, operation, slot, display?} entries in 1.21.5 through 26.3+ (show_in_tooltip moved to tooltip_display).",
    },
    "minecraft:enchantments": {
        "introduced_in": "1.20.5",
        "modern_schema_since": "1.21.5",
        "value_type": "object",
        "notes": "Direct map of namespaced enchantment ID to integer level (1..255) in 1.21.5 through 26.3+.",
    },
    "minecraft:stored_enchantments": {
        "introduced_in": "1.20.5",
        "modern_schema_since": "1.21.5",
        "value_type": "object",
        "notes": "Direct map of stored enchantment ID to integer level (1..255) for enchanted books.",
    },
    "minecraft:max_stack_size": {
        "introduced_in": "1.20.5",
        "value_type": "int",
        "min": 1,
        "max": 99,
        "notes": "Stack limit (1..99); mutually exclusive with max_damage when max_stack_size > 1.",
    },
    "minecraft:max_damage": {
        "introduced_in": "1.20.5",
        "value_type": "int",
        "min": 1,
        "notes": "Maximum durability (>= 1); requires max_stack_size == 1.",
    },
    "minecraft:damage": {
        "introduced_in": "1.20.5",
        "value_type": "int",
        "min": 0,
        "notes": "Current durability damage (>= 0).",
    },
    "minecraft:unbreakable": {
        "introduced_in": "1.20.5",
        "modern_schema_since": "1.21.5",
        "value_type": "unit_object",
        "notes": "Empty unit object {} in 1.21.5 through 26.3+ (show_in_tooltip moved to tooltip_display).",
    },
    "minecraft:enchantable": {
        "introduced_in": "1.21.2",
        "value_type": "object",
        "required_keys": ["value"],
        "allowed_keys": ["value"],
        "notes": "Enchantability weight ({value: int >= 1}).",
    },
    "minecraft:repairable": {
        "introduced_in": "1.21.2",
        "value_type": "object",
        "required_keys": ["items"],
        "allowed_keys": ["items"],
        "notes": "Anvil repair ingredient item ID, #tag, or list of item IDs.",
    },
    "minecraft:glider": {
        "introduced_in": "1.21.2",
        "value_type": "unit_object",
        "notes": "Empty unit object {} enabling elytra-style gliding when equipped.",
    },
    "minecraft:death_protection": {
        "introduced_in": "1.21.2",
        "value_type": "object",
        "allowed_keys": ["death_effects"],
        "notes": "Totem-of-undying style resurrection effects.",
    },
    "minecraft:rarity": {
        "introduced_in": "1.20.5",
        "value_type": "enum",
        "enum": ["common", "uncommon", "rare", "epic"],
        "notes": "Item name rarity tier.",
    },
    "minecraft:dyed_color": {
        "introduced_in": "1.20.5",
        "modern_schema_since": "1.21.5",
        "value_type": "color",
        "notes": "Packed RGB integer or [r, g, b] float array in 1.21.5 through 26.3+ (show_in_tooltip removed).",
    },
    "minecraft:trim": {
        "introduced_in": "1.20.5",
        "modern_schema_since": "1.21.5",
        "value_type": "object",
        "required_keys": ["material", "pattern"],
        "allowed_keys": ["material", "pattern"],
        "notes": "Armor trim material and pattern IDs (show_in_tooltip removed in 1.21.5+).",
    },
    "minecraft:custom_data": {
        "introduced_in": "1.20.5",
        "value_type": "object_or_snbt",
        "notes": "Plugin/datapack custom compound backing Paper PersistentDataContainer (PublicBukkitValues).",
    },
}


def _parse_java_properties(text: str) -> dict[str, Any]:
    values: dict[str, str] = {}
    lines: dict[str, int] = {}
    duplicates: list[str] = []

    raw_lines = text.splitlines()
    idx = 0
    total = len(raw_lines)
    while idx < total:
        line_no = idx + 1
        raw = raw_lines[idx]
        idx += 1
        stripped = raw.lstrip(" \t\f")
        if not stripped or stripped[0] in ("#", "!"):
            continue

        logical = stripped
        while logical.endswith("\\") and (len(logical) - len(logical.rstrip("\\"))) % 2 == 1 and idx < total:
            logical = logical[:-1] + raw_lines[idx].lstrip(" \t\f")
            idx += 1

        key_chars: list[str] = []
        pos = 0
        n = len(logical)
        escaped = False
        while pos < n:
            ch = logical[pos]
            if escaped:
                key_chars.append(ch)
                escaped = False
                pos += 1
                continue
            if ch == "\\":
                escaped = True
                pos += 1
                continue
            if ch in ("=", ":", " ", "\t", "\f"):
                break
            key_chars.append(ch)
            pos += 1

        while pos < n and logical[pos] in (" ", "\t", "\f"):
            pos += 1
        if pos < n and logical[pos] in ("=", ":"):
            pos += 1
            while pos < n and logical[pos] in (" ", "\t", "\f"):
                pos += 1

        val_raw = logical[pos:]
        val_chars: list[str] = []
        vpos = 0
        vn = len(val_raw)
        while vpos < vn:
            ch = val_raw[vpos]
            if ch == "\\" and vpos + 1 < vn:
                nxt = val_raw[vpos + 1]
                if nxt == "n":
                    val_chars.append("\n")
                    vpos += 2
                elif nxt == "r":
                    val_chars.append("\r")
                    vpos += 2
                elif nxt == "t":
                    val_chars.append("\t")
                    vpos += 2
                elif nxt == "u" and vpos + 5 < vn and re.fullmatch(r"[0-9a-fA-F]{4}", val_raw[vpos + 2: vpos + 6]):
                    val_chars.append(chr(int(val_raw[vpos + 2: vpos + 6], 16)))
                    vpos += 6
                else:
                    val_chars.append(nxt)
                    vpos += 2
            else:
                val_chars.append(ch)
                vpos += 1

        key = "".join(key_chars).strip()
        if not key:
            continue
        if key in values and key not in duplicates:
            duplicates.append(key)
        values[key] = "".join(val_chars).strip()
        lines[key] = line_no

    return {"values": values, "lines": lines, "duplicates": duplicates}


def _parse_nested_yaml_scalars(text: str) -> dict[str, Any]:
    root_keys: list[str] = []
    dotted: dict[str, str] = {}
    stack: list[tuple[int, str]] = []

    for raw_line in text.splitlines():
        cleaned = _strip_yaml_inline_comment(raw_line.replace("\t", "  "))
        content = cleaned.strip()
        if not content or content == "---" or content.startswith("-"):
            continue
        indent = len(cleaned) - len(cleaned.lstrip(" "))
        while stack and stack[-1][0] >= indent:
            stack.pop()
        if ":" not in content:
            continue
        k_part, _, r_part = content.partition(":")
        key, _ = _unquote_yaml_scalar(k_part.strip())
        if not key:
            continue
        if indent == 0 and key not in root_keys:
            root_keys.append(key)
        rest = r_part.strip()
        full_key = ".".join([*(seg for _, seg in stack), key])
        if rest == "":
            stack.append((indent, key))
        elif rest in ("{}", "[]"):
            dotted[full_key] = rest
        elif rest not in ("|", ">"):
            val, _ = _unquote_yaml_scalar(rest)
            dotted[full_key] = val

    return {"root_keys": root_keys, "scalars": dotted}


def _parse_jvm_memory_mb(spec: str) -> float | None:
    m = re.fullmatch(r"(\d+(?:\.\d+)?)([kKmMgGtT]?)", spec.strip())
    if not m:
        return None
    amount = float(m.group(1))
    unit = m.group(2).lower()
    if unit == "t":
        return amount * 1024.0 * 1024.0
    if unit == "g":
        return amount * 1024.0
    if unit == "m":
        return amount
    if unit == "k":
        return amount / 1024.0
    return amount / (1024.0 * 1024.0)


_NAMESPACED_ID_RE = re.compile(r"^(?:[a-z0-9_.-]+:)?[a-z0-9_./-]+$")


def _validate_client_item_model_node(
    node: Any,
    *,
    path: str,
    cmd_counts: dict[str, int] | None,
    findings: list[dict[str, Any]],
    depth: int = 0,
) -> None:
    if depth > 16:
        findings.append({
            "rule_id": "COMP-006",
            "severity": "high",
            "title": "Client item definition exceeds maximum selector nesting depth",
            "evidence": [f"{path} depth > 16"],
            "problem": "Excessively nested item model selector graphs fail client model baking or indicate a cyclic generator bug.",
            "remediation": "Flatten nested select/condition/composite branches to depth <= 16.",
        })
        return

    if not isinstance(node, dict):
        findings.append({
            "rule_id": "COMP-006",
            "severity": "critical",
            "title": "Client item model node must be a JSON object",
            "evidence": [f"{path}={type(node).__name__}"],
            "problem": "Every node in assets/<namespace>/items/<id>.json model trees must be an object declaring 'type'.",
            "remediation": "Provide a valid item model object such as {\"type\": \"minecraft:model\", \"model\": \"ns:item/name\"}.",
        })
        return

    raw_type = node.get("type")
    if not isinstance(raw_type, str) or not raw_type.strip():
        findings.append({
            "rule_id": "COMP-006",
            "severity": "critical",
            "title": "Missing 'type' discriminator in client item model node",
            "evidence": [path],
            "problem": "Minecraft 1.21.4 through 26.3+ item definitions dispatch strictly on 'type'.",
            "remediation": "Set 'type' to 'minecraft:model', 'minecraft:condition', 'minecraft:select', 'minecraft:range_dispatch', 'minecraft:composite', 'minecraft:bundle/selected_item', 'minecraft:empty', or 'minecraft:special'.",
        })
        return

    norm_type = raw_type if ":" in raw_type else f"minecraft:{raw_type}"
    valid_types = {
        "minecraft:model",
        "minecraft:condition",
        "minecraft:select",
        "minecraft:range_dispatch",
        "minecraft:composite",
        "minecraft:bundle/selected_item",
        "minecraft:empty",
        "minecraft:special",
    }
    if norm_type not in valid_types:
        findings.append({
            "rule_id": "COMP-006",
            "severity": "critical",
            "title": "Unknown client item model selector type",
            "evidence": [f"{path}.type={raw_type!r}"],
            "problem": f"'{raw_type}' is not a valid Minecraft 1.21.4-26.3 item model type.",
            "remediation": f"Use one of: {', '.join(sorted(valid_types))}.",
        })
        return

    def _check_cmd_channel(channel: str, raw_idx: Any, ctx_path: str) -> None:
        idx_val = 0 if raw_idx is None else raw_idx
        if isinstance(idx_val, bool) or not isinstance(idx_val, int) or idx_val < 0:
            findings.append({
                "rule_id": "COMP-006",
                "severity": "high",
                "title": "Invalid negative or non-integer custom_model_data index",
                "evidence": [f"{ctx_path}.index={raw_idx!r}"],
                "problem": "custom_model_data channel indices in client item definitions must be non-negative integers.",
                "remediation": "Set 'index' to a 0-based integer matching the server item's custom_model_data channel list.",
            })
            return
        if cmd_counts is not None and idx_val >= cmd_counts.get(channel, 0):
            findings.append({
                "rule_id": "COMP-006",
                "severity": "high",
                "title": f"Client custom_model_data.{channel}[{idx_val}] index out of bounds for server component",
                "evidence": [
                    f"{ctx_path} requests {channel}[{idx_val}], server component provides len({channel})={cmd_counts.get(channel, 0)}"
                ],
                "problem": (
                    f"The client item definition reads custom_model_data.{channel}[{idx_val}], "
                    "which is missing from the server item's minecraft:custom_model_data component and falls back to default/missing visuals."
                ),
                "remediation": f"Populate at least {idx_val + 1} element(s) in minecraft:custom_model_data.{channel} or adjust 'index'.",
            })

    if norm_type == "minecraft:model":
        model_ref = node.get("model")
        if not isinstance(model_ref, str) or not model_ref.strip() or _NAMESPACED_ID_RE.fullmatch(model_ref) is None:
            findings.append({
                "rule_id": "COMP-006",
                "severity": "critical",
                "title": "Invalid or missing 'model' resource location in minecraft:model",
                "evidence": [f"{path}.model={model_ref!r}"],
                "problem": "minecraft:model requires a lowercase namespaced resource location resolving assets/<ns>/models/<path>.json.",
                "remediation": "Specify a valid lowercase resource location such as 'myplugin:item/sunblade'.",
            })
        tints = node.get("tints")
        if isinstance(tints, list):
            for tidx, tint in enumerate(tints):
                if isinstance(tint, dict):
                    t_type = str(tint.get("type", ""))
                    if t_type in {"custom_model_data", "minecraft:custom_model_data"}:
                        _check_cmd_channel("colors", tint.get("index"), f"{path}.tints[{tidx}]")

    elif norm_type == "minecraft:condition":
        prop = node.get("property")
        if not isinstance(prop, str) or not prop.strip():
            findings.append({
                "rule_id": "COMP-006",
                "severity": "critical",
                "title": "Missing 'property' in minecraft:condition item model",
                "evidence": [path],
                "problem": "minecraft:condition requires a boolean 'property' plus 'on_true' and 'on_false' branches.",
                "remediation": "Declare 'property' (e.g. 'minecraft:using_item' or 'minecraft:custom_model_data'), 'on_true', and 'on_false'.",
            })
        elif prop in {"custom_model_data", "minecraft:custom_model_data"}:
            _check_cmd_channel("flags", node.get("index"), path)
        for branch in ("on_true", "on_false"):
            if branch not in node:
                findings.append({
                    "rule_id": "COMP-006",
                    "severity": "critical",
                    "title": f"Missing '{branch}' branch in minecraft:condition",
                    "evidence": [path],
                    "problem": f"minecraft:condition requires both 'on_true' and 'on_false' child model definitions (missing '{branch}').",
                    "remediation": f"Add '{branch}' with a valid item model object.",
                })
            else:
                _validate_client_item_model_node(
                    node[branch], path=f"{path}.{branch}", cmd_counts=cmd_counts, findings=findings, depth=depth + 1
                )

    elif norm_type == "minecraft:select":
        prop = node.get("property")
        cases = node.get("cases")
        if not isinstance(prop, str) or not prop.strip():
            findings.append({
                "rule_id": "COMP-006",
                "severity": "critical",
                "title": "Missing 'property' in minecraft:select item model",
                "evidence": [path],
                "problem": "minecraft:select requires a 'property' discriminator and a non-empty 'cases' array.",
                "remediation": "Set 'property' (e.g. 'minecraft:custom_model_data' or 'minecraft:display_context') and 'cases'.",
            })
        elif prop in {"custom_model_data", "minecraft:custom_model_data"}:
            _check_cmd_channel("strings", node.get("index"), path)
        if not isinstance(cases, list) or not cases:
            findings.append({
                "rule_id": "COMP-006",
                "severity": "critical",
                "title": "Empty or missing 'cases' array in minecraft:select",
                "evidence": [f"{path}.cases"],
                "problem": "minecraft:select requires at least one {when, model} entry in 'cases'.",
                "remediation": "Populate 'cases' with objects containing 'when' and 'model'.",
            })
        else:
            for cidx, case_obj in enumerate(cases):
                if not isinstance(case_obj, dict) or "when" not in case_obj or "model" not in case_obj:
                    findings.append({
                        "rule_id": "COMP-006",
                        "severity": "critical",
                        "title": "Malformed case entry in minecraft:select",
                        "evidence": [f"{path}.cases[{cidx}]"],
                        "problem": "Each select case must be an object containing 'when' and 'model'.",
                        "remediation": "Provide both 'when' and 'model' in every select case.",
                    })
                else:
                    _validate_client_item_model_node(
                        case_obj["model"], path=f"{path}.cases[{cidx}].model", cmd_counts=cmd_counts, findings=findings, depth=depth + 1
                    )
        if "fallback" in node:
            _validate_client_item_model_node(
                node["fallback"], path=f"{path}.fallback", cmd_counts=cmd_counts, findings=findings, depth=depth + 1
            )

    elif norm_type == "minecraft:range_dispatch":
        prop = node.get("property")
        entries = node.get("entries")
        if not isinstance(prop, str) or not prop.strip():
            findings.append({
                "rule_id": "COMP-006",
                "severity": "critical",
                "title": "Missing 'property' in minecraft:range_dispatch",
                "evidence": [path],
                "problem": "minecraft:range_dispatch requires a numeric 'property' and an 'entries' array.",
                "remediation": "Set 'property' (e.g. 'minecraft:custom_model_data' or 'minecraft:damage') and 'entries'.",
            })
        elif prop in {"custom_model_data", "minecraft:custom_model_data"}:
            _check_cmd_channel("floats", node.get("index"), path)
        if not isinstance(entries, list) or not entries:
            findings.append({
                "rule_id": "COMP-006",
                "severity": "critical",
                "title": "Empty or missing 'entries' in minecraft:range_dispatch",
                "evidence": [f"{path}.entries"],
                "problem": "minecraft:range_dispatch requires at least one {threshold, model} entry.",
                "remediation": "Add {threshold: <number>, model: {...}} objects sorted in ascending threshold order.",
            })
        else:
            thresholds: list[float] = []
            for eidx, ent in enumerate(entries):
                if not isinstance(ent, dict) or isinstance(ent.get("threshold"), bool) or not isinstance(ent.get("threshold"), (int, float)) or "model" not in ent:
                    findings.append({
                        "rule_id": "COMP-006",
                        "severity": "critical",
                        "title": "Malformed entry in minecraft:range_dispatch",
                        "evidence": [f"{path}.entries[{eidx}]"],
                        "problem": "Each range_dispatch entry requires a numeric 'threshold' and a 'model' object.",
                        "remediation": "Specify numeric 'threshold' and valid 'model' for every range_dispatch entry.",
                    })
                else:
                    thresholds.append(float(ent["threshold"]))
                    _validate_client_item_model_node(
                        ent["model"], path=f"{path}.entries[{eidx}].model", cmd_counts=cmd_counts, findings=findings, depth=depth + 1
                    )
            if len(thresholds) >= 2 and (thresholds != sorted(thresholds) or len(set(thresholds)) != len(thresholds)):
                findings.append({
                    "rule_id": "COMP-006",
                    "severity": "high",
                    "title": "Unsorted or duplicate thresholds in minecraft:range_dispatch",
                    "evidence": [f"{path}.entries thresholds={thresholds}"],
                    "problem": "Duplicate or unsorted range_dispatch thresholds shadow entries or produce ambiguous client dispatch.",
                    "remediation": "Sort range_dispatch entries by strictly increasing numeric threshold.",
                })
        if "fallback" in node:
            _validate_client_item_model_node(
                node["fallback"], path=f"{path}.fallback", cmd_counts=cmd_counts, findings=findings, depth=depth + 1
            )

    elif norm_type == "minecraft:composite":
        models = node.get("models")
        if not isinstance(models, list) or not models:
            findings.append({
                "rule_id": "COMP-006",
                "severity": "critical",
                "title": "Empty or missing 'models' array in minecraft:composite",
                "evidence": [f"{path}.models"],
                "problem": "minecraft:composite requires a non-empty 'models' array.",
                "remediation": "Populate 'models' with one or more valid child item model objects.",
            })
        else:
            for midx, child in enumerate(models):
                _validate_client_item_model_node(
                    child, path=f"{path}.models[{midx}]", cmd_counts=cmd_counts, findings=findings, depth=depth + 1
                )

    elif norm_type == "minecraft:special":
        spec_model = node.get("model")
        if not isinstance(spec_model, dict) or not isinstance(spec_model.get("type"), str):
            findings.append({
                "rule_id": "COMP-006",
                "severity": "critical",
                "title": "Missing special renderer 'model.type' in minecraft:special",
                "evidence": [f"{path}.model"],
                "problem": "minecraft:special requires a nested 'model' object declaring special renderer 'type' (e.g. 'minecraft:head', 'minecraft:shield').",
                "remediation": "Provide 'base' and a nested special renderer object under 'model'.",
            })


def _resolve_pack_format(
    spec: str,
    *,
    pack_type: str,
    dynamic_caps: dict[str, tuple[int, int | None]],
) -> tuple[int, int | None]:
    table = _RESOURCE_PACK_FORMATS if pack_type == "resource" else _DATA_PACK_FORMATS
    cleaned = spec.strip()
    if cleaned in dynamic_caps:
        return dynamic_caps[cleaned]
    if cleaned in table:
        return table[cleaned]

    parts = cleaned.split(".")
    if len(parts) == 1 and parts[0].isdigit():
        return (int(parts[0]), None)
    if len(parts) == 2 and parts[0].isdigit() and parts[1].isdigit():
        major = int(parts[0])
        minor = int(parts[1])
        # Distinguish pack_format tuples (e.g. 88.0, 97.1, 107.1, 121.0) from unknown MC releases (e.g. 1.19)
        if major >= 65:
            return (major, minor)

    known = ", ".join(table.keys())
    raise ValueError(
        f"Unknown Minecraft version '{cleaned}' for {pack_type} pack. "
        f"Known releases: {known}. For snapshots, pass the numeric pack format directly (e.g. '88' or '97.1')."
    )


def _pack_format_sort_key(fmt: tuple[int, int | None], *, is_max: bool) -> tuple[int, int]:
    major, minor = fmt
    if minor is None:
        return (major, 999999 if is_max else 0)
    return (major, minor)


def _pack_format_to_json(fmt: tuple[int, int | None]) -> int | list[int]:
    major, minor = fmt
    if minor is None:
        return major
    return [major, minor]


def _format_pack_tuple(fmt: tuple[int, int | None]) -> str:
    major, minor = fmt
    return f"{major}" if minor is None else f"{major}.{minor}"


class MinecraftKitMcpServer:
    """Pure-Python MCP server exposing MinecraftKit's offline catalogs over JSON-RPC 2.0."""

    def __init__(self, root: Path | None = None) -> None:
        self.store = CatalogStore(root or SCRIPTS_DIR.parent)
        self._handlers = {
            "mc_search_api": self._tool_search_api,
            "mc_list_plugins": self._tool_list_plugins,
            "mc_search_sources": self._tool_search_sources,
            "mc_version_capabilities": self._tool_version_capabilities,
            "mc_route_skill": self._tool_route_skill,
            "mc_folia_migration_advisor": self._tool_folia_migration_advisor,
            "mc_diagnose_server_log": self._tool_diagnose_server_log,
            "mc_inspect_type": self._tool_inspect_type,
            "mc_audit_gradle_build": self._tool_audit_gradle_build,
            "mc_audit_paper_plugin_yml": self._tool_audit_paper_plugin_yml,
            "mc_generate_pack_overlay": self._tool_generate_pack_overlay,
            "mc_audit_server_properties": self._tool_audit_server_properties,
            "mc_validate_item_components": self._tool_validate_item_components,
            "mc_diagnose_crash_report": self._tool_diagnose_crash_report,
            "mc_audit_datapack": self._tool_audit_datapack,
            "mc_audit_spark_flamegraph": self._tool_audit_spark_flamegraph,
            "mc_analyze_folia_scheduler_trace": self._tool_analyze_folia_scheduler_trace,
        }

    def handle_message(self, raw: str) -> str | None:
        stripped = raw.strip()
        if not stripped:
            return None
        try:
            message = _strict_loads(stripped)
        except (ValueError, json.JSONDecodeError) as error:
            return self._error_response(None, PARSE_ERROR, f"Malformed JSON-RPC payload: {error}")

        if not isinstance(message, dict) or message.get("jsonrpc") != "2.0":
            msg_id = message.get("id") if isinstance(message, dict) else None
            return self._error_response(msg_id, INVALID_REQUEST, "JSON-RPC 2.0 object with jsonrpc='2.0' is required.")

        method = message.get("method")
        is_notification = "id" not in message
        msg_id = message.get("id")
        if not isinstance(method, str) or not method:
            if is_notification:
                return None
            return self._error_response(msg_id, INVALID_REQUEST, "Request 'method' must be a non-empty string.")

        params = message.get("params", {})
        if params is None:
            params = {}
        if not isinstance(params, dict):
            if is_notification:
                return None
            return self._error_response(msg_id, INVALID_PARAMS, "Request 'params' must be a JSON object.")

        if method in {"notifications/initialized", "notifications/cancelled"} or method.startswith("notifications/"):
            return None
        if is_notification:
            return None

        if method == "initialize":
            return self._result_response(msg_id, self._initialize(params))
        if method == "ping":
            return self._result_response(msg_id, {})
        if method == "tools/list":
            return self._result_response(msg_id, {"tools": list(TOOL_DEFINITIONS)})
        if method == "tools/call":
            return self._call_tool(msg_id, params)
        if method == "resources/list":
            return self._result_response(msg_id, {"resources": self._list_resources()})
        if method == "resources/read":
            return self._read_resource(msg_id, params)
        if method == "prompts/list":
            return self._result_response(msg_id, {"prompts": self._list_prompts()})
        if method == "prompts/get":
            return self._get_prompt(msg_id, params)

        return self._error_response(msg_id, METHOD_NOT_FOUND, f"Unsupported method: {method}")

    def _initialize(self, params: dict[str, Any]) -> dict[str, Any]:
        requested = params.get("protocolVersion")
        agreed = requested if isinstance(requested, str) and requested in SUPPORTED_PROTOCOL_VERSIONS else PROTOCOL_VERSION
        return {
            "protocolVersion": agreed,
            "capabilities": {
                "tools": {"listChanged": False},
                "resources": {"subscribe": False, "listChanged": False},
                "prompts": {"listChanged": False},
            },
            "serverInfo": {
                "name": "minecraftkit",
                "version": self.store.kit_version(),
            },
            "instructions": (
                "Offline Minecraft engineering knowledge server backed by Salyyy Minecraft Kit catalogs. "
                "Use mc_route_skill first to select the right mc:* engineering domain, mc_version_capabilities "
                "to pin exact Minecraft/protocol/pack formats, mc_search_sources for reviewed upstream GitHub "
                "repositories, mc_list_plugins / mc_search_api / mc_inspect_type for verified RPG plugin bytecode "
                "hierarchies and signatures, mc_generate_pack_overlay, mc_validate_item_components, and mc_audit_datapack "
                "for multi-version pack.mcmeta, Paper 26.3 item components, and datapack recipe/tag validation, "
                "and mc_audit_gradle_build / mc_audit_paper_plugin_yml / mc_audit_server_properties / "
                "mc_folia_migration_advisor / mc_analyze_folia_scheduler_trace / mc_audit_spark_flamegraph / "
                "mc_diagnose_server_log / mc_diagnose_crash_report for static build, descriptor, network/Netty config, "
                "4-domain Folia scheduler affinity, Spark flamegraph hotspots, and crash-log/report verification."
            ),
        }

    def _list_resources(self) -> list[dict[str, Any]]:
        resources: list[dict[str, Any]] = [
            {
                "uri": "minecraftkit://catalog/overview",
                "name": "catalog-overview",
                "title": "MinecraftKit Catalog Overview",
                "description": "JSON summary of indexed RPG plugins, Mojang release capabilities, and /mc:* engineering domains.",
                "mimeType": "application/json",
            },
            {
                "uri": "minecraftkit://catalog/paper-26.3-item-components",
                "name": "paper-26.3-item-components",
                "title": "Paper 26.3 Structured Item Data Component Schemas",
                "description": "Machine-readable schema catalog of Minecraft and Paper 1.20.5 through 26.3+ item data components, era migrations, and client item model selectors.",
                "mimeType": "application/json",
            },
        ]
        for ref_path in self.store.reference_files():
            heading = ref_path.stem.replace("-", " ").title()
            for line in ref_path.read_text(encoding="utf-8").splitlines()[:10]:
                if line.startswith("# "):
                    heading = line[2:].strip()
                    break
            resources.append({
                "uri": f"minecraftkit://references/{ref_path.name}",
                "name": ref_path.stem,
                "title": heading,
                "description": f"Curated Minecraft engineering reference handbook ({ref_path.name}).",
                "mimeType": "text/markdown",
            })
        return resources

    def _read_resource(self, msg_id: Any, params: dict[str, Any]) -> str:
        uri = params.get("uri")
        if not isinstance(uri, str) or not uri.strip():
            return self._error_response(msg_id, INVALID_PARAMS, "Missing non-empty string 'uri' in resources/read params.")
        uri = uri.strip()

        if uri == "minecraftkit://catalog/overview":
            cov = self.store.coverage().get("plugins", [])
            ver_cat = self.store.version_catalog()
            domains = self.store.domain_catalog().get("domains", [])
            overview = {
                "name": "minecraftkit",
                "version": self.store.kit_version(),
                "plugin_count": len(cov),
                "plugin_owned_types": sum(int(p.get("plugin_owned_types", 0)) for p in cov),
                "plugin_owned_members": sum(int(p.get("plugin_owned_members", 0)) for p in cov),
                "mojang_version_count": ver_cat.get("version_count", len(ver_cat.get("versions", []))),
                "latest": ver_cat.get("latest", {}),
                "routes": [
                    {
                        "id": d["id"],
                        "route": f"/{d['route']}",
                        "name": d["name"],
                        "reference_uri": f"minecraftkit://references/{Path(d['reference']).name}",
                    }
                    for d in domains
                ],
            }
            return self._result_response(
                msg_id,
                {
                    "contents": [
                        {
                            "uri": uri,
                            "mimeType": "application/json",
                            "text": _pretty_json(overview),
                        }
                    ]
                },
            )

        if uri == "minecraftkit://catalog/paper-26.3-item-components":
            schema_doc = {
                "target_release": "26.3",
                "resource_pack_format": [97, 1],
                "data_pack_format": [121, 0],
                "component_count": len(PAPER_26_3_ITEM_COMPONENT_SCHEMAS),
                "components": PAPER_26_3_ITEM_COMPONENT_SCHEMAS,
                "removed_legacy_components": {
                    "minecraft:hide_tooltip": "Replaced in 1.21.5+ by minecraft:tooltip_display: {hide_tooltip: true}.",
                    "minecraft:hide_additional_tooltip": "Replaced in 1.21.5+ by minecraft:tooltip_display: {hidden_components: [...]}.",
                },
            }
            return self._result_response(
                msg_id,
                {
                    "contents": [
                        {
                            "uri": uri,
                            "mimeType": "application/json",
                            "text": _pretty_json(schema_doc),
                        }
                    ]
                },
            )

        prefix = "minecraftkit://references/"
        if uri.startswith(prefix):
            slug = uri[len(prefix):]
            if not slug or "/" in slug or "\\" in slug or ".." in slug or not slug.endswith(".md"):
                return self._error_response(msg_id, INVALID_PARAMS, f"Invalid reference resource URI: {uri}")
            allowed = {p.name: p for p in self.store.reference_files()}
            target = allowed.get(slug)
            if target is None:
                return self._error_response(msg_id, INVALID_PARAMS, f"Unknown reference resource: {uri}")
            return self._result_response(
                msg_id,
                {
                    "contents": [
                        {
                            "uri": uri,
                            "mimeType": "text/markdown",
                            "text": target.read_text(encoding="utf-8"),
                        }
                    ]
                },
            )

        return self._error_response(msg_id, INVALID_PARAMS, f"Unknown resource URI: {uri}")

    def _list_prompts(self) -> list[dict[str, Any]]:
        prompts: list[dict[str, Any]] = []
        for domain in self.store.domain_catalog().get("domains", []):
            prompts.append({
                "name": str(domain["skill_directory"]),
                "title": f"/{domain['route']} - {domain['name']}",
                "description": f"Engineering workflow, runtime contracts, and verification checklist for /{domain['route']} ({domain['name']}).",
                "arguments": [
                    {
                        "name": "task",
                        "description": "Optional Minecraft plugin, server, or resource-pack engineering task.",
                        "required": False,
                    }
                ],
            })
        return prompts

    def _get_prompt(self, msg_id: Any, params: dict[str, Any]) -> str:
        raw_name = params.get("name")
        if not isinstance(raw_name, str) or not raw_name.strip():
            return self._error_response(msg_id, INVALID_PARAMS, "Missing non-empty string 'name' in prompts/get params.")
        norm = raw_name.strip().lstrip("/").lower().replace(":", "-")
        if not norm.startswith("mc-"):
            norm = f"mc-{norm}"

        domains = self.store.domain_catalog().get("domains", [])
        domain = next((d for d in domains if str(d.get("skill_directory", "")).lower() == norm), None)
        if domain is None:
            return self._error_response(msg_id, INVALID_PARAMS, f"Unknown prompt: {raw_name}")

        arguments = params.get("arguments") or {}
        if not isinstance(arguments, dict):
            return self._error_response(msg_id, INVALID_PARAMS, "Prompt 'arguments' must be a JSON object.")
        task = arguments.get("task", "")
        if task is not None and not isinstance(task, str):
            return self._error_response(msg_id, INVALID_PARAMS, "Prompt argument 'task' must be a string.")

        workflow_steps = self.store.extract_route_workflow(str(domain["skill_directory"]))
        ref_rel = str(domain["reference"])
        ref_uri = f"minecraftkit://references/{Path(ref_rel).name}"

        lines = [
            f"Route: /{domain['route']} ({domain['name']})",
            f"Primary Reference Handbook: {ref_uri} ({ref_rel})",
        ]
        if task and task.strip():
            lines.append(f"Target Task: {task.strip()}")
        if workflow_steps:
            lines.append("\nWorkflow Steps:")
            for idx, step in enumerate(workflow_steps, start=1):
                lines.append(f"{idx}. {step}")
        lines.extend([
            "\nVerification Tools:",
            "- Call mc_version_capabilities to pin Minecraft release, protocol, Java major version, and pack formats.",
            "- Call mc_search_api and mc_inspect_type to verify exact RPG plugin class hierarchies and method signatures.",
            "- Call mc_audit_gradle_build and mc_folia_migration_advisor before finalizing build scripts or scheduler code.",
        ])

        return self._result_response(
            msg_id,
            {
                "description": f"/{domain['route']} ({domain['name']})",
                "messages": [
                    {
                        "role": "user",
                        "content": {
                            "type": "text",
                            "text": "\n".join(lines),
                        },
                    }
                ],
            },
        )

    def _call_tool(self, msg_id: Any, params: dict[str, Any]) -> str:
        name = params.get("name")
        if not isinstance(name, str) or not name:
            return self._error_response(msg_id, INVALID_PARAMS, "Missing string 'name' in tools/call params.")
        handler = self._handlers.get(name)
        if handler is None:
            return self._error_response(msg_id, INVALID_PARAMS, f"Unknown tool: {name}")

        arguments = params.get("arguments", {})
        if arguments is None:
            arguments = {}
        if not isinstance(arguments, dict):
            return self._error_response(msg_id, INVALID_PARAMS, "Tool 'arguments' must be a JSON object.")

        try:
            outcome = handler(arguments)
        except Exception as error:  # noqa: BLE001
            outcome = ToolOutcome(f"{type(error).__name__}: {error}", is_error=True)

        return self._result_response(
            msg_id,
            {
                "content": [{"type": "text", "text": outcome.text}],
                "isError": outcome.is_error,
            },
        )

    def _tool_search_api(self, args: dict[str, Any]) -> ToolOutcome:
        terms = _normalize_terms(args.get("terms"), "terms")
        plugin = args.get("plugin")
        if plugin is not None and not isinstance(plugin, str):
            raise ValueError("'plugin' must be a string.")
        plugin = plugin.strip() if isinstance(plugin, str) and plugin.strip() else None

        valid_kinds = {"class", "interface", "enum", "annotation", "record", "field", "method", "constructor"}
        kind = args.get("kind")
        if kind is not None:
            if not isinstance(kind, str) or kind.lower() not in valid_kinds:
                raise ValueError(f"'kind' must be one of {sorted(valid_kinds)}.")
            kind = kind.lower()

        origin_raw = args.get("origin", "plugin-owned")
        if not isinstance(origin_raw, str) or origin_raw not in {"plugin-owned", "bundled-third-party", "all"}:
            raise ValueError("'origin' must be 'plugin-owned', 'bundled-third-party', or 'all'.")
        origin_filter = None if origin_raw == "all" else origin_raw

        limit = _parse_bounded_int(args.get("limit"), field="limit", default=25, minimum=1, maximum=200)

        results: list[dict[str, Any]] = []
        total = 0
        for record in self.store.api_records():
            if query_api.matches(record, terms, plugin, kind, origin_filter):
                total += 1
                if len(results) < limit:
                    results.append(record)

        payload = {
            "total": total,
            "returned": len(results),
            "filters": {
                "terms": terms,
                "plugin": plugin,
                "kind": kind,
                "origin": origin_raw,
                "limit": limit,
            },
            "results": results,
        }
        return ToolOutcome(_pretty_json(payload))

    def _tool_list_plugins(self, args: dict[str, Any]) -> ToolOutcome:
        plugin_filter = args.get("plugin")
        if plugin_filter is not None and not isinstance(plugin_filter, str):
            raise ValueError("'plugin' must be a string.")
        needle = plugin_filter.strip().casefold() if isinstance(plugin_filter, str) and plugin_filter.strip() else None

        include_insights = args.get("include_insights", True)
        if not isinstance(include_insights, bool):
            raise ValueError("'include_insights' must be a boolean.")

        coverage_entries = self.store.coverage().get("plugins", [])
        insights_by_name = {
            item["name"].casefold(): item
            for item in self.store.plugin_insights().get("plugins", [])
            if isinstance(item, dict) and isinstance(item.get("name"), str)
        }

        combined: list[dict[str, Any]] = []
        for cov in coverage_entries:
            name = str(cov.get("plugin", ""))
            insight = insights_by_name.get(name.casefold(), {})
            plugin_id = str(insight.get("id", name.lower()))
            if needle and needle not in {name.casefold(), plugin_id.casefold()}:
                continue
            entry: dict[str, Any] = {
                "id": plugin_id,
                "name": name,
                "version": insight.get("version"),
                "family": insight.get("family"),
                "max_class_major": insight.get("max_class_major"),
                "plugin_owned_types": cov.get("plugin_owned_types", 0),
                "plugin_owned_members": cov.get("plugin_owned_members", 0),
                "published_types": cov.get("published_types", 0),
                "published_members": cov.get("published_members", 0),
                "bundled_third_party_types": cov.get("bundled_third_party_types", 0),
                "bundled_third_party_members": cov.get("bundled_third_party_members", 0),
            }
            if include_insights and insight:
                entry["insights"] = {
                    "role": insight.get("role"),
                    "architecture": insight.get("architecture"),
                    "api_boundaries": insight.get("api_boundaries", []),
                    "capabilities": insight.get("capabilities", []),
                    "patterns": insight.get("patterns", []),
                    "risks": insight.get("risks", []),
                    "evidence": insight.get("evidence", []),
                }
            combined.append(entry)

        if needle and not combined:
            available = [str(c.get("plugin", "")) for c in coverage_entries]
            return ToolOutcome(
                _pretty_json({
                    "error": f"Unknown plugin '{plugin_filter}'.",
                    "available_plugins": available,
                }),
                is_error=True,
            )

        payload = {
            "plugin_count": len(combined),
            "totals": {
                "plugin_owned_types": sum(item["plugin_owned_types"] for item in combined),
                "plugin_owned_members": sum(item["plugin_owned_members"] for item in combined),
                "published_types": sum(item["published_types"] for item in combined),
                "published_members": sum(item["published_members"] for item in combined),
            },
            "plugins": combined,
        }
        return ToolOutcome(_pretty_json(payload))

    def _tool_search_sources(self, args: dict[str, Any]) -> ToolOutcome:
        terms = _normalize_terms(args.get("terms"), "terms")

        domain = args.get("domain")
        if domain is not None:
            if not isinstance(domain, str):
                raise ValueError("'domain' must be a string.")
            domain = domain.strip().lower() or None

        priority = args.get("priority")
        if priority is not None:
            if not isinstance(priority, str) or priority.upper() not in {"P0", "P1", "P2"}:
                raise ValueError("'priority' must be P0, P1, or P2.")
            priority = priority.upper()

        policy = args.get("policy")
        if policy is not None:
            if not isinstance(policy, str) or policy not in {"derive", "index", "link-only", "metadata-only"}:
                raise ValueError("'policy' must be derive, index, link-only, or metadata-only.")

        include_archived = args.get("include_archived", False)
        if not isinstance(include_archived, bool):
            raise ValueError("'include_archived' must be a boolean.")

        limit = _parse_bounded_int(args.get("limit"), field="limit", default=20, minimum=1, maximum=200)

        matches = query_sources.query_records(
            self.store.upstream_sources(),
            terms=terms,
            domain=domain,
            priority=priority,
            policy=policy,
            include_archived=include_archived,
            limit=limit,
        )
        return ToolOutcome(_pretty_json({"count": len(matches), "sources": matches}))

    def _tool_version_capabilities(self, args: dict[str, Any]) -> ToolOutcome:
        version_arg = args.get("version")
        if version_arg is not None and not isinstance(version_arg, str):
            raise ValueError("'version' must be a string.")
        requested = version_arg.strip() if isinstance(version_arg, str) and version_arg.strip() else None

        type_filter = args.get("type")
        if type_filter is not None:
            if not isinstance(type_filter, str) or type_filter not in {"release", "snapshot", "old_beta", "old_alpha"}:
                raise ValueError("'type' must be release, snapshot, old_beta, or old_alpha.")

        limit = _parse_bounded_int(args.get("limit"), field="limit", default=15, minimum=1, maximum=100)

        catalog = self.store.version_catalog()
        cap_doc = self.store.release_capabilities()
        latest = catalog.get("latest", {})
        versions = catalog.get("versions", [])
        details = catalog.get("details", {})
        cap_by_id = {
            item["id"]: item
            for item in cap_doc.get("releases", [])
            if isinstance(item, dict) and isinstance(item.get("id"), str)
        }

        if requested:
            target_id = requested
            if requested.lower() == "latest":
                target_id = str(latest.get("release", ""))
            elif requested.lower() == "latest-snapshot":
                target_id = str(latest.get("snapshot", ""))

            entry = next((v for v in versions if isinstance(v, dict) and v.get("id") == target_id), None)
            if entry is None:
                lower = target_id.casefold()
                suggestions = [
                    v["id"] for v in versions
                    if isinstance(v, dict) and isinstance(v.get("id"), str) and lower in v["id"].casefold()
                ][:10]
                return ToolOutcome(
                    _pretty_json({
                        "error": f"Version '{requested}' was not found in the Minecraft version catalog.",
                        "latest": latest,
                        "suggestions": suggestions,
                        "profiled_release_ids": sorted(cap_by_id),
                    }),
                    is_error=True,
                )

            payload = {
                "requested": requested,
                "resolved_id": target_id,
                "latest": latest,
                "version": entry,
                "hydrated_detail": details.get(target_id),
                "release_capabilities": cap_by_id.get(target_id),
                "profiled_release_ids": sorted(cap_by_id),
            }
            return ToolOutcome(_pretty_json(payload))

        recent = [
            v for v in versions
            if isinstance(v, dict) and (type_filter is None or v.get("type") == type_filter)
        ][:limit]
        payload = {
            "latest": latest,
            "version_count": catalog.get("version_count", len(versions)),
            "counts_by_type": catalog.get("counts_by_type", {}),
            "hydrated_version_ids": sorted(details),
            "profiled_releases": list(cap_by_id.values()),
            "recent_versions": recent,
        }
        return ToolOutcome(_pretty_json(payload))

    def _tool_route_skill(self, args: dict[str, Any]) -> ToolOutcome:
        task = args.get("task")
        if not isinstance(task, str) or not task.strip():
            raise ValueError("'task' must be a non-empty string.")
        include_checklist = args.get("include_checklist", True)
        if not isinstance(include_checklist, bool):
            raise ValueError("'include_checklist' must be a boolean.")

        normalized = task.casefold()
        words = set(re.findall(r"[a-z0-9_.:/-]+", normalized))
        domains = self.store.domain_catalog().get("domains", [])

        scored: list[dict[str, Any]] = []
        for domain in domains:
            domain_id = str(domain["id"])
            matched: list[str] = []
            score = 0

            if f"mc:{domain_id}" in normalized or f"/mc:{domain_id}" in normalized or f"mc-{domain_id}" in normalized:
                score += 10
                matched.append(f"mc:{domain_id}")

            for kw in domain.get("keywords", []):
                kw_low = str(kw).casefold()
                if " " in kw_low or "." in kw_low or "-" in kw_low:
                    if kw_low in normalized:
                        score += 4
                        matched.append(str(kw))
                elif kw_low in words or re.search(rf"\b{re.escape(kw_low)}s?\b", normalized):
                    score += 2
                    matched.append(str(kw))

            for syn in DOMAIN_SYNONYM_HINTS.get(domain_id, ()):
                if syn in matched:
                    continue
                if " " in syn or "." in syn:
                    if syn in normalized:
                        score += 3
                        matched.append(syn)
                elif syn in words or re.search(rf"\b{re.escape(syn)}s?\b", normalized):
                    score += 2
                    matched.append(syn)

            scored.append({
                "id": domain_id,
                "route": domain["route"],
                "slash_command": f"/{domain['route']}",
                "skill_directory": domain["skill_directory"],
                "name": domain["name"],
                "reference": domain["reference"],
                "score": score,
                "matched_signals": sorted(set(matched)),
            })

        scored.sort(key=lambda item: (-item["score"], 0 if item["id"] == "core" else 1, item["id"]))
        primary = scored[0]
        fallback_used = primary["score"] == 0
        if fallback_used:
            primary = next(item for item in scored if item["id"] == "core")
        secondary = [item for item in scored if item["id"] != primary["id"] and item["score"] > 0][:3]

        references: list[str] = [primary["reference"]]
        for extra in secondary:
            if extra["reference"] not in references:
                references.append(extra["reference"])

        active_ids = {primary["id"], *(item["id"] for item in secondary)}
        if "build" in active_ids:
            for ref in (
                "references/kotlin-java-gradle.md",
                "references/database-config-and-runtime.md",
                "references/release-publishing-checklist.md",
            ):
                if ref not in references:
                    references.append(ref)
        if "rpg" in active_ids:
            for ref in ("references/api-lookup.md", "references/plugin-routing-index.md"):
                if ref not in references:
                    references.append(ref)
        if "references/compatibility-and-safety.md" not in references:
            references.append("references/compatibility-and-safety.md")

        payload: dict[str, Any] = {
            "task": task.strip(),
            "fallback_to_core": fallback_used,
            "primary_route": primary,
            "secondary_routes": secondary,
            "recommended_references": references,
        }
        if include_checklist:
            route_steps = self.store.extract_route_workflow(primary["skill_directory"])
            payload["contract_checklist"] = [
                "Pin exact Minecraft edition, release version, Java major version, and protocol/pack format.",
                "Identify server/proxy/loader runtime (Paper, Folia, Purpur, Velocity, Fabric, NeoForge).",
                "Separate vanilla-client server projections from required client-side mods or resource packs.",
                "Prefer stable public APIs before escalating to packet libraries or version-isolated NMS.",
                "Define scheduler/region thread ownership, persistence lifecycle, reload safety, and failure fallbacks.",
            ]
            if route_steps:
                payload["route_workflow"] = route_steps

        return ToolOutcome(_pretty_json(payload))

    def _tool_folia_migration_advisor(self, args: dict[str, Any]) -> ToolOutcome:
        snippet = args.get("code_or_symbol")
        if not isinstance(snippet, str) or not snippet.strip():
            raise ValueError("'code_or_symbol' must be a non-empty string.")
        lower = snippet.casefold()

        rules: tuple[tuple[str, str, tuple[str, ...], str, str], ...] = (
            (
                "FOLIA-001",
                "high",
                ("getscheduler(", "bukkitscheduler", "runtask", "schedulesync"),
                "Legacy BukkitScheduler / Server.getScheduler() assumes a single global main thread and throws UnsupportedOperationException on Folia.",
                "Route entity-bound work to entity.getScheduler().run(plugin, task, retired), chunk/block work to Bukkit.getRegionScheduler().execute(plugin, location, task), global console/weather work to Bukkit.getGlobalRegionScheduler(), and non-world I/O to Bukkit.getAsyncScheduler().",
            ),
            (
                "FOLIA-002",
                "high",
                ("bukkitrunnable",),
                "BukkitRunnable delegates directly to legacy BukkitScheduler methods that fail at runtime on Folia.",
                "Replace BukkitRunnable with Consumer<ScheduledTask> lambdas scheduled on EntityScheduler, RegionScheduler, GlobalRegionScheduler, or AsyncScheduler, calling ScheduledTask.cancel() to stop repeating tasks.",
            ),
            (
                "FOLIA-003",
                "high",
                (".teleport(", "entity.teleport"),
                "Synchronous Entity.teleport(...) fails on Folia when source and destination chunks belong to different tick regions.",
                "Use entity.teleportAsync(destinationLocation).thenAccept(success -> ...) and run follow-up entity mutations on entity.getScheduler().",
            ),
            (
                "FOLIA-004",
                "medium",
                ("getentities(", "getlivingentities(", "getonlineplayers("),
                "Iterating world-wide entity or player collections and mutating entities directly crosses independent Folia tick regions.",
                "Snapshot references safely and dispatch per-entity state changes onto each target's entity.getScheduler().run(plugin, task, null).",
            ),
            (
                "FOLIA-005",
                "high",
                ("settype(", "setblockdata(", "getchunkat(", "chunk.load"),
                "Mutating blocks or loading chunks from AsyncScheduler or another entity's region triggers TickThread.ensureTickThread failures.",
                "Use world.getChunkAtAsync(x, z) or dispatch block mutations via Bukkit.getRegionScheduler().execute(plugin, targetLocation, () -> ...).",
            ),
            (
                "FOLIA-006",
                "medium",
                ("dispatchcommand(", "consolesender", "setstorm(", "settime("),
                "Global server commands, weather, time, and scoreboard/world-border mutations belong to Folia's GlobalRegionScheduler rather than chunk regions.",
                "Schedule via Bukkit.getGlobalRegionScheduler().execute(plugin, () -> Bukkit.dispatchCommand(...)).",
            ),
            (
                "FOLIA-007",
                "medium",
                ("new hashmap", "hashmap<", "new arraylist", "hashset<"),
                "Unprotected HashMap/HashSet/ArrayList fields shared across event handlers race concurrently under Folia's parallel region threads.",
                "Use ConcurrentHashMap, ConcurrentHashMap.newKeySet(), AtomicLong, or immutable snapshots for cross-region plugin state.",
            ),
            (
                "FOLIA-008",
                "low",
                ("plugin.yml", "paper-plugin.yml", "folia-supported"),
                "Folia refuses to load plugin JARs unless folia-supported: true is declared in plugin.yml or paper-plugin.yml.",
                "Add 'folia-supported: true' to plugin.yml / paper-plugin.yml and audit compiled bytecode with https://github.com/SalyyS1/foliascan.",
            ),
        )

        findings: list[dict[str, str]] = []
        for rule_id, severity, triggers, problem, replacement in rules:
            if any(trig in lower for trig in triggers):
                if rule_id == "FOLIA-003" and "teleportasync" in lower and ".teleport(" not in lower:
                    continue
                findings.append({
                    "rule_id": rule_id,
                    "severity": severity,
                    "problem": problem,
                    "folia_replacement": replacement,
                })

        if not findings:
            findings.append({
                "rule_id": "FOLIA-GEN",
                "severity": "info",
                "problem": "No direct legacy scheduler or sync teleport token matched in snippet; verify transitive call-graph region ownership.",
                "folia_replacement": "Ensure folia-supported: true is set and run bytecode taint analysis with SalyyS1/foliascan before shipping.",
            })

        return ToolOutcome(_pretty_json({
            "input_preview": snippet.strip()[:200],
            "finding_count": len(findings),
            "findings": findings,
            "bytecode_verifier": "https://github.com/SalyyS1/foliascan",
        }))

    def _tool_diagnose_server_log(self, args: dict[str, Any]) -> ToolOutcome:
        log_text = args.get("log_text")
        if not isinstance(log_text, str) or not log_text.strip():
            raise ValueError("'log_text' must be a non-empty string.")
        lower = log_text.casefold()
        diagnoses: list[dict[str, Any]] = []

        # Extract non-core plugin stack frames
        frames = re.findall(r"at\s+([a-zA-Z0-9_.$]+)\.([a-zA-Z0-9_$<>]+)\(([^)]+)\)", log_text)
        plugin_frames = [
            f"{cls}.{meth}({src})"
            for cls, meth, src in frames
            if not cls.startswith((
                "java.", "javax.", "jdk.", "sun.", "kotlin.",
                "net.minecraft.", "org.bukkit.", "org.spigotmc.",
                "io.papermc.", "ca.spottedleaf.", "com.mojang.", "io.netty.",
            ))
        ][:5]

        if "thread failed main thread check" in lower or "ensuretickthread" in lower or "unsupportedoperationexception" in lower and "folia" in lower:
            diagnoses.append({
                "category": "folia_region_violation",
                "severity": "critical",
                "summary": "Off-region or legacy main-thread access violated Folia's TickThread region ownership guard.",
                "suspect_plugin_frames": plugin_frames,
                "remediation": "Dispatch entity mutations onto entity.getScheduler(), block/chunk mutations onto Bukkit.getRegionScheduler(), and audit the plugin JAR with https://github.com/SalyyS1/foliascan.",
            })

        ver_match = re.search(r"class file version (\d+)\.\d+", log_text)
        if "unsupportedclassversionerror" in lower or ver_match:
            major = int(ver_match.group(1)) if ver_match else None
            java_ver = (major - 44) if major and major >= 52 else None
            diagnoses.append({
                "category": "java_bytecode_mismatch",
                "severity": "critical",
                "summary": (
                    f"Plugin JAR was compiled for class file major {major} (Java {java_ver}), which is newer than the server JVM."
                    if java_ver
                    else "Plugin bytecode major version exceeds the running JVM runtime."
                ),
                "suspect_plugin_frames": plugin_frames,
                "remediation": f"Upgrade the server container/host JVM to Java {java_ver or 21}+ or set Gradle java.toolchain.languageVersion properly.",
            })

        if any(tok in lower for tok in ("classnotfoundexception", "noclassdeffounderror", "linkageerror", "loader constraint violation")):
            diagnoses.append({
                "category": "classloader_or_shading_conflict",
                "severity": "high",
                "summary": "Missing dependency or isolated classloader / un-relocated shaded library collision.",
                "suspect_plugin_frames": plugin_frames,
                "remediation": "Verify paper-plugin.yml dependencies declare join-classpath: true when accessing another plugin's classes, relocate shaded libraries in Gradle shadowJar, and inspect the JAR with https://github.com/SalyyS1/pluginscope.",
            })

        if any(tok in lower for tok in ("do not report this to paper", "server thread dump", "can't keep up!", "hikaripool", "sync chunk load")):
            diagnoses.append({
                "category": "tick_stall_or_blocking_io",
                "severity": "high",
                "summary": "Synchronous I/O, JDBC pool exhaustion, or main-thread chunk loading stalled server tick execution.",
                "suspect_plugin_frames": plugin_frames,
                "remediation": "Move JDBC/HTTP calls to AsyncScheduler / CompletableFuture, switch sync chunk loads to getChunkAtAsync, and inspect full server logs with https://github.com/SalyyS1/serverdoctor.",
            })

        if "not marked as supporting folia" in lower:
            diagnoses.append({
                "category": "missing_folia_descriptor",
                "severity": "high",
                "summary": "Plugin descriptor omits 'folia-supported: true', causing Folia to reject loading it.",
                "suspect_plugin_frames": plugin_frames,
                "remediation": "Add 'folia-supported: true' to plugin.yml or paper-plugin.yml only after verifying scheduler safety with FoliaScan.",
            })

        if not diagnoses:
            diagnoses.append({
                "category": "unclassified_log",
                "severity": "info",
                "summary": "No fatal Folia, bytecode version, classloader, or watchdog stall signature matched.",
                "suspect_plugin_frames": plugin_frames,
                "remediation": "Include the full Caused by stack trace or inspect server configuration with SalyyS1/serverdoctor.",
            })

        return ToolOutcome(_pretty_json({
            "diagnosis_count": len(diagnoses),
            "suspect_plugin_frames": plugin_frames,
            "diagnoses": diagnoses,
        }))

    def _tool_inspect_type(self, args: dict[str, Any]) -> ToolOutcome:
        raw_type = args.get("type_name")
        if not isinstance(raw_type, str) or not raw_type.strip():
            raise ValueError("'type_name' must be a non-empty string.")
        query = raw_type.strip()

        plugin_arg = args.get("plugin")
        if plugin_arg is not None and not isinstance(plugin_arg, str):
            raise ValueError("'plugin' must be a string.")
        plugin_filter = plugin_arg.strip() if isinstance(plugin_arg, str) and plugin_arg.strip() else None

        if ":" in query and plugin_filter is None:
            maybe_plugin, _, remainder = query.partition(":")
            if maybe_plugin.strip() and remainder.strip():
                plugin_filter = maybe_plugin.strip()
                query = remainder.strip()

        query = query.replace("/", ".")
        q_low = query.casefold()

        member_filter_raw = args.get("member_filter")
        if member_filter_raw is not None and not isinstance(member_filter_raw, str):
            raise ValueError("'member_filter' must be a string.")
        member_needle = member_filter_raw.strip().casefold() if isinstance(member_filter_raw, str) and member_filter_raw.strip() else None

        public_only = args.get("public_only", True)
        if not isinstance(public_only, bool):
            raise ValueError("'public_only' must be a boolean.")

        include_synthetic = args.get("include_synthetic", False)
        if not isinstance(include_synthetic, bool):
            raise ValueError("'include_synthetic' must be a boolean.")

        member_limit = _parse_bounded_int(
            args.get("member_limit"),
            field="member_limit",
            default=100,
            minimum=1,
            maximum=500,
        )

        graph = self.store.class_graph()
        candidates: list[dict[str, Any]] = list(graph["by_fqcn_lower"].get(q_low, []))
        if not candidates:
            candidates = list(graph["by_simple_lower"].get(q_low, []))
        if not candidates:
            suffix = "." + q_low
            candidates = [
                cls for cls in graph["all_classes"]
                if str(cls.get("name", "")).casefold().endswith(suffix)
            ]

        if plugin_filter:
            p_low = plugin_filter.casefold()
            candidates = [cls for cls in candidates if str(cls.get("plugin", "")).casefold() == p_low]

        if not candidates:
            suggestions: list[dict[str, str]] = []
            for cls in graph["all_classes"]:
                if plugin_filter and str(cls.get("plugin", "")).casefold() != plugin_filter.casefold():
                    continue
                if cls.get("origin", "plugin-owned") != "plugin-owned":
                    continue
                fqcn = str(cls.get("name", ""))
                if q_low in fqcn.casefold():
                    suggestions.append({
                        "plugin": str(cls.get("plugin", "")),
                        "name": fqcn,
                        "kind": str(cls.get("kind", "class")),
                    })
                    if len(suggestions) >= 12:
                        break
            return ToolOutcome(
                _pretty_json({
                    "error": f"Type '{raw_type}' was not found in indexed plugin bytecode.",
                    "plugin_filter": plugin_filter,
                    "suggestions": suggestions,
                }),
                is_error=True,
            )

        candidates.sort(
            key=lambda c: (
                0 if c.get("origin", "plugin-owned") == "plugin-owned" else 1,
                0 if c.get("visibility") == "public" else 1,
                str(c.get("name", "")).count("."),
                str(c.get("plugin", "")),
                str(c.get("name", "")),
            )
        )
        selected = candidates[0]
        other_candidates = [
            {
                "plugin": str(c.get("plugin", "")),
                "name": str(c.get("name", "")),
                "kind": str(c.get("kind", "class")),
                "origin": str(c.get("origin", "plugin-owned")),
            }
            for c in candidates[1:15]
        ]

        fqcn = str(selected.get("name", ""))
        major = selected.get("major_version")
        min_java = (major - 44) if isinstance(major, int) and major >= 52 else None

        raw_subtypes = list(graph["subtypes"].get(fqcn.casefold(), []))
        raw_subtypes.sort(
            key=lambda s: (
                0 if s.get("origin") == "plugin-owned" else 1,
                s.get("plugin", ""),
                s.get("name", ""),
            )
        )

        constructors: list[dict[str, Any]] = []
        methods: list[dict[str, Any]] = []
        fields: list[dict[str, Any]] = []

        raw_members = selected.get("members") or []
        matched_total = 0
        for m in raw_members:
            if not include_synthetic and (m.get("synthetic") or m.get("bridge")):
                continue
            vis = str(m.get("visibility", ""))
            if public_only and vis not in {"public", "protected"}:
                continue
            m_name = str(m.get("name", ""))
            ret_type = str(m.get("return_type", ""))
            params = [str(p) for p in (m.get("parameters") or [])]
            throws = [str(t) for t in (m.get("throws") or [])]
            sig_haystack = f"{m_name} {ret_type} {' '.join(params)} {' '.join(throws)}".casefold()
            if member_needle and member_needle not in sig_haystack:
                continue

            matched_total += 1
            m_kind = str(m.get("kind", "method"))
            formatted: dict[str, Any] = {
                "name": m_name,
                "visibility": vis,
                "modifiers": list(m.get("modifiers") or []),
                "return_type": ret_type,
                "parameters": params,
            }
            if throws:
                formatted["throws"] = throws
            if m.get("generic_signature"):
                formatted["generic_signature"] = m["generic_signature"]
            if m.get("deprecated"):
                formatted["deprecated"] = True
            if m.get("constant") is not None:
                formatted["constant"] = m["constant"]

            if m_kind == "constructor":
                if len(constructors) < member_limit:
                    constructors.append(formatted)
            elif m_kind == "field":
                formatted.pop("parameters", None)
                if len(fields) < member_limit:
                    fields.append(formatted)
            else:
                if len(methods) < member_limit:
                    methods.append(formatted)

        payload: dict[str, Any] = {
            "plugin": str(selected.get("plugin", "")),
            "id": str(selected.get("id", "")),
            "name": fqcn,
            "simple_name": str(selected.get("simple_name") or fqcn.rsplit(".", 1)[-1]),
            "package": str(selected.get("package", "")),
            "kind": str(selected.get("kind", "class")),
            "origin": str(selected.get("origin", "plugin-owned")),
            "visibility": str(selected.get("visibility", "")),
            "modifiers": list(selected.get("modifiers") or []),
            "deprecated": bool(selected.get("deprecated", False)),
            "major_version": major,
            "min_java_version": min_java,
            "super": selected.get("super"),
            "interfaces": list(selected.get("interfaces") or []),
            "generic_signature": selected.get("generic_signature"),
            "known_subtype_count": len(raw_subtypes),
            "known_subtypes": raw_subtypes[:50],
            "member_counts": {
                "total_in_classfile": len(raw_members),
                "matched_after_filters": matched_total,
                "returned_constructors": len(constructors),
                "returned_methods": len(methods),
                "returned_fields": len(fields),
            },
            "constructors": constructors,
            "methods": methods,
            "fields": fields,
        }
        if other_candidates:
            payload["other_candidates"] = other_candidates
        return ToolOutcome(_pretty_json(payload))

    def _tool_audit_gradle_build(self, args: dict[str, Any]) -> ToolOutcome:
        build_script = args.get("build_script")
        if not isinstance(build_script, str) or not build_script.strip():
            raise ValueError("'build_script' must be a non-empty string.")

        descriptor_yaml = args.get("descriptor_yaml")
        if descriptor_yaml is not None and not isinstance(descriptor_yaml, str):
            raise ValueError("'descriptor_yaml' must be a string.")
        descriptor = descriptor_yaml.strip() if isinstance(descriptor_yaml, str) else ""

        target_mc_raw = args.get("target_mc_version")
        if target_mc_raw is not None and not isinstance(target_mc_raw, str):
            raise ValueError("'target_mc_version' must be a string.")

        cleaned_script = _strip_gradle_comments(build_script)
        script_low = cleaned_script.casefold()

        # Infer target Minecraft version
        detected_mc: str | None = target_mc_raw.strip() if isinstance(target_mc_raw, str) and target_mc_raw.strip() else None
        if detected_mc is None:
            mc_patterns = (
                r"paperDevBundle\s*\(\s*['\"]([0-9]+\.[0-9]+(?:\.[0-9]+)?)",
                r"(?:paper-api|folia-api|spigot-api|purpur-api):([0-9]+\.[0-9]+(?:\.[0-9]+)?)",
                r"api-version\s*:\s*['\"]?([0-9]+\.[0-9]+(?:\.[0-9]+)?)",
            )
            for pat in mc_patterns:
                m_ver = re.search(pat, cleaned_script + "\n" + descriptor, flags=re.IGNORECASE)
                if m_ver:
                    detected_mc = m_ver.group(1)
                    break

        mc_tuple = _parse_mc_version_tuple(detected_mc) if detected_mc else None
        findings: list[dict[str, Any]] = []

        # GRADLE-001: Server or external plugin API bundled via implementation/api/runtimeOnly
        bundled_apis: list[str] = []
        api_tokens = (
            "paper-api", "folia-api", "spigot-api", "purpur-api", "bukkit",
            "velocity-api", "bungeecord-api", "mmoitems", "mythicmobs",
            "modelengine", "mmocore", "placeholderapi", "vaultapi", "vault",
            "luckperms", "protocollib", "citizens", "packetevents-spigot",
        )
        dep_pattern = re.compile(
            r"\b(implementation|api|runtimeOnly|shadow)\s*(?:\(\s*)?['\"]([^'\"]+)['\"]",
            flags=re.IGNORECASE,
        )
        runtime_coords: list[str] = []
        for match in dep_pattern.finditer(cleaned_script):
            scope = match.group(1)
            coord = match.group(2)
            coord_low = coord.casefold()
            runtime_coords.append(coord_low)
            if any(tok in coord_low for tok in api_tokens):
                bundled_apis.append(f"{scope}(\"{coord}\")")

        if bundled_apis:
            findings.append({
                "rule_id": "GRADLE-001",
                "severity": "critical",
                "title": "Server or external plugin API bundled into runtime jar",
                "evidence": bundled_apis,
                "problem": (
                    "Declaring server or external plugin APIs with implementation/api bundles duplicate "
                    "server classes into the plugin jar and triggers LinkageError or ClassCastException at runtime."
                ),
                "remediation": "Switch server and external plugin dependencies to compileOnly(\"...\").",
            })

        # GRADLE-002: Runtime libraries bundled without shadowJar relocation
        relocatable_libs: tuple[tuple[str, str, str], ...] = (
            ("hikaricp", "com.zaxxer.hikari", "HikariCP"),
            ("sqlite-jdbc", "org.sqlite", "SQLite JDBC"),
            ("mysql-connector", "com.mysql", "MySQL Connector"),
            ("mariadb-java-client", "org.mariadb.jdbc", "MariaDB Connector"),
            ("jedis", "redis.clients", "Jedis"),
            ("bstats", "org.bstats", "bStats"),
            ("caffeine", "com.github.benmanes.caffeine", "Caffeine"),
            ("gson", "com.google.gson", "Gson"),
            ("jackson-", "com.fasterxml.jackson", "Jackson"),
            ("snakeyaml", "org.yaml.snakeyaml", "SnakeYAML"),
        )
        has_shadow = any(tok in script_low for tok in ("shadowjar", "com.gradleup.shadow", "johnrengelman.shadow"))
        auto_relocate = bool(re.search(r"\b(?:isEnableRelocation|enableRelocation)\s*(?:=|\s)\s*true\b", cleaned_script))
        relocated_prefixes = [
            m.group(1).casefold()
            for m in re.finditer(r"\brelocate\s*(?:\(\s*)?['\"]([^'\"]+)['\"]", cleaned_script)
        ]

        unrelocated: list[dict[str, str]] = []
        for token, pkg_prefix, label in relocatable_libs:
            if any(token in coord for coord in runtime_coords):
                if auto_relocate:
                    continue
                if not has_shadow or not any(
                    pkg_prefix.casefold().startswith(rel) or rel.startswith(pkg_prefix.casefold())
                    for rel in relocated_prefixes
                ):
                    unrelocated.append({"library": label, "package": pkg_prefix})

        if unrelocated:
            reloc_lines = "\n".join(
                f'    relocate("{item["package"]}", "your.plugin.shaded.{item["package"].split(".")[-1]}")'
                for item in unrelocated
            )
            findings.append({
                "rule_id": "GRADLE-002",
                "severity": "high",
                "title": "Shaded or implementation libraries missing package relocation",
                "evidence": unrelocated,
                "problem": (
                    "Bundling common third-party libraries without Shadow relocation causes cross-plugin "
                    "classpath collisions and NoSuchMethodError / LinkageError when another plugin loads a different version."
                ),
                "remediation": (
                    "Apply com.gradleup.shadow and relocate each shaded namespace inside tasks.shadowJar:\n"
                    f"tasks.shadowJar {{\n{reloc_lines}\n}}"
                ),
            })

        # GRADLE-003: Paperweight userdev mapping era mismatch
        has_paperweight = "paperweight" in script_low or "paperdevbundle" in script_low
        if has_paperweight and mc_tuple is not None:
            has_reobf = "reobfjar" in script_low or "reobf_production" in script_low
            has_mojang_prod = "mojang_production" in script_low
            is_paper_plugin_yml = "dependencies:" in descriptor and "server:" in descriptor
            if mc_tuple >= (26, 1, 0) and has_reobf:
                findings.append({
                    "rule_id": "GRADLE-003",
                    "severity": "high",
                    "title": "Legacy Spigot reobfuscation enabled on unobfuscated Minecraft 26.1+",
                    "evidence": [f"target_mc={detected_mc}"],
                    "problem": "Minecraft 26.1+ ships unobfuscated Mojang class and member names; reobfJar / REOBF_PRODUCTION is obsolete and breaks packaging.",
                    "remediation": "Remove reobfJar wiring and REOBF_PRODUCTION so artifacts remain Mojang-named.",
                })
            elif (1, 20, 5) <= mc_tuple < (26, 0, 0) and has_reobf and not has_mojang_prod and is_paper_plugin_yml:
                findings.append({
                    "rule_id": "GRADLE-003",
                    "severity": "medium",
                    "title": "Paper 1.20.5+ plugin using Spigot reobfuscation instead of MOJANG_PRODUCTION",
                    "evidence": [f"target_mc={detected_mc}"],
                    "problem": "Paper 1.20.5+ runs Mojang mappings at runtime; shipping REOBF_PRODUCTION forces Paper to remap your jar on every startup.",
                    "remediation": (
                        "Set paperweight.reobfArtifactConfiguration = "
                        "io.papermc.paperweight.userdev.ReobfArtifactConfiguration.MOJANG_PRODUCTION."
                    ),
                })

        # GRADLE-004: Java toolchain below required Minecraft runtime
        java_versions: list[int] = []
        for pat in (
            r"JavaLanguageVersion\.of\s*\(\s*(\d+)\s*\)",
            r"jvmToolchain\s*\(\s*(\d+)\s*\)",
            r"JavaVersion\.VERSION_(\d+)",
            r"sourceCompatibility\s*=\s*['\"]?(\d+)['\"]?",
        ):
            for jm in re.finditer(pat, cleaned_script):
                val = int(jm.group(1))
                if val > 0:
                    java_versions.append(val)

        if mc_tuple is not None and java_versions:
            required_java = _required_java_for_mc(mc_tuple)
            min_configured_java = min(java_versions)
            if min_configured_java < required_java:
                findings.append({
                    "rule_id": "GRADLE-004",
                    "severity": "high",
                    "title": "Java toolchain version is lower than target Minecraft requirement",
                    "evidence": [f"configured_java={min_configured_java}", f"required_java={required_java}", f"target_mc={detected_mc}"],
                    "problem": (
                        f"Minecraft {detected_mc} targets Java {required_java}+, while the build configures Java {min_configured_java}."
                    ),
                    "remediation": f"Set java.toolchain.languageVersion.set(JavaLanguageVersion.of({required_java})).",
                })

        # GRADLE-005 & GRADLE-006: Descriptor YAML checks (paper-plugin.yml / plugin.yml)
        if descriptor:
            if not re.search(r"(?m)^\s*api-version\s*:", descriptor):
                findings.append({
                    "rule_id": "GRADLE-006",
                    "severity": "medium",
                    "title": "Plugin descriptor omits api-version",
                    "evidence": ["missing api-version key"],
                    "problem": "Omitting api-version triggers Paper legacy material compatibility bytecode rewriting at server startup.",
                    "remediation": "Declare api-version: '1.21' (or your minimum supported release) in plugin.yml / paper-plugin.yml.",
                })

            if re.search(r"(?m)^dependencies\s*:", descriptor) and re.search(r"(?m)^\s+server\s*:", descriptor):
                missing_join: list[str] = []
                in_server_deps = False
                server_indent: int | None = None
                current_dep: str | None = None
                current_has_join = False

                for raw_line in descriptor.splitlines():
                    stripped_comment = re.sub(r"#.*$", "", raw_line).rstrip()
                    if not stripped_comment.strip():
                        continue
                    indent = len(stripped_comment) - len(stripped_comment.lstrip(" "))
                    content = stripped_comment.strip()

                    if re.match(r"^server\s*:$", content):
                        in_server_deps = True
                        server_indent = indent
                        continue

                    if in_server_deps and server_indent is not None:
                        if indent <= server_indent:
                            if current_dep and not current_has_join:
                                missing_join.append(current_dep)
                            current_dep = None
                            in_server_deps = False
                            continue

                        dep_header = re.match(r"^([A-Za-z0-9_.-]+)\s*:\s*$", content)
                        if dep_header and indent == server_indent + 2:
                            if current_dep and not current_has_join:
                                missing_join.append(current_dep)
                            current_dep = dep_header.group(1)
                            current_has_join = False
                        elif current_dep and re.match(r"^join-classpath\s*:\s*true\b", content, flags=re.IGNORECASE):
                            current_has_join = True

                if in_server_deps and current_dep and not current_has_join:
                    missing_join.append(current_dep)

                if missing_join:
                    findings.append({
                        "rule_id": "GRADLE-005",
                        "severity": "medium",
                        "title": "paper-plugin.yml server dependencies omit join-classpath: true",
                        "evidence": missing_join,
                        "problem": (
                            "Paper plugins run inside isolated ConfiguredPluginClassLoader instances; "
                            "referencing classes from a server dependency without join-classpath: true fails with ClassNotFoundException."
                        ),
                        "remediation": "Add 'join-classpath: true' under each server dependency whose Java API classes your plugin imports.",
                    })

        # GRADLE-007: Insecure HTTP Maven repository URLs
        insecure_urls = [
            m.group(0)
            for m in re.finditer(r"http://(?!localhost|127\.0\.0\.1)[a-zA-Z0-9._/-]+", cleaned_script)
        ]
        if insecure_urls:
            findings.append({
                "rule_id": "GRADLE-007",
                "severity": "low",
                "title": "Insecure http:// Maven repository URL",
                "evidence": insecure_urls,
                "problem": "Plain HTTP Maven repositories fail by default in Gradle 7+ and expose build artifacts to MITM tampering.",
                "remediation": "Switch Maven repository URLs to https://.",
            })

        counts = {"critical": 0, "high": 0, "medium": 0, "low": 0}
        for item in findings:
            sev = str(item.get("severity", "low"))
            if sev in counts:
                counts[sev] += 1

        return ToolOutcome(_pretty_json({
            "inferred_target_mc_version": detected_mc,
            "finding_count": len(findings),
            "severity_counts": counts,
            "status": "fail" if (counts["critical"] + counts["high"]) > 0 else ("warn" if len(findings) > 0 else "pass"),
            "findings": findings,
            "companion_jar_auditor": "https://github.com/SalyyS1/pluginscope",
        }))

    def _tool_audit_paper_plugin_yml(self, args: dict[str, Any]) -> ToolOutcome:
        raw_yaml = args.get("paper_plugin_yaml")
        if not isinstance(raw_yaml, str) or not raw_yaml.strip():
            raise ValueError("'paper_plugin_yaml' must be a non-empty string.")

        legacy_raw = args.get("legacy_plugin_yaml")
        if legacy_raw is not None and not isinstance(legacy_raw, str):
            raise ValueError("'legacy_plugin_yaml' must be a string.")

        require_folia = args.get("require_folia", False)
        if not isinstance(require_folia, bool):
            raise ValueError("'require_folia' must be a boolean.")

        parsed = _parse_paper_plugin_yaml(raw_yaml)
        legacy = _parse_legacy_plugin_yaml(legacy_raw) if isinstance(legacy_raw, str) and legacy_raw.strip() else None

        findings: list[dict[str, Any]] = []
        scalars = parsed["scalars"]
        raw_scalars = parsed["raw_scalars"]
        quoted_flags = parsed["quoted_flags"]
        root_keys = parsed["root_keys"]

        if parsed["has_tab_indentation"]:
            findings.append({
                "rule_id": "PAPER-001",
                "severity": "critical",
                "title": "Tab character used for YAML indentation",
                "evidence": ["leading '\\t' indentation detected"],
                "problem": "YAML 1.2 forbids tab characters for block indentation; SnakeYAML throws ScannerException when Paper loads paper-plugin.yml.",
                "remediation": "Replace all leading tab characters with 2-space indentation.",
            })

        # PAPER-001: Required root keys & valid plugin identifier
        required_keys = ("name", "version", "main", "api-version")
        missing_required = [k for k in required_keys if not scalars.get(k)]
        if missing_required:
            findings.append({
                "rule_id": "PAPER-001",
                "severity": "critical",
                "title": "Missing required paper-plugin.yml root attributes",
                "evidence": missing_required,
                "problem": "PaperPluginMeta requires name, version, main, and api-version to be non-empty strings at the root of paper-plugin.yml.",
                "remediation": "Declare name, version, main, and quoted api-version (for example: api-version: '1.21.4' or '26.2') at the root level.",
            })

        plugin_name = scalars.get("name", "")
        if plugin_name and re.fullmatch(r"[A-Za-z0-9_-]+", plugin_name) is None:
            findings.append({
                "rule_id": "PAPER-001",
                "severity": "critical",
                "title": "Invalid characters in plugin name",
                "evidence": [f"name={plugin_name!r}"],
                "problem": "Paper plugin names may only contain alphanumeric characters, underscores, and hyphens (^[A-Za-z0-9_-]+$).",
                "remediation": "Remove spaces or punctuation from 'name' and use 'prefix' or 'description' for display formatting.",
            })

        # PAPER-002: api-version validation (1.19..1.21.x and 26.1..26.x + YAML float truncation)
        api_ver = scalars.get("api-version", "")
        api_raw = raw_scalars.get("api-version", "")
        api_quoted = quoted_flags.get("api-version", False)
        required_java: int | None = None
        if api_ver:
            if not api_quoted and re.fullmatch(r"\d+\.\d*0", api_raw):
                truncated = api_raw.rstrip("0").rstrip(".")
                findings.append({
                    "rule_id": "PAPER-002",
                    "severity": "critical",
                    "title": "Unquoted api-version loses trailing zero under YAML float parsing",
                    "evidence": [f"api-version: {api_raw} -> parsed as float '{truncated}'"],
                    "problem": (
                        f"In YAML, unquoted '{api_raw}' is parsed by SnakeYAML as floating-point {truncated}, "
                        "causing PaperPluginMeta to reject the descriptor as an unsupported legacy version."
                    ),
                    "remediation": f"Quote the string value explicitly: api-version: '{api_raw}'.",
                })

            ver_match = re.fullmatch(r"(\d+)\.(\d+)(?:\.(\d+))?", api_ver)
            if ver_match is None:
                findings.append({
                    "rule_id": "PAPER-002",
                    "severity": "critical",
                    "title": "Malformed api-version string in paper-plugin.yml",
                    "evidence": [f"api-version={api_ver!r}"],
                    "problem": "Paper expects 'major.minor' or 'major.minor.patch' (e.g. '1.20.4', '1.21.4', '26.2', '26.3').",
                    "remediation": "Set a quoted release version such as api-version: '1.21.4' or api-version: '26.2'.",
                })
            else:
                v_maj, v_min, v_pat = int(ver_match.group(1)), int(ver_match.group(2)), int(ver_match.group(3) or 0)
                required_java = _required_java_for_mc((v_maj, v_min, v_pat))
                if (v_maj == 1 and v_min < 19) or v_maj < 1 or (1 < v_maj < 26):
                    findings.append({
                        "rule_id": "PAPER-002",
                        "severity": "critical",
                        "title": "Unsupported api-version for paper-plugin.yml",
                        "evidence": [f"api-version={api_ver}"],
                        "problem": (
                            "Paper introduced paper-plugin.yml in 1.19.3 (minimum api-version '1.19'); "
                            "supported eras are 1.19..1.21.x and Mojang's year-based 26.1+ releases."
                        ),
                        "remediation": "Set api-version to '1.20.1'+ (or '26.2' / '26.3' for Java 25 servers), or use legacy plugin.yml for <= 1.18.",
                    })

        # PAPER-003: Legacy plugin.yml keys mistakenly placed in paper-plugin.yml
        legacy_key_replacements = {
            "commands": "Register commands programmatically via LifecycleEvents.COMMANDS in PluginBootstrap or JavaPlugin.",
            "depend": "Move hard dependencies under dependencies.server.<Plugin> with required: true and load: BEFORE.",
            "softdepend": "Move optional dependencies under dependencies.server.<Plugin> with required: false.",
            "loadbefore": "Move reverse load-order edges under dependencies.server.<Plugin> with load: AFTER.",
            "libraries": "Implement io.papermc.paper.plugin.loader.PluginLoader (MavenLibraryResolver) and wire it via 'loader:'.",
        }
        illegal_present = [k for k in legacy_key_replacements if k in root_keys]
        if illegal_present:
            findings.append({
                "rule_id": "PAPER-003",
                "severity": "critical",
                "title": "Legacy plugin.yml keys are ignored or rejected in paper-plugin.yml",
                "evidence": illegal_present,
                "problem": (
                    "paper-plugin.yml does not support root 'commands', 'depend', 'softdepend', 'loadbefore', or 'libraries' "
                    "blocks; leaving them in paper-plugin.yml silently drops command registration, library downloads, or load order."
                ),
                "remediation": " ".join(legacy_key_replacements[k] for k in illegal_present),
            })

        # PAPER-004: main / bootstrapper / loader FQCN validation and lifecycle collision
        fqcn_pattern = re.compile(r"^[A-Za-z_$][A-Za-z0-9_$]*(?:\.[A-Za-z_$][A-Za-z0-9_$]*)+$")
        entrypoints = {
            role: scalars[role]
            for role in ("main", "bootstrapper", "loader")
            if scalars.get(role)
        }
        bad_fqcns: list[str] = []
        for role, fqcn in entrypoints.items():
            if fqcn.endswith(".class") or "/" in fqcn or fqcn_pattern.fullmatch(fqcn) is None:
                bad_fqcns.append(f"{role}={fqcn}")
        if bad_fqcns:
            findings.append({
                "rule_id": "PAPER-004",
                "severity": "critical",
                "title": "Invalid Java fully-qualified class name in entrypoint",
                "evidence": bad_fqcns,
                "problem": "Entrypoint classes must be dot-separated packaged Java class names without '.class' suffixes or '/' slashes.",
                "remediation": "Use valid packaged FQCNs such as 'com.example.myplugin.MyPlugin'.",
            })

        collisions: list[str] = []
        main_cls = entrypoints.get("main")
        boot_cls = entrypoints.get("bootstrapper")
        load_cls = entrypoints.get("loader")
        if main_cls and boot_cls and main_cls == boot_cls:
            collisions.append(f"main == bootstrapper ({main_cls})")
        if main_cls and load_cls and main_cls == load_cls:
            collisions.append(f"main == loader ({main_cls})")
        if boot_cls and load_cls and boot_cls == load_cls:
            collisions.append(f"bootstrapper == loader ({boot_cls})")
        if collisions:
            findings.append({
                "rule_id": "PAPER-004",
                "severity": "critical",
                "title": "Colliding main, bootstrapper, or loader entrypoint classes",
                "evidence": collisions,
                "problem": (
                    "Paper instantiates PluginLoader and PluginBootstrap before Bukkit server state exists; "
                    "pointing them at a JavaPlugin main class triggers class-initialization failures at boot."
                ),
                "remediation": "Isolate PluginBootstrap and PluginLoader in dedicated classes that do not extend JavaPlugin or touch Bukkit statics.",
            })

        # PAPER-005 & PAPER-006: Dependency graph & classloader audit
        bootstrap_deps: dict[str, dict[str, Any]] = parsed["dependencies"]["bootstrap"]
        server_deps: dict[str, dict[str, Any]] = parsed["dependencies"]["server"]

        known_java_api_plugins = {
            "modelengine", "mmoitems", "mmocore", "mmoinventory", "mmoprofiles",
            "mythiccrucible", "mythicdungeons", "mythicenchants", "mythicrpg", "coretools",
            "mythicmobs", "mythiclib", "placeholderapi", "vault", "luckperms",
            "protocollib", "packetevents", "worldguard", "worldedit", "citizens",
        }

        graph_errors: list[str] = []
        classpath_hazards: list[str] = []

        for section_name, section_map in (("bootstrap", bootstrap_deps), ("server", server_deps)):
            for dep_name, cfg in section_map.items():
                if plugin_name and dep_name.casefold() == plugin_name.casefold():
                    graph_errors.append(f"{section_name}.{dep_name}: self-dependency on '{plugin_name}'")
                raw_load = cfg["raw_load"]
                if raw_load not in {"BEFORE", "AFTER", "OMIT"}:
                    graph_errors.append(
                        f"{section_name}.{dep_name}.load={raw_load!r} (must be BEFORE, AFTER, or OMIT)"
                    )
                if cfg["invalid_bool_fields"]:
                    for bf in cfg["invalid_bool_fields"]:
                        graph_errors.append(f"{section_name}.{dep_name}.{bf} must be boolean true or false")
                if cfg["join_classpath"] is False and dep_name.casefold() in known_java_api_plugins:
                    classpath_hazards.append(
                        f"{section_name}.{dep_name} sets join-classpath: false (blocks Java API class visibility)"
                    )

        boot_by_low = {k.casefold(): (k, v) for k, v in bootstrap_deps.items()}
        for s_name, s_cfg in server_deps.items():
            b_entry = boot_by_low.get(s_name.casefold())
            if b_entry is not None:
                b_name, b_cfg = b_entry
                b_load = b_cfg["load"]
                s_load = s_cfg["load"]
                if {b_load, s_load} == {"BEFORE", "AFTER"}:
                    graph_errors.append(
                        f"Contradictory load order on '{s_name}': bootstrap.{b_name}.load={b_load} vs server.{s_name}.load={s_load}"
                    )

        if legacy is not None:
            server_by_low = {k.casefold(): (k, v) for k, v in server_deps.items()}
            missing_from_paper: list[str] = []
            for hard_dep in legacy["depend"]:
                s_entry = server_by_low.get(hard_dep.casefold())
                if s_entry is None:
                    missing_from_paper.append(f"depend:{hard_dep}")
                elif s_entry[1]["load"] == "AFTER":
                    graph_errors.append(
                        f"Dual-descriptor conflict on '{hard_dep}': plugin.yml 'depend' loads {hard_dep} BEFORE plugin, "
                        f"but paper-plugin.yml sets server.{s_entry[0]}.load=AFTER"
                    )
            for soft_dep in legacy["softdepend"]:
                if soft_dep.casefold() not in server_by_low:
                    missing_from_paper.append(f"softdepend:{soft_dep}")
            for lb_dep in legacy["loadbefore"]:
                s_entry = server_by_low.get(lb_dep.casefold())
                if s_entry is not None and s_entry[1]["load"] == "BEFORE":
                    graph_errors.append(
                        f"Dual-descriptor conflict on '{lb_dep}': plugin.yml 'loadbefore' loads plugin BEFORE {lb_dep}, "
                        f"but paper-plugin.yml sets server.{s_entry[0]}.load=BEFORE"
                    )
            if missing_from_paper:
                classpath_hazards.append(
                    "Dependencies in plugin.yml missing from paper-plugin.yml dependencies.server: "
                    + ", ".join(missing_from_paper)
                )

        if graph_errors:
            findings.append({
                "rule_id": "PAPER-005",
                "severity": "critical",
                "title": "Dependency graph schema or topological ordering conflict",
                "evidence": graph_errors,
                "problem": (
                    "Invalid dependency load modes, self-dependencies, or contradictory BEFORE/AFTER edges "
                    "cause Paper's cyclic plugin dependency resolver to abort startup."
                ),
                "remediation": (
                    "Ensure load is BEFORE (dependency loads before your plugin), AFTER (your plugin loads before dependency), "
                    "or OMIT, and keep bootstrap, server, and companion plugin.yml edges consistent."
                ),
            })

        if classpath_hazards:
            findings.append({
                "rule_id": "PAPER-006",
                "severity": "high",
                "title": "Isolated ConfiguredPluginClassLoader visibility hazard",
                "evidence": classpath_hazards,
                "problem": (
                    "When paper-plugin.yml is present, Paper ignores plugin.yml completely and isolates classloaders; "
                    "omitting a dependency from dependencies.server or setting join-classpath: false causes ClassNotFoundException."
                ),
                "remediation": (
                    "Declare every hooked external plugin under dependencies.server.<Plugin> with join-classpath: true."
                ),
            })

        open_cl_raw = scalars.get("has-open-classloader")
        has_open_classloader = open_cl_raw.lower() == "true" if isinstance(open_cl_raw, str) else False
        if has_open_classloader:
            findings.append({
                "rule_id": "PAPER-006",
                "severity": "low",
                "title": "has-open-classloader: true weakens Paper classloader isolation",
                "evidence": ["has-open-classloader: true"],
                "problem": "Opening the plugin classloader exposes internal shaded classes to legacy Spigot plugins on the shared classpath.",
                "remediation": "Keep has-open-classloader omitted (false) unless legacy plugins reflectively access your classes without declaring a dependency.",
            })

        # PAPER-007: Folia support validation
        folia_raw = scalars.get("folia-supported")
        folia_supported: bool | None = None
        if folia_raw is not None:
            if folia_raw.lower() == "true":
                folia_supported = True
            elif folia_raw.lower() == "false":
                folia_supported = False
            else:
                findings.append({
                    "rule_id": "PAPER-007",
                    "severity": "high",
                    "title": "Non-boolean folia-supported value",
                    "evidence": [f"folia-supported={folia_raw!r}"],
                    "problem": "Paper and Folia require folia-supported to be a YAML boolean (true or false).",
                    "remediation": "Set folia-supported: true once regionized scheduler compliance is verified.",
                })

        if require_folia and folia_supported is not True:
            findings.append({
                "rule_id": "PAPER-007",
                "severity": "high",
                "title": "Plugin does not declare folia-supported: true",
                "evidence": [f"folia-supported={folia_supported!r}"],
                "problem": "Folia refuses to load plugins whose descriptor omits folia-supported: true.",
                "remediation": (
                    "Audit schedulers and teleports with mc_folia_migration_advisor (or SalyyS1/foliascan) "
                    "and add 'folia-supported: true' to paper-plugin.yml."
                ),
            })

        counts = {"critical": 0, "high": 0, "medium": 0, "low": 0}
        for item in findings:
            sev = str(item.get("severity", "low"))
            if sev in counts:
                counts[sev] += 1

        load_before_us = sorted({
            dep for sec in (bootstrap_deps, server_deps)
            for dep, cfg in sec.items() if cfg["load"] == "BEFORE"
        })
        load_after_us = sorted({
            dep for sec in (bootstrap_deps, server_deps)
            for dep, cfg in sec.items() if cfg["load"] == "AFTER"
        })

        return ToolOutcome(_pretty_json({
            "plugin_meta": {
                "name": plugin_name or None,
                "version": scalars.get("version") or None,
                "api_version": api_ver or None,
                "required_java_version": required_java,
                "main": main_cls,
                "bootstrapper": boot_cls,
                "loader": load_cls,
                "folia_supported": bool(folia_supported),
                "has_open_classloader": has_open_classloader,
            },
            "dependency_graph": {
                "bootstrap": {
                    k: {
                        "load": v["load"],
                        "required": v["required"],
                        "join_classpath": v["join_classpath"],
                    }
                    for k, v in bootstrap_deps.items()
                },
                "server": {
                    k: {
                        "load": v["load"],
                        "required": v["required"],
                        "join_classpath": v["join_classpath"],
                    }
                    for k, v in server_deps.items()
                },
                "loads_before_this_plugin": load_before_us,
                "loads_after_this_plugin": load_after_us,
            },
            "finding_count": len(findings),
            "severity_counts": counts,
            "status": "fail" if (counts["critical"] + counts["high"]) > 0 else ("warn" if len(findings) > 0 else "pass"),
            "findings": findings,
        }))

    def _tool_generate_pack_overlay(self, args: dict[str, Any]) -> ToolOutcome:
        pack_type = args.get("pack_type", "resource")
        if pack_type not in {"resource", "data"}:
            raise ValueError("'pack_type' must be 'resource' or 'data'.")

        raw_min = args.get("min_version")
        if not isinstance(raw_min, str) or not raw_min.strip():
            raise ValueError("'min_version' must be a non-empty string.")
        raw_min = raw_min.strip()

        raw_max = args.get("max_version")
        if raw_max is not None and not isinstance(raw_max, str):
            raise ValueError("'max_version' must be a string.")

        if ".." in raw_min:
            if raw_max is not None and raw_max.strip():
                raise ValueError("Specify either 'min_version' with '..' range syntax or 'max_version', not both.")
            parts = raw_min.split("..")
            if len(parts) != 2 or not parts[0].strip() or not parts[1].strip():
                raise ValueError(f"Invalid version range '{raw_min}'; expected '<min>..<max>' (e.g. '1.20.1..26.2').")
            min_spec, max_spec = parts[0].strip(), parts[1].strip()
        else:
            min_spec = raw_min
            max_spec = raw_max.strip() if isinstance(raw_max, str) and raw_max.strip() else min_spec

        description = args.get("description", "Multi-version Minecraft pack")
        if not isinstance(description, str):
            raise ValueError("'description' must be a string.")

        auto_split = args.get("auto_split_epochs", False)
        if not isinstance(auto_split, bool):
            raise ValueError("'auto_split_epochs' must be a boolean.")

        raw_overlays = args.get("overlays")
        if raw_overlays is not None and not isinstance(raw_overlays, list):
            raise ValueError("'overlays' must be an array of overlay specifications.")

        dynamic_caps: dict[str, tuple[int, int | None]] = {}
        cap_field = "resource_pack" if pack_type == "resource" else "data_pack"
        for rel_entry in self.store.release_capabilities().get("releases", []):
            rel_id = rel_entry.get("id")
            fmt_obj = rel_entry.get(cap_field)
            if isinstance(rel_id, str) and isinstance(fmt_obj, dict) and isinstance(fmt_obj.get("major"), int):
                minor_val = fmt_obj.get("minor")
                dynamic_caps[rel_id] = (int(fmt_obj["major"]), int(minor_val) if isinstance(minor_val, int) else None)

        min_fmt = _resolve_pack_format(min_spec, pack_type=pack_type, dynamic_caps=dynamic_caps)
        max_fmt = _resolve_pack_format(max_spec, pack_type=pack_type, dynamic_caps=dynamic_caps)

        if _pack_format_sort_key(min_fmt, is_max=False) > _pack_format_sort_key(max_fmt, is_max=True):
            raise ValueError(
                f"min_version ({min_spec} -> {_format_pack_tuple(min_fmt)}) exceeds "
                f"max_version ({max_spec} -> {_format_pack_tuple(max_fmt)})."
            )

        last_pre_minor = 64 if pack_type == "resource" else 81
        multi_version_floor = 15

        if min_fmt[0] != max_fmt[0] and min_fmt[0] < multi_version_floor:
            raise ValueError(
                f"Multi-version {pack_type} packs cannot start below format {multi_version_floor} (Minecraft 1.20); "
                f"got {_format_pack_tuple(min_fmt)}."
            )

        pack_block: dict[str, Any] = {"description": description}
        if min_fmt[0] > last_pre_minor:
            format_era = "modern_minor_tuple"
            pack_block["min_format"] = _pack_format_to_json(min_fmt)
            pack_block["max_format"] = _pack_format_to_json(max_fmt)
        elif max_fmt[0] > last_pre_minor:
            format_era = "dual_era_hybrid"
            pack_block["pack_format"] = min_fmt[0]
            pack_block["supported_formats"] = [min_fmt[0], last_pre_minor]
            pack_block["min_format"] = _pack_format_to_json(min_fmt)
            pack_block["max_format"] = _pack_format_to_json(max_fmt)
        else:
            format_era = "pre_minor"
            pack_block["pack_format"] = min_fmt[0]
            if min_fmt[0] != max_fmt[0]:
                pack_block["supported_formats"] = [min_fmt[0], max_fmt[0]]
            pack_block["min_format"] = _pack_format_to_json(min_fmt)
            pack_block["max_format"] = _pack_format_to_json(max_fmt)

        overlay_specs: list[dict[str, str]] = []
        if raw_overlays is not None:
            for idx, item in enumerate(raw_overlays):
                if not isinstance(item, dict):
                    raise ValueError(f"overlays[{idx}] must be an object.")
                d_name = item.get("directory")
                ov_min = item.get("min_version")
                ov_max = item.get("max_version")
                if not isinstance(d_name, str) or not d_name.strip():
                    raise ValueError(f"overlays[{idx}].directory must be a non-empty string.")
                if re.fullmatch(r"[a-z0-9_-]+", d_name) is None:
                    raise ValueError(
                        f"Invalid overlay directory '{d_name}': Mojang OverlayMetadataSection allows only "
                        "lowercase ASCII letters, digits, underscores, and hyphens (^[a-z0-9_-]+$)."
                    )
                if not isinstance(ov_min, str) or not ov_min.strip():
                    raise ValueError(f"overlays[{idx}].min_version must be a non-empty string.")
                if ov_max is not None and not isinstance(ov_max, str):
                    raise ValueError(f"overlays[{idx}].max_version must be a string.")
                overlay_specs.append({
                    "directory": d_name,
                    "min_version": ov_min.strip(),
                    "max_version": ov_max.strip() if isinstance(ov_max, str) and ov_max.strip() else max_spec,
                })
        elif auto_split and min_fmt[0] < max_fmt[0]:
            epoch_defs = (
                _RESOURCE_BREAKING_EPOCHS if pack_type == "resource" else _DATA_BREAKING_EPOCHS
            )
            for directory, epoch_ver, _reason in epoch_defs:
                ep_fmt = _resolve_pack_format(epoch_ver, pack_type=pack_type, dynamic_caps=dynamic_caps)
                if min_fmt[0] < ep_fmt[0] <= max_fmt[0]:
                    overlay_specs.append({
                        "directory": directory,
                        "min_version": epoch_ver,
                        "max_version": max_spec,
                    })

        compiled_overlays: list[dict[str, Any]] = []
        seen_dirs: set[str] = set()
        for spec in overlay_specs:
            d_name = spec["directory"]
            if d_name in seen_dirs:
                raise ValueError(f"Duplicate overlay directory '{d_name}'.")
            seen_dirs.add(d_name)
            ov_min_fmt = _resolve_pack_format(spec["min_version"], pack_type=pack_type, dynamic_caps=dynamic_caps)
            ov_max_fmt = _resolve_pack_format(spec["max_version"], pack_type=pack_type, dynamic_caps=dynamic_caps)
            if _pack_format_sort_key(ov_min_fmt, is_max=False) > _pack_format_sort_key(ov_max_fmt, is_max=True):
                raise ValueError(
                    f"Overlay '{d_name}' min_version ({spec['min_version']}) exceeds max_version ({spec['max_version']})."
                )
            entry: dict[str, Any] = {"directory": d_name}
            if ov_min_fmt[0] > last_pre_minor:
                entry["min_format"] = _pack_format_to_json(ov_min_fmt)
                entry["max_format"] = _pack_format_to_json(ov_max_fmt)
            elif ov_max_fmt[0] > last_pre_minor:
                entry["formats"] = [ov_min_fmt[0], last_pre_minor]
                entry["min_format"] = _pack_format_to_json(ov_min_fmt)
                entry["max_format"] = _pack_format_to_json(ov_max_fmt)
            else:
                entry["formats"] = (
                    ov_min_fmt[0] if ov_min_fmt[0] == ov_max_fmt[0] else [ov_min_fmt[0], ov_max_fmt[0]]
                )
                entry["min_format"] = _pack_format_to_json(ov_min_fmt)
                entry["max_format"] = _pack_format_to_json(ov_max_fmt)
            compiled_overlays.append(entry)

        mcmeta: dict[str, Any] = {"pack": pack_block}
        if compiled_overlays:
            mcmeta["overlays"] = {"entries": compiled_overlays}

        root_subtree = "assets/<namespace>/" if pack_type == "resource" else "data/<namespace>/"
        directory_layout = ["pack.mcmeta", root_subtree] + [
            f"{entry['directory']}/{root_subtree}" for entry in compiled_overlays
        ]

        epoch_source = _RESOURCE_BREAKING_EPOCHS if pack_type == "resource" else _DATA_BREAKING_EPOCHS
        applicable_epochs: list[dict[str, Any]] = []
        for directory, epoch_ver, reason in epoch_source:
            ep_fmt = _resolve_pack_format(epoch_ver, pack_type=pack_type, dynamic_caps=dynamic_caps)
            if min_fmt[0] < ep_fmt[0] <= max_fmt[0]:
                applicable_epochs.append({
                    "introduced_in": epoch_ver,
                    "format_major": ep_fmt[0],
                    "suggested_overlay_directory": directory,
                    "breaking_change": reason,
                })

        return ToolOutcome(_pretty_json({
            "pack_type": pack_type,
            "format_era": format_era,
            "resolved_min_format": {"major": min_fmt[0], "minor": min_fmt[1]},
            "resolved_max_format": {"major": max_fmt[0], "minor": max_fmt[1]},
            "last_pre_minor_format": last_pre_minor,
            "pack_mcmeta": mcmeta,
            "pack_mcmeta_json": _pretty_json(mcmeta) + "\n",
            "directory_layout": directory_layout,
            "breaking_epochs_in_range": applicable_epochs,
        }))

    def _tool_audit_server_properties(self, args: dict[str, Any]) -> ToolOutcome:
        raw_props = args.get("server_properties")
        if not isinstance(raw_props, str) or not raw_props.strip():
            raise ValueError("'server_properties' must be a non-empty string.")

        raw_paper = args.get("paper_global_yaml")
        if raw_paper is not None and not isinstance(raw_paper, str):
            raise ValueError("'paper_global_yaml' must be a string.")

        raw_spigot = args.get("spigot_yaml")
        if raw_spigot is not None and not isinstance(raw_spigot, str):
            raise ValueError("'spigot_yaml' must be a string.")

        raw_jvm = args.get("jvm_args")
        if raw_jvm is not None and not isinstance(raw_jvm, str):
            raise ValueError("'jvm_args' must be a string.")

        behind_proxy = args.get("behind_proxy", "none")
        if behind_proxy not in {"none", "velocity", "bungeecord"}:
            raise ValueError("'behind_proxy' must be 'none', 'velocity', or 'bungeecord'.")

        expected_players = _parse_bounded_int(
            args.get("expected_players"),
            field="expected_players",
            default=50,
            minimum=1,
            maximum=5000,
        )
        cpu_cores = _parse_bounded_int(
            args.get("cpu_cores"),
            field="cpu_cores",
            default=4,
            minimum=1,
            maximum=512,
        )

        parsed_props = _parse_java_properties(raw_props)
        props: dict[str, str] = parsed_props["values"]
        duplicates: list[str] = parsed_props["duplicates"]

        paper_doc = _parse_nested_yaml_scalars(raw_paper) if isinstance(raw_paper, str) and raw_paper.strip() else None
        spigot_doc = _parse_nested_yaml_scalars(raw_spigot) if isinstance(raw_spigot, str) and raw_spigot.strip() else None
        jvm_text = raw_jvm.strip() if isinstance(raw_jvm, str) else ""

        findings: list[dict[str, Any]] = []

        def _prop_bool(key: str, default: bool) -> bool:
            val = props.get(key)
            if val is None:
                return default
            return val.strip().lower() == "true"

        def _prop_int(key: str, default: int) -> int:
            val = props.get(key)
            if val is None or not val.strip():
                return default
            try:
                return int(val.strip())
            except ValueError:
                findings.append({
                    "rule_id": "PROP-007",
                    "severity": "high",
                    "title": f"Non-integer value for server.properties '{key}'",
                    "evidence": [f"{key}={val!r}"],
                    "problem": f"Minecraft DedicatedServerProperties parses '{key}' as a 32-bit integer; malformed values fall back silently or fail startup.",
                    "remediation": f"Set '{key}' to a valid integer (for example: {key}={default}).",
                })
                return default

        online_mode = _prop_bool("online-mode", True)
        compression_threshold = _prop_int("network-compression-threshold", 256)
        view_distance = _prop_int("view-distance", 10)
        sim_distance = _prop_int("simulation-distance", 10)
        sync_chunk_writes = _prop_bool("sync-chunk-writes", True)
        enable_rcon = _prop_bool("enable-rcon", False)
        rcon_password = props.get("rcon.password", "")
        server_ip = props.get("server-ip", "").strip()
        pause_empty = _prop_int("pause-when-empty-seconds", 0)
        rp_url = props.get("resource-pack", "").strip()
        rp_sha1 = props.get("resource-pack-sha1", "").strip()
        rp_id = props.get("resource-pack-id", "").strip()

        paper_scalars = paper_doc["scalars"] if paper_doc else {}
        spigot_scalars = spigot_doc["scalars"] if spigot_doc else {}

        velocity_cfg_enabled = paper_scalars.get("proxies.velocity.enabled", "").lower() == "true"
        velocity_secret = paper_scalars.get("proxies.velocity.secret", "")
        bungee_cfg_enabled = spigot_scalars.get("settings.bungeecord", "").lower() == "true"

        effective_proxy = behind_proxy
        if effective_proxy == "none":
            if velocity_cfg_enabled:
                effective_proxy = "velocity"
            elif bungee_cfg_enabled:
                effective_proxy = "bungeecord"

        # PROP-001: Proxy authentication & forwarding security
        if velocity_cfg_enabled and bungee_cfg_enabled:
            findings.append({
                "rule_id": "PROP-001",
                "severity": "critical",
                "title": "Both Velocity modern forwarding and BungeeCord forwarding are enabled",
                "evidence": ["paper-global.yml: proxies.velocity.enabled=true", "spigot.yml: settings.bungeecord=true"],
                "problem": "Enabling both forwarding schemes creates conflicting login handshake state and breaks player authentication.",
                "remediation": "Disable settings.bungeecord in spigot.yml and keep only proxies.velocity.enabled: true with a strong HMAC secret.",
            })

        if effective_proxy == "none" and not online_mode:
            findings.append({
                "rule_id": "PROP-001",
                "severity": "critical",
                "title": "Unauthenticated offline mode enabled without a forwarding proxy",
                "evidence": ["online-mode=false", "behind_proxy=none"],
                "problem": "With online-mode=false and no authenticating proxy, any client can connect with an arbitrary username and spoof operator/admin accounts.",
                "remediation": "Set online-mode=true on standalone servers, or place the backend behind Velocity modern forwarding and bind server-ip=127.0.0.1.",
            })
        elif effective_proxy == "velocity":
            if online_mode:
                findings.append({
                    "rule_id": "PROP-001",
                    "severity": "high",
                    "title": "Backend online-mode=true conflicts with Velocity player forwarding",
                    "evidence": ["online-mode=true", "behind_proxy=velocity"],
                    "problem": "Velocity terminates Mojang session encryption at the proxy edge; leaving online-mode=true on the Paper backend rejects forwarded connections.",
                    "remediation": "Set online-mode=false in backend server.properties and enable proxies.velocity.enabled: true + proxies.velocity.online-mode: true in config/paper-global.yml.",
                })
            if paper_doc is not None:
                if not velocity_cfg_enabled:
                    findings.append({
                        "rule_id": "PROP-001",
                        "severity": "critical",
                        "title": "Velocity backend omits proxies.velocity.enabled: true in paper-global.yml",
                        "evidence": ["config/paper-global.yml: proxies.velocity.enabled is not true"],
                        "problem": "Running offline-mode behind Velocity without enabling Velocity modern forwarding leaves the backend open to UUID spoofing.",
                        "remediation": "Set proxies.velocity.enabled: true, proxies.velocity.online-mode: true, and a 32+ byte random proxies.velocity.secret in config/paper-global.yml.",
                    })
                elif len(velocity_secret.strip()) < 12:
                    findings.append({
                        "rule_id": "PROP-001",
                        "severity": "critical",
                        "title": "Empty or weak proxies.velocity.secret in paper-global.yml",
                        "evidence": [f"proxies.velocity.secret length={len(velocity_secret.strip())}"],
                        "problem": "Velocity modern forwarding relies on HMAC-SHA256 over the shared forwarding secret; an empty or short secret allows forged login payloads.",
                        "remediation": "Configure an identical random 32+ character secret in Velocity forwarding.secret and paper-global.yml proxies.velocity.secret.",
                    })
        elif effective_proxy == "bungeecord":
            if server_ip not in {"127.0.0.1", "::1", "localhost"}:
                findings.append({
                    "rule_id": "PROP-001",
                    "severity": "critical",
                    "title": "BungeeCord backend port is not restricted to loopback interface",
                    "evidence": [f"server-ip={server_ip or '0.0.0.0'}", "behind_proxy=bungeecord"],
                    "problem": "Legacy BungeeCord ip_forward carries no cryptographic signature; if the backend port is reachable directly, attackers can inject arbitrary UUIDs and IPs.",
                    "remediation": "Bind server-ip=127.0.0.1 (or enforce strict host firewall rules) or migrate to Velocity modern HMAC forwarding.",
                })

        # PROP-002: network-compression-threshold packet pipeline hazard
        if effective_proxy in {"velocity", "bungeecord"}:
            recommended_compression = -1
            if compression_threshold != -1:
                findings.append({
                    "rule_id": "PROP-002",
                    "severity": "high",
                    "title": "Redundant double zlib packet compression behind proxy",
                    "evidence": [f"network-compression-threshold={compression_threshold}", f"proxy={effective_proxy}"],
                    "problem": (
                        "When compression is enabled on both the Paper backend and the proxy, every chunk and entity "
                        "packet undergoes deflate -> proxy inflate -> proxy deflate, burning 15-30% extra Netty CPU and adding latency."
                    ),
                    "remediation": "Set network-compression-threshold=-1 in backend server.properties and keep compression (256 or 512) solely at the Velocity/proxy edge.",
                })
        else:
            recommended_compression = 512 if expected_players >= 100 else 256
            if 0 <= compression_threshold < 64:
                findings.append({
                    "rule_id": "PROP-002",
                    "severity": "high",
                    "title": "Sub-64-byte network-compression-threshold causes Netty CPU burn and header inflation",
                    "evidence": [f"network-compression-threshold={compression_threshold}"],
                    "problem": (
                        "Compressing tiny packets (< 64 bytes such as keepalives, entity head rotations, and movement deltas) "
                        "invokes zlib deflate on nearly every packet while often increasing wire size due to zlib framing overhead."
                    ),
                    "remediation": f"Set network-compression-threshold={recommended_compression} in server.properties.",
                })
            elif compression_threshold == -1 and expected_players >= 15:
                findings.append({
                    "rule_id": "PROP-002",
                    "severity": "medium",
                    "title": "Packet compression disabled on standalone server",
                    "evidence": ["network-compression-threshold=-1", f"expected_players={expected_players}"],
                    "problem": "Disabling packet compression on a direct internet-facing server sends full chunk section palettes uncompressed, multiplying outbound bandwidth 3-5x.",
                    "remediation": f"Set network-compression-threshold={recommended_compression} unless an upstream reverse proxy handles compression.",
                })
            elif compression_threshold > 1500:
                findings.append({
                    "rule_id": "PROP-002",
                    "severity": "low",
                    "title": "network-compression-threshold exceeds standard Ethernet MTU (1500 bytes)",
                    "evidence": [f"network-compression-threshold={compression_threshold}"],
                    "problem": "Thresholds above 1500 bytes leave multi-packet entity equipment and dialog bursts uncompressed across TCP segments.",
                    "remediation": f"Set network-compression-threshold={recommended_compression} (256-512 bytes).",
                })

        # PROP-003: Netty EventLoop thread sizing & direct memory bounds
        recommended_netty = max(4, min(max(cpu_cores * 2, 4), max(4, (expected_players + 39) // 40 * 2)))
        configured_netty: int | None = None
        netty_source: str | None = None

        jvm_netty_match = re.search(r"-Dio\.netty\.eventLoopThreads=(\d+)", jvm_text)
        if jvm_netty_match:
            configured_netty = int(jvm_netty_match.group(1))
            netty_source = f"-Dio.netty.eventLoopThreads={configured_netty}"
        elif "settings.netty-threads" in spigot_scalars:
            try:
                sp_netty = int(spigot_scalars["settings.netty-threads"])
                configured_netty = sp_netty
                netty_source = f"spigot.yml settings.netty-threads={sp_netty}"
            except ValueError:
                pass

        if configured_netty is not None:
            min_safe_netty = 2 if expected_players < 25 else max(4, min(cpu_cores, (expected_players + 74) // 75 * 2))
            if configured_netty <= 1 or configured_netty < min_safe_netty:
                findings.append({
                    "rule_id": "PROP-003",
                    "severity": "high",
                    "title": "Netty EventLoop thread pool is undersized for player concurrency",
                    "evidence": [netty_source or f"netty_threads={configured_netty}", f"expected_players={expected_players}", f"cpu_cores={cpu_cores}"],
                    "problem": (
                        "Netty EventLoop threads perform AES packet encryption, zlib deflate/inflate, and socket flushes. "
                        "Pinning Netty to 1 thread (or too few threads at scale) serializes network I/O and triggers keepalive timeouts."
                    ),
                    "remediation": f"Increase Netty EventLoop threads to {recommended_netty} (or remove the manual override so Netty scales automatically with CPU cores).",
                })
            elif configured_netty > max(32, cpu_cores * 4):
                findings.append({
                    "rule_id": "PROP-003",
                    "severity": "medium",
                    "title": "Netty EventLoop thread pool oversubscribes host CPU cores",
                    "evidence": [netty_source or f"netty_threads={configured_netty}", f"cpu_cores={cpu_cores}"],
                    "problem": "Excessive Netty worker threads increase OS scheduler context switches and per-thread PooledByteBufAllocator arena memory overhead.",
                    "remediation": f"Cap Netty EventLoop threads near {recommended_netty} for a {cpu_cores}-core host.",
                })

        direct_mem_match = re.search(r"-XX:MaxDirectMemorySize=([0-9]+[kKmMgGtT]?)", jvm_text)
        if direct_mem_match:
            direct_mb = _parse_jvm_memory_mb(direct_mem_match.group(1))
            if direct_mb is not None and direct_mb < max(256.0, expected_players * 2.5):
                findings.append({
                    "rule_id": "PROP-003",
                    "severity": "high",
                    "title": "MaxDirectMemorySize is too small for Netty off-heap ByteBuf arenas",
                    "evidence": [f"-XX:MaxDirectMemorySize={direct_mem_match.group(1)} ({direct_mb:.0f} MB)", f"expected_players={expected_players}"],
                    "problem": "Netty allocates off-heap direct ByteBuf arenas per EventLoop thread; starving MaxDirectMemorySize causes io.netty.util.internal.OutOfDirectMemoryError disconnects.",
                    "remediation": "Remove the restrictive -XX:MaxDirectMemorySize cap or raise it to at least 512M-2G.",
                })

        # PROP-004: Quadratic chunk/simulation budget & sync-chunk-writes
        view_chunks_per_player = (2 * max(2, view_distance) + 1) ** 2
        sim_chunks_per_player = (2 * max(2, sim_distance) + 1) ** 2

        if sim_distance > view_distance:
            findings.append({
                "rule_id": "PROP-004",
                "severity": "medium",
                "title": "simulation-distance exceeds view-distance",
                "evidence": [f"simulation-distance={sim_distance} ({sim_chunks_per_player} chunks/player)", f"view-distance={view_distance} ({view_chunks_per_player} chunks/player)"],
                "problem": "Ticking entities, crops, and block ticks beyond client view-distance consumes server tick time for chunks players cannot see.",
                "remediation": f"Set simulation-distance <= view-distance (recommended simulation-distance={min(view_distance, 8 if expected_players >= 50 else 10)}).",
            })
        elif sim_distance > 10 and expected_players >= 40:
            findings.append({
                "rule_id": "PROP-004",
                "severity": "high",
                "title": "Quadratic simulation-distance chunk budget risks tick-thread saturation",
                "evidence": [f"simulation-distance={sim_distance} ({sim_chunks_per_player} ticked chunks/player)", f"expected_players={expected_players}"],
                "problem": (
                    f"Chunk ticking scales quadratically as (2d + 1)^2: simulation-distance={sim_distance} ticks "
                    f"{sim_chunks_per_player} chunks per isolated player versus 289 chunks at simulation-distance=8."
                ),
                "remediation": "Lower simulation-distance to 6-8 for 40+ concurrent players while keeping view-distance at 10-12 via Paper's async Moonrise chunk sender.",
            })

        if "sync-chunk-writes" in props and sync_chunk_writes:
            findings.append({
                "rule_id": "PROP-004",
                "severity": "medium",
                "title": "sync-chunk-writes=true forces blocking disk flushes on chunk saves",
                "evidence": ["sync-chunk-writes=true"],
                "problem": "Enabling synchronous chunk writes serializes region file saves and degrades Paper/Folia Moonrise async chunk I/O throughput on Linux hosts.",
                "remediation": "Set sync-chunk-writes=false in server.properties.",
            })

        # PROP-005: RCON exposure & pause-when-empty-seconds
        if enable_rcon:
            if len(rcon_password) < 12:
                findings.append({
                    "rule_id": "PROP-005",
                    "severity": "critical",
                    "title": "RCON enabled with an empty or short password",
                    "evidence": ["enable-rcon=true", f"rcon.password length={len(rcon_password)}"],
                    "problem": "Minecraft RCON transmits console commands with root server privileges over unencrypted TCP; empty or short passwords permit trivial remote takeover.",
                    "remediation": "Disable RCON (enable-rcon=false) or set a 24+ character random rcon.password and bind RCON strictly to localhost/WireGuard.",
                })
        if pause_empty > 0:
            findings.append({
                "rule_id": "PROP-005",
                "severity": "low",
                "title": "pause-when-empty-seconds freezes server tick schedulers when 0 players are online",
                "evidence": [f"pause-when-empty-seconds={pause_empty}"],
                "problem": (
                    "Minecraft 1.21.2+ pauses tick execution after pause-when-empty-seconds with no players online, "
                    "stalling plugin repeating tasks, database maintenance jobs, web/Discord bridges, and automated CI probes."
                ),
                "remediation": "Set pause-when-empty-seconds=-1 (or 0) on dedicated multiplayer servers with background plugin tasks.",
            })

        # PROP-006: Resource-pack SHA-1, UUID & HTTPS delivery contract
        if rp_url:
            if rp_url.lower().startswith("http://") and not rp_url.lower().startswith(("http://127.0.0.1", "http://localhost")):
                findings.append({
                    "rule_id": "PROP-006",
                    "severity": "high",
                    "title": "Insecure plain-HTTP resource-pack download URL",
                    "evidence": [f"resource-pack={rp_url}"],
                    "problem": "Serving server resource packs over unencrypted HTTP exposes clients to MITM payload tampering and modern client download blocks.",
                    "remediation": "Host the resource pack over HTTPS on a CDN or static HTTPS endpoint.",
                })
            if re.fullmatch(r"[0-9a-fA-F]{40}", rp_sha1) is None:
                findings.append({
                    "rule_id": "PROP-006",
                    "severity": "high",
                    "title": "Missing or malformed 40-hex resource-pack-sha1 checksum",
                    "evidence": [f"resource-pack-sha1={rp_sha1!r}"],
                    "problem": "Without an exact 40-character SHA-1 digest, clients cannot verify archive integrity or invalidate stale cached packs reliably.",
                    "remediation": "Compute sha1sum of the exact published ZIP bytes and set resource-pack-sha1=<40-hex-digest>.",
                })
            if not rp_id or re.fullmatch(r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}", rp_id) is None:
                findings.append({
                    "rule_id": "PROP-006",
                    "severity": "medium",
                    "title": "Missing or invalid UUID in resource-pack-id",
                    "evidence": [f"resource-pack-id={rp_id!r}"],
                    "problem": "Minecraft 1.20.3+ identifies stacked server resource packs by UUID; omitting resource-pack-id derives a URL-based fallback that breaks clean pack replacement across CDN URLs.",
                    "remediation": "Assign a stable RFC 4122 UUID to resource-pack-id in server.properties.",
                })

        # PROP-007: Paper 26.3 schema & duplicate server.properties keys
        if duplicates:
            findings.append({
                "rule_id": "PROP-007",
                "severity": "medium",
                "title": "Duplicate keys in server.properties silently shadow earlier entries",
                "evidence": duplicates,
                "problem": "Java Properties.load overwrites duplicate keys with the last occurrence in the file, causing confusing configuration drift.",
                "remediation": "Remove duplicate property definitions so each key appears exactly once.",
            })

        if paper_doc is not None:
            raw_ver = paper_scalars.get("_version") or paper_scalars.get("version")
            if raw_ver is not None and raw_ver.lstrip("-").isdigit() and int(raw_ver) < 30:
                findings.append({
                    "rule_id": "PROP-007",
                    "severity": "medium",
                    "title": "Outdated Paper configuration schema version (< 30 for Paper 26.3)",
                    "evidence": [f"paper-global.yml version={raw_ver}"],
                    "problem": "Paper 26.3 uses global configuration schema version 30+; legacy config files miss modern item-validation and Moonrise chunk-system defaults.",
                    "remediation": "Boot Paper 26.3 once in staging to migrate config/paper-global.yml cleanly and remove obsolete keys.",
                })
            deprecated_roots = [k for k in ("timings", "chunk-loading", "messages") if k in paper_doc["root_keys"]]
            if deprecated_roots:
                findings.append({
                    "rule_id": "PROP-007",
                    "severity": "medium",
                    "title": "Deprecated legacy root sections present in paper-global.yml",
                    "evidence": deprecated_roots,
                    "problem": "Root 'timings' (replaced by built-in Spark profiler), 'chunk-loading' (replaced by 'chunk-system'), and legacy 'messages' blocks are obsolete in Paper 26.3.",
                    "remediation": "Remove obsolete root sections from config/paper-global.yml and use Spark (/spark) plus chunk-system.",
                })
            book_page_max = paper_scalars.get("item-validation.book-size.page-max")
            if book_page_max is not None and book_page_max.lstrip("-").isdigit() and (int(book_page_max) <= 0 or int(book_page_max) > 16384):
                findings.append({
                    "rule_id": "PROP-007",
                    "severity": "high",
                    "title": "Paper 26.3 item-validation book-size guard disabled or dangerously raised",
                    "evidence": [f"item-validation.book-size.page-max={book_page_max}"],
                    "problem": "Disabling or inflating Paper's item-validation book/component size limits exposes Netty decoders and chunk NBT storage to oversized book/component crash exploits.",
                    "remediation": "Keep item-validation.book-size.page-max at Paper's default (2560 bytes).",
                })

        # PROP-008: JVM Heap & GC startup flags
        if jvm_text:
            if "-XX:+UseConcMarkSweepGC" in jvm_text or "-XX:+CMSIncrementalMode" in jvm_text:
                findings.append({
                    "rule_id": "PROP-008",
                    "severity": "critical",
                    "title": "Removed CMS garbage collector flag aborts JVM startup on Java 17/21/25",
                    "evidence": ["-XX:+UseConcMarkSweepGC"],
                    "problem": "Concurrent Mark Sweep (CMS) was removed in JDK 14; passing -XX:+UseConcMarkSweepGC causes Java 21/25 to exit immediately on boot.",
                    "remediation": "Use Aikar's G1GC flags (-XX:+UseG1GC -XX:MaxGCPauseMillis=200) or Java 25 Generational ZGC (-XX:+UseZGC).",
                })
            if "-XX:+ZGenerational" in jvm_text or "-XX:-ZGenerational" in jvm_text:
                findings.append({
                    "rule_id": "PROP-008",
                    "severity": "medium",
                    "title": "Deprecated/removed ZGenerational JVM flag for Java 24/25+ (Paper 26.x)",
                    "evidence": ["-XX:+/-ZGenerational"],
                    "problem": "JEP 474 and JEP 490 made Generational ZGC the sole mode of -XX:+UseZGC and removed non-generational ZGC; ZGenerational prints deprecation/obsolescence warnings on Java 24/25+.",
                    "remediation": "Pass '-XX:+UseZGC' alone on Java 25+ without '-XX:+ZGenerational'.",
                })
            xms_m = re.search(r"-Xms([0-9]+[kKmMgGtT]?)", jvm_text)
            xmx_m = re.search(r"-Xmx([0-9]+[kKmMgGtT]?)", jvm_text)
            if xms_m and xmx_m:
                xms_mb = _parse_jvm_memory_mb(xms_m.group(1))
                xmx_mb = _parse_jvm_memory_mb(xmx_m.group(1))
                if xms_mb is not None and xmx_mb is not None and abs(xms_mb - xmx_mb) > 1.0:
                    findings.append({
                        "rule_id": "PROP-008",
                        "severity": "medium",
                        "title": "Mismatched -Xms and -Xmx heap bounds cause runtime heap-resize pauses",
                        "evidence": [f"-Xms{xms_m.group(1)}", f"-Xmx{xmx_m.group(1)}"],
                        "problem": "Setting -Xms lower than -Xmx forces the JVM to request and zero OS memory pages dynamically during GC spikes, causing multi-hundred-millisecond tick stalls.",
                        "remediation": f"Pin -Xms equal to -Xmx (for example: -Xms{xmx_m.group(1)} -Xmx{xmx_m.group(1)}).",
                    })

        counts = {"critical": 0, "high": 0, "medium": 0, "low": 0}
        for item in findings:
            sev = str(item.get("severity", "low"))
            if sev in counts:
                counts[sev] += 1

        moonrise_workers = max(1, min(16, (cpu_cores - 2) if cpu_cores > 4 else max(1, cpu_cores // 2)))
        est_kbps_per_player = 45 if recommended_compression == -1 and effective_proxy == "none" else 110
        if effective_proxy == "none" and compression_threshold == -1:
            est_kbps_per_player = 380

        return ToolOutcome(_pretty_json({
            "effective_proxy": effective_proxy,
            "parsed_property_count": len(props),
            "finding_count": len(findings),
            "severity_counts": counts,
            "status": "fail" if (counts["critical"] + counts["high"]) > 0 else ("warn" if len(findings) > 0 else "pass"),
            "tuning_recommendations": {
                "recommended_network_compression_threshold": recommended_compression,
                "recommended_netty_event_loop_threads": recommended_netty,
                "recommended_moonrise_worker_threads": moonrise_workers,
                "recommended_moonrise_io_threads": 2 if cpu_cores >= 4 else 1,
                "chunk_budget_per_player": {
                    "view_distance": view_distance,
                    "view_chunks_per_player": view_chunks_per_player,
                    "simulation_distance": sim_distance,
                    "ticked_chunks_per_player": sim_chunks_per_player,
                    "worst_case_ticked_chunks": sim_chunks_per_player * expected_players,
                },
                "estimated_outbound_mbps": round((expected_players * est_kbps_per_player * 8) / 1000.0, 2),
            },
            "findings": findings,
            "companion_server_auditor": "https://github.com/SalyyS1/serverdoctor",
        }))

    def _tool_validate_item_components(self, args: dict[str, Any]) -> ToolOutcome:
        raw_payload = args.get("payload")
        if isinstance(raw_payload, str):
            if not raw_payload.strip():
                raise ValueError("'payload' string must not be empty.")
            try:
                parsed_payload = _strict_loads(raw_payload)
            except (ValueError, json.JSONDecodeError) as exc:
                raise ValueError(f"'payload' is not valid JSON: {exc}") from exc
        elif isinstance(raw_payload, dict):
            parsed_payload = raw_payload
        else:
            raise ValueError("'payload' must be a JSON string or JSON object.")

        if not isinstance(parsed_payload, dict):
            raise ValueError("'payload' must decode to a JSON object.")

        target_version = args.get("target_version", "26.3")
        if not isinstance(target_version, str) or not target_version.strip():
            raise ValueError("'target_version' must be a non-empty string.")
        target_version = target_version.strip()
        mc_tuple = _parse_mc_version_tuple(target_version)
        if mc_tuple is None or (mc_tuple < (1, 20, 5)):
            raise ValueError(
                f"Structured item data components require Minecraft 1.20.5+ (for example '1.20.5', '1.21.4', '1.21.5', '26.2', '26.3'); got '{target_version}'."
            )

        raw_client_def = args.get("client_item_definition")
        client_def: dict[str, Any] | None = None
        if raw_client_def is not None:
            if isinstance(raw_client_def, str):
                if not raw_client_def.strip():
                    raise ValueError("'client_item_definition' string must not be empty.")
                try:
                    loaded_c = _strict_loads(raw_client_def)
                except (ValueError, json.JSONDecodeError) as exc:
                    raise ValueError(f"'client_item_definition' is not valid JSON: {exc}") from exc
                if not isinstance(loaded_c, dict):
                    raise ValueError("'client_item_definition' must decode to a JSON object.")
                client_def = loaded_c
            elif isinstance(raw_client_def, dict):
                client_def = raw_client_def
            else:
                raise ValueError("'client_item_definition' must be a JSON string or JSON object.")

        findings: list[dict[str, Any]] = []
        is_modern_1214 = mc_tuple >= (1, 21, 4)
        is_modern_1215 = mc_tuple >= (1, 21, 5)
        is_modern_1212 = mc_tuple >= (1, 21, 2)

        # Detect payload shape: client items/<id>.json vs item stack {id, count, components} vs direct component map
        is_standalone_client_def = (
            "model" in parsed_payload
            and isinstance(parsed_payload.get("model"), dict)
            and "id" not in parsed_payload
            and "components" not in parsed_payload
            and not any(k.startswith(("minecraft:", "!")) for k in parsed_payload)
        )

        components_map: dict[str, Any] = {}
        payload_kind = "component_map"

        if is_standalone_client_def:
            payload_kind = "client_item_definition"
            client_def = parsed_payload
        else:
            legacy_root_nbt = [k for k in ("tag", "Count", "Damage", "HideFlags", "CustomModelData") if k in parsed_payload]
            if legacy_root_nbt:
                findings.append({
                    "rule_id": "COMP-001",
                    "severity": "critical",
                    "title": "Legacy pre-1.20.5 item NBT keys detected at root",
                    "evidence": legacy_root_nbt,
                    "problem": (
                        "Minecraft 1.20.5 through 26.3+ removed raw 'tag', uppercase 'Count', 'HideFlags', and root 'Damage' "
                        "in favor of lowercase 'id', 'count', and structured 'components'."
                    ),
                    "remediation": "Migrate legacy NBT fields into 'components' (e.g. minecraft:custom_data, minecraft:custom_model_data, minecraft:tooltip_display).",
                })

            if "components" in parsed_payload or ("id" in parsed_payload and not any(k.startswith("minecraft:") for k in parsed_payload)):
                payload_kind = "item_stack"
                item_id = parsed_payload.get("id")
                if item_id is not None and (not isinstance(item_id, str) or _NAMESPACED_ID_RE.fullmatch(item_id) is None):
                    findings.append({
                        "rule_id": "COMP-001",
                        "severity": "critical",
                        "title": "Invalid item 'id' resource location",
                        "evidence": [f"id={item_id!r}"],
                        "problem": "Item stack 'id' must be a lowercase namespaced item identifier (for example 'minecraft:diamond_sword').",
                        "remediation": "Use a valid lowercase item registry ID.",
                    })
                raw_comps = parsed_payload.get("components", {})
                if not isinstance(raw_comps, dict):
                    findings.append({
                        "rule_id": "COMP-001",
                        "severity": "critical",
                        "title": "Item stack 'components' field must be an object",
                        "evidence": [f"components={type(raw_comps).__name__}"],
                        "problem": "DataComponentMap / DataComponentPatch serializes 'components' as a JSON object keyed by component ID.",
                        "remediation": "Set 'components' to a JSON object mapping 'minecraft:<component>' keys to typed values.",
                    })
                else:
                    components_map = raw_comps
            else:
                components_map = parsed_payload

        normalized_active: dict[str, Any] = {}
        cmd_counts: dict[str, int] | None = None

        removed_1215 = {
            "minecraft:hide_tooltip": "Replace with 'minecraft:tooltip_display': {'hide_tooltip': true}.",
            "minecraft:hide_additional_tooltip": "Replace with 'minecraft:tooltip_display': {'hidden_components': [...]}.",
        }

        def _looks_like_escaped_json_text(val: Any) -> bool:
            if not isinstance(val, str):
                return False
            s = val.strip()
            return (s.startswith("{") and s.endswith("}") and ('"text"' in s or '"translate"' in s or '"extra"' in s)) or (
                s.startswith("[") and s.endswith("]") and '"text"' in s
            )

        for raw_key, val in components_map.items():
            is_removal = raw_key.startswith("!")
            bare_key = raw_key[1:] if is_removal else raw_key
            if not bare_key or _NAMESPACED_ID_RE.fullmatch(bare_key) is None:
                findings.append({
                    "rule_id": "COMP-002",
                    "severity": "critical",
                    "title": "Malformed data component resource location key",
                    "evidence": [raw_key],
                    "problem": "Component keys must be lowercase resource locations (e.g. 'minecraft:custom_model_data' or '!minecraft:damage').",
                    "remediation": "Prefix lowercase component names with 'minecraft:' (or '!' for patch removals).",
                })
                continue

            norm_key = bare_key if ":" in bare_key else f"minecraft:{bare_key}"
            if is_removal:
                if val != {}:
                    findings.append({
                        "rule_id": "COMP-004",
                        "severity": "high",
                        "title": "Component removal tombstone must have an empty {} value",
                        "evidence": [f"{raw_key}={val!r}"],
                        "problem": "DataComponentPatch removal entries ('!minecraft:<id>') require an empty JSON object {}.",
                        "remediation": f"Set '{raw_key}': {{}}.",
                    })
                continue

            normalized_active[norm_key] = val

            if is_modern_1215 and norm_key in removed_1215:
                findings.append({
                    "rule_id": "COMP-002",
                    "severity": "critical",
                    "title": f"Component '{norm_key}' was removed in Minecraft 1.21.5+ / Paper {target_version}",
                    "evidence": [norm_key],
                    "problem": f"'{norm_key}' no longer exists in DataComponents on {target_version} and fails strict Codec deserialization.",
                    "remediation": removed_1215[norm_key],
                })
                continue

            schema = PAPER_26_3_ITEM_COMPONENT_SCHEMAS.get(norm_key)
            if schema is not None:
                intro_tuple = _parse_mc_version_tuple(str(schema["introduced_in"]))
                if intro_tuple is not None and mc_tuple < intro_tuple:
                    findings.append({
                        "rule_id": "COMP-002",
                        "severity": "critical",
                        "title": f"Component '{norm_key}' requires Minecraft {schema['introduced_in']}+ (target is {target_version})",
                        "evidence": [f"{norm_key} introduced_in={schema['introduced_in']}", f"target_version={target_version}"],
                        "problem": f"Target version {target_version} predates the introduction of '{norm_key}' in {schema['introduced_in']}.",
                        "remediation": f"Raise target_version to {schema['introduced_in']}+ or emit a versioned datapack overlay via mc_generate_pack_overlay.",
                    })
                    continue

            # Component-specific deep validation
            if norm_key == "minecraft:custom_model_data":
                if is_modern_1214:
                    if isinstance(val, bool) or isinstance(val, (int, float)) or not isinstance(val, dict):
                        findings.append({
                            "rule_id": "COMP-003",
                            "severity": "critical",
                            "title": "Legacy integer minecraft:custom_model_data fails on Minecraft 1.21.4-26.3+",
                            "evidence": [f"minecraft:custom_model_data={val!r}"],
                            "problem": (
                                "Minecraft 1.21.4 through 26.3+ replaced integer CustomModelData with typed channels "
                                "{floats: number[], flags: boolean[], strings: string[], colors: (int|number[3])[]}."
                            ),
                            "remediation": f"Convert integer IDs to typed channels, e.g. {{\"floats\": [{val if isinstance(val, (int, float)) and not isinstance(val, bool) else 1.0}]}} or {{\"strings\": [\"variant_id\"]}}.",
                        })
                    else:
                        allowed_cmd = {"floats", "flags", "strings", "colors"}
                        bad_cmd_keys = [k for k in val if k not in allowed_cmd]
                        if bad_cmd_keys:
                            findings.append({
                                "rule_id": "COMP-003",
                                "severity": "critical",
                                "title": "Unknown channel key in minecraft:custom_model_data",
                                "evidence": bad_cmd_keys,
                                "problem": "Only 'floats', 'flags', 'strings', and 'colors' channels are recognized by CustomModelData codecs.",
                                "remediation": "Use only 'floats', 'flags', 'strings', and 'colors' arrays.",
                            })
                        floats_ch = val.get("floats", [])
                        flags_ch = val.get("flags", [])
                        strings_ch = val.get("strings", [])
                        colors_ch = val.get("colors", [])
                        type_errs: list[str] = []
                        if not isinstance(floats_ch, list) or any(isinstance(x, bool) or not isinstance(x, (int, float)) for x in floats_ch):
                            type_errs.append("floats must be an array of numbers")
                        if not isinstance(flags_ch, list) or any(not isinstance(x, bool) for x in flags_ch):
                            type_errs.append("flags must be an array of booleans")
                        if not isinstance(strings_ch, list) or any(not isinstance(x, str) for x in strings_ch):
                            type_errs.append("strings must be an array of strings")
                        if not isinstance(colors_ch, list) or any(
                            isinstance(x, bool) or not (
                                isinstance(x, int) or (isinstance(x, list) and len(x) == 3 and all(not isinstance(c, bool) and isinstance(c, (int, float)) for c in x))
                            )
                            for x in colors_ch
                        ):
                            type_errs.append("colors must be an array of packed RGB ints or [r, g, b] triples")
                        if type_errs:
                            findings.append({
                                "rule_id": "COMP-003",
                                "severity": "critical",
                                "title": "Invalid element type in minecraft:custom_model_data channel",
                                "evidence": type_errs,
                                "problem": "Mismatched element types in CustomModelData channels fail DFU/StreamCodec decoding.",
                                "remediation": "Ensure floats contains numbers, flags contains booleans, strings contains strings, and colors contains ints or [r,g,b] arrays.",
                            })
                        else:
                            cmd_counts = {
                                "floats": len(floats_ch),
                                "flags": len(flags_ch),
                                "strings": len(strings_ch),
                                "colors": len(colors_ch),
                            }
                else:
                    if isinstance(val, bool) or not isinstance(val, int):
                        findings.append({
                            "rule_id": "COMP-003",
                            "severity": "critical",
                            "title": "Pre-1.21.4 minecraft:custom_model_data requires an integer",
                            "evidence": [f"minecraft:custom_model_data={val!r}", f"target_version={target_version}"],
                            "problem": f"Minecraft {target_version} expects a single 32-bit integer for minecraft:custom_model_data.",
                            "remediation": "Pass an integer or target 1.21.4 / 26.3+ for typed channel objects.",
                        })

            elif norm_key in {"minecraft:item_name", "minecraft:custom_name"}:
                if is_modern_1215 and _looks_like_escaped_json_text(val):
                    findings.append({
                        "rule_id": "COMP-005",
                        "severity": "high",
                        "title": f"JSON-escaped string inside '{norm_key}' renders literally on 1.21.5-26.3+",
                        "evidence": [f"{norm_key}={val!r}"],
                        "problem": (
                            "Minecraft 1.21.5 through 26.3+ decodes text components directly as structured objects or plain literals "
                            "rather than parsing JSON-encoded strings; double-encoded JSON renders raw braces on item tooltips."
                        ),
                        "remediation": f"Pass a direct text object (e.g. {{\"text\": \"Sunblade\", \"italic\": false}}) or plain string instead of a JSON-serialized string.",
                    })

            elif norm_key == "minecraft:lore":
                if not isinstance(val, list):
                    findings.append({
                        "rule_id": "COMP-003",
                        "severity": "critical",
                        "title": "minecraft:lore must be an array of text components",
                        "evidence": [f"type={type(val).__name__}"],
                        "problem": "ItemLore codec expects a JSON list of text components.",
                        "remediation": "Wrap lore lines in a JSON array.",
                    })
                else:
                    if len(val) > 256:
                        findings.append({
                            "rule_id": "COMP-004",
                            "severity": "high",
                            "title": "minecraft:lore exceeds vanilla 256-line maximum",
                            "evidence": [f"lines={len(val)}"],
                            "problem": "Vanilla ItemLore codec rejects item stacks with more than 256 lore lines.",
                            "remediation": "Keep minecraft:lore to <= 256 lines.",
                        })
                    if is_modern_1215 and any(_looks_like_escaped_json_text(line) for line in val):
                        findings.append({
                            "rule_id": "COMP-005",
                            "severity": "high",
                            "title": "JSON-escaped string inside minecraft:lore array on 1.21.5-26.3+",
                            "evidence": ["escaped JSON string element in minecraft:lore"],
                            "problem": "Minecraft 1.21.5 through 26.3+ treats strings inside minecraft:lore as literal text rather than parsing nested JSON.",
                            "remediation": "Replace JSON strings with structured text component objects (e.g. {\"text\": \"+15 Strength\", \"italic\": false}).",
                        })

            elif norm_key == "minecraft:tooltip_display":
                if not isinstance(val, dict):
                    findings.append({
                        "rule_id": "COMP-003",
                        "severity": "critical",
                        "title": "minecraft:tooltip_display must be an object",
                        "evidence": [f"type={type(val).__name__}"],
                        "problem": "tooltip_display expects {hide_tooltip?: boolean, hidden_components?: string[]}.",
                        "remediation": "Provide an object with optional 'hide_tooltip' boolean and 'hidden_components' list.",
                    })
                else:
                    bad_td = [k for k in val if k not in {"hide_tooltip", "hidden_components"}]
                    if bad_td:
                        findings.append({
                            "rule_id": "COMP-003",
                            "severity": "high",
                            "title": "Unknown keys in minecraft:tooltip_display",
                            "evidence": bad_td,
                            "problem": "tooltip_display accepts only 'hide_tooltip' and 'hidden_components'.",
                            "remediation": "Use 'hide_tooltip' (boolean) and 'hidden_components' (array of component IDs).",
                        })

            elif norm_key in {"minecraft:unbreakable", "minecraft:glider"}:
                if not isinstance(val, dict):
                    findings.append({
                        "rule_id": "COMP-003",
                        "severity": "critical",
                        "title": f"{norm_key} must be a unit object {{}}",
                        "evidence": [f"{norm_key}={val!r}"],
                        "problem": f"{norm_key} is serialized as an empty unit object {{}}, not a boolean.",
                        "remediation": f"Set '{norm_key}': {{}}.",
                    })
                elif is_modern_1215 and "show_in_tooltip" in val:
                    findings.append({
                        "rule_id": "COMP-003",
                        "severity": "critical",
                        "title": f"Removed 'show_in_tooltip' key inside {norm_key} on 1.21.5-26.3+",
                        "evidence": [f"{norm_key}.show_in_tooltip"],
                        "problem": "Minecraft 1.21.5+ removed per-component 'show_in_tooltip' fields across unbreakable, trim, dyed_color, enchantments, and attribute_modifiers.",
                        "remediation": f"Set '{norm_key}': {{}} and add '{norm_key}' to minecraft:tooltip_display.hidden_components.",
                    })

            elif norm_key in {"minecraft:enchantments", "minecraft:stored_enchantments"}:
                if not isinstance(val, dict):
                    findings.append({
                        "rule_id": "COMP-003",
                        "severity": "critical",
                        "title": f"{norm_key} must be an object",
                        "evidence": [f"type={type(val).__name__}"],
                        "problem": f"{norm_key} maps namespaced enchantment IDs to integer levels 1..255.",
                        "remediation": f"Provide a direct map such as {{'minecraft:sharpness': 5}}.",
                    })
                elif is_modern_1215 and ("levels" in val or "show_in_tooltip" in val):
                    findings.append({
                        "rule_id": "COMP-003",
                        "severity": "critical",
                        "title": f"Legacy 'levels'/'show_in_tooltip' wrapper in {norm_key} on 1.21.5-26.3+",
                        "evidence": [k for k in ("levels", "show_in_tooltip") if k in val],
                        "problem": "Minecraft 1.21.5 through 26.3+ flattened enchantments into a direct {'minecraft:sharpness': 5} map and moved tooltip hiding to minecraft:tooltip_display.",
                        "remediation": f"Inline enchantment entries directly under '{norm_key}' and move tooltip suppression to minecraft:tooltip_display.hidden_components.",
                    })

            elif norm_key == "minecraft:equippable":
                if not isinstance(val, dict):
                    findings.append({
                        "rule_id": "COMP-003",
                        "severity": "critical",
                        "title": "minecraft:equippable must be an object",
                        "evidence": [f"type={type(val).__name__}"],
                        "problem": "Equippable component requires an object declaring 'slot'.",
                        "remediation": "Set 'minecraft:equippable': {'slot': 'head', 'asset_id': 'myplugin:ruby'}.",
                    })
                else:
                    if is_modern_1214 and "model" in val:
                        findings.append({
                            "rule_id": "COMP-003",
                            "severity": "critical",
                            "title": "Obsolete 'model' field in minecraft:equippable (renamed to 'asset_id' in 1.21.4+)",
                            "evidence": [f"equippable.model={val.get('model')!r}"],
                            "problem": "Minecraft 1.21.4 through 26.3+ renamed minecraft:equippable.model to 'asset_id' (resolving assets/<ns>/equipment/<id>.json).",
                            "remediation": "Rename 'model' to 'asset_id' inside minecraft:equippable.",
                        })
                    valid_slots = {"head", "chest", "legs", "feet", "body", "mainhand", "offhand"} | ({"saddle"} if is_modern_1215 else set())
                    slot_val = val.get("slot")
                    if slot_val not in valid_slots:
                        findings.append({
                            "rule_id": "COMP-003",
                            "severity": "critical",
                            "title": "Missing or invalid 'slot' in minecraft:equippable",
                            "evidence": [f"slot={slot_val!r}"],
                            "problem": f"Equippable 'slot' must be one of {sorted(valid_slots)}.",
                            "remediation": "Set 'slot' to a valid EquipmentSlot name (for example 'head', 'chest', 'offhand', or 'saddle').",
                        })

            elif norm_key == "minecraft:food":
                if not isinstance(val, dict):
                    findings.append({
                        "rule_id": "COMP-003",
                        "severity": "critical",
                        "title": "minecraft:food must be an object",
                        "evidence": [f"type={type(val).__name__}"],
                        "problem": "FoodProperties requires an object with 'nutrition' and 'saturation'.",
                        "remediation": "Set 'minecraft:food': {'nutrition': 6, 'saturation': 7.2}.",
                    })
                else:
                    if is_modern_1212:
                        moved_food = [k for k in ("eat_seconds", "using_converts_to", "effects") if k in val]
                        if moved_food:
                            findings.append({
                                "rule_id": "COMP-003",
                                "severity": "critical",
                                "title": "Obsolete 1.20.5 food keys inside minecraft:food on 1.21.2-26.3+",
                                "evidence": moved_food,
                                "problem": "Minecraft 1.21.2+ split eat_seconds/effects into minecraft:consumable and using_converts_to into minecraft:use_remainder.",
                                "remediation": "Keep only {nutrition, saturation, can_always_eat} in minecraft:food and add minecraft:consumable / minecraft:use_remainder.",
                            })
                    if isinstance(val.get("nutrition"), bool) or not isinstance(val.get("nutrition"), int) or val["nutrition"] < 0 or isinstance(val.get("saturation"), bool) or not isinstance(val.get("saturation"), (int, float)):
                        findings.append({
                            "rule_id": "COMP-003",
                            "severity": "critical",
                            "title": "minecraft:food requires non-negative int 'nutrition' and numeric 'saturation'",
                            "evidence": [f"nutrition={val.get('nutrition')!r}", f"saturation={val.get('saturation')!r}"],
                            "problem": "FoodProperties codec requires integer nutrition >= 0 and float saturation.",
                            "remediation": "Provide valid 'nutrition' (int >= 0) and 'saturation' (number) fields.",
                        })

            elif norm_key == "minecraft:attribute_modifiers":
                mods_list: list[Any] | None = None
                if isinstance(val, dict):
                    if is_modern_1215 and "show_in_tooltip" in val:
                        findings.append({
                            "rule_id": "COMP-003",
                            "severity": "critical",
                            "title": "Removed 'show_in_tooltip' inside minecraft:attribute_modifiers on 1.21.5-26.3+",
                            "evidence": ["attribute_modifiers.show_in_tooltip"],
                            "problem": "Minecraft 1.21.5+ removed show_in_tooltip from attribute_modifiers and accepts a direct array of modifiers.",
                            "remediation": "Pass a direct list [...] for minecraft:attribute_modifiers and list 'minecraft:attribute_modifiers' in minecraft:tooltip_display.hidden_components.",
                        })
                    mods_list = val.get("modifiers") if isinstance(val.get("modifiers"), list) else None
                elif isinstance(val, list):
                    mods_list = val
                else:
                    findings.append({
                        "rule_id": "COMP-003",
                        "severity": "critical",
                        "title": "Invalid type for minecraft:attribute_modifiers",
                        "evidence": [f"type={type(val).__name__}"],
                        "problem": "attribute_modifiers must be an array of modifier entries.",
                        "remediation": "Provide an array of {type, id, amount, operation, slot} objects.",
                    })

                if mods_list is not None:
                    valid_ops = {"add_value", "add_multiplied_base", "add_multiplied_total"}
                    for midx, mod in enumerate(mods_list):
                        if not isinstance(mod, dict):
                            continue
                        if mc_tuple >= (1, 21, 0) and ("uuid" in mod or "name" in mod) and "id" not in mod:
                            findings.append({
                                "rule_id": "COMP-005",
                                "severity": "critical",
                                "title": "Legacy 1.20.5 uuid/name in attribute_modifiers (replaced by NamespacedKey 'id' in 1.21+)",
                                "evidence": [f"attribute_modifiers[{midx}] keys={sorted(mod.keys())}"],
                                "problem": "Minecraft 1.21 through 26.3+ replaced AttributeModifier UUID + Name pairs with a single namespaced resource location 'id'.",
                                "remediation": "Replace 'uuid' and 'name' with 'id': 'myplugin:bonus_attack_damage'.",
                            })
                        op_val = mod.get("operation")
                        if op_val not in valid_ops:
                            findings.append({
                                "rule_id": "COMP-005",
                                "severity": "critical",
                                "title": "Invalid attribute modifier operation enum",
                                "evidence": [f"attribute_modifiers[{midx}].operation={op_val!r}"],
                                "problem": f"AttributeModifier operation must be one of {sorted(valid_ops)} (not legacy ADDITION or numeric 0/1/2).",
                                "remediation": "Use 'add_value', 'add_multiplied_base', or 'add_multiplied_total'.",
                            })

            elif norm_key == "minecraft:max_stack_size":
                if isinstance(val, bool) or not isinstance(val, int) or not 1 <= val <= 99:
                    findings.append({
                        "rule_id": "COMP-004",
                        "severity": "critical",
                        "title": "minecraft:max_stack_size out of bounds (1..99)",
                        "evidence": [f"max_stack_size={val!r}"],
                        "problem": "Vanilla DataComponents bounds max_stack_size strictly between 1 and 99.",
                        "remediation": "Set minecraft:max_stack_size to an integer between 1 and 99.",
                    })

            elif norm_key == "minecraft:max_damage":
                if isinstance(val, bool) or not isinstance(val, int) or val < 1:
                    findings.append({
                        "rule_id": "COMP-004",
                        "severity": "critical",
                        "title": "minecraft:max_damage must be a positive integer (>= 1)",
                        "evidence": [f"max_damage={val!r}"],
                        "problem": "max_damage requires an integer >= 1.",
                        "remediation": "Set minecraft:max_damage >= 1.",
                    })

            elif norm_key == "minecraft:use_cooldown":
                if not isinstance(val, dict) or isinstance(val.get("seconds"), bool) or not isinstance(val.get("seconds"), (int, float)) or val["seconds"] <= 0:
                    findings.append({
                        "rule_id": "COMP-004",
                        "severity": "critical",
                        "title": "minecraft:use_cooldown requires positive numeric 'seconds'",
                        "evidence": [f"use_cooldown={val!r}"],
                        "problem": "UseCooldown codec requires {'seconds': <float > 0>, 'cooldown_group'?: '<ns:id>'}.",
                        "remediation": "Specify a positive float 'seconds' inside minecraft:use_cooldown.",
                    })

            elif norm_key == "minecraft:enchantable":
                if not isinstance(val, dict) or isinstance(val.get("value"), bool) or not isinstance(val.get("value"), int) or val["value"] < 1:
                    findings.append({
                        "rule_id": "COMP-004",
                        "severity": "critical",
                        "title": "minecraft:enchantable requires {'value': int >= 1}",
                        "evidence": [f"enchantable={val!r}"],
                        "problem": "Enchantable codec requires a positive integer 'value'.",
                        "remediation": "Set 'minecraft:enchantable': {'value': 15}.",
                    })

            elif norm_key in {"minecraft:dyed_color", "minecraft:trim"} and isinstance(val, dict) and is_modern_1215 and "show_in_tooltip" in val:
                findings.append({
                    "rule_id": "COMP-003",
                    "severity": "critical",
                    "title": f"Removed 'show_in_tooltip' inside {norm_key} on 1.21.5-26.3+",
                    "evidence": [f"{norm_key}.show_in_tooltip"],
                    "problem": f"Minecraft 1.21.5+ removed show_in_tooltip from {norm_key}.",
                    "remediation": f"Remove 'show_in_tooltip' from {norm_key} and add '{norm_key}' to minecraft:tooltip_display.hidden_components.",
                })

            elif norm_key == "minecraft:item_model":
                if not isinstance(val, str) or _NAMESPACED_ID_RE.fullmatch(val) is None:
                    findings.append({
                        "rule_id": "COMP-003",
                        "severity": "critical",
                        "title": "Invalid resource location in minecraft:item_model",
                        "evidence": [f"item_model={val!r}"],
                        "problem": "minecraft:item_model must be a lowercase namespaced ID resolving assets/<ns>/items/<id>.json.",
                        "remediation": "Use a lowercase namespaced ID such as 'myplugin:sunblade'.",
                    })

        # Cross-component mutual exclusion invariant: max_damage + max_stack_size > 1
        max_dmg = normalized_active.get("minecraft:max_damage")
        max_stack = normalized_active.get("minecraft:max_stack_size")
        if isinstance(max_dmg, int) and not isinstance(max_dmg, bool) and isinstance(max_stack, int) and not isinstance(max_stack, bool) and max_stack > 1:
            findings.append({
                "rule_id": "COMP-004",
                "severity": "critical",
                "title": "Item cannot combine minecraft:max_damage with minecraft:max_stack_size > 1",
                "evidence": [f"minecraft:max_damage={max_dmg}", f"minecraft:max_stack_size={max_stack}"],
                "problem": "DataComponentMap validation throws IllegalStateException when an item is both damageable (max_damage) and stackable (max_stack_size > 1).",
                "remediation": "Set minecraft:max_stack_size to 1 or omit minecraft:max_damage.",
            })

        # Validate client item definition (assets/<ns>/items/<id>.json) if present
        expected_client_asset_path: str | None = None
        item_model_id = normalized_active.get("minecraft:item_model")
        if isinstance(item_model_id, str) and _NAMESPACED_ID_RE.fullmatch(item_model_id):
            ns, _, rel_path = item_model_id.partition(":")
            if not rel_path:
                ns, rel_path = "minecraft", ns
            expected_client_asset_path = f"assets/{ns}/items/{rel_path}.json"

        if client_def is not None:
            allowed_client_root = {"model", "hand_animation_on_swap", "oversized_in_gui", "swap_animation_scale"}
            unknown_root = [k for k in client_def if k not in allowed_client_root]
            if unknown_root:
                findings.append({
                    "rule_id": "COMP-006",
                    "severity": "high",
                    "title": "Unknown root property in client items/<id>.json definition",
                    "evidence": unknown_root,
                    "problem": f"Client item definitions only recognize {sorted(allowed_client_root)} at the root.",
                    "remediation": "Place selector properties inside the root 'model' object.",
                })
            if "oversized_in_gui" in client_def and mc_tuple < (1, 21, 6):
                findings.append({
                    "rule_id": "COMP-006",
                    "severity": "medium",
                    "title": "'oversized_in_gui' requires Minecraft 1.21.6 / 26.x+ client",
                    "evidence": [f"target_version={target_version}", "oversized_in_gui"],
                    "problem": "Older 1.21.4-1.21.5 clients ignore or reject 'oversized_in_gui' in items/<id>.json.",
                    "remediation": "Place 'oversized_in_gui' inside a 1.21.6+ / 26.x resource pack overlay.",
                })
            if "model" not in client_def:
                findings.append({
                    "rule_id": "COMP-006",
                    "severity": "critical",
                    "title": "Client items/<id>.json omits required root 'model' object",
                    "evidence": ["missing root 'model' key"],
                    "problem": "Every assets/<namespace>/items/<id>.json file must define a root 'model' object.",
                    "remediation": "Add a root 'model' object (e.g. {'model': {'type': 'minecraft:model', 'model': 'ns:item/id'}}).",
                })
            else:
                effective_cmd = cmd_counts
                if effective_cmd is None and payload_kind != "client_item_definition":
                    effective_cmd = {"floats": 0, "flags": 0, "strings": 0, "colors": 0}
                _validate_client_item_model_node(
                    client_def["model"],
                    path="model",
                    cmd_counts=effective_cmd,
                    findings=findings,
                )

        counts = {"critical": 0, "high": 0, "medium": 0, "low": 0}
        for item in findings:
            sev = str(item.get("severity", "low"))
            if sev in counts:
                counts[sev] += 1

        return ToolOutcome(_pretty_json({
            "target_version": target_version,
            "payload_kind": payload_kind,
            "validated_component_count": len(normalized_active),
            "expected_client_item_definition_path": expected_client_asset_path,
            "finding_count": len(findings),
            "severity_counts": counts,
            "status": "fail" if (counts["critical"] + counts["high"]) > 0 else ("warn" if len(findings) > 0 else "pass"),
            "findings": findings,
            "schema_resource_uri": "minecraftkit://catalog/paper-26.3-item-components",
        }))

    def _tool_diagnose_crash_report(self, args: dict[str, Any]) -> ToolOutcome:
        raw_report = args.get("crash_report")
        if not isinstance(raw_report, str) or not raw_report.strip():
            raise ValueError("'crash_report' must be a non-empty string.")

        server_flavor = str(args.get("server_flavor", "auto")).strip().lower()
        sarif = bool(args.get("sarif", False))

        lines = raw_report.splitlines()
        report_text = raw_report

        # 1. Metadata extraction
        time_match = re.search(r"Time:\s*(.+)", report_text)
        crash_time = time_match.group(1).strip() if time_match else None

        desc_match = re.search(r"Description:\s*(.+)", report_text)
        description = desc_match.group(1).strip() if desc_match else None

        mc_ver_match = re.search(r"Minecraft Version:\s*([^\r\n]+)", report_text)
        mc_version = mc_ver_match.group(1).strip() if mc_ver_match else None

        os_match = re.search(r"Operating System:\s*([^\r\n]+)", report_text)
        os_info = os_match.group(1).strip() if os_match else None

        java_match = re.search(r"Java Version:\s*([^\r\n]+)", report_text)
        java_version = java_match.group(1).strip() if java_match else None

        # Detect platform flavor
        flavor = server_flavor
        if flavor == "auto":
            lower_text = report_text.lower()
            if "folia" in lower_text or "io.papermc.paper.threadedregions" in lower_text:
                flavor = "folia"
            elif "paper" in lower_text or "com.destroystokyo.paper" in lower_text:
                flavor = "paper"
            elif "fabric" in lower_text or "fabric mods:" in lower_text or "net.fabricmc" in lower_text:
                flavor = "fabric"
            elif "neoforge" in lower_text or "net.neoforged" in lower_text:
                flavor = "neoforge"
            elif "forge" in lower_text or "net.minecraftforge" in lower_text:
                flavor = "forge"
            else:
                flavor = "vanilla"

        findings: list[dict[str, Any]] = []
        root_cause_category = "UNKNOWN"
        offending_component: dict[str, Any] = {
            "type": "unknown",
            "name": None,
            "class_name": None,
            "method_name": None,
            "location": None,
        }
        remediation_steps: list[str] = []

        # Check 1: TICKING_ENTITY
        if (description and "ticking entity" in description.lower()) or "-- Entity being ticked --" in report_text:
            root_cause_category = "TICKING_ENTITY"
            offending_component["type"] = "entity"

            ent_type_match = re.search(r"Entity Type:\s*([^\s\r\n]+)", report_text)
            if ent_type_match:
                offending_component["name"] = ent_type_match.group(1).strip()

            ent_name_match = re.search(r"Entity Name:\s*([^\r\n]+)", report_text)
            ent_name = ent_name_match.group(1).strip() if ent_name_match else offending_component["name"]

            ent_id_match = re.search(r"Entity ID:\s*(\d+)", report_text)
            ent_id = ent_id_match.group(1) if ent_id_match else None

            loc_match = re.search(r"Entity's Exact location:\s*([-\d.]+),\s*([-\d.]+),\s*([-\d.]+)", report_text)
            block_loc_match = re.search(r"Entity's Block location:\s*World:\s*\(([-\d]+),([-\d]+),([-\d]+)\)", report_text)

            bx, by, bz = None, None, None
            if block_loc_match:
                bx, by, bz = block_loc_match.group(1), block_loc_match.group(2), block_loc_match.group(3)
                offending_component["location"] = f"World: ({bx},{by},{bz})"
            elif loc_match:
                bx, by, bz = str(int(float(loc_match.group(1)))), str(int(float(loc_match.group(2)))), str(int(float(loc_match.group(3))))
                offending_component["location"] = f"World: ({bx},{by},{bz})"

            kill_cmd = f"/minecraft:kill @e[type={offending_component['name']},x={bx},y={by},z={bz},distance=..2]" if (bx and offending_component['name']) else f"/minecraft:kill @e[type={offending_component['name']}]"

            findings.append({
                "rule_id": "CRASH001",
                "name": "TickingEntity",
                "severity": "critical",
                "message": f"Entity '{ent_name}' ({offending_component['name']}) crashed the server tick loop at {offending_component['location'] or 'unknown location'}.",
                "details": {
                    "entity_type": offending_component["name"],
                    "entity_id": ent_id,
                    "location": offending_component["location"],
                    "kill_command": kill_cmd,
                }
            })
            remediation_steps.append(f"Execute console command: {kill_cmd}")
            remediation_steps.append("If server crashes before console access, load world in MCA Selector / Chunker and prune the entity from chunk data.")

        # Check 2: TICKING_BLOCK_ENTITY
        elif (description and "ticking block entity" in description.lower()) or "-- Block entity being ticked --" in report_text:
            root_cause_category = "TICKING_BLOCK_ENTITY"
            offending_component["type"] = "block_entity"

            bloc_match = re.search(r"Block location:\s*World:\s*\(([-\d]+),([-\d]+),([-\d]+)\)", report_text)
            bx, by, bz = None, None, None
            if bloc_match:
                bx, by, bz = bloc_match.group(1), bloc_match.group(2), bloc_match.group(3)
                offending_component["location"] = f"World: ({bx},{by},{bz})"

            block_match = re.search(r"Block:\s*([^\r\n]+)", report_text)
            block_desc = block_match.group(1).strip() if block_match else "unknown"
            offending_component["name"] = block_desc

            be_type_match = re.search(r"Block Entity Type:\s*([^\s\r\n]+)", report_text)
            be_type = be_type_match.group(1).strip() if be_type_match else "unknown"

            setblock_cmd = f"/setblock {bx} {by} {bz} minecraft:air destroy" if bx else None

            findings.append({
                "rule_id": "CRASH002",
                "name": "TickingBlockEntity",
                "severity": "critical",
                "message": f"Block entity '{be_type}' at {offending_component['location'] or 'unknown'} crashed during tick.",
                "details": {
                    "block": block_desc,
                    "block_entity_type": be_type,
                    "location": offending_component["location"],
                    "setblock_command": setblock_cmd,
                }
            })
            if setblock_cmd:
                remediation_steps.append(f"Execute console command: {setblock_cmd}")
            remediation_steps.append("Alternatively prune the block entity from the chunk using MCA Selector or world editor.")

        # Check 3: MIXIN_APPLICATION_FAILED
        elif "MixinTransformerError" in report_text or "InvalidInjectionException" in report_text or "Mixin apply failed" in report_text:
            root_cause_category = "MIXIN_APPLICATION_FAILED"
            offending_component["type"] = "mixin"

            mixin_match = re.search(r"(?:failing mixin|Mixin|mixin):\s*([a-zA-Z0-9_.]+(?:Mixin[a-zA-Z0-9_]*|Injector))", report_text, re.IGNORECASE)
            target_match = re.search(r"(?:Target class|target):\s*([a-zA-Z0-9_.]+)", report_text, re.IGNORECASE)
            cfg_match = re.search(r"config\s*\[([a-zA-Z0-9_.-]+\.mixins?\.json)\]", report_text)

            if mixin_match:
                offending_component["class_name"] = mixin_match.group(1)
            if target_match:
                offending_component["name"] = target_match.group(1)
            mod_id = cfg_match.group(1).split(".")[0] if cfg_match else None
            if mod_id:
                offending_component["name"] = mod_id

            findings.append({
                "rule_id": "CRASH003",
                "name": "MixinApplicationFailed",
                "severity": "critical",
                "message": f"Bytecode mixin transformation failed on target class '{target_match.group(1) if target_match else 'unknown'}' by mixin config '{cfg_match.group(1) if cfg_match else 'unknown'}'.",
                "details": {
                    "mixin": mixin_match.group(1) if mixin_match else None,
                    "target": target_match.group(1) if target_match else None,
                    "config": cfg_match.group(1) if cfg_match else None,
                }
            })
            remediation_steps.append(f"Check mod compatibility for mod '{mod_id or 'unknown'}'. Update or remove this mod.")
            remediation_steps.append("Verify both mods target the exact same Minecraft minor version.")

        # Check 4: LINKAGE_OR_API_MISMATCH
        elif any(err in report_text for err in ("NoSuchMethodError", "NoClassDefFoundError", "AbstractMethodError", "NoSuchFieldError")):
            root_cause_category = "LINKAGE_OR_API_MISMATCH"
            offending_component["type"] = "plugin_or_mod"

            err_type = "NoSuchMethodError"
            for candidate in ("NoSuchMethodError", "NoClassDefFoundError", "AbstractMethodError", "NoSuchFieldError"):
                if candidate in report_text:
                    err_type = candidate
                    break

            err_match = re.search(rf"{err_type}:\s*([^\r\n]+)", report_text)
            missing_sig = err_match.group(1).strip() if err_match else "unknown"

            plugin_name = None
            for line in lines:
                stripped = line.strip()
                if stripped.startswith("at ") and not any(pkg in stripped for pkg in ("java.", "javax.", "jdk.", "sun.", "net.minecraft.", "io.netty.")):
                    frame_match = re.search(r"at\s+([a-zA-Z0-9_.]+)\.([a-zA-Z0-9_$<]+)\(", stripped)
                    if frame_match:
                        offending_component["class_name"] = frame_match.group(1)
                        offending_component["method_name"] = frame_match.group(2)
                        parts = offending_component["class_name"].split(".")
                        plugin_name = parts[1] if len(parts) > 1 and parts[0] in ("com", "net", "org", "io") else parts[0]
                        offending_component["name"] = plugin_name
                        break

            findings.append({
                "rule_id": "CRASH004",
                "name": "LinkageOrApiMismatch",
                "severity": "high",
                "message": f"Binary API mismatch ({err_type}): missing '{missing_sig}'. Offending caller: '{offending_component['class_name'] or 'unknown'}'.",
                "details": {
                    "error_type": err_type,
                    "missing_symbol": missing_sig,
                    "caller_class": offending_component["class_name"],
                    "inferred_plugin": plugin_name,
                }
            })
            remediation_steps.append(f"Plugin/mod '{plugin_name or 'unknown'}' was built against an incompatible Bukkit/Paper/Minecraft API.")
            remediation_steps.append("Update the plugin to a build compiled for this server version, or report the missing API method to the plugin author.")

        # Check 5: OUT_OF_MEMORY
        elif "OutOfMemoryError" in report_text:
            root_cause_category = "OUT_OF_MEMORY"
            offending_component["type"] = "jvm_memory"

            oom_type = "Java heap space"
            if "Metaspace" in report_text:
                oom_type = "Metaspace"
            elif "Direct buffer memory" in report_text:
                oom_type = "Direct buffer memory"

            findings.append({
                "rule_id": "CRASH005",
                "name": "OutOfMemory",
                "severity": "critical",
                "message": f"JVM exhausted {oom_type}.",
                "details": {
                    "pool": oom_type,
                    "java_version": java_version,
                }
            })
            if oom_type == "Java heap space":
                remediation_steps.append("Increase maximum heap size using JVM flag -Xmx (e.g. -Xms8G -Xmx8G -XX:+UseG1GC).")
            elif oom_type == "Metaspace":
                remediation_steps.append("Increase Metaspace limit with -XX:MaxMetaspaceSize=512M (or 1G for modded servers).")
            else:
                remediation_steps.append("Check for Netty direct memory leaks or increase -XX:MaxDirectMemorySize=1G.")

        # Check 6: ASYNC_CATCHER_OR_CONCURRENCY
        elif any(term in report_text for term in ("Asynchronous entity", "Asynchronous world access", "Current thread is not tick thread")):
            root_cause_category = "ASYNC_CATCHER_OR_CONCURRENCY"
            offending_component["type"] = "concurrency"

            caller_class = None
            for line in lines:
                stripped = line.strip()
                if stripped.startswith("at ") and not any(pkg in stripped for pkg in ("java.", "javax.", "jdk.", "sun.", "net.minecraft.", "org.bukkit.", "io.papermc.")):
                    frame_match = re.search(r"at\s+([a-zA-Z0-9_.]+)\.([a-zA-Z0-9_$<]+)\(", stripped)
                    if frame_match:
                        caller_class = frame_match.group(1)
                        offending_component["class_name"] = caller_class
                        offending_component["method_name"] = frame_match.group(2)
                        break

            findings.append({
                "rule_id": "CRASH006",
                "name": "AsyncCatcherOrConcurrency",
                "severity": "high",
                "message": f"Illegal asynchronous state mutation detected by Paper/Folia: '{caller_class or 'unknown'}'.",
                "details": {
                    "caller_class": caller_class,
                }
            })
            remediation_steps.append("Wrap entity/world mutations in Bukkit.getScheduler().runTask(...) or Folia RegionScheduler.")

        # Check 7: CORRUPTED_CHUNK
        elif any(term in report_text for term in ("wrong location", "Tag 'Level' not found", "IllegalChunkPos")):
            root_cause_category = "CORRUPTED_CHUNK"
            offending_component["type"] = "world_chunk"

            coord_match = re.search(r"Chunk coordinates:\s*([-\d]+),\s*([-\d]+)", report_text)
            cx, cz = (coord_match.group(1), coord_match.group(2)) if coord_match else (None, None)

            findings.append({
                "rule_id": "CRASH007",
                "name": "CorruptedChunk",
                "severity": "critical",
                "message": f"Corrupted chunk data at coordinates [{cx or '?'}, {cz or '?'}].",
                "details": {
                    "chunk_x": cx,
                    "chunk_z": cz,
                }
            })
            remediation_steps.append("Use MCA Selector to select and prune or regenerate the affected chunk.")

        # Check 8: WATCHDOG_TIMEOUT
        elif any(term in report_text for term in ("stopped responding", "Watchdog")):
            root_cause_category = "WATCHDOG_TIMEOUT"
            offending_component["type"] = "watchdog"

            findings.append({
                "rule_id": "CRASH008",
                "name": "WatchdogTimeout",
                "severity": "high",
                "message": "Main server thread stopped responding exceeding watchdog limit.",
                "details": {}
            })
            remediation_steps.append("Inspect thread dump for long-running synchronous database queries, infinite loops, or network calls.")

        # Default fallback
        if not findings:
            findings.append({
                "rule_id": "CRASH_GENERIC",
                "name": "UncategorizedCrash",
                "severity": "medium",
                "message": description or "Uncategorized Minecraft crash report.",
                "details": {}
            })
            remediation_steps.append("Inspect full stack trace and update plugins/mods to latest releases.")

        counts = {"critical": 0, "high": 0, "medium": 0, "low": 0}
        for f in findings:
            sev = f.get("severity", "low")
            if sev in counts:
                counts[sev] += 1

        res_dict: dict[str, Any] = {
            "status": "fail" if (counts["critical"] + counts["high"]) > 0 else "pass",
            "root_cause_category": root_cause_category,
            "server_flavor": flavor,
            "minecraft_version": mc_version,
            "crash_time": crash_time,
            "description": description,
            "offending_component": offending_component,
            "remediation_steps": remediation_steps,
            "finding_count": len(findings),
            "severity_counts": counts,
            "findings": findings,
        }

        if sarif:
            res_dict["sarif_report"] = {
                "$schema": "https://raw.githubusercontent.com/oasis-tcs/sarif-spec/master/Schemata/sarif-schema-2.1.0.json",
                "version": "2.1.0",
                "runs": [
                    {
                        "tool": {
                            "driver": {
                                "name": "minecraftkit",
                                "semanticVersion": self.store.kit_version(),
                                "rules": [
                                    {
                                        "id": f["rule_id"],
                                        "name": f["name"],
                                        "shortDescription": {"text": f["message"]},
                                        "defaultConfiguration": {
                                            "level": "error" if f["severity"] == "critical" else "warning"
                                        }
                                    }
                                    for f in findings
                                ]
                            }
                        },
                        "results": [
                            {
                                "ruleId": f["rule_id"],
                                "level": "error" if f["severity"] == "critical" else "warning",
                                "message": {"text": f["message"]},
                            }
                            for f in findings
                        ]
                    }
                ]
            }

        return ToolOutcome(_pretty_json(res_dict))

    def _tool_audit_datapack(self, args: dict[str, Any]) -> ToolOutcome:
        raw_mcmeta = args.get("pack_mcmeta")
        if isinstance(raw_mcmeta, str):
            if not raw_mcmeta.strip():
                raise ValueError("'pack_mcmeta' string must not be empty.")
            try:
                meta_obj = _strict_loads(raw_mcmeta)
            except (ValueError, json.JSONDecodeError) as exc:
                raise ValueError(f"'pack_mcmeta' is not valid JSON: {exc}") from exc
        elif isinstance(raw_mcmeta, dict):
            meta_obj = raw_mcmeta
        else:
            raise ValueError("'pack_mcmeta' must be a JSON string or JSON object.")

        target_version = str(args.get("target_version", "26.3")).strip()
        raw_files = args.get("files") or {}
        if not isinstance(raw_files, dict):
            raise ValueError("'files' must be a dictionary mapping file paths to their string contents.")

        findings: list[dict[str, Any]] = []

        # 1. pack.mcmeta validation
        pack_section = meta_obj.get("pack")
        if not isinstance(pack_section, dict):
            findings.append({
                "rule_id": "DP001",
                "name": "PackMcmetaMissingOrInvalid",
                "severity": "critical",
                "path": "pack.mcmeta",
                "message": "Missing 'pack' root object in pack.mcmeta."
            })
        else:
            pack_format = pack_section.get("pack_format")
            if pack_format is None:
                findings.append({
                    "rule_id": "DP001",
                    "name": "PackMcmetaMissingOrInvalid",
                    "severity": "critical",
                    "path": "pack.mcmeta",
                    "message": "Missing 'pack_format' inside 'pack' object."
                })
            else:
                expected_format = 97
                if target_version.startswith("1.20.5") or target_version.startswith("1.20.6"):
                    expected_format = 41
                elif target_version.startswith("1.21.0") or target_version.startswith("1.21.1") or target_version == "1.21":
                    expected_format = 48
                elif target_version.startswith("1.21.2") or target_version.startswith("1.21.3"):
                    expected_format = 57
                elif target_version.startswith("1.21.4"):
                    expected_format = 61
                elif target_version.startswith("26."):
                    expected_format = 97

                matched = False
                if isinstance(pack_format, int):
                    matched = (pack_format == expected_format)
                elif isinstance(pack_format, dict):
                    min_f = pack_format.get("min_inclusive", 0)
                    max_f = pack_format.get("max_inclusive", 0)
                    matched = (min_f <= expected_format <= max_f)
                elif isinstance(pack_format, list) and len(pack_format) == 2:
                    matched = (pack_format[0] <= expected_format <= pack_format[1])

                if not matched:
                    findings.append({
                        "rule_id": "DP002",
                        "name": "PackFormatMismatch",
                        "severity": "high",
                        "path": "pack.mcmeta",
                        "message": f"Target Minecraft version '{target_version}' expects pack_format {expected_format}, but pack.mcmeta specifies {pack_format}."
                    })

        # 2. Virtual files validation
        tag_graph: dict[str, list[str]] = {}

        for file_path, content in raw_files.items():
            clean_path = str(file_path).replace("\\", "/").strip()
            if not clean_path.startswith("data/"):
                findings.append({
                    "rule_id": "DP006",
                    "name": "InvalidResourceLocation",
                    "severity": "medium",
                    "path": clean_path,
                    "message": f"Datapack asset '{clean_path}' does not reside inside 'data/<namespace>/' directory structure."
                })
                continue

            parts = clean_path.split("/")
            if len(parts) < 3:
                continue
            ns = parts[1]
            if not re.match(r"^[a-z0-9_.-]+$", ns):
                findings.append({
                    "rule_id": "DP006",
                    "name": "InvalidResourceLocation",
                    "severity": "high",
                    "path": clean_path,
                    "message": f"Invalid datapack namespace '{ns}': namespaces must contain only lowercase ASCII letters, numbers, underscores, periods, and hyphens."
                })

            # Recipe audit
            if "/recipe/" in clean_path or "/recipes/" in clean_path:
                try:
                    recipe_data = _strict_loads(content)
                except (ValueError, json.JSONDecodeError) as exc:
                    findings.append({
                        "rule_id": "DP003",
                        "name": "LegacyRecipeResultSyntax",
                        "severity": "critical",
                        "path": clean_path,
                        "message": f"Invalid recipe JSON syntax: {exc}"
                    })
                    continue

                rec_type = recipe_data.get("type", "")
                if rec_type in ("minecraft:crafting_shaped", "crafting_shaped"):
                    pattern = recipe_data.get("pattern")
                    if not isinstance(pattern, list) or not (1 <= len(pattern) <= 3):
                        findings.append({
                            "rule_id": "DP004",
                            "name": "InvalidShapedRecipePattern",
                            "severity": "high",
                            "path": clean_path,
                            "message": "Shaped recipe 'pattern' must be an array of 1 to 3 strings."
                        })
                    else:
                        first_len = len(pattern[0])
                        if not (1 <= first_len <= 3):
                            findings.append({
                                "rule_id": "DP004",
                                "name": "InvalidShapedRecipePattern",
                                "severity": "high",
                                "path": clean_path,
                                "message": f"Shaped recipe pattern row length ({first_len}) must be between 1 and 3."
                            })
                        for row in pattern:
                            if len(row) != first_len:
                                findings.append({
                                    "rule_id": "DP004",
                                    "name": "InvalidShapedRecipePattern",
                                    "severity": "high",
                                    "path": clean_path,
                                    "message": f"Shaped recipe pattern rows must all be of equal length; got {len(row)} vs {first_len}."
                                })

                    key_dict = recipe_data.get("key", {})
                    if pattern and isinstance(pattern, list):
                        for row in pattern:
                            for char in row:
                                if char != " " and char not in key_dict:
                                    findings.append({
                                        "rule_id": "DP004",
                                        "name": "InvalidShapedRecipePattern",
                                        "severity": "high",
                                        "path": clean_path,
                                        "message": f"Pattern references key '{char}' which is not mapped in recipe 'key' dictionary."
                                    })

                result = recipe_data.get("result")
                if isinstance(result, dict):
                    if "item" in result and "id" not in result:
                        findings.append({
                            "rule_id": "DP003",
                            "name": "LegacyRecipeResultSyntax",
                            "severity": "high",
                            "path": clean_path,
                            "message": "Modern 1.20.5+ recipes require 'result.id' instead of legacy 'result.item'."
                        })
                    if "tag" in result:
                        findings.append({
                            "rule_id": "DP003",
                            "name": "LegacyRecipeResultSyntax",
                            "severity": "high",
                            "path": clean_path,
                            "message": "Legacy string 'tag' in recipe result is deprecated in 1.20.5+; use structured 'components' patch instead."
                        })

            # Tags audit & cyclical dependency check
            elif "/tags/" in clean_path:
                tag_id = f"{ns}:{clean_path.rsplit('/', 1)[-1].split('.', 1)[0]}"
                try:
                    tag_data = _strict_loads(content)
                except (ValueError, json.JSONDecodeError):
                    continue
                values = tag_data.get("values", [])
                tag_deps = []
                if isinstance(values, list):
                    for v in values:
                        val_id = v.get("id") if isinstance(v, dict) else v
                        if isinstance(val_id, str) and val_id.startswith("#"):
                            tag_deps.append(val_id[1:])
                tag_graph[tag_id] = tag_deps

            # Function file audit
            elif clean_path.endswith(".mcfunction"):
                for idx, line in enumerate(str(content).splitlines(), start=1):
                    stripped = line.strip()
                    if not stripped or stripped.startswith("#"):
                        continue
                    if stripped.startswith("/"):
                        findings.append({
                            "rule_id": "DP009",
                            "name": "FunctionSyntaxHazard",
                            "severity": "low",
                            "path": f"{clean_path}:{idx}",
                            "message": f"Command in .mcfunction starts with unnecessary slash '/': '{stripped[:30]}'."
                        })

        # Detect cycle in tag_graph
        def find_cycle(node: str, visited: set[str], path: list[str]) -> list[str] | None:
            visited.add(node)
            path.append(node)
            for neighbor in tag_graph.get(node, []):
                if neighbor not in visited:
                    cycle = find_cycle(neighbor, visited, path)
                    if cycle:
                        return cycle
                elif neighbor in path:
                    cycle_start = path.index(neighbor)
                    return path[cycle_start:] + [neighbor]
            path.pop()
            return None

        visited_nodes: set[str] = set()
        for root_tag in list(tag_graph.keys()):
            if root_tag not in visited_nodes:
                cycle = find_cycle(root_tag, visited_nodes, [])
                if cycle:
                    cycle_str = " -> ".join(cycle)
                    findings.append({
                        "rule_id": "DP005",
                        "name": "CyclicalTagReference",
                        "severity": "critical",
                        "path": f"data/tags/{cycle[0]}",
                        "message": f"Cyclical tag dependency detected: {cycle_str}."
                    })
                    break

        severity_counts = {"critical": 0, "high": 0, "medium": 0, "low": 0}
        for f in findings:
            sev = f.get("severity", "low")
            if sev in severity_counts:
                severity_counts[sev] += 1

        return ToolOutcome(_pretty_json({
            "status": "fail" if (severity_counts["critical"] + severity_counts["high"]) > 0 else ("warn" if len(findings) > 0 else "pass"),
            "target_version": target_version,
            "files_audited": len(raw_files),
            "finding_count": len(findings),
            "severity_counts": severity_counts,
            "findings": findings,
            "schema_resource_uri": "minecraftkit://catalog/overview",
        }))

    @staticmethod
    def _demangle_jvm_frame(raw_frame: str) -> str:
        frame = raw_frame.strip()
        frame = re.sub(r"^(?:at\s+)", "", frame)
        frame = re.sub(r"^[a-zA-Z0-9_.]+@[0-9A-Za-z_.+-]+/", "", frame)
        frame = re.sub(r"\$\$Lambda(?:\$0x[0-9a-fA-F]+)?(?:/0x[0-9a-fA-F]+)?", "::Lambda", frame)
        frame = re.sub(r"\.lambda\$([A-Za-z0-9_$]+)\$\d+", r"::lambda$\1", frame)
        frame = re.sub(r"\([^)]*\)$", "()", frame)
        return frame.strip()

    @staticmethod
    def _attribute_frame_owner(frame: str) -> tuple[str, str | None]:
        clean = frame.lstrip("[")
        rpg_prefixes = (
            ("com.ticxo.modelengine", "ModelEngine"),
            ("net.Indyuce.mmoitems", "MMOItems"),
            ("net.indyuce.mmoitems", "MMOItems"),
            ("net.Indyuce.mmocore", "MMOCore"),
            ("net.indyuce.mmocore", "MMOCore"),
            ("net.Indyuce.mmoinventory", "MMOInventory"),
            ("net.indyuce.mmoinventory", "MMOInventory"),
            ("fr.phoenixdevt.mmoprofiles", "MMOProfiles"),
            ("io.lumine.mythiccrucible", "MythicCrucible"),
            ("net.playavalon.mythicdungeons", "MythicDungeons"),
            ("io.lumine.mythicenchants", "MythicEnchants"),
            ("io.lumine.mythicrpg", "MythicRPG"),
            ("io.lumine.mythic.core", "CoreTools"),
            ("com.coretools", "CoreTools"),
        )
        for prefix, plugin_name in rpg_prefixes:
            if clean.startswith(prefix):
                return ("indexed_rpg_plugin", plugin_name)

        engine_prefixes = (
            "net.minecraft.",
            "com.mojang.",
            "io.papermc.",
            "ca.spottedleaf.",
            "org.bukkit.",
            "org.spigotmc.",
            "com.destroystokyo.paper.",
            "gg.pufferfish.",
            "org.purpurmc.",
            "java.",
            "javax.",
            "jdk.",
            "sun.",
            "com.sun.",
            "io.netty.",
            "it.unimi.dsi.",
            "com.google.common.",
            "com.google.gson.",
            "org.apache.logging.",
            "org.slf4j.",
            "kotlin.",
            "kotlinx.",
            "com.zaxxer.hikari.",
            "com.mysql.",
            "org.mariadb.",
            "org.postgresql.",
            "org.sqlite.",
            "okhttp3.",
            "org.spongepowered.asm.",
        )
        if clean.startswith(engine_prefixes):
            return ("engine", None)

        pkg_match = re.match(r"^([a-z][a-z0-9_]*)\.([a-zA-Z0-9_]+)(?:\.([a-zA-Z0-9_]+))?\.[A-Z]", clean)
        if pkg_match:
            tld, vendor, sub = pkg_match.group(1), pkg_match.group(2), pkg_match.group(3)
            if tld in {"com", "net", "org", "io", "me", "dev", "de", "fr", "pl", "ru", "uk", "gg", "xyz"}:
                if vendor.lower() in {"github", "gitlab"} and sub:
                    return ("third_party_plugin", sub)
                return ("third_party_plugin", vendor)
        return ("runtime", None)

    @classmethod
    def _is_thread_name(cls, label: str) -> bool:
        lower = label.strip().strip('"').lower()
        thread_markers = (
            "server thread",
            "region scheduler",
            "global region",
            "entity scheduler",
            "async scheduler",
            "craft async",
            "folia async",
            "netty ",
            "forkjoinpool",
            "worker-main",
            "tuinity chunk",
            "moonrise ",
            "hikaripool",
            "pool-",
            "thread-",
        )
        return any(marker in lower for marker in thread_markers)

    @classmethod
    def _is_async_worker_thread(cls, thread_name: str) -> bool:
        lower = thread_name.lower()
        return any(
            token in lower
            for token in (
                "async scheduler",
                "craft async",
                "folia async",
                "forkjoinpool",
                "completablefuture",
                "worker-main",
                "async chat",
                "pool-",
            )
        )

    @classmethod
    def _is_tick_or_region_thread(cls, thread_name: str) -> bool:
        lower = thread_name.lower()
        if cls._is_async_worker_thread(lower) or "netty" in lower:
            return False
        return any(
            token in lower
            for token in (
                "server thread",
                "region scheduler",
                "global region",
                "entity scheduler",
                "profile root",
            )
        )

    def _build_sarif_report(self, findings: list[dict[str, Any]]) -> dict[str, Any]:
        seen_rules: dict[str, dict[str, Any]] = {}
        for f in findings:
            rid = str(f["rule_id"])
            if rid not in seen_rules:
                sev = f.get("severity", "medium")
                level = "error" if sev in {"critical", "high"} else ("warning" if sev == "medium" else "note")
                seen_rules[rid] = {
                    "id": rid,
                    "name": str(f.get("name", rid)),
                    "shortDescription": {"text": str(f.get("message", ""))},
                    "defaultConfiguration": {"level": level},
                }
        results = []
        for f in findings:
            sev = f.get("severity", "medium")
            level = "error" if sev in {"critical", "high"} else ("warning" if sev == "medium" else "note")
            entry: dict[str, Any] = {
                "ruleId": str(f["rule_id"]),
                "level": level,
                "message": {"text": str(f.get("message", ""))},
            }
            loc_target = f.get("frame") or f.get("violating_frame") or f.get("thread")
            if loc_target:
                entry["locations"] = [
                    {
                        "logicalLocations": [
                            {
                                "fullyQualifiedName": str(loc_target),
                                "kind": "function",
                            }
                        ]
                    }
                ]
            results.append(entry)
        return {
            "$schema": "https://raw.githubusercontent.com/oasis-tcs/sarif-spec/master/Schemata/sarif-schema-2.1.0.json",
            "version": "2.1.0",
            "runs": [
                {
                    "tool": {
                        "driver": {
                            "name": "minecraftkit",
                            "semanticVersion": self.store.kit_version(),
                            "rules": list(seen_rules.values()),
                        }
                    },
                    "results": results,
                }
            ],
        }

    def _tool_audit_spark_flamegraph(self, args: dict[str, Any]) -> ToolOutcome:
        raw_profile = args.get("profile")
        if not isinstance(raw_profile, str) or not raw_profile.strip():
            raise ValueError("'profile' must be a non-empty Spark/JFR collapsed stack or call-tree string.")

        raw_threshold = args.get("hotspot_threshold_pct", 5.0)
        if isinstance(raw_threshold, bool) or not isinstance(raw_threshold, (int, float)):
            raise ValueError("'hotspot_threshold_pct' must be a number between 0.1 and 100.0.")
        threshold_pct = float(raw_threshold)
        if not (0.1 <= threshold_pct <= 100.0):
            raise ValueError("'hotspot_threshold_pct' must be between 0.1 and 100.0.")

        sarif = bool(args.get("sarif", False))

        lines = [ln.rstrip("\r") for ln in raw_profile.splitlines() if ln.strip() and not ln.lstrip().startswith("#")]
        if not lines:
            raise ValueError("'profile' contains no parseable stack samples or call-tree nodes.")

        collapsed_re = re.compile(r"^([^;\s][^;]*(?:;[^;]+)+)\s+([0-9]+(?:\.[0-9]+)?)\s*$")
        collapsed_matches = [collapsed_re.match(ln.strip()) for ln in lines]
        is_collapsed = sum(1 for m in collapsed_matches if m is not None) >= max(1, len(lines) // 2)

        # Unified sample representation: list of (thread_name, stack_frames_root_to_leaf, leaf_self_weight)
        samples: list[tuple[str, list[str], float]] = []
        inclusive_weights: dict[str, float] = {}
        self_weights: dict[str, float] = {}
        frame_threads: dict[str, set[str]] = {}
        frame_callers: dict[str, tuple[str, str]] = {}  # frame -> (owner_kind, plugin_name)
        total_weight = 0.0
        detected_format = "collapsed" if is_collapsed else "call_tree"

        if is_collapsed:
            for ln in lines:
                m = collapsed_re.match(ln.strip())
                if not m:
                    continue
                raw_chain, weight_str = m.group(1), m.group(2)
                weight = float(weight_str)
                if weight <= 0:
                    continue
                parts = [p.strip() for p in raw_chain.split(";") if p.strip()]
                if not parts:
                    continue
                if self._is_thread_name(parts[0]) and len(parts) > 1:
                    thread_name = parts[0].strip('"')
                    raw_frames = parts[1:]
                else:
                    thread_name = "Server thread"
                    raw_frames = parts
                norm_frames = [self._demangle_jvm_frame(f) for f in raw_frames if f.strip()]
                if not norm_frames:
                    continue
                total_weight += weight
                samples.append((thread_name, norm_frames, weight))

                active_plugin: tuple[str, str] | None = None
                seen_in_sample: set[str] = set()
                for fr in norm_frames:
                    owner_kind, owner_name = self._attribute_frame_owner(fr)
                    if owner_kind in {"indexed_rpg_plugin", "third_party_plugin"} and owner_name:
                        active_plugin = (owner_kind, owner_name)
                    if fr not in seen_in_sample:
                        seen_in_sample.add(fr)
                        inclusive_weights[fr] = inclusive_weights.get(fr, 0.0) + weight
                    frame_threads.setdefault(fr, set()).add(thread_name)
                    if active_plugin and fr not in frame_callers:
                        frame_callers[fr] = active_plugin
                leaf = norm_frames[-1]
                self_weights[leaf] = self_weights.get(leaf, 0.0) + weight
        else:
            # Parse indented Spark / JFR call tree and compute exact child-subtracted self weights
            tree_nodes: list[dict[str, Any]] = []
            stack: list[int] = []  # indices into tree_nodes

            pct_prefix_re = re.compile(r"^\[?\s*([0-9]+(?:\.[0-9]+)?)%\s*\]?\s*(?:\([0-9.,]+\s*(?:ms|s|samples)?\)\s*)?(.+?)\s*$")
            pct_suffix_re = re.compile(r"^(.+?)\s+([0-9]+(?:\.[0-9]+)?)%\s*(?:\([0-9.,]+\s*(?:ms|s|samples)?\))?\s*$")

            for ln in lines:
                prefix_match = re.match(r"^([\s│|├└─+`\\-]*)", ln)
                prefix = prefix_match.group(1) if prefix_match else ""
                body = ln[len(prefix):].strip()
                if not body:
                    continue
                depth = len(prefix.expandtabs(2))

                pct_val: float | None = None
                label = body
                m_pre = pct_prefix_re.match(body)
                if m_pre:
                    pct_val = float(m_pre.group(1))
                    label = m_pre.group(2).strip()
                else:
                    m_suf = pct_suffix_re.match(body)
                    if m_suf:
                        label = m_suf.group(1).strip()
                        pct_val = float(m_suf.group(2))

                if pct_val is None:
                    continue

                while stack and tree_nodes[stack[-1]]["depth"] >= depth:
                    stack.pop()

                parent_idx = stack[-1] if stack else None
                clean_label = label.strip('"')
                is_thread_root = parent_idx is None and self._is_thread_name(clean_label)
                node_idx = len(tree_nodes)
                node = {
                    "idx": node_idx,
                    "depth": depth,
                    "raw_label": clean_label,
                    "frame": clean_label if is_thread_root else self._demangle_jvm_frame(clean_label),
                    "is_thread_root": is_thread_root,
                    "weight": pct_val,
                    "parent": parent_idx,
                    "children": [],
                }
                tree_nodes.append(node)
                if parent_idx is not None:
                    tree_nodes[parent_idx]["children"].append(node_idx)
                stack.append(node_idx)

            if not tree_nodes:
                raise ValueError("Unable to parse Spark/JFR call-tree percentages or collapsed stack weights from 'profile'.")

            root_nodes = [n for n in tree_nodes if n["parent"] is None]
            tick_roots = [n for n in root_nodes if not self._is_async_worker_thread(n["raw_label"])]
            total_weight = sum(n["weight"] for n in (tick_roots or root_nodes))
            if total_weight <= 0:
                total_weight = 100.0

            for node in tree_nodes:
                if node["is_thread_root"] and node["children"]:
                    continue
                child_sum = sum(tree_nodes[ch]["weight"] for ch in node["children"])
                node_self = max(0.0, node["weight"] - child_sum)

                # Reconstruct root-to-node path
                chain: list[dict[str, Any]] = []
                cur: int | None = node["idx"]
                while cur is not None:
                    chain.append(tree_nodes[cur])
                    cur = tree_nodes[cur]["parent"]
                chain.reverse()

                thread_name = chain[0]["raw_label"] if chain[0]["is_thread_root"] else "Server thread"
                frames = [c["frame"] for c in chain if not c["is_thread_root"]]
                if not frames:
                    continue

                fr_leaf = frames[-1]
                inclusive_weights[fr_leaf] = inclusive_weights.get(fr_leaf, 0.0) + node["weight"]
                self_weights[fr_leaf] = self_weights.get(fr_leaf, 0.0) + node_self
                frame_threads.setdefault(fr_leaf, set()).add(thread_name)

                active_plugin = None
                for fr in frames:
                    owner_kind, owner_name = self._attribute_frame_owner(fr)
                    if owner_kind in {"indexed_rpg_plugin", "third_party_plugin"} and owner_name:
                        active_plugin = (owner_kind, owner_name)
                if active_plugin and fr_leaf not in frame_callers:
                    frame_callers[fr_leaf] = active_plugin

                if node_self > 0 or not node["children"]:
                    samples.append((thread_name, frames, max(node_self, 0.01)))

        if total_weight <= 0:
            raise ValueError("'profile' total sample weight must be greater than zero.")

        # Aggregate plugin attribution across self weights and inclusive leaf chains
        plugin_attribution: dict[str, dict[str, Any]] = {}
        for thread_name, frames, leaf_w in samples:
            if not self._is_tick_or_region_thread(thread_name):
                continue
            initiating: tuple[str, str] | None = None
            top_plugin_frame: str | None = None
            for fr in frames:
                kind, pname = self._attribute_frame_owner(fr)
                if kind in {"indexed_rpg_plugin", "third_party_plugin"} and pname:
                    initiating = (kind, pname)
                    top_plugin_frame = fr
            if initiating and top_plugin_frame:
                kind, pname = initiating
                bucket = plugin_attribution.setdefault(
                    pname,
                    {
                        "plugin": pname,
                        "indexed_in_minecraftkit": kind == "indexed_rpg_plugin",
                        "attributed_weight": 0.0,
                        "top_frame": top_plugin_frame,
                    },
                )
                bucket["attributed_weight"] += leaf_w

        plugin_breakdown = []
        for entry in sorted(plugin_attribution.values(), key=lambda x: x["attributed_weight"], reverse=True):
            pct = round((entry["attributed_weight"] / total_weight) * 100.0, 2)
            plugin_breakdown.append({
                "plugin": entry["plugin"],
                "indexed_in_minecraftkit": entry["indexed_in_minecraftkit"],
                "attributed_pct": min(100.0, pct),
                "top_frame": entry["top_frame"],
            })

        # Classify 7 tick hotspot categories + async pool starvation
        findings: list[dict[str, Any]] = []
        emitted_rules: set[tuple[str, str]] = set()

        def add_finding(
            rule_id: str,
            name: str,
            category: str,
            severity: str,
            frame: str,
            inc_pct: float,
            self_pct: float,
            thread_label: str,
            plugin_owner: str | None,
            message: str,
            remediation: str,
        ) -> None:
            dedup_key = (rule_id, plugin_owner or frame)
            if dedup_key in emitted_rules:
                return
            emitted_rules.add(dedup_key)
            findings.append({
                "rule_id": rule_id,
                "name": name,
                "category": category,
                "severity": severity,
                "frame": frame,
                "thread": thread_label,
                "plugin": plugin_owner,
                "inclusive_pct": round(min(100.0, inc_pct), 2),
                "self_pct": round(min(100.0, self_pct), 2),
                "message": message,
                "remediation": remediation,
            })

        for fr, inc_w in sorted(inclusive_weights.items(), key=lambda kv: kv[1], reverse=True):
            inc_pct = (inc_w / total_weight) * 100.0
            self_pct = (self_weights.get(fr, 0.0) / total_weight) * 100.0
            threads = frame_threads.get(fr, {"Server thread"})
            on_tick = any(self._is_tick_or_region_thread(t) for t in threads)
            primary_thread = sorted(threads)[0]
            caller_info = frame_callers.get(fr)
            caller_plugin = caller_info[1] if caller_info else None
            lower_fr = fr.lower()

            if on_tick and max(inc_pct, self_pct) >= threshold_pct:
                if any(tok in lower_fr for tok in (
                    "serverchunkcache.getchunk",
                    "syncload",
                    "blockingload",
                    "getchunkat(",
                    "getchunkat()",
                    "chunksystem.schedulechunkload",
                    "chunkmap.save",
                )):
                    add_finding(
                        "SPARK-001",
                        "SyncChunkIoOnTickThread",
                        "SYNC_CHUNK_IO",
                        "critical",
                        fr,
                        inc_pct,
                        self_pct,
                        primary_thread,
                        caller_plugin,
                        f"Synchronous chunk load '{fr}' consumes {inc_pct:.1f}% of tick budget on '{primary_thread}'"
                        + (f" (triggered by plugin '{caller_plugin}')." if caller_plugin else "."),
                        "Replace synchronous World.getChunkAt / Location.getChunk calls with World.getChunkAtAsync(x, z).thenAccept(...) and pre-generate world borders with Chunky.",
                    )
                elif any(tok in lower_fr for tok in (
                    "java.sql.",
                    "hikaripool",
                    "preparedstatement",
                    "drivermanager.getconnection",
                    "mysql",
                    "mariadb",
                    "postgresql",
                    "sqlite",
                    "socketinputstream.socketread",
                    "sun.net.www.protocol.http",
                    "jdk.internal.net.http",
                    "okhttp3.",
                )):
                    add_finding(
                        "SPARK-002",
                        "SyncJdbcOrNetworkIoOnTickThread",
                        "SYNCHRONOUS_JDBC_OR_HTTP_IO",
                        "critical",
                        fr,
                        inc_pct,
                        self_pct,
                        primary_thread,
                        caller_plugin,
                        f"Blocking JDBC or network I/O '{fr}' stalls '{primary_thread}' for {inc_pct:.1f}% of profile samples"
                        + (f" (initiated by '{caller_plugin}')." if caller_plugin else "."),
                        "Move all database queries and HTTP calls onto Bukkit.getAsyncScheduler() (or CompletableFuture.supplyAsync) and marshal results back via RegionScheduler or EntityScheduler.",
                    )
                elif any(tok in lower_fr for tok in (
                    "goalselector",
                    "brain.tick",
                    "pathnavigation",
                    "walknodeevaluator",
                    "voxelshapes",
                    "entitylookup",
                    "pushentities",
                    "livingentity.aistep",
                )):
                    add_finding(
                        "SPARK-003",
                        "EntityAiOrCollisionHotspot",
                        "ENTITY_AI_PATHFINDING",
                        "high",
                        fr,
                        inc_pct,
                        self_pct,
                        primary_thread,
                        caller_plugin,
                        f"Entity AI pathfinding or voxel collision '{fr}' accounts for {inc_pct:.1f}% inclusive ({self_pct:.1f}% self) tick time.",
                        "Tighten entity-activation-range and max-entity-collisions in spigot.yml/paper-world-defaults.yml, and disable per-tick path recalculation on stationary custom mobs.",
                    )
                elif any(tok in lower_fr for tok in (
                    "hopperblockentity",
                    "boundtickingblockentity",
                    "pistonmovingblockentity",
                    "furnaceblockentity",
                )):
                    add_finding(
                        "SPARK-004",
                        "HopperOrBlockEntityTickHotspot",
                        "HOPPER_BLOCK_ENTITY_TICK",
                        "high",
                        fr,
                        inc_pct,
                        self_pct,
                        primary_thread,
                        caller_plugin,
                        f"Block-entity ticking '{fr}' consumes {inc_pct:.1f}% of tick budget.",
                        "Enable Paper hopper.disable-move-event when InventoryMoveItemEvent listeners are unnecessary, increase ticks-per.hopper-check, and cap concentrated hopper chains.",
                    )
                elif any(tok in lower_fr for tok in (
                    "packetencoder",
                    "packetdecoder",
                    "trackedentity.broadcast",
                    "deflater.deflate",
                    "streamcodec",
                )):
                    add_finding(
                        "SPARK-005",
                        "NettyPacketCodecPressure",
                        "NETTY_PACKET_SERIALIZATION",
                        "medium",
                        fr,
                        inc_pct,
                        self_pct,
                        primary_thread,
                        caller_plugin,
                        f"Packet serialization/compression '{fr}' consumes {inc_pct:.1f}% of sampled time.",
                        "Raise network-compression-threshold to 256 or 512 (or -1 behind Velocity on localhost) and throttle high-frequency entity metadata/equipment packet broadcasts.",
                    )
                elif any(tok in lower_fr for tok in (
                    "findnearestmapstructure",
                    "noisebasedchunkgenerator",
                    "biomesource",
                    "surfacebuilders",
                    "structurecheck",
                )):
                    add_finding(
                        "SPARK-006",
                        "WorldgenOrStructureSearchHotspot",
                        "WORLDGEN_NOISE_BIOME",
                        "high",
                        fr,
                        inc_pct,
                        self_pct,
                        primary_thread,
                        caller_plugin,
                        f"World generation or synchronous structure search '{fr}' consumes {inc_pct:.1f}% of tick time.",
                        "Pre-generate exploration worlds, disable treasure-maps.enabled for ungenerated oceans/mansions if /locate stalls occur, and avoid calling World.locateNearestStructure on high-frequency events.",
                    )
                else:
                    owner_kind, owner_name = self._attribute_frame_owner(fr)
                    if owner_kind in {"indexed_rpg_plugin", "third_party_plugin"} and self_pct >= threshold_pct:
                        add_finding(
                            "SPARK-007",
                            "PluginExecutionOrReflectionHotspot",
                            "PLUGIN_EVENT_REFLECTION_HOTSPOT",
                            "high",
                            fr,
                            inc_pct,
                            self_pct,
                            primary_thread,
                            owner_name,
                            f"Plugin frame '{fr}' ({owner_name}) consumes {self_pct:.1f}% self ({inc_pct:.1f}% inclusive) on '{primary_thread}'.",
                            f"Cache reflective lookups or NBT/DataComponent reads in '{owner_name}', debounce PlayerMoveEvent/EntityDamageByEntityEvent handlers, and offload pure computation to AsyncScheduler.",
                        )

        # Inspect async worker pool samples: distinguish benign idle park from real starvation
        async_starvation_events: list[dict[str, Any]] = []
        benign_idle_workers = 0
        active_async_workers = 0

        for thread_name, frames, leaf_w in samples:
            if not self._is_async_worker_thread(thread_name):
                continue
            joined_lower = " ; ".join(frames).lower()
            has_plugin_task = any(
                self._attribute_frame_owner(f)[0] in {"indexed_rpg_plugin", "third_party_plugin"}
                for f in frames
            )
            is_idle_queue_park = any(
                idle_tok in joined_lower
                for idle_tok in (
                    "threadpoolexecutor.gettask",
                    "delayedworkqueue.take",
                    "synchronousqueue.transfer",
                    "forkjoinpool.runworker",
                    "forkjoinpool.scan",
                )
            ) and not has_plugin_task

            if is_idle_queue_park:
                benign_idle_workers += 1
                continue

            active_async_workers += 1
            plugin_caller = next(
                (self._attribute_frame_owner(f)[1] for f in reversed(frames) if self._attribute_frame_owner(f)[1]),
                None,
            )
            leaf_fr = frames[-1]

            starvation_kind: str | None = None
            remediation_hint = ""
            if "hikaripool.getconnection" in joined_lower:
                starvation_kind = "HIKARICP_POOL_EXHAUSTION"
                remediation_hint = "HikariCP connection pool is exhausted across async workers; check leaked ResultSet/Connection handles, add indexes to slow SQL queries, and align maximumPoolSize with database max_connections."
            elif "socketread0" in joined_lower or "socketchannelimpl.read" in joined_lower or "http2clientimpl" in joined_lower:
                starvation_kind = "UNTIMED_SOCKET_STALL"
                remediation_hint = "Async scheduler worker is pinned on a blocking socket read; configure explicit connectTimeout and readTimeout (e.g. 3000-5000ms) and isolate external HTTP webhooks on a dedicated bounded executor."
            elif any(tok in joined_lower for tok in ("reentrantlock.lock", "object.wait", "monitorenter", "synchronized")):
                starvation_kind = "ASYNC_LOCK_CONVOY"
                remediation_hint = "Async workers are serialized on a shared lock or monitor; replace coarse synchronized caches with ConcurrentHashMap.computeIfAbsent or striped locks."
            elif any(tok in joined_lower for tok in ("completablefuture.waitingget", "completablefuture.join", "futuretask.awaitdone")):
                starvation_kind = "NESTED_FUTURE_DEADLOCK"
                remediation_hint = "Async worker blocks on CompletableFuture.join()/get(), risking thread-pool starvation deadlock when child tasks target the same bounded pool; compose stages with thenCompose/thenCombine instead."

            if starvation_kind:
                async_starvation_events.append({
                    "thread": thread_name,
                    "starvation_type": starvation_kind,
                    "plugin": plugin_caller,
                    "blocking_frame": leaf_fr,
                    "weight": round(leaf_w, 2),
                })
                add_finding(
                    "SPARK-008",
                    "AsyncWorkerPoolStarvation",
                    "ASYNC_POOL_STARVATION",
                    "critical" if starvation_kind in {"HIKARICP_POOL_EXHAUSTION", "NESTED_FUTURE_DEADLOCK"} else "high",
                    leaf_fr,
                    (leaf_w / total_weight) * 100.0,
                    (leaf_w / total_weight) * 100.0,
                    thread_name,
                    plugin_caller,
                    f"Async worker '{thread_name}' exhibits {starvation_kind} at '{leaf_fr}'"
                    + (f" inside plugin '{plugin_caller}'." if plugin_caller else "."),
                    remediation_hint,
                )

        top_self_frames = [
            {
                "frame": fr,
                "self_pct": round(min(100.0, (sw / total_weight) * 100.0), 2),
                "inclusive_pct": round(min(100.0, (inclusive_weights.get(fr, sw) / total_weight) * 100.0), 2),
                "owner_type": self._attribute_frame_owner(fr)[0],
                "plugin": self._attribute_frame_owner(fr)[1] or (frame_callers.get(fr, (None, None))[1]),
            }
            for fr, sw in sorted(self_weights.items(), key=lambda kv: kv[1], reverse=True)[:10]
            if sw > 0
        ]

        severity_counts = {"critical": 0, "high": 0, "medium": 0, "low": 0}
        for f in findings:
            sev = f.get("severity", "low")
            if sev in severity_counts:
                severity_counts[sev] += 1

        report: dict[str, Any] = {
            "status": "fail" if (severity_counts["critical"] + severity_counts["high"]) > 0 else ("warn" if findings else "pass"),
            "profile_format": detected_format,
            "total_sample_weight": round(total_weight, 2),
            "sample_paths_analyzed": len(samples),
            "hotspot_threshold_pct": threshold_pct,
            "top_self_hotspots": top_self_frames,
            "plugin_attribution": plugin_breakdown,
            "async_pool_summary": {
                "active_async_samples": active_async_workers,
                "benign_idle_parked_workers": benign_idle_workers,
                "starvation_events": async_starvation_events,
            },
            "finding_count": len(findings),
            "severity_counts": severity_counts,
            "findings": findings,
        }
        if sarif:
            report["sarif_report"] = self._build_sarif_report(findings)

        return ToolOutcome(_pretty_json(report))

    def _tool_analyze_folia_scheduler_trace(self, args: dict[str, Any]) -> ToolOutcome:
        raw_trace = args.get("trace")
        if not isinstance(raw_trace, str) or not raw_trace.strip():
            raise ValueError("'trace' must be a non-empty stack trace, thread dump, or Folia crash log string.")

        declared = str(args.get("declared_domain", "auto")).strip().lower()
        if declared not in {"auto", "region", "entity", "global", "async", "netty"}:
            raise ValueError("'declared_domain' must be one of: auto, region, entity, global, async, netty.")
        sarif = bool(args.get("sarif", False))

        # Split multi-thread JVM dumps on quoted thread headers ("Thread Name" ...), else single block
        thread_header_re = re.compile(r'^"([^"]+)"(?:\s+#\d+)?.*$')
        blocks: list[tuple[str, list[str]]] = []
        current_header: str | None = None
        current_lines: list[str] = []

        for raw_ln in raw_trace.splitlines():
            stripped = raw_ln.strip()
            if not stripped:
                continue
            m_hdr = thread_header_re.match(stripped)
            if m_hdr:
                if current_lines or current_header is not None:
                    blocks.append((current_header or "Trace Snippet", current_lines))
                current_header = m_hdr.group(1)
                current_lines = [stripped]
                continue
            inline_thr = re.search(r"Thread\s+(Region Scheduler Thread #[0-9]+|Global Region Scheduler[^\n:]*|Folia Async Scheduler[^\n:]*|Craft Async Scheduler[^\n:]*|Netty [^\n:]+|Server thread)", stripped)
            if inline_thr and current_header is None:
                current_header = inline_thr.group(1).strip()
            current_lines.append(stripped)

        if current_lines or current_header is not None:
            blocks.append((current_header or "Trace Snippet", current_lines))
        if not blocks:
            raise ValueError("'trace' contains no parseable stack frames.")

        def infer_domain(header: str, frames: list[str]) -> str:
            if declared != "auto":
                return declared.upper()
            h_low = header.lower()
            joined = " \n ".join(frames).lower()
            if "netty" in h_low or "epollserver" in h_low or "nioeventloop.run" in joined or "epolleventloop.run" in joined:
                # Check if packet was already handed off to a Folia scheduler/tick thread
                if not any(k in joined for k in ("tickregions", "regionizedtaskqueue", "entityscheduler.executetick", "globalregionscheduler")):
                    return "NETTY"
            if "global region" in h_low or "globalregionscheduler" in joined or "regionizedserver.globaltick" in joined:
                return "GLOBAL"
            if "entityscheduler.executetick" in joined or "craftentityscheduler" in joined or "entity.getscheduler()" in joined:
                return "ENTITY"
            if "region scheduler" in h_low or "tickregions" in joined or "regionizedtaskqueue" in joined or "craftregionscheduler" in joined:
                return "REGION"
            if (
                "async scheduler" in h_low
                or "craft async" in h_low
                or "folia async" in h_low
                or "foliaasyncscheduler" in joined
                or "craftasyncscheduler" in joined
                or "completablefuture$async" in joined
                or "forkjoinworkerthread" in joined
            ):
                return "ASYNC"
            if "server thread" in h_low:
                return "LEGACY_MAIN"
            return "UNKNOWN"

        findings: list[dict[str, Any]] = []
        thread_reports: list[dict[str, Any]] = []
        remediation_snippets: list[str] = []
        emitted: set[tuple[str, str, str]] = set()

        def record_violation(
            rule_id: str,
            name: str,
            severity: str,
            domain: str,
            thread_label: str,
            violating_frame: str,
            plugin_frame: str | None,
            plugin_name: str | None,
            message: str,
            snippet: str,
        ) -> None:
            key = (rule_id, domain, violating_frame)
            if key in emitted:
                return
            emitted.add(key)
            findings.append({
                "rule_id": rule_id,
                "name": name,
                "severity": severity,
                "active_domain": domain,
                "thread": thread_label,
                "violating_frame": violating_frame,
                "initiating_plugin_frame": plugin_frame,
                "plugin": plugin_name,
                "message": message,
                "remediation": snippet,
            })
            if snippet not in remediation_snippets:
                remediation_snippets.append(snippet)

        spatial_world_tokens = (
            "getblockat",
            "settype",
            "setblockdata",
            "setblock(",
            "getchunkat(",
            "getchunkat()",
            "loadchunk",
            "unloadchunk",
            "breaknaturally",
            "tilestate",
            "blockstate.update",
            "createexplosion",
            "generatechunk",
        )
        entity_mutation_tokens = (
            ".teleport(",
            ".teleport()",
            ".damage(",
            ".damage()",
            "addpotioneffect",
            "setvelocity",
            "spawnentity",
            "addpassenger",
            "removepassenger",
            "openinventory",
            "closeinventory",
            "getinventory().setitem",
            "getinventory().additem",
            "entity.remove",
        )
        global_iteration_tokens = (
            "bukkit.getonlineplayers",
            "server.getonlineplayers",
            "world.getplayers",
            "world.getentities",
            "world.getlivingentities",
        )
        blocking_wait_tokens = (
            "completablefuture.join",
            "completablefuture.waitingget",
            "futuretask.get",
            "abstractqueuedsynchronizer.acquire",
            "countdownlatch.await",
            "semaphore.acquire",
        )
        legacy_scheduler_tokens = (
            "bukkit.getscheduler()",
            "craftscheduler.runtask",
            "craftscheduler.schedulesync",
            "bukkitrunnable.runtask",
        )

        domains_detected: list[str] = []

        for header, raw_lines in blocks:
            frames = [
                self._demangle_jvm_frame(ln)
                for ln in raw_lines
                if ln != f'"{header}"' and not ln.startswith('"')
            ]
            domain = infer_domain(header, frames)
            if domain not in domains_detected:
                domains_detected.append(domain)

            plugin_frame: str | None = None
            plugin_name: str | None = None
            for fr in frames:
                kind, pname = self._attribute_frame_owner(fr)
                if kind in {"indexed_rpg_plugin", "third_party_plugin"} and pname:
                    plugin_frame = fr
                    plugin_name = pname
                    break

            block_violations = 0
            for fr in frames:
                low = fr.lower()

                # Rule 6: Legacy BukkitScheduler on Folia (applies in any domain)
                if any(tok in low for tok in legacy_scheduler_tokens):
                    block_violations += 1
                    record_violation(
                        "FOLIA-TRC-006",
                        "LegacyBukkitSchedulerOnFolia",
                        "critical",
                        domain,
                        header,
                        fr,
                        plugin_frame,
                        plugin_name,
                        f"Legacy BukkitScheduler call '{fr}' throws UnsupportedOperationException on Folia.",
                        "Declare folia-supported: true in paper-plugin.yml/plugin.yml and dispatch via Bukkit.getRegionScheduler(), entity.getScheduler(), Bukkit.getGlobalRegionScheduler(), or Bukkit.getAsyncScheduler().",
                    )

                # Rule 1: ASYNC mutating or reading regional world/entity/inventory state
                if domain == "ASYNC" and any(tok in low for tok in spatial_world_tokens + entity_mutation_tokens + global_iteration_tokens):
                    block_violations += 1
                    record_violation(
                        "FOLIA-TRC-001",
                        "AsyncWorldOrEntityMutation",
                        "critical",
                        domain,
                        header,
                        fr,
                        plugin_frame,
                        plugin_name,
                        f"ASYNC scheduler domain ('{header}') illegally accesses live world/entity state at '{fr}'.",
                        "Compute pure data asynchronously, then marshal world mutations to Bukkit.getRegionScheduler().execute(plugin, location, () -> ...) or entity mutations to entity.getScheduler().run(plugin, task -> ..., null).",
                    )

                # Rule 2: GLOBAL scheduler touching chunk/block/entity spatial state
                if domain == "GLOBAL" and any(tok in low for tok in spatial_world_tokens + entity_mutation_tokens):
                    block_violations += 1
                    record_violation(
                        "FOLIA-TRC-002",
                        "GlobalSchedulerSpatialEscape",
                        "critical",
                        domain,
                        header,
                        fr,
                        plugin_frame,
                        plugin_name,
                        f"GlobalRegionScheduler ('{header}') accesses chunk/block/entity spatial state at '{fr}'; GlobalRegionScheduler owns zero chunks or entities.",
                        "Do not treat GlobalRegionScheduler as a main-thread replacement for world edits. Dispatch block/chunk work via Bukkit.getRegionScheduler().execute(plugin, world, chunkX, chunkZ, () -> ...) and entity work via entity.getScheduler().",
                    )

                # Rule 3: REGION or ENTITY cross-region global iteration or synchronous teleport
                if domain in {"REGION", "ENTITY"}:
                    if any(tok in low for tok in global_iteration_tokens):
                        block_violations += 1
                        record_violation(
                            "FOLIA-TRC-003",
                            "CrossRegionCollectionIteration",
                            "high",
                            domain,
                            header,
                            fr,
                            plugin_frame,
                            plugin_name,
                            f"{domain} thread ('{header}') iterates global player/entity collection '{fr}' across foreign regions.",
                            "Snapshot player references safely and hop onto each player's owning region via player.getScheduler().run(plugin, task -> ..., null) before reading inventory, health, or location.",
                        )
                    elif (".teleport(" in low or ".teleport()" in low) and "teleportasync" not in low:
                        block_violations += 1
                        record_violation(
                            "FOLIA-TRC-003",
                            "SynchronousTeleportOnFolia",
                            "critical",
                            domain,
                            header,
                            fr,
                            plugin_frame,
                            plugin_name,
                            f"{domain} thread ('{header}') invokes synchronous '{fr}', which violates cross-region entity handoff on Folia.",
                            "Replace entity.teleport(destination) with entity.teleportAsync(destination).thenAccept(success -> ...) and run post-teleport logic inside entity.getScheduler().",
                        )

                # Rule 4: NETTY network I/O thread directly accessing world/entity/inventory
                if domain == "NETTY" and any(tok in low for tok in spatial_world_tokens + entity_mutation_tokens):
                    block_violations += 1
                    record_violation(
                        "FOLIA-TRC-004",
                        "NettyThreadSyncWorldAccess",
                        "critical",
                        domain,
                        header,
                        fr,
                        plugin_frame,
                        plugin_name,
                        f"Netty network EventLoop ('{header}') directly accesses live world/entity state at '{fr}' without scheduler handoff.",
                        "Decode packet fields into an immutable record on the Netty thread, then schedule world/player interaction onto player.getScheduler().run(plugin, task -> ..., null).",
                    )

                # Rule 5: Blocking future .join() / .get() / latch wait on REGION, ENTITY, or GLOBAL tick thread
                if domain in {"REGION", "ENTITY", "GLOBAL"} and any(tok in low for tok in blocking_wait_tokens):
                    block_violations += 1
                    record_violation(
                        "FOLIA-TRC-005",
                        "BlockingFutureWaitOnTickThread",
                        "critical",
                        domain,
                        header,
                        fr,
                        plugin_frame,
                        plugin_name,
                        f"Tick domain {domain} ('{header}') blocks synchronously on '{fr}', risking a ThreadedRegionizer merge/split barrier deadlock.",
                        "Never call CompletableFuture.join() or Future.get() on a Folia region, entity, or global tick thread; attach .thenAccept(...) and schedule the continuation back onto RegionScheduler or EntityScheduler.",
                    )

                # Rule 7: EntityScheduler delayed/repeating lifecycle hazard (null retired callback)
                if ("entityscheduler.rundelayed" in low or "entityscheduler.runatfixedrate" in low) and "null" in raw_trace.lower():
                    block_violations += 1
                    record_violation(
                        "FOLIA-TRC-007",
                        "EntitySchedulerMissingRetiredCallback",
                        "medium",
                        domain,
                        header,
                        fr,
                        plugin_frame,
                        plugin_name,
                        f"Delayed/repeating EntityScheduler registration '{fr}' detected alongside null retired callback; tasks silently drop cleanup if the entity dies or unloads before firing.",
                        "Pass an explicit Runnable retired callback (entity.getScheduler().runDelayed(plugin, task -> ..., () -> cleanupState(), delayTicks)) to release cooldowns, locks, or bossbars when the entity retires.",
                    )

            thread_reports.append({
                "thread": header,
                "inferred_domain": domain,
                "frame_count": len(frames),
                "initiating_plugin": plugin_name,
                "violations": block_violations,
            })

        severity_counts = {"critical": 0, "high": 0, "medium": 0, "low": 0}
        for f in findings:
            sev = f.get("severity", "low")
            if sev in severity_counts:
                severity_counts[sev] += 1

        ownership_matrix = {
            "REGION": {
                "owns": ["Chunks, blocks, and TileStates inside current region section", "Entities currently located inside region bounds"],
                "forbidden": ["Cross-world or distant chunk access", "Synchronous Entity.teleport()", "Blocking Future.join()/get()"],
            },
            "ENTITY": {
                "owns": ["Bound Entity instance across region splits, merges, and teleports", "Local chunk surrounding the bound entity while ticking"],
                "forbidden": ["Arbitrary distant coordinates", "Bukkit.getOnlinePlayers() direct iteration", "Blocking Future.join()/get()"],
            },
            "GLOBAL": {
                "owns": ["WorldBorder, weather, daytime, gamerules", "Console commands, global scoreboards/bossbars, PluginManager"],
                "forbidden": ["ALL chunks, blocks, block-entities, and entities"],
            },
            "ASYNC": {
                "owns": ["JDBC/HTTP I/O, cryptographic/JSON serialization, pure off-heap or immutable math"],
                "forbidden": ["ALL live Bukkit/NMS world, chunk, block, entity, and inventory APIs"],
            },
        }

        out: dict[str, Any] = {
            "status": "fail" if (severity_counts["critical"] + severity_counts["high"]) > 0 else ("warn" if findings else "pass"),
            "domains_detected": domains_detected,
            "threads_analyzed": len(thread_reports),
            "thread_traces": thread_reports,
            "state_ownership_matrix": ownership_matrix,
            "finding_count": len(findings),
            "severity_counts": severity_counts,
            "findings": findings,
            "remediation_snippets": remediation_snippets,
        }
        if sarif:
            out["sarif_report"] = self._build_sarif_report(findings)

        return ToolOutcome(_pretty_json(out))

    @staticmethod
    def _result_response(msg_id: Any, result: dict[str, Any]) -> str:
        return _compact_json({
            "jsonrpc": "2.0",
            "id": msg_id,
            "result": result,
        })

    @staticmethod
    def _error_response(msg_id: Any, code: int, message: str) -> str:
        return _compact_json({
            "jsonrpc": "2.0",
            "id": msg_id,
            "error": {
                "code": code,
                "message": message,
            },
        })


def _read_exact(stream: BinaryIO, byte_count: int) -> bytes:
    chunks: list[bytes] = []
    remaining = byte_count
    while remaining > 0:
        piece = stream.read(remaining)
        if not piece:
            break
        chunks.append(piece)
        remaining -= len(piece)
    return b"".join(chunks)


def read_rpc_message(stream: BinaryIO) -> tuple[str, bool] | None:
    """Read one newline-delimited or Content-Length-framed JSON-RPC message."""
    while True:
        first_line = stream.readline()
        if not first_line:
            return None
        if first_line in (b"\n", b"\r\n"):
            continue

        stripped_ascii = first_line.strip()
        if stripped_ascii.lower().startswith(b"content-length:"):
            _, _, raw_length = stripped_ascii.partition(b":")
            try:
                content_length = int(raw_length.strip().decode("ascii"))
            except ValueError as error:
                raise ValueError(f"Invalid Content-Length header: {first_line!r}") from error
            if content_length <= 0 or content_length > MAX_MESSAGE_BYTES:
                raise ValueError(f"Content-Length out of bounds: {content_length}")

            while True:
                header_line = stream.readline()
                if not header_line:
                    raise ValueError("Unexpected EOF while reading framed headers.")
                if header_line in (b"\n", b"\r\n"):
                    break

            body = _read_exact(stream, content_length)
            if len(body) != content_length:
                raise ValueError("Unexpected EOF while reading framed JSON-RPC body.")
            return body.decode("utf-8"), True

        if len(first_line) > MAX_MESSAGE_BYTES:
            raise ValueError("Newline-delimited JSON-RPC line exceeds safety limit.")
        return first_line.decode("utf-8").strip(), False


def write_rpc_message(stream: BinaryIO, response: str, framed: bool) -> None:
    payload = response.encode("utf-8")
    if framed:
        header = f"Content-Length: {len(payload)}\r\n\r\n".encode("ascii")
        stream.write(header)
        stream.write(payload)
    else:
        stream.write(payload + b"\n")
    stream.flush()


def serve_stdio(
    server: MinecraftKitMcpServer,
    input_stream: BinaryIO | None = None,
    output_stream: BinaryIO | None = None,
) -> int:
    reader = input_stream if input_stream is not None else sys.stdin.buffer
    writer = output_stream if output_stream is not None else sys.stdout.buffer
    while True:
        try:
            incoming = read_rpc_message(reader)
        except (UnicodeDecodeError, ValueError) as error:
            err = server._error_response(None, PARSE_ERROR, str(error))
            write_rpc_message(writer, err, framed=False)
            continue
        if incoming is None:
            return 0
        raw_text, framed = incoming
        response = server.handle_message(raw_text)
        if response is not None:
            write_rpc_message(writer, response, framed=framed)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root",
        type=Path,
        default=SCRIPTS_DIR.parent,
        help="Path to the canonical MinecraftKit root directory.",
    )
    args = parser.parse_args(argv)
    root = args.root.resolve()
    if not (root / "data").is_dir():
        print(f"MinecraftKit MCP server error: missing data directory under {root}", file=sys.stderr)
        return 2
    server = MinecraftKitMcpServer(root=root)
    return serve_stdio(server)


if __name__ == "__main__":
    raise SystemExit(main())
