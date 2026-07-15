"""Search the MinecraftRPG Kit API index without loading it into an agent context."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Iterable


def iter_records(index: dict[str, Any]) -> Iterable[dict[str, Any]]:
    for plugin in index["plugins"]:
        for class_record in plugin["classes"]:
            yield {
                "record": "type",
                "plugin": plugin["name"],
                "origin": class_record.get("origin", "plugin-owned"),
                "owner": class_record["name"],
                "id": class_record["id"],
                "name": class_record["name"],
                "kind": class_record["kind"],
                "visibility": class_record["visibility"],
                "descriptor": class_record.get("generic_signature") or "",
                "source_path": class_record.get("source_path"),
            }
            for member in class_record["members"]:
                yield {
                    "record": "member",
                    "plugin": plugin["name"],
                    "origin": class_record.get("origin", "plugin-owned"),
                    "owner": class_record["name"],
                    "id": member["id"],
                    "name": member["name"],
                    "kind": member["kind"],
                    "visibility": member["visibility"],
                    "descriptor": member["descriptor"],
                    "return_type": member["return_type"],
                    "parameters": member["parameters"],
                    "throws": member.get("throws", []),
                    "generic_signature": member.get("generic_signature"),
                    "source_path": class_record.get("source_path"),
                }


def matches(record: dict[str, Any], terms: list[str], plugin: str | None, kind: str | None, origin: str | None) -> bool:
    if plugin and record["plugin"].lower() != plugin.lower():
        return False
    if kind and record["kind"].lower() != kind.lower():
        return False
    if origin and record["origin"].lower() != origin.lower():
        return False
    fields = [str(record.get(key, "")) for key in ("id", "name", "owner", "descriptor", "generic_signature", "return_type")]
    fields.extend(record.get("parameters", []))
    fields.extend(record.get("throws", []))
    haystack = " ".join(fields).replace("/", ".").lower()
    return all(term.lower() in haystack for term in terms)


def text_line(record: dict[str, Any]) -> str:
    if record["record"] == "type":
        return f"[{record['plugin']}] {record['visibility']} {record['kind']} {record['name']}"
    params = ", ".join(record.get("parameters", []))
    return f"[{record['plugin']}] {record['owner']} :: {record['visibility']} {record.get('return_type', '')} {record['name']}({params})"


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("terms", nargs="*", help="Case-insensitive terms; all must match")
    parser.add_argument("--index", type=Path, default=Path(__file__).resolve().parents[1] / "data" / "api-index.json")
    parser.add_argument("--plugin")
    parser.add_argument("--kind", choices=("class", "interface", "enum", "annotation", "record", "field", "method", "constructor"))
    parser.add_argument("--origin", choices=("plugin-owned", "bundled-third-party"), default="plugin-owned")
    parser.add_argument("--limit", type=int, default=50)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    if args.limit < 1 or args.limit > 5000:
        parser.error("--limit must be between 1 and 5000")
    index = json.loads(args.index.read_text(encoding="utf-8"))
    results, total = [], 0
    for record in iter_records(index):
        if matches(record, args.terms, args.plugin, args.kind, args.origin):
            total += 1
            if len(results) < args.limit:
                results.append(record)
    if args.json:
        print(json.dumps({"total": total, "returned": len(results), "results": results}, indent=2, ensure_ascii=False, allow_nan=False))
    else:
        print(f"Matches: {total}; showing: {len(results)}")
        for record in results:
            print(text_line(record))
    return 0 if total else 1


if __name__ == "__main__":
    sys.exit(main())
