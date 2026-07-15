"""Hash the supplied plugin JARs and every decompiled file, or verify a saved inventory."""

from __future__ import annotations

import argparse
import concurrent.futures
import hashlib
import json
import os
import sys
from collections import Counter
from pathlib import Path
from typing import Any


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def is_reparse(path: Path) -> bool:
    if path.is_symlink():
        return True
    attributes = getattr(path.lstat(), "st_file_attributes", 0)
    return bool(attributes & 0x400)


def require_contained(path: Path, root: Path) -> Path:
    if is_reparse(path):
        raise ValueError(f"Refusing reparse point or symlink: {path}")
    resolved_path = path.resolve(strict=True)
    resolved_root = root.resolve(strict=True)
    if resolved_path == resolved_root or resolved_root not in resolved_path.parents:
        raise ValueError(f"Path escapes authorized root {resolved_root}: {resolved_path}")
    return resolved_path


def safe_files(root: Path) -> list[Path]:
    if is_reparse(root):
        raise ValueError(f"Refusing reparse point or symlink root: {root}")
    result: list[Path] = []
    pending = [root]
    while pending:
        directory = pending.pop()
        for child in sorted(directory.iterdir(), key=lambda value: value.name.lower()):
            if is_reparse(child):
                raise ValueError(f"Refusing reparse point or symlink: {child}")
            if child.is_dir():
                pending.append(child)
            elif child.is_file():
                require_contained(child, root)
                result.append(child)
    return sorted(result, key=lambda value: value.as_posix().lower())


def record(path: Path, root: Path) -> dict[str, Any]:
    resolved = require_contained(path, root)
    return {
        "path": resolved.relative_to(root.resolve(strict=True)).as_posix(),
        "size": resolved.stat().st_size,
        "sha256": sha256(resolved),
    }


def records(paths: list[Path], root: Path) -> list[dict[str, Any]]:
    workers = min(8, max(2, (os.cpu_count() or 2)))
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
        return list(executor.map(lambda path: record(path, root), paths))


def build_inventory(bundle: Path) -> dict[str, Any]:
    if is_reparse(bundle):
        raise ValueError(f"Refusing reparse point or symlink bundle: {bundle}")
    bundle = bundle.resolve(strict=True)
    decompiled = bundle / "decompiled"
    if is_reparse(bundle) or is_reparse(decompiled):
        raise ValueError("Bundle and decompiled roots must not be reparse points or symlinks")
    jars = sorted(bundle.glob("*.jar"), key=lambda value: value.name.lower())
    roots = []
    for value in sorted(decompiled.iterdir(), key=lambda item: item.name.lower()):
        if is_reparse(value):
            raise ValueError(f"Refusing reparse point or symlink: {value}")
        if value.is_dir():
            roots.append(value)
    if len(jars) != 10 or len(roots) != 10:
        raise ValueError(f"Expected 10 JARs and 10 decompiled roots; found {len(jars)} and {len(roots)}")

    jar_records = records(jars, bundle)
    source_records: list[dict[str, Any]] = []
    root_counts: Counter[str] = Counter()
    extension_counts: Counter[str] = Counter()
    source_paths: list[Path] = []
    for root in roots:
        files = safe_files(root)
        source_paths.extend(files)
        for path in files:
            root_counts[root.name] += 1
            extension_counts[path.suffix.lower() or "<none>"] += 1
    source_records = records(source_paths, decompiled)

    return {
        "schema_version": 1,
        "bundle_label": bundle.name,
        "jar_count": len(jar_records),
        "decompiled_root_count": len(roots),
        "decompiled_file_count": len(source_records),
        "root_file_counts": dict(sorted(root_counts.items())),
        "extension_counts": dict(sorted(extension_counts.items())),
        "jars": jar_records,
        "decompiled_files": source_records,
    }


def validate_inventory(inventory: dict[str, Any]) -> list[str]:
    problems: list[str] = []
    if inventory.get("schema_version") != 1:
        problems.append(f"schema_version: expected 1, got {inventory.get('schema_version')!r}")
    jars = inventory.get("jars")
    files = inventory.get("decompiled_files")
    if not isinstance(jars, list) or not isinstance(files, list):
        return problems + ["jars and decompiled_files must be arrays"]
    paths = [item.get("path") for item in jars + files if isinstance(item, dict)]
    duplicates = sorted(path for path, count in Counter(paths).items() if path is not None and count > 1)
    for path in duplicates:
        problems.append(f"duplicate path: {path}")
    if inventory.get("jar_count") != len(jars):
        problems.append(f"jar_count: expected {len(jars)}, got {inventory.get('jar_count')!r}")
    if inventory.get("decompiled_file_count") != len(files):
        problems.append(f"decompiled_file_count: expected {len(files)}, got {inventory.get('decompiled_file_count')!r}")
    for item in jars + files:
        if not isinstance(item, dict) or not {"path", "size", "sha256"} <= item.keys():
            problems.append("inventory record missing path, size, or sha256")
            break
    return problems


def verify(bundle: Path, expected: dict[str, Any]) -> tuple[bool, list[str]]:
    problems = validate_inventory(expected)
    if problems:
        return False, problems
    actual = build_inventory(bundle)
    expected_files = {item["path"]: item for item in expected["jars"] + expected["decompiled_files"]}
    actual_files = {item["path"]: item for item in actual["jars"] + actual["decompiled_files"]}
    for missing in sorted(expected_files.keys() - actual_files.keys()):
        problems.append(f"missing: {missing}")
    for added in sorted(actual_files.keys() - expected_files.keys()):
        problems.append(f"added: {added}")
    for path in sorted(expected_files.keys() & actual_files.keys()):
        if expected_files[path]["size"] != actual_files[path]["size"]:
            problems.append(f"size changed: {path}")
        elif expected_files[path]["sha256"] != actual_files[path]["sha256"]:
            problems.append(f"hash changed: {path}")
    for key in ("bundle_label", "jar_count", "decompiled_root_count", "decompiled_file_count", "root_file_counts", "extension_counts"):
        if expected.get(key) != actual.get(key):
            problems.append(f"{key} changed: expected {expected.get(key)!r}, got {actual.get(key)!r}")
    return not problems, problems


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--verify", action="store_true")
    args = parser.parse_args()
    if args.verify:
        expected = json.loads(args.output.read_text(encoding="utf-8"), parse_constant=lambda value: (_ for _ in ()).throw(ValueError(f"Invalid JSON constant {value}")))
        valid, problems = verify(args.bundle, expected)
        print(f"Inventory verification: {'PASS' if valid else 'FAIL'}")
        for problem in problems[:100]:
            print(problem)
        return 0 if valid else 1

    inventory = build_inventory(args.bundle)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(inventory, indent=2, ensure_ascii=False, allow_nan=False) + "\n", encoding="utf-8", newline="\n")
    print(f"Inventoried {inventory['jar_count']} JARs and {inventory['decompiled_file_count']} decompiled files")
    return 0


if __name__ == "__main__":
    sys.exit(main())
