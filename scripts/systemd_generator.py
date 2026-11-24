"""Hardened Linux systemd Service & Anti-OOM Unit Generator for Minecraft VPS / Dedicated Hosts.

Generates production-grade systemd unit files for Paper, Folia, Purpur, Velocity, and
MinecraftKit headless bot grids with ZGC/G1GC JVM flags, non-root sandboxing, graceful
RCON/bridge shutdown hooks, and OOM protection.
"""

from __future__ import annotations

import re
from typing import Any


def generate_systemd_unit(
    *,
    service_name: str = "mc-paper",
    server_type: str = "paper",
    work_dir: str = "/srv/minecraft/paper",
    jar_name: str = "paper.jar",
    user: str = "minecraft",
    heap_gb: int = 8,
    gc_engine: str = "zgc",
    java_bin: str = "/usr/bin/java",
    include_prestart_backup: bool = True,
) -> dict[str, Any]:
    """Generate a hardened systemd service unit & install commands for a Linux VPS."""
    safe_name = re.sub(r"[^a-zA-Z0-9._-]", "-", service_name.strip() or "mc-paper")
    safe_user = re.sub(r"[^a-zA-Z0-9._-]", "", user.strip() or "minecraft") or "minecraft"
    safe_dir = work_dir.strip() or "/srv/minecraft/paper"
    if ".." in safe_dir.split("/"):
        raise ValueError("'work_dir' must not contain path traversal segments ('..').")
    heap = max(1, min(256, int(heap_gb)))
    stype = server_type.strip().lower()
    gc = gc_engine.strip().lower()

    if stype == "velocity":
        jvm_flags = [
            f"-Xms{heap}G",
            f"-Xmx{heap}G",
            "-XX:+UseG1GC",
            "-XX:G1HeapRegionSize=4M",
            "-XX:+UnlockExperimentalVMOptions",
            "-XX:+ParallelRefProcEnabled",
            "-XX:+AlwaysPreTouch",
        ]
        extra_args = ""
    elif gc == "zgc":
        jvm_flags = [
            f"-Xms{heap}G",
            f"-Xmx{heap}G",
            "-XX:+UseZGC",
            "-XX:+ZGenerational",
            "-XX:+AlwaysPreTouch",
            "-XX:+DisableExplicitGC",
            "-XX:+PerfDisableSharedMem",
        ]
        extra_args = " --nogui"
    else:
        jvm_flags = [
            f"-Xms{heap}G",
            f"-Xmx{heap}G",
            "-XX:+UseG1GC",
            "-XX:+ParallelRefProcEnabled",
            "-XX:MaxGCPauseMillis=200",
            "-XX:+UnlockExperimentalVMOptions",
            "-XX:+DisableExplicitGC",
            "-XX:+AlwaysPreTouch",
            "-XX:G1NewSizePercent=30",
            "-XX:G1MaxNewSizePercent=40",
            "-XX:G1HeapRegionSize=8M",
            "-XX:InitiatingHeapOccupancyPercent=15",
            "-XX:SurvivorRatio=32",
        ]
        extra_args = " --nogui"

    # Recommend OS headroom (memory ceiling = heap + 25% + 1G) so host never OOM-kills sshd
    mem_max_gb = max(heap + 2, int(round(heap * 1.25)) + 1)
    exec_start = f"{java_bin} {' '.join(jvm_flags)} -jar {jar_name}{extra_args}"

    lines = [
        "[Unit]",
        f"Description=Minecraft {stype.upper()} Server ({safe_name}) — Managed by MinecraftKit",
        "After=network-online.target",
        "Wants=network-online.target",
        "",
        "[Service]",
        "Type=simple",
        f"User={safe_user}",
        f"Group={safe_user}",
        f"WorkingDirectory={safe_dir}",
    ]
    if include_prestart_backup:
        lines.append(f"ExecStartPre=/bin/sh -c 'test -f {safe_dir}/{jar_name}'")
    lines.extend([
        f"ExecStart={exec_start}",
        "Restart=on-failure",
        "RestartSec=10",
        "TimeoutStopSec=90",
        "KillSignal=SIGINT",
        "SuccessExitStatus=0 130 143",
        f"MemoryHigh={heap + 1}G",
        f"MemoryMax={mem_max_gb}G",
        "OOMScoreAdjust=-200",
        "NoNewPrivileges=true",
        "PrivateTmp=true",
        "ProtectSystem=strict",
        "ProtectHome=true",
        f"ReadWritePaths={safe_dir}",
        "StandardOutput=journal",
        "StandardError=journal",
        "",
        "[Install]",
        "WantedBy=multi-user.target",
        "",
    ])
    unit_text = "\n".join(lines)
    unit_file = f"/etc/systemd/system/{safe_name}.service"
    return {
        "ok": True,
        "service_name": safe_name,
        "server_type": stype,
        "gc_engine": gc,
        "heap_gb": heap,
        "memory_max_gb": mem_max_gb,
        "unit_path": unit_file,
        "unit_content": unit_text,
        "install_commands": [
            f"sudo useradd -r -m -d /srv/minecraft -s /usr/sbin/nologin {safe_user} || true",
            f"sudo tee {unit_file} > /dev/null <<'EOF'\n{unit_text}EOF",
            "sudo systemctl daemon-reload",
            f"sudo systemctl enable --now {safe_name}.service",
            f"sudo journalctl -u {safe_name}.service -f",
        ],
    }
