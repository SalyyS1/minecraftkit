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
        return "2.3.0"

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
)


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

        return self._error_response(msg_id, METHOD_NOT_FOUND, f"Unsupported method: {method}")

    def _initialize(self, params: dict[str, Any]) -> dict[str, Any]:
        requested = params.get("protocolVersion")
        agreed = requested if isinstance(requested, str) and requested in SUPPORTED_PROTOCOL_VERSIONS else PROTOCOL_VERSION
        return {
            "protocolVersion": agreed,
            "capabilities": {
                "tools": {"listChanged": False},
            },
            "serverInfo": {
                "name": "minecraftkit",
                "version": self.store.kit_version(),
            },
            "instructions": (
                "Offline Minecraft engineering knowledge server backed by Salyyy Minecraft Kit catalogs. "
                "Use mc_route_skill first to select the right mc:* engineering domain, mc_version_capabilities "
                "to pin exact Minecraft/protocol/pack formats, mc_search_sources for reviewed upstream GitHub "
                "repositories, and mc_list_plugins / mc_search_api for verified RPG plugin bytecode signatures."
            ),
        }

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
