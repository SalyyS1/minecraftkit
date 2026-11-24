#!/usr/bin/env python3
"""Headless VPS / Dedicated Minecraft Server Hardening, Anti-OOM Memory & Firewall Preflight Planner."""

from __future__ import annotations

from typing import Any


def plan_vps_deployment(
    *,
    vps_ram_gb: float = 8.0,
    vps_vcpu: int = 4,
    proxy_mode: str = "standalone",
    server_port: int = 25565,
    bridge_port: int = 25590,
    rcon_port: int = 25575,
    rcon_enabled: bool = False,
    concurrent_bots: int = 5,
    enable_visual_docker_bot: bool = False,
) -> dict[str, Any]:
    ram_gb = max(1.0, float(vps_ram_gb))
    vcpu = max(1, int(vps_vcpu))
    bots = max(0, min(int(concurrent_bots), 25))
    mode = proxy_mode.strip().lower()
    if mode not in ("standalone", "velocity-network", "bungeecord-network"):
        mode = "standalone"

    os_reserve_mb = 1024 if ram_gb >= 6 else 512
    bot_protocol_mb = bots * 42
    visual_container_mb = 1400 if enable_visual_docker_bot else 0
    total_ram_mb = int(ram_gb * 1024)
    available_for_mc_mb = total_ram_mb - os_reserve_mb - bot_protocol_mb - visual_container_mb
    recommended_heap_mb = max(1024, (available_for_mc_mb // 256) * 256)
    fits_safely = available_for_mc_mb >= 1024

    gc_flags = (
        ["-XX:+UseZGC", "-XX:+ZGenerational"]
        if recommended_heap_mb >= 12288 and vcpu >= 4
        else [
            "-XX:+UseG1GC",
            "-XX:+ParallelRefProcEnabled",
            "-XX:MaxGCPauseMillis=200",
            "-XX:+UnlockExperimentalVMOptions",
            "-XX:+DisableExplicitGC",
            "-XX:G1NewSizePercent=30",
            "-XX:G1MaxNewSizePercent=40",
            "-XX:G1HeapRegionSize=8M",
        ]
    )
    jvm_command = f"java -Xms{recommended_heap_mb}M -Xmx{recommended_heap_mb}M " + " ".join(gc_flags) + " -jar paper.jar --nogui"

    ufw_rules = [
        "ufw default deny incoming",
        "ufw default allow outgoing",
        "ufw allow 22/tcp comment 'SSH/SFTP (restrict to admin IP if static)'",
    ]
    if mode == "standalone":
        ufw_rules.append(f"ufw allow {server_port}/tcp comment 'Public Minecraft Java server'")
    else:
        ufw_rules.append(f"ufw allow 25565/tcp comment 'Public Velocity/Proxy edge ONLY'")
        ufw_rules.append(f"ufw deny {server_port}/tcp comment 'Block direct external access to offline backend'")
    ufw_rules.append(f"ufw deny {bridge_port}/tcp comment 'Keep mckit-bridge-plugin strictly loopback 127.0.0.1'")
    if rcon_enabled:
        ufw_rules.append(f"ufw deny {rcon_port}/tcp comment 'Never expose plaintext RCON publicly; use SSH tunnel'")

    warnings: list[str] = []
    if not fits_safely:
        warnings.append(
            f"VPS RAM ({ram_gb:.1f} GB) is too tight for MC server + {bots} protocol bots + visual Docker container; disable Tier-2 visual container on this host or upgrade to >= 4 GB."
        )
    if rcon_enabled:
        warnings.append("Source RCON is unencrypted; tunnel port via `ssh -L 25575:127.0.0.1:25575 user@vps` or prefer mckit-bridge-plugin loopback HTTP.")
    if mode != "standalone":
        warnings.append("Verify `server-ip=127.0.0.1` on backend Paper nodes and match Velocity modern forwarding secret (`mc_audit_proxy_topology`).")

    return {
        "ok": fits_safely,
        "vps_ram_gb": ram_gb,
        "vps_vcpu": vcpu,
        "proxy_mode": mode,
        "memory_budget_mb": {
            "total_vps_mb": total_ram_mb,
            "os_and_kernel_reserve_mb": os_reserve_mb,
            "tier1_protocol_bots_mb": bot_protocol_mb,
            "tier2_visual_docker_mb": visual_container_mb,
            "recommended_mc_heap_mb": recommended_heap_mb,
        },
        "recommended_jvm_command": jvm_command,
        "ufw_firewall_plan": ufw_rules,
        "sftp_security_checklist": [
            "Use dedicated non-root `minecraft` OS user with SSH key or vaulted password (`mc_ops_profile_vault`).",
            "Always deploy plugin JARs atomically via `plugins/.tmp -> rename` + SHA-256 (`mc_sftp_operations`).",
            "Keep `mckit-bridge-plugin` bound to `127.0.0.1` with a 32-byte random `X-MCKit-Token`.",
        ],
        "warnings": warnings,
    }
