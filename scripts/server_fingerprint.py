#!/usr/bin/env python3
"""Unified 1-Call Live Minecraft Server Fingerprinter & Bot Strategy Advisor.

Combines pure-Python Java Edition SLP TCP probing, optional Bedrock/Geyser UDP
RakNet probing, optional companion `mckit-bridge-plugin` health inspection, and
protocol matrix resolution into a single ~15 MB, zero-GUI preflight call.
"""

from __future__ import annotations

import re
from typing import Any

import bot_engine
import protocol_version_matrix


def _infer_brand(version_name: str, motd: str) -> str:
    hay = f"{version_name} {motd}".lower()
    for brand in ("folia", "purpur", "paper", "pufferfish", "velocity", "bungeecord", "waterfall", "fabric", "neoforge", "forge", "spigot"):
        if brand in hay:
            return brand
    return "vanilla-or-custom"


def _extract_mc_version(version_name: str) -> str:
    m = re.search(r"(\d+\.\d+(?:\.\d+)?)", version_name or "")
    return m.group(1) if m else "1.21.4"


def fingerprint_server_stack(
    *,
    host: str = "127.0.0.1",
    port: int = 25565,
    probe_bedrock: bool = False,
    bedrock_port: int = 19132,
    bridge_url: str = "",
    bridge_token: str = "",
    timeout_seconds: float = 2.5,
) -> dict[str, Any]:
    """Fingerprint a live Minecraft server stack and recommend exact headless bot parameters."""
    java_res = bot_engine.ping_minecraft_server(host, int(port), timeout_seconds=float(timeout_seconds))
    bedrock_res: dict[str, Any] | None = None
    if probe_bedrock:
        bedrock_res = bot_engine.ping_bedrock_server(host, int(bedrock_port), timeout_seconds=float(timeout_seconds))

    bridge_res: dict[str, Any] | None = None
    if bridge_url.strip():
        bridge_res = bot_engine.query_bridge_plugin(
            base_url=bridge_url.strip(),
            token=bridge_token,
            endpoint="health",
            timeout_seconds=float(timeout_seconds),
        )

    version_name = str(java_res.get("version_name") or java_res.get("version") or "")
    motd = str(java_res.get("motd") or "")
    brand = _infer_brand(version_name, motd)
    mc_ver = _extract_mc_version(version_name)
    proto_matrix = protocol_version_matrix.probe_protocol_matrix(
        server_version=mc_ver,
        has_geyser=bool(bedrock_res and bedrock_res.get("reachable")),
    )

    proto_num = java_res.get("protocol") or proto_matrix["recommended_bot_protocol"]
    is_proxy = brand in ("velocity", "bungeecord", "waterfall")
    recommended_preset = (
        "folia_region_stress" if brand == "folia"
        else "authme_lobby" if is_proxy
        else "rpg_shop_gui"
    )

    return {
        "ok": bool(java_res.get("reachable")) or bool(bedrock_res and bedrock_res.get("reachable")),
        "host": host,
        "port": int(port),
        "screen_lock_free": True,
        "estimated_probe_ram_mb": 15,
        "detected_brand": brand,
        "detected_mc_version": mc_ver,
        "detected_protocol": proto_num,
        "java_slp": java_res,
        "bedrock_udp": bedrock_res,
        "bridge_plugin": bridge_res,
        "recommended_bot_config": {
            "tier": "tier1-protocol",
            "host": host,
            "port": int(port),
            "version": mc_ver,
            "protocol_version": proto_num,
            "preset": recommended_preset,
            "estimated_ram_mb_per_bot": 42,
        },
        "protocol_warnings": proto_matrix["warnings"],
    }
