"""Validate MinecraftRPG Kit structure, catalogs, generated docs, and offline web data."""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import re
import sys
from collections import Counter
from pathlib import Path, PurePosixPath
from typing import Any

from build_manifest import (
    INSTALL_TARGETS,
    KIT_NAME,
    KIT_VERSION,
    RESEARCH_DATE,
    SCHEMA_VERSION,
    TRACKED,
    build as build_release_manifest,
)
from render_ecosystem_web import build_payload as build_ecosystem_payload
from render_wiki_web import validate as validate_wiki_document
from validate_minecraftkit_catalogs import validate_minecraftkit


REQUIRED = (
    "SKILL.md", "README.md", "NOTICE.md", "manifest.json", "agents/openai.yaml",
    "data/api-index.json", "data/api-coverage.json", "data/docs-manifest.json",
    "data/source-inventory.json", "data/plugin-insights.json", "data/feature-catalog.json", "data/addon-ideas.json",
    "data/minecraft-domain-catalog.json", "data/minecraft-version-catalog.json",
    "data/minecraft-release-capabilities.json",
    "data/github-source-catalog.json", "data/github-source-snapshot.json",
    "docs/index.md", "docs/api/index.md", "docs/plugin-architecture-and-logic.md",
    "docs/professional-engineering-patterns.md", "docs/rpg-feature-catalog.md",
    "docs/original-addon-blueprints.md", "docs/agentkit-skill-design.md",
    "docs/codex-claude-compatibility.md", "docs/research-methodology.md",
    "docs/minecraft-ecosystem-api-atlas.md", "docs/plugin-engineering-handbook.md",
    "web/index.html", "web/styles.css", "web/app.js", "web/data/manifest.js", "web/data/insights.js",
    "web/ecosystem.html", "web/ecosystem.css", "web/ecosystem-app.js",
    "web/ecosystem-renderers.js", "web/data/ecosystem.js",
    "web/wiki.html", "web/wiki.css", "web/wiki-app.js", "web/shell.css", "web/shell.js",
    "web/assets/salyyy-minecraft-kit-logo.webp", "web/data/wiki.js", "data/wiki-content.json",
    "references/api-lookup.md", "references/architecture-review.md",
    "references/source-analysis-and-regeneration.md", "references/rpg-feature-design.md",
    "references/addon-blueprint.md", "references/compatibility-and-safety.md",
    "references/plugin-routing-index.md", "references/client-compatibility.md",
    "references/core-platforms-and-versions.md", "references/packets-and-protocols.md",
    "references/nms-and-mappings.md", "references/shaders-and-rendering.md",
    "references/dialogs-and-client-actions.md", "references/client-and-projection.md",
    "references/resource-and-data-packs.md", "references/models-and-animation.md",
    "references/upstream-source-catalog.md", "references/plugin-build-and-shipping.md",
    "references/kotlin-java-gradle.md", "references/database-config-and-runtime.md",
    "references/release-publishing-checklist.md",
    "commands/mc/core.md", "commands/mc/rpg.md", "commands/mc/shader.md",
    "commands/mc/dialog.md", "commands/mc/client.md", "commands/mc/pack.md",
    "commands/mc/model.md", "commands/mc/protocol.md", "commands/mc/nms.md", "commands/mc/build.md",
    "skill-wrappers/mc-core/SKILL.md", "skill-wrappers/mc-rpg/SKILL.md",
    "skill-wrappers/mc-shader/SKILL.md", "skill-wrappers/mc-dialog/SKILL.md",
    "skill-wrappers/mc-client/SKILL.md", "skill-wrappers/mc-pack/SKILL.md",
    "skill-wrappers/mc-model/SKILL.md", "skill-wrappers/mc-protocol/SKILL.md",
    "skill-wrappers/mc-nms/SKILL.md", "skill-wrappers/mc-build/SKILL.md",
    "scripts/render_ecosystem_web.py", "tests/test_render_ecosystem_web.py",
    "scripts/render_wiki_web.py", "tests/test_render_wiki_web.py",
    "scripts/install-global.ps1", "scripts/install-from-github.ps1",
    "tests/test_install_layout.py", "tests/test_github_bootstrap_installer.py",
    "tests/evals.json",
)

ALLOWED_TOP_LEVEL_FILES = {"SKILL.md", "README.md", "NOTICE.md", "manifest.json"}
ALLOWED_DIRECTORY_EXTENSIONS = {
    "agents": {".yaml"},
    "assets": set(),
    "commands": {".md"},
    "data": {".json"},
    "docs": {".md"},
    "references": {".md"},
    "scripts": {".py", ".ps1"},
    "skill-wrappers": {".md"},
    "tests": {".py", ".json"},
    "web": {".html", ".css", ".js", ".webp"},
}
EXCLUDED_DIRECTORY_NAMES = {"dist", "npm", "__pycache__", ".git", ".gitignore", ".gitattributes"}
EXCLUDED_DIRECTORY_PREFIXES = (".api-stage-", ".web-stage-", ".minecraft-rpg-kit-stage-", ".minecraftkit-stage-")
FORBIDDEN_SOURCE_EXTENSIONS = {".class", ".dex", ".groovy", ".jar", ".java", ".kt", ".kts", ".scala"}
FORBIDDEN_SOURCE_DIRECTORIES = {"decomp", "decompiled", "decompiled-source", "decompiled-sources"}
RELEASE_TOP_LEVEL_KEYS = {
    "schema_version", "name", "version", "research_date", "catalog", "plugins", "artifacts", "install_targets",
}


def strict_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"), parse_constant=lambda value: (_ for _ in ()).throw(ValueError(f"Non-standard JSON constant {value} in {path}")))


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest()


def safe_posix_descendant(root: Path, relative: str) -> Path:
    """Resolve a normalized POSIX-relative path and prove it stays under root."""
    if not isinstance(relative, str) or not relative or "\\" in relative or "\0" in relative:
        raise ValueError(f"unsafe relative path: {relative!r}")
    pure = PurePosixPath(relative)
    if pure.is_absolute() or pure.as_posix() != relative or any(part in {"", ".", ".."} or ":" in part for part in pure.parts):
        raise ValueError(f"unsafe relative path: {relative!r}")
    resolved_root = root.resolve()
    candidate = (resolved_root / Path(*pure.parts)).resolve()
    try:
        candidate.relative_to(resolved_root)
    except ValueError as error:
        raise ValueError(f"path escapes release root: {relative!r}") from error
    return candidate


def _is_excluded(relative: Path) -> bool:
    return any(
        part in EXCLUDED_DIRECTORY_NAMES or any(part.startswith(prefix) for prefix in EXCLUDED_DIRECTORY_PREFIXES)
        for part in relative.parts
    )


def release_payload_files(root: Path) -> list[Path]:
    """Return the explicit, copyright-safe release payload or raise ValueError."""
    root = root.resolve()
    for child in root.iterdir():
        relative = Path(child.name)
        if child.is_symlink() or getattr(child.lstat(), "st_file_attributes", 0) & 0x400:
            raise ValueError(f"reparse point is not allowed: {child.name}")
        if _is_excluded(relative):
            continue
        if child.is_file() and child.name not in ALLOWED_TOP_LEVEL_FILES:
            raise ValueError(f"unexpected top-level file: {child.name}")
        if child.is_dir() and child.name not in ALLOWED_DIRECTORY_EXTENSIONS:
            raise ValueError(f"unexpected top-level directory: {child.name}")
        if not child.is_file() and not child.is_dir():
            raise ValueError(f"unsupported top-level entry: {child.name}")

    files: list[Path] = []
    for path in root.rglob("*"):
        relative = path.relative_to(root)
        if _is_excluded(relative):
            continue
        if path.is_symlink() or getattr(path.lstat(), "st_file_attributes", 0) & 0x400:
            raise ValueError(f"reparse point is not allowed: {relative.as_posix()}")
        if any(part.lower() in FORBIDDEN_SOURCE_DIRECTORIES for part in relative.parts):
            raise ValueError(f"decompiled-source directory is not allowed: {relative.as_posix()}")
        if not path.is_file():
            continue
        lower_name = path.name.lower()
        suffix = path.suffix.lower()
        if suffix in FORBIDDEN_SOURCE_EXTENSIONS or lower_name == ".env" or lower_name.startswith(".env."):
            raise ValueError(f"forbidden release payload: {relative.as_posix()}")
        top_level = relative.parts[0]
        if len(relative.parts) == 1:
            if path.name not in ALLOWED_TOP_LEVEL_FILES:
                raise ValueError(f"unexpected top-level file: {relative.as_posix()}")
        elif suffix not in ALLOWED_DIRECTORY_EXTENSIONS.get(top_level, set()):
            raise ValueError(f"unsupported file type in {top_level}: {relative.as_posix()}")
        files.append(path)
    return sorted(files, key=lambda path: path.relative_to(root).as_posix())


def frontmatter(text: str) -> dict[str, str]:
    if not text.startswith("---\n") or "\n---\n" not in text[4:]:
        raise ValueError("SKILL.md must start with YAML frontmatter")
    block = text[4:text.index("\n---\n", 4)]
    result = {}
    for line in block.splitlines():
        if ":" not in line:
            raise ValueError(f"Invalid frontmatter line: {line}")
        key, value = line.split(":", 1)
        result[key.strip()] = value.strip().strip('"\'')
    return result


def parse_assignment(path: Path, prefix: str) -> Any:
    text = path.read_text(encoding="utf-8").strip()
    if not text.startswith(prefix) or not text.endswith(";"):
        raise ValueError(f"Invalid JavaScript data assignment: {path}")
    return json.loads(text[len(prefix):-1], parse_constant=lambda value: (_ for _ in ()).throw(ValueError(value)))


def strictly_equal(actual: Any, expected: Any) -> bool:
    if type(actual) is not type(expected):
        return False
    if isinstance(expected, dict):
        return set(actual) == set(expected) and all(strictly_equal(actual[key], value) for key, value in expected.items())
    if isinstance(expected, list):
        return len(actual) == len(expected) and all(strictly_equal(left, right) for left, right in zip(actual, expected))
    return actual == expected


def validate_release_manifest(root: Path, release: Any, expected: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if not isinstance(release, dict):
        return ["release manifest must be a JSON object"]
    if set(release) != RELEASE_TOP_LEVEL_KEYS:
        errors.append("release manifest top-level keys are invalid")
    scalar_expectations = {
        "schema_version": SCHEMA_VERSION,
        "name": KIT_NAME,
        "version": KIT_VERSION,
        "research_date": RESEARCH_DATE,
    }
    for key, value in scalar_expectations.items():
        if type(release.get(key)) is not type(value) or release.get(key) != value:
            errors.append(f"release manifest {key} is invalid")
    if not strictly_equal(release.get("catalog"), expected["catalog"]):
        errors.append("release manifest catalog is invalid")
    if not strictly_equal(release.get("plugins"), expected["plugins"]):
        errors.append("release manifest plugins are invalid")
    if not strictly_equal(release.get("install_targets"), INSTALL_TARGETS):
        errors.append("release manifest install targets are invalid")

    artifacts = release.get("artifacts")
    if not isinstance(artifacts, dict):
        errors.append("release manifest artifacts must be an object")
        return errors
    if set(artifacts) != set(TRACKED):
        errors.append("release manifest artifact set is invalid")
    for relative, descriptor in artifacts.items():
        try:
            path = safe_posix_descendant(root, relative)
        except ValueError as error:
            errors.append(f"release artifact path is invalid: {error}")
            continue
        if not isinstance(descriptor, dict) or set(descriptor) != {"bytes", "sha256"}:
            errors.append(f"release artifact descriptor is invalid: {relative}")
            continue
        byte_count = descriptor.get("bytes")
        checksum = descriptor.get("sha256")
        if type(byte_count) is not int or byte_count < 0 or not isinstance(checksum, str) or re.fullmatch(r"[0-9a-f]{64}", checksum) is None:
            errors.append(f"release artifact descriptor is invalid: {relative}")
            continue
        expected_descriptor = expected["artifacts"].get(relative)
        if expected_descriptor is None or not strictly_equal(descriptor, expected_descriptor) or not path.is_file():
            errors.append(f"release artifact hash mismatch: {relative}")
    return errors


def validate(root: Path) -> list[str]:
    errors: list[str] = []
    for relative in REQUIRED:
        if not (root / relative).is_file():
            errors.append(f"missing required file: {relative}")
    if errors:
        return errors

    try:
        release_payload_files(root)
    except (OSError, ValueError) as error:
        errors.append(f"release tree is invalid: {error}")

    skill_text = (root / "SKILL.md").read_text(encoding="utf-8")
    try:
        metadata = frontmatter(skill_text)
        if set(metadata) != {"name", "description"}:
            errors.append("SKILL.md frontmatter must contain only name and description")
        if metadata.get("name") != root.name.lower() and root.name.lower() != "minecraftrpgkit":
            errors.append("skill folder/name mismatch")
        if metadata.get("name") != "minecraftkit":
            errors.append("skill name must be minecraftkit")
        if not 1 <= len(metadata.get("description", "")) <= 1024:
            errors.append("skill description length must be 1..1024")
    except ValueError as error:
        errors.append(str(error))
    if len(skill_text.splitlines()) > 300:
        errors.append("SKILL.md exceeds 300 lines")
    if re.search(r"\bTODO\b|\[TODO", skill_text, re.IGNORECASE):
        errors.append("SKILL.md contains a placeholder")
    for target in re.findall(r"\[[^]]+\]\(([^)]+)\)", skill_text):
        if "://" not in target and not (root / target.split("#", 1)[0]).is_file():
            errors.append(f"broken SKILL.md link: {target}")

    try:
        api = strict_json(root / "data/api-index.json")
        coverage_doc = strict_json(root / "data/api-coverage.json")
        docs_manifest = strict_json(root / "data/docs-manifest.json")
        source = strict_json(root / "data/source-inventory.json")
        insights = strict_json(root / "data/plugin-insights.json")
        features = strict_json(root / "data/feature-catalog.json")
        addons = strict_json(root / "data/addon-ideas.json")
        release = strict_json(root / "manifest.json")
    except (OSError, UnicodeError, ValueError, json.JSONDecodeError) as error:
        return errors + [f"JSON validation failed: {error}"]

    named_documents = {
        "api-index.json": api,
        "api-coverage.json": coverage_doc,
        "docs-manifest.json": docs_manifest,
        "source-inventory.json": source,
        "plugin-insights.json": insights,
        "feature-catalog.json": features,
        "addon-ideas.json": addons,
    }
    invalid_documents = [name for name, document in named_documents.items() if not isinstance(document, dict)]
    if invalid_documents:
        return errors + [f"JSON schema invalid; expected objects: {', '.join(invalid_documents)}"]

    try:
        plugins = api["plugins"]
        coverage = coverage_doc["plugins"]
        if not isinstance(plugins, list) or not isinstance(coverage, list):
            raise TypeError("API and coverage plugins must be arrays")
        insight_plugins = insights["plugins"]
        feature_domains = features["domains"]
        addon_ideas = addons["ideas"]
        if not all(isinstance(value, list) for value in (insight_plugins, feature_domains, addon_ideas)):
            raise TypeError("insights, feature domains, and addon ideas must be arrays")
        if not all(isinstance(item, dict) for item in coverage + plugins + insight_plugins + feature_domains + addon_ideas):
            raise TypeError("catalog array entries must be objects")
        if len(plugins) != 10 or len(coverage) != 10:
            errors.append("API and coverage must each contain 10 plugins")
        if coverage_doc.get("unexplained_errors") != 0 or any(not isinstance(item.get("parse_errors"), list) or item["parse_errors"] for item in coverage):
            errors.append("API coverage contains parser errors")
        ids: list[str] = []
        all_types = all_members = owned_types = owned_members = 0
        for plugin in plugins:
            classes = plugin["classes"]
            if not isinstance(classes, list):
                raise TypeError("API classes must be arrays")
            all_types += len(classes)
            for record in classes:
                if not isinstance(record, dict):
                    raise TypeError("API class entries must be objects")
                ids.append(record["id"])
                members = record["members"]
                if not isinstance(members, list) or not all(isinstance(member, dict) for member in members):
                    raise TypeError("API members must be arrays of objects")
                all_members += len(members)
                if record.get("origin", "plugin-owned") == "plugin-owned":
                    owned_types += 1
                    owned_members += len(members)
                ids.extend(member["id"] for member in members)
        duplicates = [value for value, count in Counter(ids).items() if count > 1]
        if duplicates:
            errors.append(f"duplicate API IDs: {len(duplicates)}")
        if (all_types, all_members, owned_types, owned_members) != (5345, 41887, 4947, 39262):
            errors.append(f"catalog counts changed: {(all_types, all_members, owned_types, owned_members)}")
        if {item["name"] for item in plugins} != {item["plugin"] for item in coverage}:
            errors.append("API and coverage plugin names differ")
        if len(insight_plugins) != 10 or len(feature_domains) < 10 or len(addon_ideas) < 20:
            errors.append("curated plugin/features/addon coverage is incomplete")
        if source.get("jar_count") != 10 or source.get("decompiled_root_count") != 10 or source.get("decompiled_file_count") != 11490:
            errors.append("source inventory counts are incomplete")
    except (AttributeError, IndexError, KeyError, TypeError) as error:
        return errors + [f"catalog schema invalid: {type(error).__name__}: {error}"]

    try:
        documented_plugins = docs_manifest["plugins"]
        if not isinstance(documented_plugins, dict):
            raise TypeError("docs-manifest plugins must be an object")
        shard_count = sum(len(value) for value in documented_plugins.values())
        if shard_count != 965:
            errors.append(f"expected 965 API shards, got {shard_count}")
        for plugin_name, shards in documented_plugins.items():
            plugin_dir = next((path for path in (root / "docs/api").iterdir() if path.is_dir() and (path / "index.md").is_file() and plugin_name in (path / "index.md").read_text(encoding="utf-8", errors="ignore")[:200]), None)
            if plugin_dir is None:
                errors.append(f"missing API directory for {plugin_name}")
                continue
            for shard in shards:
                shard_path = safe_posix_descendant(plugin_dir, shard["file"])
                if not shard_path.is_file():
                    errors.append(f"missing API shard: {plugin_name}/{shard['file']}")
    except (AttributeError, IndexError, KeyError, TypeError, ValueError) as error:
        errors.append(f"docs manifest schema invalid: {type(error).__name__}: {error}")
    for path in (root / "docs").rglob("*.md"):
        if len(path.read_text(encoding="utf-8").splitlines()) > 800:
            errors.append(f"documentation exceeds 800 lines: {path.relative_to(root)}")

    try:
        web_manifest = parse_assignment(root / "web/data/manifest.js", "window.MinecraftRPGManifest=")
        web_insights = parse_assignment(root / "web/data/insights.js", "window.MinecraftRPGInsights=")
        web_ecosystem = parse_assignment(root / "web/data/ecosystem.js", "window.MinecraftKitEcosystem=")
        web_wiki = parse_assignment(root / "web/data/wiki.js", "window.SalyyyMinecraftKitWiki=")
        if len(web_manifest.get("plugins", [])) != 10 or not web_manifest.get("insightsFile"):
            errors.append("web manifest is incomplete")
        if web_insights.get("stats", {}).get("totalMembers") != 41887:
            errors.append("web insight counts do not reconcile")
        if len(web_ecosystem.get("domains", [])) != 10:
            errors.append("ecosystem web domain count does not reconcile")
        if len(web_ecosystem.get("sources", [])) != 103:
            errors.append("ecosystem web source count does not reconcile")
        versions = web_ecosystem.get("versions", {})
        if versions.get("versionCount") != 901 or len(versions.get("history", [])) != 901:
            errors.append("ecosystem web version count does not reconcile")
        release_capabilities = web_ecosystem.get("releaseCapabilities", {})
        if len(release_capabilities.get("releases", [])) != 1 or release_capabilities["releases"][0].get("id") != "26.2":
            errors.append("ecosystem web release capability profile does not reconcile")
        expected_ecosystem = build_ecosystem_payload(
            strict_json(root / "data/minecraft-domain-catalog.json"),
            strict_json(root / "data/github-source-catalog.json"),
            strict_json(root / "data/github-source-snapshot.json"),
            strict_json(root / "data/minecraft-version-catalog.json"),
            strict_json(root / "data/minecraft-release-capabilities.json"),
            source_catalog_sha256=digest(root / "data/github-source-catalog.json"),
            release_capabilities_sha256=digest(root / "data/minecraft-release-capabilities.json"),
        )
        if not strictly_equal(web_ecosystem, expected_ecosystem):
            errors.append("ecosystem web payload is stale or differs from its source catalogs")
        expected_wiki = validate_wiki_document(strict_json(root / "data/wiki-content.json"))
        if not strictly_equal(web_wiki, expected_wiki):
            errors.append("wiki web payload is stale or differs from its source catalog")
        if len(web_wiki.get("routes", [])) != 10 or len(web_wiki.get("installers", [])) != 3:
            errors.append("wiki route or installer count does not reconcile")
        for plugin in web_manifest.get("plugins", []):
            plugin_path = safe_posix_descendant(root / "web", plugin["file"])
            if not plugin_path.is_file():
                errors.append(f"missing web plugin shard: {plugin['file']}")
    except (AttributeError, IndexError, KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
        errors.append(f"web data validation failed: {error}")
    web_text = "\n".join(
        (root / "web" / name).read_text(encoding="utf-8")
        for name in (
            "index.html", "styles.css", "app.js", "ecosystem.html",
            "ecosystem.css", "ecosystem-app.js", "ecosystem-renderers.js", "shell.css", "shell.js",
            "wiki.html", "wiki.css", "wiki-app.js",
        )
    )
    if re.search(r"https?://|\bfetch\s*\(", web_text, re.IGNORECASE):
        errors.append("offline web contains a remote URL or fetch call")
    wiki_runtime = (root / "web/wiki-app.js").read_text(encoding="utf-8")
    if re.search(r"innerHTML|outerHTML|insertAdjacentHTML|document\.write|\beval\s*\(", wiki_runtime):
        errors.append("wiki runtime contains an unsafe DOM or evaluation sink")

    errors.extend(validate_minecraftkit(root))

    try:
        expected_release = build_release_manifest(root)
        errors.extend(validate_release_manifest(root, release, expected_release))
    except (AttributeError, IndexError, KeyError, OSError, TypeError, ValueError) as error:
        errors.append(f"release manifest inputs are invalid: {type(error).__name__}: {error}")

    for path in (root / "scripts").glob("*.py"):
        try:
            ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except SyntaxError as error:
            errors.append(f"Python syntax error in {path.name}: {error}")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path, nargs="?", default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    root = args.root.resolve()
    errors = validate(root)
    if errors:
        print(f"MinecraftKit validation: FAIL ({len(errors)} issues)")
        for error in errors:
            print(f"- {error}")
        return 1
    print("MinecraftKit validation: PASS")
    print("10 domains; 10 deep RPG plugins; 4,947 plugin-owned types; 41,887 members; 965 API shards")
    return 0


if __name__ == "__main__":
    sys.exit(main())
