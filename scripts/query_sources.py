"""Query MinecraftKit's reviewed upstream source catalog without network access."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from catalog_io import strict_json_file
from sync_github_sources import INGESTION_POLICIES, PRIORITIES, validate_catalog


def source_text(record: dict[str, Any]) -> str:
    github = record.get("github")
    release = github.get("latest_release") if isinstance(github, dict) else None
    fields: list[Any] = [
        record.get("id"), record.get("name"), record.get("repository"),
        record.get("docs_url"), record.get("rationale"), record.get("domains"),
        record.get("priority"), record.get("ingestion_policy"),
    ]
    if isinstance(github, dict):
        fields.extend((github.get("description"), github.get("default_branch")))
    if isinstance(release, dict):
        fields.append(release.get("tag"))
    return " ".join(
        str(item) for value in fields
        for item in (value if isinstance(value, list) else [value])
        if item is not None
    ).casefold()


def load_records(catalog_path: Path, snapshot_path: Path | None) -> list[dict[str, Any]]:
    catalog = strict_json_file(catalog_path)
    sources = validate_catalog(catalog)
    if snapshot_path is None or not snapshot_path.is_file():
        return sources
    snapshot = strict_json_file(snapshot_path)
    records = snapshot.get("sources") if isinstance(snapshot, dict) else None
    if not isinstance(records, list):
        raise ValueError("GitHub source snapshot must contain sources")
    by_id = {
        record.get("id"): record for record in records
        if isinstance(record, dict) and isinstance(record.get("id"), str)
    }
    if set(by_id) != {source["id"] for source in sources}:
        raise ValueError("GitHub source snapshot identities differ from catalog")
    return [by_id[source["id"]] for source in sources]


def query_records(
    records: list[dict[str, Any]],
    *,
    terms: list[str],
    domain: str | None,
    priority: str | None,
    policy: str | None,
    include_archived: bool,
    limit: int,
) -> list[dict[str, Any]]:
    normalized_terms = [term.casefold() for term in terms if term.strip()]
    matches: list[dict[str, Any]] = []
    for record in records:
        github = record.get("github")
        if not include_archived and isinstance(github, dict) and github.get("archived") is True:
            continue
        if domain and domain not in record.get("domains", []):
            continue
        if priority and record.get("priority") != priority:
            continue
        if policy and record.get("ingestion_policy") != policy:
            continue
        haystack = source_text(record)
        if not all(term in haystack for term in normalized_terms):
            continue
        matches.append(record)
        if len(matches) >= limit:
            break
    return matches


def human_record(record: dict[str, Any]) -> str:
    github = record.get("github")
    head = github.get("default_branch_head") if isinstance(github, dict) else None
    release = github.get("latest_release") if isinstance(github, dict) else None
    revision = head.get("sha", "unpinned")[:12] if isinstance(head, dict) else "catalog-only"
    tag = release.get("tag") if isinstance(release, dict) else None
    suffix = f"; release={tag}" if tag else ""
    return (
        f"{record['id']}: {record['name']} ({record['repository']})\n"
        f"  domains={','.join(record['domains'])}; priority={record['priority']}; "
        f"policy={record['ingestion_policy']}; revision={revision}{suffix}\n"
        f"  {record['rationale']}\n"
        f"  {record['docs_url']}"
    )


def main(argv: list[str] | None = None) -> int:
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("terms", nargs="*", help="All case-insensitive terms must match")
    parser.add_argument("--domain")
    parser.add_argument("--priority", choices=sorted(PRIORITIES))
    parser.add_argument("--policy", choices=sorted(INGESTION_POLICIES))
    parser.add_argument("--include-archived", action="store_true")
    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--catalog", type=Path, default=root / "data" / "github-source-catalog.json")
    parser.add_argument("--snapshot", type=Path, default=root / "data" / "github-source-snapshot.json")
    args = parser.parse_args(argv)
    if not 1 <= args.limit <= 500:
        parser.error("--limit must be between 1 and 500")
    try:
        records = load_records(args.catalog.resolve(), args.snapshot.resolve())
        matches = query_records(
            records,
            terms=args.terms,
            domain=args.domain,
            priority=args.priority,
            policy=args.policy,
            include_archived=args.include_archived,
            limit=args.limit,
        )
    except (OSError, UnicodeError, ValueError, json.JSONDecodeError) as error:
        print(f"MinecraftKit source query failed: {error}", file=sys.stderr)
        return 2
    if args.json:
        print(json.dumps({"count": len(matches), "sources": matches}, indent=2, ensure_ascii=False, allow_nan=False))
    elif matches:
        print("\n\n".join(human_record(record) for record in matches))
    return 0 if matches else 1


if __name__ == "__main__":
    raise SystemExit(main())
