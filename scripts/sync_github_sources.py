"""Refresh a reviewed MinecraftKit GitHub source catalog into a pinned snapshot."""

from __future__ import annotations

import argparse
import os
import re
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

from catalog_io import (
    atomic_write_json,
    require_github_repository,
    require_https_url,
    require_kebab_id,
    require_string_list,
    sha256_bytes,
    strict_json_bytes,
    strict_json_file,
)


API_ROOT = "https://api.github.com"
INGESTION_POLICIES = {"index", "derive", "metadata-only", "link-only"}
PRIORITIES = {"P0", "P1", "P2"}
COMMIT_SHA = re.compile(r"[0-9a-f]{40}")
SHA256 = re.compile(r"[0-9a-f]{64}")


def validate_catalog(document: Any) -> list[dict[str, Any]]:
    if not isinstance(document, dict) or document.get("schema_version") != 1:
        raise ValueError("GitHub source catalog schema_version must be 1")
    sources = document.get("sources")
    if not isinstance(sources, list) or not sources:
        raise ValueError("GitHub source catalog must contain sources")

    seen_ids: set[str] = set()
    seen_repositories: set[str] = set()
    validated: list[dict[str, Any]] = []
    for index, source in enumerate(sources):
        label = f"sources[{index}]"
        if not isinstance(source, dict):
            raise ValueError(f"{label} must be an object")
        expected = {
            "id", "name", "repository", "domains", "priority", "ingestion_policy",
            "docs_url", "rationale",
        }
        if set(source) != expected:
            raise ValueError(f"{label} keys must be exactly {sorted(expected)}")
        source_id = require_kebab_id(source["id"], label=f"{label}.id")
        repository = require_github_repository(
            source["repository"], label=f"{label}.repository"
        )
        if source_id in seen_ids or repository.lower() in seen_repositories:
            raise ValueError(f"duplicate source id or repository at {label}")
        seen_ids.add(source_id)
        seen_repositories.add(repository.lower())
        if not isinstance(source["name"], str) or not source["name"].strip():
            raise ValueError(f"{label}.name must be a string")
        require_string_list(source["domains"], label=f"{label}.domains")
        if source["priority"] not in PRIORITIES:
            raise ValueError(f"{label}.priority must be P0, P1, or P2")
        if source["ingestion_policy"] not in INGESTION_POLICIES:
            raise ValueError(f"{label}.ingestion_policy is invalid")
        require_https_url(source["docs_url"], label=f"{label}.docs_url")
        if not isinstance(source["rationale"], str) or not source["rationale"].strip():
            raise ValueError(f"{label}.rationale must be a string")
        validated.append(source)

    if [source["id"] for source in validated] != sorted(seen_ids):
        raise ValueError("sources must be sorted by id")
    return validated


def validate_snapshot(
    document: Any,
    catalog_sources: list[dict[str, Any]],
    catalog_sha256: str,
) -> dict[str, Any]:
    """Validate a pinned snapshot against the exact reviewed catalog that produced it."""
    if not isinstance(document, dict) or set(document) != {
        "schema_version", "retrieved_at", "catalog_sha256", "source_count", "sources",
    }:
        raise ValueError("GitHub source snapshot shape is invalid")
    if document.get("schema_version") != 1:
        raise ValueError("GitHub source snapshot schema_version must be 1")
    if not isinstance(document.get("retrieved_at"), str) or not document["retrieved_at"]:
        raise ValueError("GitHub source snapshot retrieved_at is missing")
    if SHA256.fullmatch(catalog_sha256) is None or document.get("catalog_sha256") != catalog_sha256:
        raise ValueError("GitHub source snapshot was not built from the supplied catalog")
    records = document.get("sources")
    if not isinstance(records, list) or document.get("source_count") != len(records):
        raise ValueError("GitHub source snapshot count is invalid")
    if len(records) != len(catalog_sources):
        raise ValueError("GitHub source snapshot count does not match its catalog")
    if [record.get("id") if isinstance(record, dict) else None for record in records] != [
        source["id"] for source in catalog_sources
    ]:
        raise ValueError("GitHub source snapshot identities or order differ from its catalog")

    github_keys = {
        "canonical_repository", "url", "description", "default_branch", "archived",
        "fork", "stars", "forks", "open_issues", "pushed_at", "default_branch_head",
        "license", "latest_release",
    }
    for source, record in zip(catalog_sources, records):
        source_id = source["id"]
        if not isinstance(record, dict) or set(record) != set(source) | {"github"}:
            raise ValueError(f"GitHub source snapshot record shape is invalid: {source_id}")
        for key, value in source.items():
            if record.get(key) != value:
                raise ValueError(f"GitHub source snapshot drifted from catalog: {source_id}.{key}")
        github = record.get("github")
        if not isinstance(github, dict) or set(github) != github_keys:
            raise ValueError(f"GitHub metadata shape is invalid: {source_id}")
        canonical = github.get("canonical_repository")
        if not isinstance(canonical, str) or canonical.casefold() != source["repository"].casefold():
            raise ValueError(f"canonical GitHub repository mismatch: {source_id}")
        repository_url = require_https_url(github.get("url"), label=f"{source_id} repository URL")
        if repository_url.casefold() != f"https://github.com/{canonical}".casefold():
            raise ValueError(f"canonical GitHub URL mismatch: {source_id}")
        if not isinstance(github.get("default_branch"), str) or not github["default_branch"]:
            raise ValueError(f"GitHub default branch is invalid: {source_id}")
        if type(github.get("archived")) is not bool or type(github.get("fork")) is not bool:
            raise ValueError(f"GitHub repository flags are invalid: {source_id}")
        for key in ("stars", "forks", "open_issues"):
            if type(github.get(key)) is not int or github[key] < 0:
                raise ValueError(f"GitHub repository count is invalid: {source_id}.{key}")
        for key in ("description", "pushed_at"):
            if github.get(key) is not None and not isinstance(github[key], str):
                raise ValueError(f"GitHub repository field is invalid: {source_id}.{key}")

        head = github.get("default_branch_head")
        if not isinstance(head, dict) or set(head) != {"sha", "committed_at", "url"}:
            raise ValueError(f"GitHub source head shape is invalid: {source_id}")
        sha = head.get("sha")
        if not isinstance(sha, str) or COMMIT_SHA.fullmatch(sha) is None:
            raise ValueError(f"GitHub source head SHA is invalid: {source_id}")
        commit_url = require_https_url(head.get("url"), label=f"{source_id} commit URL")
        if commit_url.casefold() != f"{repository_url}/commit/{sha}".casefold():
            raise ValueError(f"GitHub source head URL is invalid: {source_id}")
        if head.get("committed_at") is not None and not isinstance(head["committed_at"], str):
            raise ValueError(f"GitHub source commit time is invalid: {source_id}")

        license_data = github.get("license")
        if license_data is not None:
            if not isinstance(license_data, dict) or set(license_data) != {"spdx_id", "name", "key"}:
                raise ValueError(f"GitHub license metadata is invalid: {source_id}")
            if any(value is not None and not isinstance(value, str) for value in license_data.values()):
                raise ValueError(f"GitHub license metadata is invalid: {source_id}")
        release = github.get("latest_release")
        if release is not None:
            if not isinstance(release, dict) or set(release) != {"tag", "published_at", "prerelease", "url"}:
                raise ValueError(f"GitHub release metadata is invalid: {source_id}")
            if not isinstance(release.get("tag"), str) or not release["tag"]:
                raise ValueError(f"GitHub release tag is invalid: {source_id}")
            if release.get("published_at") is not None and not isinstance(release["published_at"], str):
                raise ValueError(f"GitHub release timestamp is invalid: {source_id}")
            if type(release.get("prerelease")) is not bool:
                raise ValueError(f"GitHub release prerelease flag is invalid: {source_id}")
            require_https_url(release.get("url"), label=f"{source_id} release URL")
    return document


class GitHubClient:
    def __init__(
        self,
        token: str | None = None,
        opener: Callable[..., Any] = urlopen,
    ) -> None:
        self._token = token
        self._opener = opener

    def get(self, path: str, *, allow_not_found: bool = False) -> Any | None:
        url = f"{API_ROOT}{path}"
        headers = {
            "Accept": "application/vnd.github+json",
            "User-Agent": "minecraftkit-source-sync/2",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        if self._token:
            headers["Authorization"] = f"Bearer {self._token}"
        request = Request(url, headers=headers)
        try:
            with self._opener(request, timeout=30) as response:
                return strict_json_bytes(response.read(), label=url)
        except HTTPError as error:
            if allow_not_found and error.code == 404:
                return None
            remaining = error.headers.get("X-RateLimit-Remaining", "unknown")
            reset = error.headers.get("X-RateLimit-Reset", "unknown")
            raise RuntimeError(
                f"GitHub request failed ({error.code}) for {path}; "
                f"rate remaining={remaining}, reset={reset}"
            ) from error
        except URLError as error:
            raise RuntimeError(f"GitHub request failed for {path}: {error.reason}") from error


def normalize_repository(
    source: dict[str, Any],
    repository: Any,
    release: Any,
    head_commit: Any,
) -> dict[str, Any]:
    if not isinstance(repository, dict):
        raise ValueError(f"GitHub returned invalid repository data for {source['repository']}")
    full_name = repository.get("full_name")
    if not isinstance(full_name, str) or full_name.lower() != source["repository"].lower():
        raise ValueError(
            f"canonical repository mismatch: expected {source['repository']}, got {full_name}"
        )
    license_data = repository.get("license")
    if license_data is not None and not isinstance(license_data, dict):
        raise ValueError(f"invalid license metadata for {full_name}")
    normalized_release = None
    if release is not None:
        if not isinstance(release, dict) or not isinstance(release.get("tag_name"), str):
            raise ValueError(f"invalid latest release metadata for {full_name}")
        normalized_release = {
            "tag": release["tag_name"],
            "published_at": release.get("published_at"),
            "prerelease": bool(release.get("prerelease")),
            "url": require_https_url(release.get("html_url"), label=f"{full_name} release URL"),
        }
    if not isinstance(head_commit, dict):
        raise ValueError(f"GitHub returned invalid head commit for {full_name}")
    commit_sha = head_commit.get("sha")
    if not isinstance(commit_sha, str) or COMMIT_SHA.fullmatch(commit_sha) is None:
        raise ValueError(f"invalid default-branch commit SHA for {full_name}")
    commit_data = head_commit.get("commit")
    committer = commit_data.get("committer") if isinstance(commit_data, dict) else None
    committed_at = committer.get("date") if isinstance(committer, dict) else None
    return {
        **source,
        "github": {
            "canonical_repository": full_name,
            "url": require_https_url(repository.get("html_url"), label=f"{full_name} URL"),
            "description": repository.get("description"),
            "default_branch": repository.get("default_branch"),
            "archived": bool(repository.get("archived")),
            "fork": bool(repository.get("fork")),
            "stars": repository.get("stargazers_count"),
            "forks": repository.get("forks_count"),
            "open_issues": repository.get("open_issues_count"),
            "pushed_at": repository.get("pushed_at"),
            "default_branch_head": {
                "sha": commit_sha,
                "committed_at": committed_at,
                "url": require_https_url(
                    head_commit.get("html_url"), label=f"{full_name} commit URL"
                ),
            },
            "license": None if license_data is None else {
                "spdx_id": license_data.get("spdx_id"),
                "name": license_data.get("name"),
                "key": license_data.get("key"),
            },
            "latest_release": normalized_release,
        },
    }


def build_snapshot(
    catalog_path: Path,
    client: GitHubClient,
    *,
    retrieved_at: str,
    workers: int = 8,
) -> dict[str, Any]:
    catalog_bytes = catalog_path.read_bytes()
    sources = validate_catalog(strict_json_bytes(catalog_bytes, label=str(catalog_path)))
    if not 1 <= workers <= 16:
        raise ValueError("GitHub source sync workers must be between 1 and 16")

    def fetch_source(source: dict[str, Any]) -> dict[str, Any]:
        repository = client.get(f"/repos/{source['repository']}")
        if not isinstance(repository, dict) or not isinstance(repository.get("default_branch"), str):
            raise ValueError(f"GitHub returned invalid default branch for {source['repository']}")
        release = client.get(
            f"/repos/{source['repository']}/releases/latest", allow_not_found=True
        )
        head_commit = client.get(
            f"/repos/{source['repository']}/commits/{quote(repository['default_branch'], safe='')}"
        )
        return normalize_repository(source, repository, release, head_commit)

    with ThreadPoolExecutor(max_workers=workers) as executor:
        records = list(executor.map(fetch_source, sources))
    snapshot = {
        "schema_version": 1,
        "retrieved_at": retrieved_at,
        "catalog_sha256": sha256_bytes(catalog_bytes),
        "source_count": len(records),
        "sources": records,
    }
    return validate_snapshot(snapshot, sources, sha256_bytes(catalog_bytes))


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--catalog", type=Path, default=root / "data" / "github-source-catalog.json")
    parser.add_argument("--output", type=Path, default=root / "data" / "github-source-snapshot.json")
    parser.add_argument("--offline", action="store_true", help="Validate catalog and snapshot without network")
    parser.add_argument("--as-of", help="Pinned UTC timestamp for reproducible fixture runs")
    parser.add_argument("--workers", type=int, default=8, help="Concurrent GitHub repository lookups (1..16)")
    args = parser.parse_args()

    catalog = args.catalog.resolve()
    catalog_bytes = catalog.read_bytes()
    catalog_sources = validate_catalog(strict_json_bytes(catalog_bytes, label=str(catalog)))
    if args.offline:
        snapshot = strict_json_file(args.output.resolve())
        validate_snapshot(snapshot, catalog_sources, sha256_bytes(catalog_bytes))
        print(f"Validated {snapshot['source_count']} pinned GitHub sources")
        return 0

    retrieved_at = args.as_of or datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    snapshot = build_snapshot(
        catalog,
        GitHubClient(token=os.environ.get("GITHUB_TOKEN")),
        retrieved_at=retrieved_at,
        workers=args.workers,
    )
    atomic_write_json(args.output, snapshot)
    print(f"Refreshed {snapshot['source_count']} GitHub sources")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, RuntimeError) as error:
        print(f"GitHub source sync failed: {error}", file=sys.stderr)
        raise SystemExit(1) from error
