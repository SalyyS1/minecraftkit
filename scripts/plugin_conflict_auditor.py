"""Cross-Plugin Conflict, Dependency & Folia Compatibility Matrix Auditor.

Inspects a server's plugin list (names or a local `plugins/` folder) before deployment
to catch auth collisions, resource-pack engine fights (ItemsAdder/Oraxen/Nexo),
missing core dependencies (MythicLib, Vault, MythicMobs), and Folia threading hazards.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any


def _norm(name: str) -> str:
    stem = re.sub(r"\.jar$", "", name.strip(), flags=re.IGNORECASE)
    stem = re.sub(r"[-_ ]+v?\d+(?:\.\d+)*(?:[-+._a-zA-Z0-9]*)?$", "", stem)
    return re.sub(r"[^a-z0-9]+", "", stem.lower())


_EXCLUSIVE_GROUPS: tuple[tuple[str, str, tuple[str, ...], str], ...] = (
    (
        "CONFLICT-AUTH",
        "Multiple authentication plugins active simultaneously",
        ("authme", "authmereloaded", "nlogin", "openlogin", "limboauth", "fastlogin", "librelogin"),
        "Running two login plugins causes double /login prompts, session lockouts, and broken autonomous bot auto-auth. Keep one auth plugin per network.",
    ),
    (
        "CONFLICT-PACK",
        "Multiple resource-pack item engines active simultaneously",
        ("itemsadder", "oraxen", "nexo", "craftengine"),
        "Competing resource-pack engines overwrite pack.mcmeta, custom_model_data namespaces, and shaders. Migrate to one pack engine or unify outputs with SalyyS1/packmerge.",
    ),
    (
        "CONFLICT-PERM",
        "Multiple permissions managers detected",
        ("luckperms", "permissionsex", "groupmanager", "ultrapermissions"),
        "Conflicting permission plugins cause unpredictable node resolution and Vault hook races. Standardize on LuckPerms.",
    ),
)

_REQUIRED_DEPS: tuple[tuple[str, tuple[str, ...], str], ...] = (
    ("mmoitems", ("mythiclib",), "MMOItems requires MythicLib to load stats, skills, and NBT serialization."),
    ("mmocore", ("mythiclib",), "MMOCore requires MythicLib to register classes, mana, and skill trees."),
    ("mmoinventory", ("mythiclib",), "MMOInventory requires MythicLib."),
    ("mythiccrucible", ("mythicmobs",), "MythicCrucible requires MythicMobs installed in plugins/."),
    ("mythicenchants", ("mythicmobs",), "MythicEnchants requires MythicMobs installed in plugins/."),
    ("shopguiplus", ("vault",), "ShopGUIPlus requires Vault + an Economy provider (EssentialsX / CMI)."),
    ("modelengine", ("protocollib", "packetevents"), "ModelEngine requires ProtocolLib or PacketEvents for packet-based bone rendering."),
)

_FOLIA_CAUTION: dict[str, str] = {
    "protocollib": "Legacy ProtocolLib builds hook global Bukkit schedulers; verify Folia-patched dev build or prefer PacketEvents.",
    "authme": "Standard AuthMeReloaded uses BukkitScheduler; use a Folia-compatible fork or proxy-level LimboAuth/LibreLogin.",
    "authmereloaded": "Standard AuthMeReloaded uses BukkitScheduler; use a Folia-compatible fork or proxy-level LimboAuth/LibreLogin.",
    "citizens": "Verify Folia-specific Citizens build; entity teleport/navigation tasks must run on EntityScheduler.",
    "worldedit": "Ensure FAWE/WorldEdit Folia build is used; legacy sync edits crash ThreadedRegionizer.",
}


def audit_plugin_matrix(
    *,
    plugins: list[str] | None = None,
    plugins_dir: str = "",
    platform: str = "paper",
) -> dict[str, Any]:
    """Audit a list of plugins (or a `plugins/` directory) for conflicts, missing deps, and Folia risks."""
    raw_names: list[str] = [str(p).strip() for p in (plugins or []) if str(p).strip()]
    if plugins_dir.strip():
        pdir = Path(plugins_dir.strip()).expanduser().resolve()
        if not pdir.is_dir():
            raise ValueError(f"Plugins directory not found: {pdir}")
        for entry in sorted(pdir.iterdir()):
            if entry.is_file() and entry.name.lower().endswith(".jar"):
                raw_names.append(entry.name)

    if not raw_names:
        raise ValueError("Provide at least one entry in 'plugins' or a valid 'plugins_dir' containing .jar files.")

    norm_map: dict[str, list[str]] = {}
    for raw in raw_names:
        key = _norm(raw)
        if not key:
            continue
        norm_map.setdefault(key, []).append(raw)

    findings: list[dict[str, Any]] = []

    # 1. Duplicate JAR versions for the same plugin
    for key, originals in sorted(norm_map.items()):
        if len(originals) > 1:
            findings.append({
                "rule_id": "MATRIX-001",
                "severity": "error",
                "plugins": originals,
                "message": f"Duplicate plugin JARs detected for '{key}': {', '.join(originals)}. Remove older version to avoid classloader collisions.",
            })

    # 2. Mutually exclusive groups
    for rule_id, title, group, advice in _EXCLUSIVE_GROUPS:
        present = [norm_map[k][0] for k in group if k in norm_map]
        if len(present) > 1:
            findings.append({
                "rule_id": rule_id,
                "severity": "error",
                "plugins": present,
                "message": f"{title}: {', '.join(present)}. {advice}",
            })

    # 3. Missing required dependencies
    for plugin_key, any_of_deps, reason in _REQUIRED_DEPS:
        if plugin_key in norm_map and not any(dep in norm_map for dep in any_of_deps):
            findings.append({
                "rule_id": "MATRIX-002",
                "severity": "error",
                "plugins": norm_map[plugin_key],
                "missing_dependency": list(any_of_deps),
                "message": f"Missing required dependency ({' or '.join(any_of_deps)}) for {norm_map[plugin_key][0]}: {reason}",
            })

    # 4. Folia regionized threading compatibility checks
    plat = platform.strip().lower()
    if plat == "folia":
        for key, note in _FOLIA_CAUTION.items():
            if key in norm_map:
                findings.append({
                    "rule_id": "MATRIX-FOLIA",
                    "severity": "warning",
                    "plugins": norm_map[key],
                    "message": f"Folia compatibility caution for {norm_map[key][0]}: {note}",
                })

    has_error = any(f["severity"] == "error" for f in findings)
    return {
        "ok": not has_error,
        "status": "fail" if has_error else ("warn" if findings else "pass"),
        "platform": plat,
        "plugin_count": len(raw_names),
        "unique_plugins": len(norm_map),
        "finding_count": len(findings),
        "findings": findings,
    }
