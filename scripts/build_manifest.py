"""Build the deterministic top-level MinecraftRPG Kit release manifest."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import tempfile
from pathlib import Path
from typing import Any


SCHEMA_VERSION = 1
KIT_NAME = "minecraft-rpg-kit"
KIT_VERSION = "1.0.0"
RESEARCH_DATE = "2026-07-15"
INSTALL_TARGETS = {
    "codex": "$HOME/.agents/skills/minecraft-rpg-kit",
    "claude": "$HOME/.claude/skills/minecraft-rpg-kit",
}
TRACKED = (
    "data/source-inventory.json",
    "data/api-index.json",
    "data/api-coverage.json",
    "data/docs-manifest.json",
    "data/plugin-insights.json",
    "data/feature-catalog.json",
    "data/addon-ideas.json",
    "web/data/manifest.js",
    "web/data/insights.js",
)


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest()


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"), parse_constant=lambda value: (_ for _ in ()).throw(ValueError(f"Invalid JSON constant {value}")))


def atomic_write_text(path: Path, text: str, *, encoding: str = "utf-8") -> None:
    """Durably write text beside its destination, then atomically promote it."""
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding=encoding, newline="\n") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def build(root: Path) -> dict[str, Any]:
    root = root.resolve()
    coverage = load(root / "data" / "api-coverage.json")["plugins"]
    insights = {item["name"]: item for item in load(root / "data" / "plugin-insights.json")["plugins"]}
    source = load(root / "data" / "source-inventory.json")
    addons = load(root / "data" / "addon-ideas.json")["ideas"]
    artifacts = {}
    for relative in TRACKED:
        path = root / relative
        if not path.is_file():
            raise FileNotFoundError(path)
        artifacts[relative] = {"bytes": path.stat().st_size, "sha256": digest(path)}
    plugins = []
    for item in coverage:
        insight = insights[item["plugin"]]
        plugins.append({
            "name": item["plugin"],
            "version": insight["version"],
            "max_class_major": insight["max_class_major"],
            "plugin_owned_types": item["plugin_owned_types"],
            "plugin_owned_members": item["plugin_owned_members"],
            "bundled_third_party_types": item["bundled_third_party_types"],
            "bundled_third_party_members": item["bundled_third_party_members"],
        })
    return {
        "schema_version": SCHEMA_VERSION,
        "name": KIT_NAME,
        "version": KIT_VERSION,
        "research_date": RESEARCH_DATE,
        "catalog": {
            "plugin_count": len(coverage),
            "plugin_owned_types": sum(item["plugin_owned_types"] for item in coverage),
            "plugin_owned_members": sum(item["plugin_owned_members"] for item in coverage),
            "all_namespace_types": sum(item["published_types"] for item in coverage),
            "all_namespace_members": sum(item["published_members"] for item in coverage),
            "parse_errors": sum(len(item["parse_errors"]) for item in coverage),
            "addon_ideas": len(addons),
            "decompiled_files_inventoried": source["decompiled_file_count"],
        },
        "plugins": plugins,
        "artifacts": artifacts,
        "install_targets": dict(INSTALL_TARGETS),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path, nargs="?", default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    root = args.root.resolve()
    manifest = build(root)
    atomic_write_text(root / "manifest.json", json.dumps(manifest, indent=2, ensure_ascii=False, allow_nan=False) + "\n")
    print(f"Built manifest for {manifest['catalog']['plugin_count']} plugins and {manifest['catalog']['addon_ideas']} addon ideas")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
