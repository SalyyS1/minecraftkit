"""Mirror Mojang's public version metadata without downloading game binaries."""

from __future__ import annotations

import argparse
import hashlib
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from catalog_io import (
    atomic_write_json,
    require_https_url,
    sha256_bytes,
    strict_json_bytes,
)


MANIFEST_URL = "https://piston-meta.mojang.com/mc/game/version_manifest_v2.json"
MOJANG_METADATA_HOSTS = {"piston-meta.mojang.com", "launchermeta.mojang.com"}
SHA1 = re.compile(r"[0-9a-f]{40}")


def fetch_json(
    url: str,
    *,
    opener: Callable[..., Any] = urlopen,
) -> tuple[Any, bytes]:
    require_https_url(url, label="Mojang metadata URL", allowed_hosts=MOJANG_METADATA_HOSTS)
    request = Request(url, headers={"User-Agent": "minecraftkit-version-sync/2"})
    try:
        with opener(request, timeout=30) as response:
            payload = response.read()
    except (HTTPError, URLError) as error:
        raise RuntimeError(f"Mojang metadata request failed for {url}: {error}") from error
    return strict_json_bytes(payload, label=url), payload


def normalize_downloads(downloads: Any) -> dict[str, Any]:
    if not isinstance(downloads, dict):
        return {}
    result = {}
    for key in sorted(downloads):
        value = downloads[key]
        if not isinstance(value, dict):
            raise ValueError(f"invalid Mojang download descriptor: {key}")
        url = value.get("url")
        if not isinstance(url, str) or not url.startswith("https://"):
            raise ValueError(f"invalid Mojang download URL: {key}")
        result[key] = {
            "sha1": value.get("sha1"),
            "size": value.get("size"),
            "url": url,
        }
    return result


def normalize_detail(version_id: str, document: Any) -> dict[str, Any]:
    if not isinstance(document, dict) or document.get("id") != version_id:
        raise ValueError(f"Mojang detail identity mismatch for {version_id}")
    java_version = document.get("javaVersion")
    if java_version is not None and not isinstance(java_version, dict):
        raise ValueError(f"invalid javaVersion for {version_id}")
    asset_index = document.get("assetIndex")
    if asset_index is not None and not isinstance(asset_index, dict):
        raise ValueError(f"invalid assetIndex for {version_id}")
    return {
        "id": version_id,
        "type": document.get("type"),
        "time": document.get("time"),
        "release_time": document.get("releaseTime"),
        "minimum_launcher_version": document.get("minimumLauncherVersion"),
        "java_version": None if java_version is None else {
            "component": java_version.get("component"),
            "major_version": java_version.get("majorVersion"),
        },
        "asset_index": None if asset_index is None else {
            "id": asset_index.get("id"),
            "sha1": asset_index.get("sha1"),
            "size": asset_index.get("size"),
            "total_size": asset_index.get("totalSize"),
            "url": asset_index.get("url"),
        },
        "downloads": normalize_downloads(document.get("downloads")),
    }


def build_catalog(
    *,
    detail_ids: list[str],
    retrieved_at: str,
    opener: Callable[..., Any] = urlopen,
) -> dict[str, Any]:
    manifest, payload = fetch_json(MANIFEST_URL, opener=opener)
    if not isinstance(manifest, dict) or not isinstance(manifest.get("versions"), list):
        raise ValueError("Mojang version manifest shape is invalid")
    latest = manifest.get("latest")
    if not isinstance(latest, dict) or not all(isinstance(latest.get(key), str) for key in ("release", "snapshot")):
        raise ValueError("Mojang latest version pointers are invalid")

    versions = []
    by_id: dict[str, dict[str, Any]] = {}
    for index, version in enumerate(manifest["versions"]):
        if not isinstance(version, dict):
            raise ValueError(f"versions[{index}] must be an object")
        version_id = version.get("id")
        if not isinstance(version_id, str) or not version_id or version_id in by_id:
            raise ValueError(f"invalid or duplicate Mojang version id at index {index}")
        detail_sha1 = version.get("sha1")
        if not isinstance(detail_sha1, str) or SHA1.fullmatch(detail_sha1) is None:
            raise ValueError(f"invalid Mojang version metadata SHA-1 for {version_id}")
        record = {
            "id": version_id,
            "type": version.get("type"),
            "url": require_https_url(
                version.get("url"),
                label=f"Mojang version URL {version_id}",
                allowed_hosts=MOJANG_METADATA_HOSTS,
            ),
            "time": version.get("time"),
            "release_time": version.get("releaseTime"),
            "sha1": detail_sha1,
            "compliance_level": version.get("complianceLevel"),
        }
        versions.append(record)
        by_id[version_id] = record

    details = {}
    for version_id in sorted(set(detail_ids)):
        if version_id not in by_id:
            raise ValueError(f"requested Mojang version does not exist: {version_id}")
        detail, detail_payload = fetch_json(by_id[version_id]["url"], opener=opener)
        # Mojang publishes SHA-1 for metadata integrity; verify bytes before parsing them into evidence.
        actual_sha1 = hashlib.sha1(detail_payload).hexdigest()
        if actual_sha1 != by_id[version_id]["sha1"]:
            raise ValueError(
                f"Mojang version metadata SHA-1 mismatch for {version_id}: "
                f"expected {by_id[version_id]['sha1']}, got {actual_sha1}"
            )
        details[version_id] = normalize_detail(version_id, detail)

    counts: dict[str, int] = {}
    for version in versions:
        kind = version.get("type")
        if not isinstance(kind, str):
            raise ValueError(f"invalid Mojang version type for {version['id']}")
        counts[kind] = counts.get(kind, 0) + 1
    return {
        "schema_version": 1,
        "retrieved_at": retrieved_at,
        "source": {
            "url": MANIFEST_URL,
            "sha256": sha256_bytes(payload),
        },
        "latest": {"release": latest["release"], "snapshot": latest["snapshot"]},
        "version_count": len(versions),
        "counts_by_type": dict(sorted(counts.items())),
        "versions": versions,
        "details": details,
    }


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=root / "data" / "minecraft-version-catalog.json")
    parser.add_argument("--detail", action="append", default=[], help="Hydrate one version's metadata; repeatable")
    parser.add_argument("--as-of", help="Pinned UTC timestamp for reproducible fixture runs")
    args = parser.parse_args()
    retrieved_at = args.as_of or datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    catalog = build_catalog(detail_ids=args.detail, retrieved_at=retrieved_at)
    atomic_write_json(args.output, catalog)
    print(
        f"Refreshed {catalog['version_count']} Mojang versions; "
        f"latest release={catalog['latest']['release']}, snapshot={catalog['latest']['snapshot']}"
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, RuntimeError) as error:
        print(f"Minecraft version sync failed: {error}", file=sys.stderr)
        raise SystemExit(1) from error
