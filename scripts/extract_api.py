"""Extract complete public/protected plugin APIs directly from supplied JAR bytecode."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import struct
import sys
import zipfile
from pathlib import Path
from typing import Any

from java_classfile import ClassFormatError, descriptor_type, method_descriptor, modifiers, parse_class, visibility


PLUGINS = (
    ("CoreTools", "CoreTools-1.4.2.jar", "CoreTools-1.4.2", ("ranet.coretools",), ("ranet.coretools.libs.",)),
    ("MMOCore", "MMOCore-1.13.1-20260531.191529-59.jar", "MMOCore-1.13.1-20260531.191529-59", ("net.Indyuce.mmocore",), ("net.Indyuce.mmocore.paperlib.",)),
    ("MMOInventory", "MMOInventory-2.0-20260330.113858-32.jar", "MMOInventory-2.0-20260330.113858-32", ("net.Indyuce.inventory",), ()),
    ("MMOItems", "MMOItems-6.10.1-20260531.191614-59.jar", "MMOItems-6.10.1-20260531.191614-59", ("net.Indyuce.mmoitems",), ()),
    ("MMOProfiles", "MMOProfiles-1.2-20260605.155157-29.jar", "MMOProfiles-1.2-20260605.155157-29", ("fr.phoenixdevt.mmoprofiles",), ("fr.phoenixdevt.mmoprofiles.shared.gson.",)),
    ("ModelEngine", "ModelEngine.jar", "ModelEngine", ("com.ticxo.modelengine",), ()),
    ("MythicCrucible", "MythicCrucible.jar", "MythicCrucible", ("io.lumine.mythiccrucible",), ("io.lumine.mythiccrucible.metrics.",)),
    ("MythicDungeons", "MythicDungeon.jar", "MythicDungeon", ("net.playavalon.mythicdungeons",), ("net.playavalon.mythicdungeons.avngui.", "net.playavalon.mythicdungeons.bstats.", "net.playavalon.mythicdungeons.objenesis.")),
    ("MythicEnchants", "MythicEnchant.jar", "MythicEnchant", ("com.stelliusstudio.mythicenchants",), ()),
    ("MythicRPG", "Mythicrpg.jar", "Mythicrpg", ("io.lumine.mythicrpg",), ("io.lumine.mythicrpg.metrics.",)),
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def release_for_entry(entry: str) -> int:
    parts = entry.split("/")
    return int(parts[2]) if len(parts) > 3 and parts[:2] == ["META-INF", "versions"] else 0


def class_kind(parsed: dict[str, Any]) -> str:
    access = parsed["access"]
    if parsed["record"]:
        return "record"
    if access & 0x2000:
        return "annotation"
    if access & 0x4000:
        return "enum"
    if access & 0x0200:
        return "interface"
    return "class"


def in_namespace(name: str, prefixes: tuple[str, ...]) -> bool:
    return any(name == prefix or name.startswith(prefix + ".") for prefix in prefixes)


def normalized_constant(value: Any, descriptor: str) -> Any:
    """Convert JVM ConstantValue data to strict-JSON-safe Java semantics."""
    if value is None:
        return None
    if descriptor == "Z":
        return bool(value)
    if descriptor in {"F", "D"} and isinstance(value, float) and not math.isfinite(value):
        if math.isnan(value):
            return "NaN"
        return "Infinity" if value > 0 else "-Infinity"
    return value


def make_member(plugin: str, owner: str, release: int, raw: dict[str, Any], kind: str) -> dict[str, Any]:
    if kind == "field":
        field_type, _ = descriptor_type(raw["descriptor"])
        parameters, return_type = [], field_type
        display_name = raw["name"]
    else:
        parameters, return_type = method_descriptor(raw["descriptor"])
        kind = "constructor" if raw["name"] == "<init>" else "method"
        display_name = owner.rsplit(".", 1)[-1].split("$")[-1] if kind == "constructor" else raw["name"]
    suffix = f"@java{release}" if release else ""
    return {
        "id": f"{plugin}:{owner}{suffix}#{raw['name']}{raw['descriptor']}",
        "kind": kind,
        "name": display_name,
        "jvm_name": raw["name"],
        "visibility": visibility(raw["access"]),
        "modifiers": modifiers(raw["access"], member_kind=kind),
        "descriptor": raw["descriptor"],
        "generic_signature": raw["signature"],
        "parameters": parameters,
        "return_type": return_type,
        "throws": raw["exceptions"],
        "constant": normalized_constant(raw["constant"], raw["descriptor"]),
        "deprecated": raw["deprecated"],
        "synthetic": bool(raw["access"] & 0x1000),
        "bridge": bool(raw["access"] & 0x0040) if kind == "method" else False,
    }


def extract_plugin(jars: Path, sources: Path, definition: tuple[Any, ...]) -> tuple[dict[str, Any], dict[str, Any]]:
    plugin, jar_name, source_name, prefixes, bundled_prefixes = definition
    jar_path, source_root = jars / jar_name, sources / source_name
    if not jar_path.is_file() or not source_root.is_dir():
        raise FileNotFoundError(f"Missing input for {plugin}: {jar_path} or {source_root}")
    classes, errors = [], []
    owned_entries = public_types = member_count = non_public = 0
    plugin_types = plugin_members = bundled_types = bundled_members = 0
    with zipfile.ZipFile(jar_path) as archive:
        entries = sorted(name for name in archive.namelist() if name.endswith(".class"))
        for entry in entries:
            logical = entry.split("META-INF/versions/", 1)[-1]
            if logical and logical[0].isdigit() and "/" in logical:
                logical = logical.split("/", 1)[1]
            candidate = logical[:-6].replace("/", ".")
            if candidate in {"module-info", "package-info"} or not in_namespace(candidate, prefixes):
                continue
            owned_entries += 1
            try:
                parsed = parse_class(archive.read(entry))
                if parsed["name"] != candidate:
                    raise ClassFormatError(f"ZIP entry {candidate} declares {parsed['name']}")
                if visibility(parsed["access"]) not in {"public", "protected"}:
                    non_public += 1
                    continue
                release = release_for_entry(entry)
                members = []
                for raw in parsed["fields"]:
                    if visibility(raw["access"]) in {"public", "protected"}:
                        members.append(make_member(plugin, parsed["name"], release, raw, "field"))
                for raw in parsed["methods"]:
                    if raw["name"] != "<clinit>" and visibility(raw["access"]) in {"public", "protected"}:
                        members.append(make_member(plugin, parsed["name"], release, raw, "method"))
                members.sort(key=lambda value: value["id"])
                source_rel = parsed["name"].split("$", 1)[0].replace(".", "/") + ".java"
                public_types += 1
                member_count += len(members)
                origin = "bundled-third-party" if parsed["name"].startswith(bundled_prefixes) else "plugin-owned"
                if origin == "plugin-owned":
                    plugin_types += 1
                    plugin_members += len(members)
                else:
                    bundled_types += 1
                    bundled_members += len(members)
                suffix = f"@java{release}" if release else ""
                classes.append({
                    "id": f"{plugin}:{parsed['name']}{suffix}",
                    "plugin": plugin,
                    "origin": origin,
                    "name": parsed["name"],
                    "package": parsed["name"].rsplit(".", 1)[0] if "." in parsed["name"] else "",
                    "simple_name": parsed["name"].rsplit(".", 1)[-1],
                    "kind": class_kind(parsed),
                    "visibility": visibility(parsed["access"]),
                    "modifiers": modifiers(parsed["access"]),
                    "major_version": parsed["major"],
                    "java_release": release,
                    "super": parsed["super"],
                    "interfaces": parsed["interfaces"],
                    "generic_signature": parsed["signature"],
                    "deprecated": parsed["deprecated"],
                    "jar_entry": entry,
                    "source_path": source_rel if (source_root / Path(source_rel)).is_file() else None,
                    "members": members,
                })
            except (ClassFormatError, KeyError, ValueError, struct.error) as error:  # type: ignore[name-defined]
                errors.append({"entry": entry, "error": str(error)})
    classes.sort(key=lambda value: value["id"])
    payload = {
        "name": plugin,
        "jar": jar_name,
        "jar_sha256": sha256(jar_path),
        "source_root": source_name,
        "namespace_prefixes": list(prefixes),
        "bundled_namespace_prefixes": list(bundled_prefixes),
        "classes": classes,
    }
    coverage = {
        "plugin": plugin,
        "owned_class_entries": owned_entries,
        "published_types": public_types,
        "published_members": member_count,
        "plugin_owned_types": plugin_types,
        "plugin_owned_members": plugin_members,
        "bundled_third_party_types": bundled_types,
        "bundled_third_party_members": bundled_members,
        "excluded_non_public_types": non_public,
        "parse_errors": errors,
    }
    return payload, coverage


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False) + "\n", encoding="utf-8", newline="\n")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--jars", type=Path, required=True)
    parser.add_argument("--sources", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--plugin", action="append", help="Limit extraction to one or more plugin names")
    args = parser.parse_args()
    selected = {value.lower() for value in args.plugin or []}
    definitions = [value for value in PLUGINS if not selected or value[0].lower() in selected]
    if not definitions:
        parser.error("No plugin matched --plugin")
    plugins, coverage = [], []
    for definition in definitions:
        payload, report = extract_plugin(args.jars, args.sources, definition)
        plugins.append(payload)
        coverage.append(report)
        print(f"{payload['name']}: {report['published_types']} types, {report['published_members']} members, {len(report['parse_errors'])} errors")
    index = {"schema_version": 1, "generated_from": "JVM class metadata", "plugins": plugins}
    coverage_doc = {"schema_version": 1, "plugins": coverage, "unexplained_errors": sum(len(value["parse_errors"]) for value in coverage)}
    write_json(args.output / "api-index.json", index)
    write_json(args.output / "api-coverage.json", coverage_doc)
    return 1 if coverage_doc["unexplained_errors"] else 0


if __name__ == "__main__":
    sys.exit(main())
