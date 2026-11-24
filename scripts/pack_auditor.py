"""Pure-Python Minecraft Resource Pack Bundle Auditor (pack.mcmeta, items/, font/, models/).

Integrates SalyyS1's packmigrate, packmerge, and glyphsmith contracts directly into
MinecraftKit's stdio MCP server with zero external dependencies.
"""

from __future__ import annotations

import json
import re
from typing import Any

# Canonical Minecraft Java Edition resource pack formats.
PACK_FORMAT_BY_MC: dict[str, int] = {
    "1.20.4": 22,
    "1.20.6": 32,
    "1.21": 34,
    "1.21.1": 34,
    "1.21.3": 42,
    "1.21.4": 46,
    "1.21.5": 55,
    "1.21.6": 63,
    "1.21.11": 75,
    "26.1": 84,
    "26.2": 88,
    "26.3": 88,
}

VALID_RESOURCE_PATH_RE = re.compile(r"^[a-z0-9/._-]+$")
VALID_ITEM_MODEL_TYPES = frozenset({
    "minecraft:model",
    "minecraft:condition",
    "minecraft:select",
    "minecraft:range_dispatch",
    "minecraft:composite",
    "minecraft:bundle/selected_item",
    "minecraft:empty",
    "minecraft:special",
})


def audit_resource_pack_bundle(
    files: dict[str, Any],
    *,
    target_mc_version: str = "1.21.4",
) -> dict[str, Any]:
    """Audit a resource pack file map (path -> JSON string or parsed dict).

    Rules:
      - PACK-001 (critical): Missing/invalid pack.mcmeta or pack_format mismatch
      - PACK-002 (high): Invalid uppercase/illegal resource location path characters
      - PACK-003 (high): 1.21.4+ assets/<ns>/items/*.json missing 'model' wrapper or valid 'type'
      - PACK-004 (high): Bitmap font glyph ascent > height or duplicate Unicode codepoint collisions
      - PACK-005 (warning): Legacy models/item/*.json 'overrides' on target >= 1.21.4
    """
    if not isinstance(files, dict) or not files:
        raise ValueError("'files' must be a non-empty mapping of relative resource-pack paths to JSON content.")

    findings: list[dict[str, Any]] = []
    expected_fmt = PACK_FORMAT_BY_MC.get(target_mc_version.strip(), 46)
    modern_items_target = expected_fmt >= 46
    seen_glyphs: dict[str, str] = {}
    parsed_count = 0

    def _load_json(path: str, raw: Any) -> dict[str, Any] | None:
        if isinstance(raw, dict):
            return raw
        if isinstance(raw, str):
            try:
                val = json.loads(raw)
                return val if isinstance(val, dict) else None
            except json.JSONDecodeError as exc:
                findings.append({
                    "rule_id": "PACK-001",
                    "severity": "critical",
                    "file": path,
                    "message": f"Invalid JSON in '{path}': {exc}.",
                    "remediation": "Fix JSON syntax (trailing commas or unquoted keys break Minecraft pack loading).",
                })
                return None
        return None

    # 1. Check pack.mcmeta
    mcmeta_raw = files.get("pack.mcmeta")
    if mcmeta_raw is None:
        findings.append({
            "rule_id": "PACK-001",
            "severity": "critical",
            "file": "pack.mcmeta",
            "message": "Missing root 'pack.mcmeta' manifest.",
            "remediation": f"Add pack.mcmeta with pack.pack_format={expected_fmt} for Minecraft {target_mc_version}.",
        })
    else:
        mcmeta = _load_json("pack.mcmeta", mcmeta_raw)
        if mcmeta is not None:
            parsed_count += 1
            pack_obj = mcmeta.get("pack")
            if not isinstance(pack_obj, dict):
                findings.append({
                    "rule_id": "PACK-001",
                    "severity": "critical",
                    "file": "pack.mcmeta",
                    "message": "pack.mcmeta is missing top-level 'pack' object.",
                    "remediation": "Wrap pack_format and description inside a 'pack' JSON object.",
                })
            else:
                fmt = pack_obj.get("pack_format")
                min_fmt = pack_obj.get("min_format")
                max_fmt = pack_obj.get("max_format")
                supported = pack_obj.get("supported_formats")
                fmt_ok = False
                if isinstance(fmt, int) and fmt == expected_fmt:
                    fmt_ok = True
                elif isinstance(supported, list) and len(supported) == 2 and supported[0] <= expected_fmt <= supported[1]:
                    fmt_ok = True
                elif isinstance(supported, dict) and supported.get("min_inclusive", 999) <= expected_fmt <= supported.get("max_inclusive", -1):
                    fmt_ok = True
                elif isinstance(min_fmt, int) and isinstance(max_fmt, int) and min_fmt <= expected_fmt <= max_fmt:
                    fmt_ok = True
                if not fmt_ok:
                    findings.append({
                        "rule_id": "PACK-001",
                        "severity": "high",
                        "file": "pack.mcmeta",
                        "message": f"pack_format={fmt!r} does not cover Minecraft {target_mc_version} (expected pack_format {expected_fmt}).",
                        "remediation": f"Set pack_format to {expected_fmt} or declare supported_formats covering {expected_fmt}.",
                    })

    # 2. Inspect all asset files
    for rel_path, raw_content in sorted(files.items()):
        norm = rel_path.replace("\\", "/").lstrip("/")
        if norm == "pack.mcmeta":
            continue
        if not VALID_RESOURCE_PATH_RE.fullmatch(norm):
            findings.append({
                "rule_id": "PACK-002",
                "severity": "high",
                "file": norm,
                "message": f"Illegal resource pack path '{norm}' (uppercase letters or invalid characters).",
                "remediation": "Rename path to lowercase ASCII [a-z0-9/._-] so Minecraft ResourceLocation accepts it.",
            })

        if not norm.endswith(".json"):
            continue
        doc = _load_json(norm, raw_content)
        if doc is None:
            continue
        parsed_count += 1

        # 2a. 1.21.4+ client item definitions: assets/<ns>/items/<id>.json
        if "/items/" in norm:
            model_node = doc.get("model")
            if not isinstance(model_node, dict):
                findings.append({
                    "rule_id": "PACK-003",
                    "severity": "high",
                    "file": norm,
                    "message": f"Client item definition '{norm}' is missing required root 'model' object.",
                    "remediation": "Wrap item definition under {\"model\": {\"type\": \"minecraft:model\", \"model\": \"ns:item/id\"}}.",
                })
            else:
                mtype = str(model_node.get("type", ""))
                norm_type = mtype if ":" in mtype else (f"minecraft:{mtype}" if mtype else "")
                if norm_type not in VALID_ITEM_MODEL_TYPES:
                    findings.append({
                        "rule_id": "PACK-003",
                        "severity": "high",
                        "file": norm,
                        "message": f"Invalid or missing model.type={mtype!r} in '{norm}'.",
                        "remediation": f"Use a valid 1.21.4+ item model type ({', '.join(sorted(VALID_ITEM_MODEL_TYPES))}).",
                    })

        # 2b. Font providers: assets/<ns>/font/*.json
        if "/font/" in norm and isinstance(doc.get("providers"), list):
            for pidx, prov in enumerate(doc["providers"]):
                if not isinstance(prov, dict):
                    continue
                if prov.get("type") == "bitmap":
                    height = int(prov.get("height", 8))
                    ascent = int(prov.get("ascent", 0))
                    if ascent > height:
                        findings.append({
                            "rule_id": "PACK-004",
                            "severity": "high",
                            "file": norm,
                            "message": f"Bitmap provider #{pidx} in '{norm}' has ascent ({ascent}) > height ({height}), which throws a load error in Minecraft.",
                            "remediation": "Set ascent <= height (commonly ascent = height - 1).",
                        })
                    chars = prov.get("chars")
                    if isinstance(chars, list):
                        for row in chars:
                            if not isinstance(row, str):
                                continue
                            for ch in row:
                                if ch == "\u0000":
                                    continue
                                cp = f"U+{ord(ch):04X}"
                                prev = seen_glyphs.get(cp)
                                if prev is not None:
                                    findings.append({
                                        "rule_id": "PACK-004",
                                        "severity": "high",
                                        "file": norm,
                                        "message": f"Duplicate Unicode glyph codepoint {cp} collides with '{prev}' (ItemsAdder/Nexo/Oraxen HUD corruption risk).",
                                        "remediation": "Reassign colliding glyph codepoints to a disjoint Private Use Area (U+E000-U+F8FF) block via glyphsmith/packmerge.",
                                    })
                                else:
                                    seen_glyphs[cp] = norm

        # 2c. Legacy models/item/*.json overrides targeting >= 1.21.4
        if modern_items_target and "/models/item/" in norm and isinstance(doc.get("overrides"), list) and doc["overrides"]:
            findings.append({
                "rule_id": "PACK-005",
                "severity": "warning",
                "file": norm,
                "message": f"Legacy 'overrides' array in '{norm}' is ignored in Minecraft {target_mc_version} (pack_format {expected_fmt}).",
                "remediation": "Migrate predicates to assets/<namespace>/items/<item>.json using range_dispatch/select (see packmigrate).",
            })

    crit = sum(1 for f in findings if f["severity"] == "critical")
    high = sum(1 for f in findings if f["severity"] == "high")
    warn = sum(1 for f in findings if f["severity"] == "warning")
    if crit > 0:
        status, grade = "fail", "F"
    elif high >= 2:
        status, grade = "fail", "D"
    elif high == 1:
        status, grade = "fail", "C"
    elif warn > 0:
        status, grade = "warn", "B"
    else:
        status, grade = "pass", "A"

    return {
        "ok": crit == 0 and high == 0,
        "status": status,
        "grade": grade,
        "target_mc_version": target_mc_version,
        "expected_pack_format": expected_fmt,
        "files_inspected": len(files),
        "json_parsed": parsed_count,
        "unique_glyphs_indexed": len(seen_glyphs),
        "finding_count": len(findings),
        "findings": findings,
    }
