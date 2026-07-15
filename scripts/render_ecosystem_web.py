"""Render the deterministic, offline MinecraftKit ecosystem web payload."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import tempfile
from collections import Counter
from pathlib import Path
from typing import Any

from sync_github_sources import validate_snapshot as validate_github_snapshot


ASSIGNMENT = "window.MinecraftKitEcosystem="
DOMAIN_IDS = {
    "build", "client", "core", "dialog", "model", "nms", "pack", "protocol", "rpg", "shader",
}
INGESTION_POLICIES = {"derive", "index", "link-only", "metadata-only"}
PRIORITIES = {"P0", "P1", "P2"}


def strict_json(path: Path) -> Any:
    return json.loads(
        path.read_text(encoding="utf-8"),
        parse_constant=lambda value: (_ for _ in ()).throw(
            ValueError(f"Non-standard JSON constant {value} in {path}")
        ),
    )


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require_object(document: Any, *, label: str) -> dict[str, Any]:
    if not isinstance(document, dict):
        raise ValueError(f"{label} must be an object")
    return document


def require_list(document: Any, *, label: str) -> list[Any]:
    if not isinstance(document, list):
        raise ValueError(f"{label} must be an array")
    return document


def validate_domains(document: Any) -> list[dict[str, Any]]:
    root = require_object(document, label="domain catalog")
    if root.get("schema_version") != 1:
        raise ValueError("domain catalog schema_version must be 1")
    domains = require_list(root.get("domains"), label="domain catalog domains")
    ids: list[str] = []
    for domain in domains:
        item = require_object(domain, label="domain")
        domain_id = item.get("id")
        if not isinstance(domain_id, str) or domain_id not in DOMAIN_IDS:
            raise ValueError(f"unknown MinecraftKit domain: {domain_id!r}")
        if item.get("route") != f"mc:{domain_id}":
            raise ValueError(f"domain route does not match id: {domain_id}")
        if not isinstance(item.get("name"), str) or not item["name"].strip():
            raise ValueError(f"domain name is missing: {domain_id}")
        keywords = require_list(item.get("keywords"), label=f"{domain_id} keywords")
        if not keywords or not all(isinstance(value, str) and value for value in keywords):
            raise ValueError(f"domain keywords are invalid: {domain_id}")
        ids.append(domain_id)
    if set(ids) != DOMAIN_IDS or len(ids) != len(set(ids)):
        raise ValueError("domain catalog must contain the ten unique MinecraftKit domains")
    return domains


def validate_source_catalog(document: Any, domain_ids: set[str]) -> list[dict[str, Any]]:
    root = require_object(document, label="GitHub source catalog")
    if root.get("schema_version") != 1:
        raise ValueError("GitHub source catalog schema_version must be 1")
    sources = require_list(root.get("sources"), label="GitHub source catalog sources")
    if not sources:
        raise ValueError("GitHub source catalog must not be empty")
    ids: list[str] = []
    repositories: list[str] = []
    for source in sources:
        item = require_object(source, label="GitHub source")
        source_id = item.get("id")
        repository = item.get("repository")
        if not isinstance(source_id, str) or not source_id:
            raise ValueError("GitHub source id is missing")
        if not isinstance(repository, str) or repository.count("/") != 1:
            raise ValueError(f"GitHub repository is invalid: {repository!r}")
        source_domains = require_list(item.get("domains"), label=f"{source_id} domains")
        if not source_domains or not set(source_domains).issubset(domain_ids):
            raise ValueError(f"GitHub source domains are invalid: {source_id}")
        if item.get("priority") not in PRIORITIES:
            raise ValueError(f"GitHub source priority is invalid: {source_id}")
        if item.get("ingestion_policy") not in INGESTION_POLICIES:
            raise ValueError(f"GitHub source ingestion policy is invalid: {source_id}")
        for key in ("name", "docs_url", "rationale"):
            if not isinstance(item.get(key), str) or not item[key].strip():
                raise ValueError(f"GitHub source {key} is missing: {source_id}")
        if not item["docs_url"].startswith("https://"):
            raise ValueError(f"GitHub source docs_url must use HTTPS: {source_id}")
        ids.append(source_id)
        repositories.append(repository.casefold())
    if len(ids) != len(set(ids)) or len(repositories) != len(set(repositories)):
        raise ValueError("GitHub source ids and repositories must be unique")
    if ids != sorted(ids):
        raise ValueError("GitHub sources must be sorted by id")
    return sources


def validate_source_snapshot(
    document: Any,
    catalog_sources: list[dict[str, Any]],
    catalog_sha256: str,
) -> dict[str, Any]:
    return validate_github_snapshot(document, catalog_sources, catalog_sha256)


def validate_versions(document: Any) -> dict[str, Any]:
    root = require_object(document, label="Minecraft version catalog")
    if root.get("schema_version") != 1:
        raise ValueError("Minecraft version catalog schema_version must be 1")
    versions = require_list(root.get("versions"), label="Minecraft versions")
    if root.get("version_count") != len(versions) or not versions:
        raise ValueError("Minecraft version_count does not match history")
    counts = Counter()
    ids: set[str] = set()
    for version in versions:
        item = require_object(version, label="Minecraft version")
        version_id = item.get("id")
        version_type = item.get("type")
        if not isinstance(version_id, str) or not version_id or version_id in ids:
            raise ValueError(f"Minecraft version id is invalid: {version_id!r}")
        if version_type not in {"release", "snapshot", "old_alpha", "old_beta"}:
            raise ValueError(f"Minecraft version type is invalid: {version_type!r}")
        ids.add(version_id)
        counts[version_type] += 1
    if dict(counts) != root.get("counts_by_type"):
        raise ValueError("Minecraft version type counts do not reconcile")
    latest = require_object(root.get("latest"), label="latest Minecraft versions")
    details = require_object(root.get("details"), label="hydrated Minecraft details")
    for version_type in ("release", "snapshot"):
        version_id = latest.get(version_type)
        if version_id not in ids or version_id not in details:
            raise ValueError(f"latest {version_type} lacks hydrated metadata")
    source = require_object(root.get("source"), label="Minecraft version source")
    if not isinstance(source.get("url"), str) or not source["url"].startswith("https://"):
        raise ValueError("Minecraft version provenance URL is invalid")
    if not isinstance(root.get("retrieved_at"), str) or not root["retrieved_at"]:
        raise ValueError("Minecraft version retrieved_at is missing")
    return root


def validate_release_capabilities(
    document: Any,
    versions: dict[str, Any],
) -> dict[str, Any]:
    root = require_object(document, label="Minecraft release capabilities")
    if root.get("schema_version") != 1:
        raise ValueError("Minecraft release capabilities schema_version must be 1")
    if not isinstance(root.get("observed_at"), str) or not root["observed_at"]:
        raise ValueError("Minecraft release capabilities observed_at is missing")
    releases = require_list(root.get("releases"), label="Minecraft release capabilities")
    if not releases:
        raise ValueError("Minecraft release capabilities must not be empty")
    seen: set[str] = set()
    for release in releases:
        item = require_object(release, label="Minecraft release capability")
        version_id = item.get("id")
        if not isinstance(version_id, str) or version_id in seen:
            raise ValueError(f"Minecraft release capability id is invalid: {version_id!r}")
        seen.add(version_id)
        details = versions["details"].get(version_id)
        if not isinstance(details, dict):
            raise ValueError(f"Minecraft release capability lacks hydrated metadata: {version_id}")
        client = details.get("downloads", {}).get("client", {})
        if item.get("client_sha1") != client.get("sha1"):
            raise ValueError(f"Minecraft release capability client SHA-1 mismatch: {version_id}")
        java_version = details.get("java_version", {})
        if item.get("java_major") != java_version.get("major_version"):
            raise ValueError(f"Minecraft release capability Java version mismatch: {version_id}")
        if type(item.get("protocol")) is not int or item["protocol"] < 0:
            raise ValueError(f"Minecraft release capability protocol is invalid: {version_id}")
        for pack_name in ("resource_pack", "data_pack"):
            pack = require_object(item.get(pack_name), label=f"{version_id} {pack_name}")
            if type(pack.get("major")) is not int or type(pack.get("minor")) is not int:
                raise ValueError(f"Minecraft release capability {pack_name} is invalid: {version_id}")
        inventory = require_object(item.get("vanilla_inventory"), label=f"{version_id} vanilla inventory")
        count_keys = {
            "core_shader_files", "include_shader_files", "post_shader_files",
            "item_geometry_entries", "item_definition_entries", "built_in_font_json_files",
        }
        if any(type(inventory.get(key)) is not int or inventory[key] < 0 for key in count_keys):
            raise ValueError(f"Minecraft release capability inventory is invalid: {version_id}")
        for key in ("built_in_dialog_ids", "observed_font_provider_kinds"):
            values = require_list(inventory.get(key), label=f"{version_id} {key}")
            if not all(isinstance(value, str) and value for value in values):
                raise ValueError(f"Minecraft release capability {key} is invalid: {version_id}")
        provenance = require_object(item.get("provenance"), label=f"{version_id} capability provenance")
        if not isinstance(provenance.get("version_metadata_url"), str) or not provenance["version_metadata_url"].startswith("https://"):
            raise ValueError(f"Minecraft release capability provenance URL is invalid: {version_id}")
        for key in ("evidence_class",):
            if not isinstance(item.get(key), str) or not item[key]:
                raise ValueError(f"Minecraft release capability {key} is missing: {version_id}")
        for key in ("method", "restrictions"):
            if not isinstance(provenance.get(key), str) or not provenance[key]:
                raise ValueError(f"Minecraft release capability provenance {key} is missing: {version_id}")
    if versions["latest"]["release"] not in seen:
        raise ValueError("latest Minecraft release lacks a capability profile")
    return root


def build_payload(
    domain_catalog: Any,
    source_catalog: Any,
    source_snapshot: Any,
    version_catalog: Any,
    release_capabilities: Any,
    *,
    source_catalog_sha256: str,
    release_capabilities_sha256: str,
) -> dict[str, Any]:
    domains = validate_domains(domain_catalog)
    domain_ids = {item["id"] for item in domains}
    catalog_sources = validate_source_catalog(source_catalog, domain_ids)
    snapshot = validate_source_snapshot(
        source_snapshot, catalog_sources, source_catalog_sha256
    )
    versions = validate_versions(version_catalog)
    capabilities = validate_release_capabilities(release_capabilities, versions)

    source_records = snapshot["sources"]
    domain_counts = {
        domain_id: sum(domain_id in source["domains"] for source in source_records)
        for domain_id in sorted(domain_ids)
    }
    license_counts = Counter(
        (source["github"].get("license") or {}).get("spdx_id") or "not-declared"
        for source in source_records
    )
    return {
        "schemaVersion": 1,
        "domains": domains,
        "sources": source_records,
        "versions": {
            "versionCount": versions["version_count"],
            "countsByType": versions["counts_by_type"],
            "latest": versions["latest"],
            "details": versions["details"],
            "history": versions["versions"],
        },
        "releaseCapabilities": {
            "observedAt": capabilities["observed_at"],
            "releases": capabilities["releases"],
        },
        "summary": {
            "sourceCount": len(source_records),
            "domainCounts": domain_counts,
            "priorityCounts": dict(sorted(Counter(source["priority"] for source in source_records).items())),
            "policyCounts": dict(sorted(Counter(source["ingestion_policy"] for source in source_records).items())),
            "licenseCounts": dict(sorted(license_counts.items())),
            "archivedCount": sum(bool(source["github"].get("archived")) for source in source_records),
        },
        "provenance": {
            "githubRetrievedAt": snapshot["retrieved_at"],
            "githubCatalogSha256": snapshot["catalog_sha256"],
            "minecraftRetrievedAt": versions["retrieved_at"],
            "minecraftManifest": versions["source"],
            "releaseCapabilitiesSha256": release_capabilities_sha256,
        },
    }


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


def render(
    domain_catalog_path: Path,
    source_catalog_path: Path,
    source_snapshot_path: Path,
    version_catalog_path: Path,
    release_capabilities_path: Path,
    output_path: Path,
) -> dict[str, Any]:
    payload = build_payload(
        strict_json(domain_catalog_path),
        strict_json(source_catalog_path),
        strict_json(source_snapshot_path),
        strict_json(version_catalog_path),
        strict_json(release_capabilities_path),
        source_catalog_sha256=file_sha256(source_catalog_path),
        release_capabilities_sha256=file_sha256(release_capabilities_path),
    )
    atomic_write(output_path, javascript(payload))
    return payload


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--domains", type=Path, default=root / "data/minecraft-domain-catalog.json")
    parser.add_argument("--sources", type=Path, default=root / "data/github-source-catalog.json")
    parser.add_argument("--snapshot", type=Path, default=root / "data/github-source-snapshot.json")
    parser.add_argument("--versions", type=Path, default=root / "data/minecraft-version-catalog.json")
    parser.add_argument("--capabilities", type=Path, default=root / "data/minecraft-release-capabilities.json")
    parser.add_argument("--output", type=Path, default=root / "web/data/ecosystem.js")
    args = parser.parse_args()
    payload = render(
        args.domains.resolve(),
        args.sources.resolve(),
        args.snapshot.resolve(),
        args.versions.resolve(),
        args.capabilities.resolve(),
        args.output.resolve(),
    )
    print(
        f"Rendered {payload['summary']['sourceCount']} sources and "
        f"{payload['versions']['versionCount']} versions to {args.output.resolve()}"
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, json.JSONDecodeError) as error:
        print(f"Ecosystem web render failed: {error}", file=sys.stderr)
        raise SystemExit(1) from error
