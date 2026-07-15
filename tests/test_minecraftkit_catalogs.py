from __future__ import annotations

import copy
import json
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

from validate_minecraftkit_catalogs import (  # noqa: E402
    validate_domains,
    validate_minecraftkit,
    validate_release_capabilities,
    validate_sources,
    validate_versions,
)


class MinecraftKitCatalogTests(unittest.TestCase):
    def load(self, relative: str):
        return json.loads((ROOT / relative).read_text(encoding="utf-8"))

    def test_checked_in_catalogs_reconcile(self) -> None:
        self.assertEqual(validate_minecraftkit(ROOT), [])

    def test_version_catalog_detects_count_and_latest_drift(self) -> None:
        versions = self.load("data/minecraft-version-catalog.json")
        broken = copy.deepcopy(versions)
        broken["version_count"] += 1
        broken["latest"]["release"] = "not-a-version"
        errors = validate_versions(broken)
        self.assertIn("Minecraft version count is incomplete", errors)
        self.assertIn("Minecraft latest release is absent from versions", errors)

    def test_release_capability_must_match_hydrated_mojang_detail(self) -> None:
        versions = self.load("data/minecraft-version-catalog.json")
        capabilities = self.load("data/minecraft-release-capabilities.json")
        broken = copy.deepcopy(capabilities)
        broken["releases"][0]["client_sha1"] = "0" * 40
        self.assertTrue(any(
            "client hash mismatch" in error
            for error in validate_release_capabilities(broken, versions)
        ))

    def test_source_snapshot_requires_catalog_hash_and_immutable_commit(self) -> None:
        domains = self.load("data/minecraft-domain-catalog.json")
        domain_ids = {item["id"] for item in domains["domains"]}
        snapshot = self.load("data/github-source-snapshot.json")
        wrong_catalog = copy.deepcopy(snapshot)
        wrong_catalog["catalog_sha256"] = "0" * 64
        catalog_errors = validate_sources(
            ROOT / "data" / "github-source-catalog.json", wrong_catalog, domain_ids
        )
        self.assertTrue(any("was not built from the supplied catalog" in error for error in catalog_errors))

        mutable_head = copy.deepcopy(snapshot)
        mutable_head["sources"][0]["github"]["default_branch_head"]["sha"] = "mutable"
        head_errors = validate_sources(
            ROOT / "data" / "github-source-catalog.json", mutable_head, domain_ids
        )
        self.assertTrue(any("head SHA is invalid" in error for error in head_errors))

    def test_domain_catalog_rejects_route_drift(self) -> None:
        domains = self.load("data/minecraft-domain-catalog.json")
        broken = copy.deepcopy(domains)
        broken["domains"][0]["route"] = "mc:wrong"
        self.assertTrue(any("route is invalid" in error for error in validate_domains(ROOT, broken)))


if __name__ == "__main__":
    unittest.main()
