from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "render_ecosystem_web.py"


def write_json(path: Path, payload: object) -> bytes:
    encoded = (json.dumps(payload, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    path.write_bytes(encoded)
    return encoded


def domain_catalog() -> dict:
    ids = ["build", "client", "core", "dialog", "model", "nms", "pack", "protocol", "rpg", "shader"]
    return {
        "schema_version": 1,
        "domains": [
            {
                "id": domain_id,
                "name": f"{domain_id.title()} systems",
                "route": f"mc:{domain_id}",
                "skill_directory": f"mc-{domain_id}",
                "reference": f"references/{domain_id}.md",
                "keywords": [domain_id, f"{domain_id} api"],
            }
            for domain_id in ids
        ],
        "evidence_classes": ["verified-upstream"],
        "ingestion_policies": ["index", "metadata-only"],
    }


def source_catalog() -> dict:
    return {
        "schema_version": 1,
        "sources": [
            {
                "id": "alpha-platform",
                "name": "Alpha Platform",
                "repository": "Example/Alpha",
                "domains": ["core", "rpg"],
                "priority": "P0",
                "ingestion_policy": "index",
                "docs_url": "https://docs.example.test/alpha",
                "rationale": "Primary platform contract.",
            },
            {
                "id": "beta-protocol",
                "name": "Beta Protocol",
                "repository": "Example/Beta",
                "domains": ["protocol"],
                "priority": "P2",
                "ingestion_policy": "metadata-only",
                "docs_url": "https://docs.example.test/beta",
                "rationale": "Historical protocol evidence.",
            },
        ],
    }


def source_snapshot(catalog: dict, catalog_bytes: bytes) -> dict:
    records = []
    for index, source in enumerate(catalog["sources"]):
        repository = source["repository"]
        release = None if index else {
            "tag": "v1.2.3",
            "published_at": "2026-07-01T00:00:00Z",
            "prerelease": False,
            "url": f"https://github.com/{repository}/releases/tag/v1.2.3",
        }
        records.append({
            **source,
            "github": {
                "canonical_repository": repository,
                "url": f"https://github.com/{repository}",
                "description": f"{source['name']} description",
                "default_branch": "main",
                "archived": bool(index),
                "fork": False,
                "stars": 100 - index,
                "forks": 20 - index,
                "open_issues": index,
                "pushed_at": "2026-07-10T00:00:00Z",
                "default_branch_head": {
                    "sha": str(index + 1) * 40,
                    "committed_at": "2026-07-09T00:00:00Z",
                    "url": f"https://github.com/{repository}/commit/{str(index + 1) * 40}",
                },
                "license": None if index else {"spdx_id": "MIT", "name": "MIT", "key": "mit"},
                "latest_release": release,
            },
        })
    return {
        "schema_version": 1,
        "retrieved_at": "2026-07-15T05:30:00Z",
        "catalog_sha256": hashlib.sha256(catalog_bytes).hexdigest(),
        "source_count": len(records),
        "sources": records,
    }


def version_catalog() -> dict:
    versions = [
        {
            "id": "26.3-snapshot-3", "type": "snapshot", "url": "https://meta.example.test/snapshot",
            "sha1": "a" * 40, "time": "2026-07-07T00:00:00Z", "release_time": "2026-07-07T00:00:00Z",
            "compliance_level": 1,
        },
        {
            "id": "26.2", "type": "release", "url": "https://meta.example.test/release",
            "sha1": "b" * 40, "time": "2026-06-16T00:00:00Z", "release_time": "2026-06-16T00:00:00Z",
            "compliance_level": 1,
        },
        {
            "id": "b1.0", "type": "old_beta", "url": "https://meta.example.test/beta",
            "sha1": "c" * 40, "time": "2010-12-20T00:00:00Z", "release_time": "2010-12-20T00:00:00Z",
            "compliance_level": 0,
        },
        {
            "id": "rd-test", "type": "old_alpha", "url": "https://meta.example.test/alpha",
            "sha1": "d" * 40, "time": "2009-05-13T00:00:00Z", "release_time": "2009-05-13T00:00:00Z",
            "compliance_level": 0,
        },
    ]

    def detail(version_id: str, version_type: str) -> dict:
        return {
            "id": version_id,
            "type": version_type,
            "time": "2026-07-07T00:00:00Z",
            "release_time": "2026-07-07T00:00:00Z",
            "minimum_launcher_version": 21,
            "java_version": {"component": "java-runtime-epsilon", "major_version": 25},
            "asset_index": {"id": "33", "sha1": "e" * 40, "size": 2, "total_size": 3, "url": "https://meta.example.test/assets"},
            "downloads": {
                "client": {"sha1": "f" * 40, "size": 1024, "url": "https://meta.example.test/client"},
                "server": {"sha1": "0" * 40, "size": 2048, "url": "https://meta.example.test/server"},
            },
        }

    return {
        "schema_version": 1,
        "retrieved_at": "2026-07-15T05:15:00Z",
        "source": {"url": "https://piston-meta.mojang.com/mc/game/version_manifest_v2.json", "sha256": "1" * 64},
        "latest": {"release": "26.2", "snapshot": "26.3-snapshot-3"},
        "version_count": len(versions),
        "counts_by_type": {"snapshot": 1, "release": 1, "old_beta": 1, "old_alpha": 1},
        "details": {
            "26.2": detail("26.2", "release"),
            "26.3-snapshot-3": detail("26.3-snapshot-3", "snapshot"),
        },
        "versions": versions,
    }


def release_capabilities() -> dict:
    return {
        "schema_version": 1,
        "observed_at": "2026-07-15T05:22:11Z",
        "releases": [{
            "id": "26.2",
            "evidence_class": "verified-upstream-artifact-inventory",
            "client_sha1": "f" * 40,
            "protocol": 776,
            "java_major": 25,
            "resource_pack": {"major": 88, "minor": 0},
            "data_pack": {"major": 107, "minor": 1},
            "vanilla_inventory": {
                "core_shader_files": 61,
                "include_shader_files": 9,
                "post_shader_files": 10,
                "item_geometry_entries": 1271,
                "item_definition_entries": 1537,
                "built_in_dialog_ids": ["custom_options", "quick_actions", "server_links"],
                "built_in_font_json_files": 7,
                "observed_font_provider_kinds": ["bitmap", "reference", "space"],
            },
            "provenance": {
                "version_metadata_url": "https://meta.example.test/release",
                "method": "Read-only artifact inventory.",
                "restrictions": "Counts and summaries only.",
            },
        }],
    }


class EcosystemWebRenderTests(unittest.TestCase):
    def prepare(self, root: Path) -> tuple[list[str], Path]:
        domains_path = root / "domains.json"
        sources_path = root / "sources.json"
        snapshot_path = root / "snapshot.json"
        versions_path = root / "versions.json"
        capabilities_path = root / "capabilities.json"
        output_path = root / "web" / "data" / "ecosystem.js"
        write_json(domains_path, domain_catalog())
        catalog = source_catalog()
        catalog_bytes = write_json(sources_path, catalog)
        write_json(snapshot_path, source_snapshot(catalog, catalog_bytes))
        write_json(versions_path, version_catalog())
        write_json(capabilities_path, release_capabilities())
        return [
            sys.executable, str(SCRIPT),
            "--domains", str(domains_path),
            "--sources", str(sources_path),
            "--snapshot", str(snapshot_path),
            "--versions", str(versions_path),
            "--capabilities", str(capabilities_path),
            "--output", str(output_path),
        ], output_path

    def test_renders_deterministic_atomic_javascript_payload(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            command, output = self.prepare(root)
            first = subprocess.run(command, text=True, capture_output=True, check=False)
            self.assertEqual(first.returncode, 0, first.stderr)
            first_bytes = output.read_bytes()
            second = subprocess.run(command, text=True, capture_output=True, check=False)
            self.assertEqual(second.returncode, 0, second.stderr)
            self.assertEqual(output.read_bytes(), first_bytes)
            prefix = b"window.MinecraftKitEcosystem="
            self.assertTrue(first_bytes.startswith(prefix))
            payload = json.loads(first_bytes[len(prefix):-2])
            self.assertEqual(payload["summary"]["sourceCount"], 2)
            self.assertEqual(len(payload["domains"]), 10)
            self.assertEqual(payload["versions"]["versionCount"], 4)
            self.assertEqual(payload["releaseCapabilities"]["releases"][0]["protocol"], 776)
            self.assertEqual(payload["sources"][0]["github"]["default_branch_head"]["sha"], "1" * 40)
            self.assertFalse(list(output.parent.glob(".ecosystem.js.*.tmp")))

    def test_validation_failure_preserves_previous_output(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            command, output = self.prepare(root)
            output.parent.mkdir(parents=True)
            output.write_bytes(b"previous\n")
            snapshot = json.loads((root / "snapshot.json").read_text(encoding="utf-8"))
            snapshot["catalog_sha256"] = "0" * 64
            write_json(root / "snapshot.json", snapshot)
            result = subprocess.run(command, text=True, capture_output=True, check=False)
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(output.read_bytes(), b"previous\n")

    def test_rejects_capability_profile_for_a_different_client_hash(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            command, output = self.prepare(root)
            capability = json.loads((root / "capabilities.json").read_text(encoding="utf-8"))
            capability["releases"][0]["client_sha1"] = "9" * 40
            write_json(root / "capabilities.json", capability)
            result = subprocess.run(command, text=True, capture_output=True, check=False)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("client SHA-1 mismatch", result.stderr)
            self.assertFalse(output.exists())

    def test_static_runtime_is_offline_and_uses_safe_dom_rendering(self) -> None:
        html = (ROOT / "web/ecosystem.html").read_text(encoding="utf-8")
        css = (ROOT / "web/ecosystem.css").read_text(encoding="utf-8")
        runtime = "\n".join(
            (ROOT / f"web/{name}").read_text(encoding="utf-8")
            for name in ("ecosystem-app.js", "ecosystem-renderers.js")
        )
        index = (ROOT / "web/index.html").read_text(encoding="utf-8")
        self.assertIn('href="ecosystem.html"', index)
        self.assertIn('href="index.html"', html)
        self.assertIn('src="data/ecosystem.js"', html)
        self.assertIn('src="ecosystem-renderers.js"', html)
        self.assertIn('All ten domains', html)
        self.assertIn('id="metric-domain-count">10</dd>', html)
        self.assertIn('aria-live="polite"', html)
        self.assertIn('prefers-reduced-motion: reduce', css)
        self.assertIn("44px", css)
        self.assertNotRegex(html + css + runtime, r"https?://|\bfetch\s*\(")
        self.assertNotRegex(runtime, r"innerHTML|outerHTML|insertAdjacentHTML|document\.write|\beval\s*\(")
        self.assertIn("textContent", runtime)
        self.assertIn("URLSearchParams", runtime)


if __name__ == "__main__":
    unittest.main()
