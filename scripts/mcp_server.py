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
        "tick", "server", "proxy", "bungeecord", "waterfall",
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
    ),
    "protocol": (
        "netty", "bytebuf", "friendlybytebuf", "registryfriendlybytebuf", "streamcodec",
        "channel", "play state", "configuration state", "handshake", "packetlistener",
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
        return "2.5.0"

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
)

_DATA_BREAKING_EPOCHS: tuple[tuple[str, str, str], ...] = (
    ("overlay_1_20_5_components", "1.20.5", "Structured item data components replaced raw NBT tags across recipes, loot tables, and predicates."),
    ("overlay_1_21_singular_dirs", "1.21", "Registry folders renamed from plural to singular (loot_table, recipe, tags/item, tags/block) plus data-driven enchantments."),
    ("overlay_1_21_5_predicates", "1.21.5", "Updated entity/item component predicates and dialog data definitions."),
    ("overlay_26_1_modern", "26.1", "Year-based 26.x data pack registry schema updates."),
)


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
                "hierarchies and signatures, mc_generate_pack_overlay for multi-version pack.mcmeta generation, and "
                "mc_audit_gradle_build / mc_audit_paper_plugin_yml / mc_folia_migration_advisor / "
                "mc_diagnose_server_log for static build, descriptor, region-threading, and crash-log verification."
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
            }
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
