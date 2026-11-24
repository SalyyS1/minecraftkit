"""Pure-Python Paper / Purpur / Spigot / Bukkit Server Config Performance & Anti-Lag Auditor.

Audits server.properties, bukkit.yml, spigot.yml, and paper-world-defaults.yml offline
without booting a JVM, emitting prioritized performance & safety findings plus copy-paste
tuning patches.
"""

from __future__ import annotations

import re
from typing import Any


def _extract_int(text: str, key: str) -> int | None:
    m = re.search(rf"(?im)^\s*{re.escape(key)}\s*[:=]\s*(-?\d+)\b", text)
    return int(m.group(1)) if m else None


def _extract_bool(text: str, key: str) -> bool | None:
    m = re.search(rf"(?im)^\s*{re.escape(key)}\s*[:=]\s*(true|false)\b", text)
    if not m:
        return None
    return m.group(1).lower() == "true"


def _extract_str(text: str, key: str) -> str | None:
    m = re.search(rf"(?im)^\s*{re.escape(key)}\s*[:=]\s*([^\r\n#]+)", text)
    return m.group(1).strip().strip("'\"") if m else None


def audit_paper_server_config(
    config_text: str,
    *,
    expected_players: int = 50,
    is_folia: bool = False,
) -> dict[str, Any]:
    """Audit Paper/Purpur/Spigot/Bukkit config text for TPS lag & safety traps.

    Rules:
      - CFG-001 (critical): sync-chunk-writes=true blocking tick loop on disk fsync
      - CFG-002 (high): view-distance or simulation-distance oversized for player count
      - CFG-003 (high): Uncapped spawn-limits / hopper-check / excessive entity activation ranges
      - CFG-004 (medium): Missing anti-xray or treasure-maps-find-already-discovered=false (sync chunk gen freeze!)
      - CFG-005 (high): Dangerous max-tick-time, network-compression-threshold, or unoptimized region-file-compression
    """
    if not isinstance(config_text, str) or not config_text.strip():
        raise ValueError("'config_text' must be a non-empty Paper/Spigot/Bukkit/server.properties snippet.")

    findings: list[dict[str, Any]] = []
    patches: list[str] = []

    # CFG-001: sync-chunk-writes=true
    if _extract_bool(config_text, "sync-chunk-writes") is True:
        findings.append({
            "rule_id": "CFG-001",
            "severity": "critical",
            "title": "sync-chunk-writes=true stalls main/region tick threads on disk I/O",
            "remediation": "Set sync-chunk-writes=false in server.properties (Paper/Folia uses async Moonrise chunk I/O).",
        })
        patches.append("server.properties -> sync-chunk-writes=false")

    # CFG-002: view-distance / simulation-distance
    view_dist = _extract_int(config_text, "view-distance")
    sim_dist = _extract_int(config_text, "simulation-distance")
    max_safe_sim = 6 if expected_players >= 40 else 8
    max_safe_view = 10 if expected_players >= 40 else 12
    if sim_dist is not None and sim_dist > max_safe_sim:
        findings.append({
            "rule_id": "CFG-002",
            "severity": "high",
            "title": f"simulation-distance={sim_dist} ticks {(2*sim_dist+1)**2} chunks per player (recommended <= {max_safe_sim} for {expected_players} players)",
            "remediation": f"Lower simulation-distance to {max_safe_sim} while keeping view-distance higher for visuals.",
        })
        patches.append(f"server.properties -> simulation-distance={max_safe_sim}")
    if view_dist is not None and view_dist > max_safe_view:
        findings.append({
            "rule_id": "CFG-002",
            "severity": "medium",
            "title": f"view-distance={view_dist} increases chunk RAM & Netty bandwidth heavily for {expected_players} players",
            "remediation": f"Cap view-distance at {max_safe_view} (use Paper no-tick-view-distance / send-distance tuning).",
        })
        patches.append(f"server.properties -> view-distance={max_safe_view}")

    # CFG-003: Mob spawns, hoppers & entity activation
    monsters = _extract_int(config_text, "monsters")
    if monsters is not None and monsters > 50:
        findings.append({
            "rule_id": "CFG-003",
            "severity": "high",
            "title": f"bukkit.yml spawn-limits.monsters={monsters} causes AI pathfinding tick spikes",
            "remediation": "Tune monsters to 35-50 (and enable per-player-mob-spawns: true in paper-world-defaults.yml).",
        })
        patches.append("bukkit.yml -> spawn-limits.monsters: 45")

    hopper_check = _extract_int(config_text, "hopper-check")
    if hopper_check is not None and hopper_check <= 1:
        findings.append({
            "rule_id": "CFG-003",
            "severity": "medium",
            "title": f"spigot.yml ticks-per.hopper-check={hopper_check} polls idle hoppers every tick",
            "remediation": "Set hopper-check: 3 (and disable-move-event: true in paper-world-defaults.yml if plugins allow).",
        })
        patches.append("spigot.yml -> ticks-per.hopper-check: 3")

    if _extract_bool(config_text, "per-player-mob-spawns") is False:
        findings.append({
            "rule_id": "CFG-003",
            "severity": "high",
            "title": "per-player-mob-spawns is disabled — single mob farms starve global spawn cap",
            "remediation": "Set per-player-mob-spawns: true in paper-world-defaults.yml.",
        })
        patches.append("paper-world-defaults.yml -> entities.spawning.per-player-mob-spawns: true")

    # CFG-004: Treasure map sync chunk gen trap & anti-xray
    if _extract_bool(config_text, "find-already-discovered") is False or re.search(
        r"(?i)treasure-maps-find-already-discovered\s*:\s*false", config_text
    ):
        findings.append({
            "rule_id": "CFG-004",
            "severity": "high",
            "title": "Treasure maps search undiscovered chunks synchronously — causes multi-second server freezes",
            "remediation": "Set treasure-maps.find-already-discovered.villager-trade & loot-tables to true.",
        })
        patches.append("paper-world-defaults.yml -> environment.treasure-maps.find-already-discovered: true")

    if re.search(r"(?i)anti-xray[\s\S]{0,60}enabled\s*:\s*false", config_text):
        findings.append({
            "rule_id": "CFG-004",
            "severity": "medium",
            "title": "Paper built-in Anti-Xray is disabled",
            "remediation": "Enable anticheat.anti-xray.enabled: true (engine-mode: 2) for zero-plugin ore protection.",
        })
        patches.append("paper-world-defaults.yml -> anticheat.anti-xray.enabled: true (engine-mode: 2)")

    # CFG-005: Compression & region compression & Folia
    net_comp = _extract_int(config_text, "network-compression-threshold")
    if net_comp is not None and 0 <= net_comp < 256:
        findings.append({
            "rule_id": "CFG-005",
            "severity": "medium",
            "title": f"network-compression-threshold={net_comp} wastes Netty CPU compressing tiny packets",
            "remediation": "Set network-compression-threshold=256 (or -1 behind a local Velocity proxy on 127.0.0.1).",
        })
        patches.append("server.properties -> network-compression-threshold=256 (or -1 behind local proxy)")

    reg_comp = _extract_str(config_text, "region-file-compression")
    if reg_comp and reg_comp.lower() in ("deflate", "zlib"):
        findings.append({
            "rule_id": "CFG-005",
            "severity": "medium",
            "title": f"region-file-compression={reg_comp} is significantly slower than LZ4 on modern NVMe",
            "remediation": "Use region-file-compression=lz4 for faster chunk load/save throughput.",
        })
        patches.append("server.properties -> region-file-compression=lz4")

    if is_folia and _extract_bool(config_text, "prevent-moving-into-unloaded-chunks") is False:
        findings.append({
            "rule_id": "CFG-005",
            "severity": "high",
            "title": "prevent-moving-into-unloaded-chunks=false risks region-boundary stalls on Folia",
            "remediation": "Set chunks.prevent-moving-into-unloaded-chunks: true in paper-world-defaults.yml.",
        })
        patches.append("paper-world-defaults.yml -> chunks.prevent-moving-into-unloaded-chunks: true")

    crit = sum(1 for f in findings if f["severity"] == "critical")
    high = sum(1 for f in findings if f["severity"] == "high")
    med = sum(1 for f in findings if f["severity"] == "medium")
    score = max(0, 100 - crit * 30 - high * 15 - med * 8)
    grade = "A" if score >= 90 else ("B" if score >= 78 else ("C" if score >= 62 else ("D" if score >= 45 else "F")))

    return {
        "ok": crit == 0 and high == 0,
        "status": "pass" if (crit == 0 and high == 0) else "fail",
        "grade": grade,
        "score": score,
        "expected_players": int(expected_players),
        "is_folia": bool(is_folia),
        "finding_count": len(findings),
        "findings": findings,
        "recommended_patches": patches,
    }
