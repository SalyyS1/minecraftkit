"""Client/Server Resource Pack & Plugin Item Model Parity Checker.

Cross-checks server plugin item configurations (MMOItems, ItemsAdder, Nexo, Oraxen,
or inline item descriptors) against client resource pack files (`assets/<ns>/items/*.json`
for 1.21.4+ `item_model` and `assets/minecraft/models/item/*.json` for legacy
`custom_model_data` overrides) to catch purple-black missing textures before deploy.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

_VALID_RL = re.compile(r"^(?:[a-z0-9_.\-]+:)?[a-z0-9_/.\-]+$")


def _split_rl(rl: str) -> tuple[str, str]:
    raw = rl.strip()
    if ":" in raw:
        ns, _, path = raw.partition(":")
        return ns, path
    return "minecraft", raw


def _extract_model_refs(node: Any, out: list[str]) -> None:
    if isinstance(node, dict):
        m = node.get("model")
        if isinstance(m, str) and m.strip():
            out.append(m.strip())
        elif isinstance(m, dict):
            _extract_model_refs(m, out)
        for k, v in node.items():
            if k != "model":
                _extract_model_refs(v, out)
    elif isinstance(node, list):
        for item in node:
            _extract_model_refs(item, out)


def verify_pack_parity(
    *,
    server_items: list[dict[str, Any]],
    resource_pack_dir: str = "",
    client_item_definitions: dict[str, dict[str, Any]] | None = None,
    client_models: list[str] | None = None,
) -> dict[str, Any]:
    """Audit server item definitions against client resource pack item & model files."""
    if not isinstance(server_items, list) or not server_items:
        raise ValueError("'server_items' must be a non-empty list of item descriptors.")

    pack_root = Path(resource_pack_dir).expanduser().resolve() if resource_pack_dir.strip() else None
    if pack_root is not None and not pack_root.is_dir():
        raise ValueError(f"Resource pack directory not found: {pack_root}")

    inline_items = client_item_definitions or {}
    inline_model_set = {m.strip() for m in (client_models or []) if isinstance(m, str) and m.strip()}

    findings: list[dict[str, Any]] = []
    checked_count = 0

    def _model_exists(model_rl: str) -> bool:
        ns, path = _split_rl(model_rl)
        canonical = f"{ns}:{path}"
        if canonical in inline_model_set or path in inline_model_set:
            return True
        if pack_root is not None:
            cand = pack_root / "assets" / ns / "models" / f"{path}.json"
            return cand.is_file()
        return False

    def _load_item_def(item_rl: str) -> dict[str, Any] | None:
        ns, path = _split_rl(item_rl)
        canonical = f"{ns}:{path}"
        if canonical in inline_items:
            return inline_items[canonical]
        if path in inline_items:
            return inline_items[path]
        if pack_root is not None:
            cand = pack_root / "assets" / ns / "items" / f"{path}.json"
            if cand.is_file():
                return json.loads(cand.read_text(encoding="utf-8"))
        return None

    def _load_legacy_base_model(material: str) -> dict[str, Any] | None:
        mat = material.strip().lower().removeprefix("minecraft:")
        key = f"minecraft:item/{mat}"
        if key in inline_items:
            return inline_items[key]
        if pack_root is not None:
            cand = pack_root / "assets" / "minecraft" / "models" / "item" / f"{mat}.json"
            if cand.is_file():
                return json.loads(cand.read_text(encoding="utf-8"))
        return None

    for idx, item in enumerate(server_items):
        if not isinstance(item, dict):
            continue
        checked_count += 1
        item_id = str(item.get("id") or f"item_{idx}")
        item_model = str(item.get("item_model") or "").strip()
        cmd = item.get("custom_model_data")
        base_mat = str(item.get("base_material") or item.get("material") or "").strip()

        if item_model:
            if not _VALID_RL.fullmatch(item_model):
                findings.append({
                    "rule_id": "PARITY-004",
                    "severity": "error",
                    "item_id": item_id,
                    "message": f"Invalid ResourceLocation syntax in item_model '{item_model}'.",
                })
                continue
            item_def = _load_item_def(item_model)
            if item_def is None:
                ns, path = _split_rl(item_model)
                findings.append({
                    "rule_id": "PARITY-001",
                    "severity": "error",
                    "item_id": item_id,
                    "message": f"Missing 1.21.4+ client item definition 'assets/{ns}/items/{path}.json' for item_model '{item_model}'.",
                })
            else:
                refs: list[str] = []
                _extract_model_refs(item_def, refs)
                for ref in refs:
                    if not _VALID_RL.fullmatch(ref):
                        findings.append({
                            "rule_id": "PARITY-004",
                            "severity": "error",
                            "item_id": item_id,
                            "message": f"Invalid model ResourceLocation '{ref}' inside '{item_model}'.",
                        })
                    elif not _model_exists(ref):
                        ns, path = _split_rl(ref)
                        findings.append({
                            "rule_id": "PARITY-003",
                            "severity": "error",
                            "item_id": item_id,
                            "message": f"Missing client model 'assets/{ns}/models/{path}.json' referenced by '{item_model}'.",
                        })

        if cmd is not None and base_mat:
            try:
                cmd_int = int(cmd)
            except (TypeError, ValueError):
                cmd_int = -1
            base_doc = _load_legacy_base_model(base_mat)
            overrides = base_doc.get("overrides", []) if isinstance(base_doc, dict) else []
            matched_ov = None
            for ov in overrides:
                if not isinstance(ov, dict):
                    continue
                pred = ov.get("predicate", {})
                if isinstance(pred, dict) and pred.get("custom_model_data") == cmd_int:
                    matched_ov = ov
                    break
            if matched_ov is None:
                findings.append({
                    "rule_id": "PARITY-002",
                    "severity": "error",
                    "item_id": item_id,
                    "message": f"Missing legacy custom_model_data={cmd_int} override in 'assets/minecraft/models/item/{base_mat.lower()}.json'.",
                })
            else:
                target_model = str(matched_ov.get("model", "")).strip()
                if target_model and not _model_exists(target_model):
                    ns, path = _split_rl(target_model)
                    findings.append({
                        "rule_id": "PARITY-003",
                        "severity": "error",
                        "item_id": item_id,
                        "message": f"Override custom_model_data={cmd_int} references missing model 'assets/{ns}/models/{path}.json'.",
                    })

    return {
        "ok": len(findings) == 0,
        "status": "pass" if not findings else "fail",
        "checked_items": checked_count,
        "finding_count": len(findings),
        "findings": findings,
    }
