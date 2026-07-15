from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from urllib.error import HTTPError


SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

from catalog_io import canonical_json  # noqa: E402
from sync_github_sources import GitHubClient, build_snapshot, validate_catalog  # noqa: E402
from sync_minecraft_versions import MANIFEST_URL, build_catalog  # noqa: E402


class FakeResponse:
    def __init__(self, document: object) -> None:
        self.payload = json.dumps(document, separators=(",", ":")).encode("utf-8")

    def __enter__(self) -> "FakeResponse":
        return self

    def __exit__(self, *_args: object) -> None:
        return None

    def read(self) -> bytes:
        return self.payload


class CatalogSyncTests(unittest.TestCase):
    def github_catalog(self) -> dict[str, object]:
        return {
            "schema_version": 1,
            "sources": [{
                "id": "paper",
                "name": "Paper",
                "repository": "PaperMC/Paper",
                "domains": ["platform", "server-api"],
                "priority": "P0",
                "ingestion_policy": "derive",
                "docs_url": "https://docs.papermc.io/",
                "rationale": "Canonical Paper implementation and API.",
            }],
        }

    def test_github_catalog_rejects_duplicate_or_unsorted_sources(self) -> None:
        catalog = self.github_catalog()
        duplicate = dict(catalog["sources"][0])  # type: ignore[index]
        duplicate["id"] = "alpha"
        catalog["sources"] = [catalog["sources"][0], duplicate]  # type: ignore[index]
        with self.assertRaisesRegex(ValueError, "duplicate"):
            validate_catalog(catalog)

    def test_github_snapshot_is_normalized_and_never_serializes_token(self) -> None:
        repository = {
            "full_name": "PaperMC/Paper",
            "html_url": "https://github.com/PaperMC/Paper",
            "description": "High performance Minecraft server",
            "default_branch": "main",
            "archived": False,
            "fork": False,
            "stargazers_count": 100,
            "forks_count": 20,
            "open_issues_count": 3,
            "pushed_at": "2026-07-15T00:00:00Z",
            "license": {"spdx_id": "GPL-3.0", "name": "GPL", "key": "gpl-3.0"},
        }
        release = {
            "tag_name": "26.2",
            "published_at": "2026-07-01T00:00:00Z",
            "prerelease": False,
            "html_url": "https://github.com/PaperMC/Paper/releases/tag/26.2",
        }
        head_commit = {
            "sha": "0123456789abcdef0123456789abcdef01234567",
            "html_url": "https://github.com/PaperMC/Paper/commit/0123456789abcdef0123456789abcdef01234567",
            "commit": {"committer": {"date": "2026-07-14T00:00:00Z"}},
        }

        def opener(request: object, timeout: int) -> FakeResponse:
            self.assertEqual(timeout, 30)
            url = request.full_url  # type: ignore[attr-defined]
            if url.endswith("/releases/latest"):
                return FakeResponse(release)
            if "/commits/" in url:
                return FakeResponse(head_commit)
            return FakeResponse(repository)

        with tempfile.TemporaryDirectory() as directory:
            catalog_path = Path(directory) / "catalog.json"
            catalog_path.write_text(canonical_json(self.github_catalog()), encoding="utf-8")
            snapshot = build_snapshot(
                catalog_path,
                GitHubClient(token="must-not-leak", opener=opener),
                retrieved_at="2026-07-15T00:00:00+00:00",
            )
        self.assertEqual(snapshot["source_count"], 1)
        record = snapshot["sources"][0]
        self.assertEqual(record["github"]["latest_release"]["tag"], "26.2")
        self.assertEqual(record["github"]["default_branch_head"]["sha"], head_commit["sha"])
        self.assertNotIn("must-not-leak", canonical_json(snapshot))

    def test_github_client_accepts_missing_latest_release(self) -> None:
        def opener(request: object, timeout: int) -> FakeResponse:
            raise HTTPError(request.full_url, 404, "missing", {}, None)  # type: ignore[attr-defined]

        client = GitHubClient(opener=opener)
        self.assertIsNone(client.get("/repos/example/no-release/releases/latest", allow_not_found=True))

    def test_mojang_manifest_indexes_all_entries_and_hydrates_requested_detail(self) -> None:
        detail_url = "https://piston-meta.mojang.com/v1/packages/example/26.2.json"
        detail = {
            "id": "26.2",
            "type": "release",
            "time": "2026-07-01T00:00:00Z",
            "releaseTime": "2026-07-01T00:00:00Z",
            "minimumLauncherVersion": 21,
            "javaVersion": {"component": "java-runtime-gamma", "majorVersion": 25},
            "assetIndex": {
                "id": "26.2",
                "sha1": "assets",
                "size": 10,
                "totalSize": 20,
                "url": "https://piston-meta.mojang.com/v1/packages/example/assets.json",
            },
            "downloads": {
                "server": {
                    "sha1": "server",
                    "size": 123,
                    "url": "https://piston-data.mojang.com/v1/objects/server/server.jar",
                }
            },
        }
        detail_sha1 = hashlib.sha1(FakeResponse(detail).payload).hexdigest()
        manifest = {
            "latest": {"release": "26.2", "snapshot": "26.3-snapshot-1"},
            "versions": [
                {
                    "id": "26.2",
                    "type": "release",
                    "url": detail_url,
                    "time": "2026-07-01T00:00:00Z",
                    "releaseTime": "2026-07-01T00:00:00Z",
                    "sha1": detail_sha1,
                    "complianceLevel": 1,
                },
                {
                    "id": "a1.0.0",
                    "type": "old_alpha",
                    "url": "https://piston-meta.mojang.com/v1/packages/example/a1.json",
                    "time": "2010-01-01T00:00:00Z",
                    "releaseTime": "2010-01-01T00:00:00Z",
                    "sha1": "d" * 40,
                    "complianceLevel": 0,
                },
            ],
        }
        calls: list[str] = []

        def opener(request: object, timeout: int) -> FakeResponse:
            url = request.full_url  # type: ignore[attr-defined]
            calls.append(url)
            return FakeResponse(manifest if url == MANIFEST_URL else detail)

        catalog = build_catalog(
            detail_ids=["26.2"],
            retrieved_at="2026-07-15T00:00:00+00:00",
            opener=opener,
        )
        self.assertEqual(catalog["version_count"], 2)
        self.assertEqual(catalog["counts_by_type"], {"old_alpha": 1, "release": 1})
        self.assertEqual(catalog["details"]["26.2"]["java_version"]["major_version"], 25)
        self.assertEqual(calls, [MANIFEST_URL, detail_url])

    def test_mojang_detail_hash_mismatch_is_rejected(self) -> None:
        detail_url = "https://piston-meta.mojang.com/v1/packages/example/26.2.json"
        manifest = {
            "latest": {"release": "26.2", "snapshot": "26.2"},
            "versions": [{
                "id": "26.2",
                "type": "release",
                "url": detail_url,
                "time": "2026-07-01T00:00:00Z",
                "releaseTime": "2026-07-01T00:00:00Z",
                "sha1": "0" * 40,
                "complianceLevel": 1,
            }],
        }
        detail = {"id": "26.2", "type": "release"}

        def opener(request: object, timeout: int) -> FakeResponse:
            return FakeResponse(manifest if request.full_url == MANIFEST_URL else detail)  # type: ignore[attr-defined]

        with self.assertRaisesRegex(ValueError, "SHA-1 mismatch"):
            build_catalog(
                detail_ids=["26.2"],
                retrieved_at="2026-07-15T00:00:00+00:00",
                opener=opener,
            )

    def test_offline_github_validation_rejects_fabricated_records(self) -> None:
        root = SCRIPTS.parent
        catalog = root / "data" / "github-source-catalog.json"
        snapshot = json.loads((root / "data" / "github-source-snapshot.json").read_text(encoding="utf-8"))
        snapshot["sources"][0] = {}
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "snapshot.json"
            output.write_text(json.dumps(snapshot), encoding="utf-8")
            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPTS / "sync_github_sources.py"),
                    "--offline",
                    "--catalog",
                    str(catalog),
                    "--output",
                    str(output),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("identities or order differ", result.stderr)


if __name__ == "__main__":
    unittest.main()
