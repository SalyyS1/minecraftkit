"""Multi-Server Velocity + Backend Mesh Autonomous Bot QA Planner."""

from __future__ import annotations

from typing import Any


def plan_multiserver_mesh(
    *,
    proxy_host: str = "play.example.net",
    proxy_port: int = 25565,
    backends: list[str] | None = None,
    bots_per_backend: int = 2,
    include_visual_xvfb: bool = False,
    has_bedrock_geyser: bool = False,
    mc_version: str = "1.21.4",
) -> dict[str, Any]:
    """Plan an anti-OOM autonomous bot QA mesh spanning Velocity proxy and N Paper/Folia backends."""
    clean_backends = [str(b).strip() for b in (backends or ["lobby", "survival", "skyblock"]) if str(b).strip()]
    if not clean_backends:
        clean_backends = ["lobby", "survival"]
    per_be = max(1, min(8, int(bots_per_backend)))
    total_bots = min(25, len(clean_backends) * per_be)

    protocol_bots = max(0, total_bots - (1 if include_visual_xvfb else 0))
    visual_bots = 1 if include_visual_xvfb else 0
    total_ram_mb = protocol_bots * 42 + visual_bots * 1400
    desktop_ram_mb = total_bots * 2600
    ram_saved_pct = round((1.0 - (total_ram_mb / float(max(1, desktop_ram_mb)))) * 100.0, 1)

    backend_plan: list[dict[str, Any]] = []
    stages: list[dict[str, Any]] = [
        {"name": "Proxy SLP & Auth Handshake", "action": "join", "target": f"{proxy_host}:{int(proxy_port)}"},
        {"name": "Auto-Auth (Secrets Redacted)", "action": "auto_auth", "redact_secrets": True},
    ]

    for idx, name in enumerate(clean_backends):
        bridge_port = 25590 + idx
        backend_plan.append({
            "backend": name,
            "assigned_bots": per_be,
            "stagger_delay_ms": idx * 900,
            "bridge_loopback_url": f"http://127.0.0.1:{bridge_port}",
            "verify_command": f"/server {name}",
        })
        stages.append({
            "name": f"Cross-Server Transfer -> {name}",
            "action": "command",
            "command": f"/server {name}",
            "bridge_health_url": f"http://127.0.0.1:{bridge_port}/api/v1/health",
        })
        stages.append({
            "name": f"Capture {name} HUD & Telemetry PNG",
            "action": "snapshot",
            "attach_to_chat": True,
        })

    return {
        "ok": True,
        "proxy": {"host": str(proxy_host), "port": int(proxy_port), "mc_version": str(mc_version), "geyser_udp_19132": bool(has_bedrock_geyser)},
        "fleet": {
            "total_bots": total_bots,
            "tier1_protocol_bots": protocol_bots,
            "tier2_xvfb_visual_bots": visual_bots,
            "estimated_ram_mb": total_ram_mb,
            "equivalent_desktop_ram_mb": desktop_ram_mb,
            "ram_saved_pct": ram_saved_pct,
            "screen_lock_free": True,
        },
        "backends": backend_plan,
        "mesh_stages": stages,
        "recommended_cloud_host": (
            "Oracle Cloud Always-Free ARM64 24 GB ($0/mo)" if total_ram_mb <= 18000 else "Hetzner CX42 16 GB"
        ),
    }
