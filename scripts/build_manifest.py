"""Build the deterministic top-level MinecraftKit release manifest."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import tempfile
from pathlib import Path
from typing import Any


SCHEMA_VERSION = 2
KIT_NAME = "minecraftkit"
KIT_VERSION = "2.2.1"
RESEARCH_DATE = "2026-07-15"
INSTALL_TARGETS = {
    "codex": {
        "core": "$HOME/.agents/skills/minecraftkit",
        "routes": "$HOME/.agents/skills/mc-*",
    },
    "claude": {
        "core": "$HOME/.claude/skills/minecraftkit",
        "routes": "$HOME/.claude/skills/mc-*",
        "commands": "$HOME/.claude/commands/mc",
    },
}
TRACKED = (
    "data/source-inventory.json",
    "data/api-index.json",
    "data/api-coverage.json",
    "data/docs-manifest.json",
    "data/plugin-insights.json",
    "data/feature-catalog.json",
    "data/addon-ideas.json",
    "data/minecraft-domain-catalog.json",
    "data/wiki-content.json",
    "data/minecraft-version-catalog.json",
    "data/minecraft-release-capabilities.json",
    "data/github-source-catalog.json",
    "data/github-source-snapshot.json",
    "web/data/manifest.js",
    "web/data/insights.js",
    "web/data/ecosystem.js",
    "web/data/wiki.js",
    "web/index.html",
    "web/styles.css",
    "web/ecosystem.html",
    "web/ecosystem.css",
    "web/ecosystem-app.js",
    "web/ecosystem-renderers.js",
    "web/wiki.html",
    "web/wiki.css",
    "web/wiki-app.js",
    "docs/plugin-engineering-handbook.md",
    "scripts/install-global.ps1",
    "scripts/install-from-github.ps1",
    "tests/test_install_layout.py",
    "tests/test_github_bootstrap_installer.py",
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
    domains = load(root / "data" / "minecraft-domain-catalog.json")["domains"]
    versions = load(root / "data" / "minecraft-version-catalog.json")
    release_capabilities = load(root / "data" / "minecraft-release-capabilities.json")["releases"]
    upstream_sources = load(root / "data" / "github-source-snapshot.json")
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
            "minecraft_domains": len(domains),
            "upstream_sources": upstream_sources["source_count"],
            "minecraft_versions": versions["version_count"],
            "latest_minecraft_release": versions["latest"]["release"],
            "latest_minecraft_snapshot": versions["latest"]["snapshot"],
            "profiled_minecraft_releases": len(release_capabilities),
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
