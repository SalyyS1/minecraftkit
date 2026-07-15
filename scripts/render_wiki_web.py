"""Render the deterministic offline Salyyy Minecraft Kit wiki payload."""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Any


ASSIGNMENT = "window.SalyyyMinecraftKitWiki="
LANGUAGES = {"vi", "en"}
ROUTE_IDS = {
    "build", "client", "core", "dialog", "model",
    "nms", "pack", "protocol", "rpg", "shader",
}
REQUIRED_ROUTE_FIELDS = {
    "title", "what", "when", "inputs", "workflow", "outputs", "guardrails", "examples",
}


def strict_json(path: Path) -> Any:
    return json.loads(
        path.read_text(encoding="utf-8"),
        parse_constant=lambda value: (_ for _ in ()).throw(
            ValueError(f"Non-standard JSON constant {value} in {path}")
        ),
    )


def require_object(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be an object")
    return value


def require_array(value: Any, label: str) -> list[Any]:
    if not isinstance(value, list):
        raise ValueError(f"{label} must be an array")
    return value


def require_text(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} must be non-empty text")
    return value


def require_text_array(value: Any, label: str) -> list[str]:
    values = require_array(value, label)
    if not values or any(not isinstance(item, str) or not item.strip() for item in values):
        raise ValueError(f"{label} must contain non-empty text")
    return values


def validate_localized(value: Any, label: str, fields: set[str]) -> dict[str, Any]:
    localized = require_object(value, label)
    if set(localized) != LANGUAGES:
        raise ValueError(f"{label} must contain exactly vi and en")
    for language in sorted(LANGUAGES):
        translation = require_object(localized[language], f"{label}.{language}")
        missing = fields - set(translation)
        if missing:
            raise ValueError(f"{label}.{language} is missing: {', '.join(sorted(missing))}")
        for field in fields:
            if field in {"title", "what", "summary", "description"}:
                require_text(translation[field], f"{label}.{language}.{field}")
            else:
                require_text_array(translation[field], f"{label}.{language}.{field}")
    return localized


def validate(document: Any) -> dict[str, Any]:
    root = require_object(document, "wiki")
    if root.get("schema_version") != 1:
        raise ValueError("wiki schema_version must be 1")

    product = require_object(root.get("product"), "product")
    for field in ("name", "author", "version"):
        require_text(product.get(field), f"product.{field}")
    if product["name"] != "Salyyy Minecraft Kit" or product["author"] not in {"SalyVn", "Salyyy"}:
        raise ValueError("product identity must name Salyyy Minecraft Kit and SalyVn/Salyyy")

    ui = require_object(root.get("ui"), "ui")
    if set(ui) != LANGUAGES:
        raise ValueError("ui must contain exactly vi and en")
    for language, translation in ui.items():
        labels = require_object(translation, f"ui.{language}")
        for key, value in labels.items():
            require_text(value, f"ui.{language}.{key}")
    if set(ui["vi"]) != set(ui["en"]):
        raise ValueError("ui translations must expose the same keys")

    routes = require_array(root.get("routes"), "routes")
    seen_routes: list[str] = []
    for route in routes:
        item = require_object(route, "route")
        route_id = require_text(item.get("id"), "route.id")
        if route_id not in ROUTE_IDS or item.get("route") != f"mc:{route_id}":
            raise ValueError(f"invalid route contract: {route_id}")
        require_text_array(item.get("keywords"), f"route.{route_id}.keywords")
        validate_localized(item.get("content"), f"route.{route_id}.content", REQUIRED_ROUTE_FIELDS)
        seen_routes.append(route_id)
    if set(seen_routes) != ROUTE_IDS or len(seen_routes) != len(ROUTE_IDS):
        raise ValueError("wiki must contain ten unique mc:* routes")

    chapters = require_array(root.get("chapters"), "chapters")
    chapter_ids: set[str] = set()
    for chapter in chapters:
        item = require_object(chapter, "chapter")
        chapter_id = require_text(item.get("id"), "chapter.id")
        if chapter_id in chapter_ids:
            raise ValueError(f"duplicate chapter: {chapter_id}")
        chapter_ids.add(chapter_id)
        require_text_array(item.get("keywords"), f"chapter.{chapter_id}.keywords")
        validate_localized(item.get("content"), f"chapter.{chapter_id}.content", {"title", "summary", "points"})
    if len(chapter_ids) < 8:
        raise ValueError("wiki must contain the complete plugin engineering handbook")

    installers = require_array(root.get("installers"), "installers")
    targets: set[str] = set()
    for installer in installers:
        item = require_object(installer, "installer")
        target = require_text(item.get("target"), "installer.target")
        if target not in {"codex", "claude", "both"} or target in targets:
            raise ValueError(f"invalid installer target: {target}")
        targets.add(target)
        command = require_text(item.get("command"), f"installer.{target}.command")
        if "raw.githubusercontent.com/SalyyS1/minecraftkit/main/scripts/install-from-github.ps1" not in command:
            raise ValueError(f"installer {target} must use the raw main install entry point")
        if f"-Target {target}" not in command:
            raise ValueError(f"installer {target} does not pass its target")
        validate_localized(item.get("content"), f"installer.{target}.content", {"title", "description"})
    if targets != {"codex", "claude", "both"}:
        raise ValueError("wiki must contain codex, claude, and both installers")
    return root


def javascript(payload: dict[str, Any]) -> str:
    encoded = json.dumps(
        payload, ensure_ascii=False, allow_nan=False, sort_keys=True, separators=(",", ":")
    )
    encoded = encoded.replace("<", "\\u003c").replace("\u2028", "\\u2028").replace("\u2029", "\\u2029")
    return f"{ASSIGNMENT}{encoded};\n"


def atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        dir=path.parent, prefix=f".{path.name}.", suffix=".tmp"
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise


def render(input_path: Path, output_path: Path) -> dict[str, Any]:
    payload = validate(strict_json(input_path))
    atomic_write(output_path, javascript(payload))
    return payload


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=root / "data/wiki-content.json")
    parser.add_argument("--output", type=Path, default=root / "web/data/wiki.js")
    args = parser.parse_args()
    payload = render(args.input.resolve(), args.output.resolve())
    print(
        f"Rendered {len(payload['routes'])} routes, {len(payload['chapters'])} chapters, "
        f"and {len(payload['installers'])} installers to {args.output.resolve()}"
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, json.JSONDecodeError) as error:
        print(f"Wiki web render failed: {error}", file=sys.stderr)
        raise SystemExit(1) from error
