"""Validate MinecraftKit's upstream, version, domain, skill, and command contracts."""

from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any

from sync_github_sources import (
    validate_catalog as validate_github_catalog,
    validate_snapshot as validate_github_snapshot,
)


ROUTE = re.compile(r"mc:([a-z0-9]+(?:-[a-z0-9]+)*)")


def load(path: Path) -> Any:
    return json.loads(
        path.read_text(encoding="utf-8"),
        parse_constant=lambda value: (_ for _ in ()).throw(
            ValueError(f"Non-standard JSON constant {value} in {path}")
        ),
    )


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def parse_frontmatter(path: Path) -> dict[str, str]:
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---\n") or "\n---\n" not in text[4:]:
        raise ValueError(f"missing frontmatter: {path}")
    block = text[4:text.index("\n---\n", 4)]
    result: dict[str, str] = {}
    for line in block.splitlines():
        if ":" not in line:
            raise ValueError(f"invalid frontmatter: {path}")
        key, value = line.split(":", 1)
        result[key.strip()] = value.strip().strip('"\'')
    return result


def validate_domains(root: Path, document: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(document, dict) or document.get("schema_version") != 1:
        return ["Minecraft domain catalog schema is invalid"]
    domains = document.get("domains")
    if not isinstance(domains, list) or len(domains) != 9:
        return ["Minecraft domain catalog must contain 9 domains"]
    expected_keys = {
        "id", "name", "route", "skill_directory", "reference", "keywords",
    }
    ids: list[str] = []
    routes: list[str] = []
    for index, domain in enumerate(domains):
        if not isinstance(domain, dict) or set(domain) != expected_keys:
            errors.append(f"domain {index} shape is invalid")
            continue
        domain_id = domain.get("id")
        route = domain.get("route")
        skill_directory = domain.get("skill_directory")
        reference = domain.get("reference")
        keywords = domain.get("keywords")
        if not isinstance(domain_id, str) or route != f"mc:{domain_id}":
            errors.append(f"domain {index} route is invalid")
            continue
        ids.append(domain_id)
        routes.append(route)
        if skill_directory != f"mc-{domain_id}":
            errors.append(f"domain {domain_id} skill directory is invalid")
        if not isinstance(keywords, list) or keywords != sorted(set(keywords)):
            errors.append(f"domain {domain_id} keywords must be sorted and unique")
        wrapper = root / "skill-wrappers" / str(skill_directory) / "SKILL.md"
        command = root / "commands" / "mc" / f"{domain_id}.md"
        reference_path = root / str(reference)
        for path, label in ((wrapper, "wrapper"), (command, "command"), (reference_path, "reference")):
            if not path.is_file():
                errors.append(f"domain {domain_id} {label} is missing")
        if wrapper.is_file():
            try:
                if parse_frontmatter(wrapper).get("name") != skill_directory:
                    errors.append(f"domain {domain_id} wrapper name is invalid")
            except ValueError as error:
                errors.append(str(error))
        if command.is_file():
            text = command.read_text(encoding="utf-8")
            if f"`/{route}`" not in text or f"`{skill_directory}`" not in text or "$ARGUMENTS" not in text:
                errors.append(f"domain {domain_id} command does not bind its slash route to its installed skill")
            if len(text.splitlines()) > 100:
                errors.append(f"domain {domain_id} command exceeds 100 lines")
    if ids != sorted(ids) or len(set(ids)) != len(ids):
        errors.append("Minecraft domains must be uniquely sorted")
    if len(set(routes)) != len(routes):
        errors.append("Minecraft domain routes must be unique")
    evidence = document.get("evidence_classes")
    policies = document.get("ingestion_policies")
    if not isinstance(evidence, list) or len(set(evidence)) != len(evidence):
        errors.append("Minecraft evidence classes are invalid")
    if policies != ["derive", "index", "link-only", "metadata-only"]:
        errors.append("Minecraft ingestion policies are invalid")
    return errors


def validate_versions(document: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(document, dict) or document.get("schema_version") != 1:
        return ["Minecraft version catalog schema is invalid"]
    versions = document.get("versions")
    latest = document.get("latest")
    counts = document.get("counts_by_type")
    details = document.get("details")
    if not isinstance(versions, list) or not isinstance(latest, dict):
        return ["Minecraft version catalog shape is invalid"]
    ids = [item.get("id") for item in versions if isinstance(item, dict)]
    if len(ids) != len(versions) or len(set(ids)) != len(ids):
        errors.append("Minecraft version IDs must be unique strings")
    if document.get("version_count") != len(versions) or len(versions) < 800:
        errors.append("Minecraft version count is incomplete")
    actual_counts = Counter(item.get("type") for item in versions if isinstance(item, dict))
    if not isinstance(counts, dict) or dict(sorted(actual_counts.items())) != counts:
        errors.append("Minecraft version type counts do not reconcile")
    for key in ("release", "snapshot"):
        if latest.get(key) not in set(ids):
            errors.append(f"Minecraft latest {key} is absent from versions")
    if not isinstance(details, dict) or not set(details).issubset(set(ids)):
        errors.append("Minecraft hydrated version details are invalid")
    else:
        for version_id, detail in details.items():
            java = detail.get("java_version") if isinstance(detail, dict) else None
            if detail.get("id") != version_id or not isinstance(java, dict) or type(java.get("major_version")) is not int:
                errors.append(f"Minecraft detail is invalid: {version_id}")
    source = document.get("source")
    if not isinstance(source, dict) or re.fullmatch(r"[0-9a-f]{64}", str(source.get("sha256"))) is None:
        errors.append("Minecraft version source hash is invalid")
    return errors


def validate_release_capabilities(document: Any, versions: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(document, dict) or document.get("schema_version") != 1:
        return ["Minecraft release capability schema is invalid"]
    releases = document.get("releases")
    details = versions.get("details") if isinstance(versions, dict) else None
    if not isinstance(releases, list) or not releases or not isinstance(details, dict):
        return ["Minecraft release capability shape is invalid"]
    ids: list[str] = []
    for release in releases:
        if not isinstance(release, dict) or not isinstance(release.get("id"), str):
            errors.append("Minecraft release capability record is invalid")
            continue
        version_id = release["id"]
        ids.append(version_id)
        detail = details.get(version_id)
        downloads = detail.get("downloads") if isinstance(detail, dict) else None
        client = downloads.get("client") if isinstance(downloads, dict) else None
        java = detail.get("java_version") if isinstance(detail, dict) else None
        if not isinstance(client, dict) or release.get("client_sha1") != client.get("sha1"):
            errors.append(f"Minecraft capability client hash mismatch: {version_id}")
        if not isinstance(java, dict) or release.get("java_major") != java.get("major_version"):
            errors.append(f"Minecraft capability Java mismatch: {version_id}")
        if type(release.get("protocol")) is not int or release["protocol"] <= 0:
            errors.append(f"Minecraft capability protocol is invalid: {version_id}")
        for key in ("resource_pack", "data_pack"):
            pack = release.get(key)
            if not isinstance(pack, dict) or set(pack) != {"major", "minor"} or not all(type(pack[field]) is int and pack[field] >= 0 for field in pack):
                errors.append(f"Minecraft capability {key} is invalid: {version_id}")
        inventory = release.get("vanilla_inventory")
        if not isinstance(inventory, dict) or not all(
            type(value) is int and value >= 0
            for value in inventory.values() if not isinstance(value, list)
        ):
            errors.append(f"Minecraft capability inventory is invalid: {version_id}")
    if len(ids) != len(set(ids)):
        errors.append("Minecraft capability release IDs must be unique")
    return errors


def validate_sources(catalog_path: Path, snapshot: Any, domain_ids: set[str]) -> list[str]:
    errors: list[str] = []
    try:
        catalog = load(catalog_path)
        sources = validate_github_catalog(catalog)
    except (OSError, UnicodeError, ValueError, json.JSONDecodeError) as error:
        return [f"GitHub source catalog is invalid: {error}"]
    if len(sources) < 50:
        errors.append("GitHub source catalog must contain at least 50 reviewed sources")
    for source in sources:
        if not set(source["domains"]).issubset(domain_ids):
            errors.append(f"GitHub source uses an unknown domain: {source['id']}")
    try:
        validate_github_snapshot(snapshot, sources, sha256(catalog_path))
    except ValueError as error:
        errors.append(f"GitHub source snapshot is invalid: {error}")
    return errors


def validate_minecraftkit(root: Path) -> list[str]:
    try:
        domains = load(root / "data" / "minecraft-domain-catalog.json")
        versions = load(root / "data" / "minecraft-version-catalog.json")
        release_capabilities = load(root / "data" / "minecraft-release-capabilities.json")
        snapshot = load(root / "data" / "github-source-snapshot.json")
    except (OSError, UnicodeError, ValueError, json.JSONDecodeError) as error:
        return [f"MinecraftKit catalog read failed: {error}"]
    domain_errors = validate_domains(root, domains)
    domain_ids = {
        item.get("id") for item in domains.get("domains", [])
        if isinstance(item, dict) and isinstance(item.get("id"), str)
    } if isinstance(domains, dict) else set()
    return (
        domain_errors
        + validate_versions(versions)
        + validate_release_capabilities(release_capabilities, versions)
        + validate_sources(root / "data" / "github-source-catalog.json", snapshot, domain_ids)
    )
