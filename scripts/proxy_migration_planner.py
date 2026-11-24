"""BungeeCord / Waterfall -> Velocity (Modern Forwarding) Migration & Rollback Planner."""

from __future__ import annotations

from typing import Any


_PLUGIN_MAP: dict[str, tuple[str, str]] = {
    "bungeetablistplus": ("TAB (Velocity)", "Use TAB universal JAR on Velocity with backend bridge."),
    "authme": ("AuthMeVelocity / LimboAuth", "Add AuthMeVelocity on Velocity + AuthMeBungee disabled, or migrate to LimboAuth."),
    "geyser-bungeecord": ("Geyser-Velocity + Floodgate-Velocity", "Install Geyser-Velocity & Floodgate on Velocity; share key.pem with Paper backends."),
    "luckperms-bungee": ("LuckPerms-Velocity", "Switch proxy JAR to LuckPerms-Velocity pointing to the same MySQL/MariaDB database."),
    "viaversion": ("ViaVersion on Velocity (or Backend)", "Run ViaVersion on Velocity for network-wide protocol translation or keep per-backend for plugin API hooks."),
    "bungeeguard": ("Native Velocity Modern Forwarding", "Remove BungeeGuard; Velocity modern forwarding signs every login with HMAC-SHA256."),
    "skinsrestorer": ("SkinsRestorer (Velocity)", "Install SkinsRestorer proxy mode on Velocity and keep backend sync enabled."),
    "viabackwards": ("ViaBackwards on Velocity", "Pair with ViaVersion on Velocity to let 1.20.x clients join 1.21.4+ backends."),
}


def plan_proxy_migration(
    *,
    source_proxy: str = "waterfall",
    backend_servers: list[str] | None = None,
    plugins: list[str] | None = None,
    has_bedrock_geyser: bool = False,
    mc_version: str = "1.21.4",
) -> dict[str, Any]:
    """Generate a zero-downtime BungeeCord/Waterfall -> Velocity modern forwarding migration plan."""
    src = str(source_proxy or "waterfall").strip().lower()
    if src not in {"bungeecord", "waterfall", "flamecord", "travertine"}:
        src = "waterfall"

    backends = [str(s).strip() for s in (backend_servers or ["lobby", "survival"]) if str(s).strip()]
    if not backends:
        backends = ["lobby", "survival"]

    installed = [str(p).strip() for p in (plugins or []) if str(p).strip()]
    replacements: list[dict[str, str]] = []
    seen: set[str] = set()
    for p in installed:
        key = p.lower().replace(".jar", "")
        for needle, (target, note) in _PLUGIN_MAP.items():
            if needle in key and needle not in seen:
                seen.add(needle)
                replacements.append({"from": p, "to": target, "action": note})

    if has_bedrock_geyser and "geyser-bungeecord" not in seen:
        replacements.append({
            "from": "Bedrock Cross-Play",
            "to": "Geyser-Velocity + Floodgate-Velocity",
            "action": "Copy Floodgate key.pem to every Paper backend and set auth-type: floodgate in Geyser config.yml.",
        })

    backend_toml = "\n".join(
        f'{name} = "127.0.0.1:{25566 + idx}"' for idx, name in enumerate(backends)
    )
    velocity_toml = f"""# Velocity 3.4+ Modern Forwarding Configuration (Migrated from {src})
bind = "0.0.0.0:25565"
online-mode = true
force-key-authentication = true
player-info-forwarding-mode = "modern"
forwarding-secret-file = "forwarding.secret"

[servers]
{backend_toml}
try = ["{backends[0]}"]
"""

    paper_global_yml = """# Paper / Folia config/paper-global.yml (apply to EVERY backend)
proxies:
  bungee-cord:
    online-mode: false
  velocity:
    enabled: true
    online-mode: true
    secret: "${VELOCITY_FORWARDING_SECRET}"
"""

    firewall_cmds = [
        "ufw allow 25565/tcp comment 'Velocity Java Proxy'",
        *(["ufw allow 19132/udp comment 'Geyser Bedrock UDP'"] if has_bedrock_geyser else []),
        f"ufw deny 25566:{25566 + len(backends) + 4}/tcp comment 'Block direct backend bypass'",
    ]

    steps = [
        "1. Snapshot all configs via SFTP (.mckit.bak) and run `mc_ops_plan_disaster_recovery` before cutover.",
        "2. Generate 32-byte random `forwarding.secret` (chmod 0600) and distribute via env/secret file — NEVER commit to Git.",
        "3. Update each Paper/Folia backend: set `server.properties` `online-mode=false`, `server-ip=127.0.0.1`, and `paper-global.yml` `proxies.velocity.enabled=true`.",
        "4. Replace legacy BungeeCord/Waterfall plugins with native Velocity equivalents and verify with `mc_ops_audit_velocity_config`.",
        "5. Lock backend TCP ports with UFW/iptables so players cannot spoof UUIDs by bypassing Velocity.",
        f"6. Boot staging stack and run headless Tier-1 bot QA (`mc_bot_run_stages` on {mc_version}) to verify AuthMe/LimboAuth, `/server {backends[0]}`, and UUID preservation.",
    ]

    return {
        "ok": True,
        "source_proxy": src,
        "target_proxy": "velocity-3.4+",
        "forwarding_mode": "modern",
        "mc_version": mc_version,
        "backend_count": len(backends),
        "plugin_replacements": replacements,
        "velocity_toml_snippet": velocity_toml,
        "paper_global_yml_snippet": paper_global_yml,
        "firewall_commands": firewall_cmds,
        "migration_steps": steps,
        "rollback_plan": (
            "If bot QA fails forwarding or UUID checks, restore `.mckit.bak` copies of `paper-global.yml` and "
            "`spigot.yml` over SFTP and restart the previous proxy unit."
        ),
    }
