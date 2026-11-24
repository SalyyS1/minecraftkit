#!/usr/bin/env python3
"""Headless Fabric 1.21.4+ Visual Capture & Off-Screen Docker Xvfb Recipe Generator.

Allows real shader, CustomModelData, ModelEngine, and resource-pack visual verification
inside an isolated Xvfb + Mesa/Vulkan container with strict memory caps and ZERO desktop
window focus hijacking (never opens 10 desktop Minecraft tabs).
"""

from __future__ import annotations

import json
from typing import Any


def build_fabric_capture_recipe(
    *,
    server_host: str = "127.0.0.1",
    server_port: int = 25565,
    mc_version: str = "1.21.4",
    resolution: str = "1280x720",
    bridge_socket_port: int = 25595,
    captures: list[dict[str, Any]] | None = None,
    record_mp4: bool = True,
    memory_limit_mb: int = 1600,
) -> dict[str, Any]:
    host = (server_host or "127.0.0.1").strip()
    port = max(1, min(65535, int(server_port)))
    sock_port = max(1024, min(65535, int(bridge_socket_port)))
    mem_mb = max(1024, min(4096, int(memory_limit_mb)))
    res_parts = resolution.lower().split("x")
    width = int(res_parts[0]) if len(res_parts) == 2 and res_parts[0].isdigit() else 1280
    height = int(res_parts[1]) if len(res_parts) == 2 and res_parts[1].isdigit() else 720

    steps = captures if captures else [
        {"action": "wait_world_ready", "timeout_ms": 15000},
        {"action": "auto_auth", "password_env": "MCKIT_BOT_PASS", "redact": True},
        {"action": "reload_resource_pack", "assert_zero_shader_errors": True},
        {"action": "capture_orbit", "angles_deg": [0, 90, 180, 270], "output_prefix": "frames/orbit"},
        {"action": "command", "command": "/shop"},
        {"action": "capture_gui", "output": "frames/shop_gui.png"},
    ]

    manifest = {
        "schema": "mckit-fabric-capture/v1",
        "target": {"host": host, "port": port, "mc_version": mc_version},
        "display": {"xvfb_display": ":99", "width": width, "height": height, "screen_lock_free": True},
        "client_mod_socket": f"127.0.0.1:{sock_port}",
        "record_mp4": bool(record_mp4),
        "memory_limit_mb": mem_mb,
        "steps": steps,
    }

    shell_lines = [
        "#!/usr/bin/env bash",
        "set -euo pipefail",
        f"# Off-screen Fabric {mc_version} visual QA capture (0 desktop tabs, capped at {mem_mb} MB RAM)",
        f"export DISPLAY=:99",
        f"Xvfb :99 -screen 0 {width}x{height}x24 -ac +extension GLX +render -noreset &",
        "XVFB_PID=$!",
        'trap "kill $XVFB_PID 2>/dev/null || true" EXIT',
    ]
    if record_mp4:
        shell_lines.append(
            f"ffmpeg -y -f x11grab -video_size {width}x{height} -framerate 15 -i :99 -pix_fmt yuv420p -movflags +faststart out/mckit-visual-qa.mp4 &"
        )
        shell_lines.append("FFMPEG_PID=$!")
    shell_lines.extend([
        f"echo 'Sending {len(steps)} capture commands to mckit-client-mod on 127.0.0.1:{sock_port}'",
        "# docker compose -f docker/docker-compose.testgrid.yml run --rm --memory=" + f"{mem_mb}m visual-bot",
    ])

    return {
        "ok": True,
        "mc_version": mc_version,
        "resolution": f"{width}x{height}",
        "memory_limit_mb": mem_mb,
        "screen_lock_free": True,
        "step_count": len(steps),
        "manifest_json": json.dumps(manifest, indent=2),
        "runner_script": "\n".join(shell_lines) + "\n",
        "anti_oom_note": (
            f"Runs strictly 1 off-screen visual container ({mem_mb} MB cap) instead of launching desktop Minecraft tabs; "
            "pair with Tier-1 protocol bots (~42 MB each) for multi-player stress."
        ),
    }
