#!/usr/bin/env python3
"""Minecraft Java + ViaVersion + Bedrock/Geyser Protocol & Breaking-Change Compatibility Matrix."""

from __future__ import annotations

from typing import Any

PROTOCOL_TABLE: list[dict[str, Any]] = [
    {"mc": "1.20.4", "protocol": 765, "rp_format": 22, "dp_format": 26, "java": 17, "notes": "Last legacy NBT item format before Data Components."},
    {"mc": "1.20.6", "protocol": 766, "rp_format": 32, "dp_format": 41, "java": 21, "notes": "Introduced Item Data Components & Java 21 requirement."},
    {"mc": "1.21.1", "protocol": 767, "rp_format": 34, "dp_format": 48, "java": 21, "notes": "Datapack singular folder rename (function/, loot_table/, recipe/)."},
    {"mc": "1.21.4", "protocol": 769, "rp_format": 46, "dp_format": 61, "java": 21, "notes": "Introduced minecraft:item_model definitions & assets/<ns>/items/*.json."},
    {"mc": "1.21.5", "protocol": 770, "rp_format": 55, "dp_format": 71, "java": 21, "notes": "Custom tooltip_display, blocks_attacks, and updated shader uniform blocks."},
    {"mc": "1.21.11", "protocol": 774, "rp_format": 75, "dp_format": 94, "java": 21, "notes": "Modern Dialog API & unified registry-driven packs."},
    {"mc": "26.3", "protocol": 775, "rp_format": 84, "dp_format": 101, "java": 21, "notes": "Calendar-versioned Paper/Folia 26.x series with strict Core shaders & modern Components."},
]

BY_MC = {row["mc"]: row for row in PROTOCOL_TABLE}


def probe_protocol_matrix(
    *,
    server_version: str = "1.21.4",
    client_versions: list[str] | None = None,
    has_viaversion: bool = False,
    has_viabackwards: bool = False,
    has_geyser: bool = False,
) -> dict[str, Any]:
    srv_ver = (server_version or "1.21.4").strip()
    srv = BY_MC.get(srv_ver, BY_MC["1.21.4"])
    targets = client_versions if client_versions else [srv["mc"], "1.21.4", "26.3"]

    matrix: list[dict[str, Any]] = []
    warnings: list[str] = []
    for cv in targets:
        c = BY_MC.get(cv.strip())
        if not c:
            matrix.append({"client_mc": cv, "compatible": False, "via_required": "unknown", "reason": "Unrecognized Minecraft version."})
            continue
        if c["protocol"] == srv["protocol"]:
            matrix.append({"client_mc": c["mc"], "protocol": c["protocol"], "compatible": True, "via_required": "native", "reason": "Exact native protocol match."})
        elif c["protocol"] > srv["protocol"]:
            compat = bool(has_viaversion)
            matrix.append({
                "client_mc": c["mc"],
                "protocol": c["protocol"],
                "compatible": compat,
                "via_required": "ViaVersion",
                "reason": "Supported via ViaVersion." if compat else "Requires ViaVersion on proxy/server for newer clients.",
            })
        else:
            compat = bool(has_viaversion and has_viabackwards)
            matrix.append({
                "client_mc": c["mc"],
                "protocol": c["protocol"],
                "compatible": compat,
                "via_required": "ViaVersion + ViaBackwards",
                "reason": "Supported via ViaBackwards." if compat else "Requires ViaVersion + ViaBackwards for older clients.",
            })

    if srv["protocol"] >= 769 and has_viabackwards:
        warnings.append("1.21.4+ minecraft:item_model definitions require pack overlays (packmigrate) so older ViaBackwards clients render CustomModelData cleanly.")
    if has_geyser:
        warnings.append("Geyser/Bedrock enabled: verify Floodgate auth-type + Bedrock 2D GUI/custom-item geometry mappings (`mc_audit_proxy_topology`).")

    return {
        "ok": True,
        "server": srv,
        "recommended_bot_protocol": srv["protocol"],
        "bedrock_geyser_enabled": bool(has_geyser),
        "client_matrix": matrix,
        "warnings": warnings,
        "known_versions": [r["mc"] for r in PROTOCOL_TABLE],
    }
