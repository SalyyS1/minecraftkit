from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

from catalog_io import canonical_json  # noqa: E402
from query_sources import load_records, query_records  # noqa: E402


class QuerySourcesTests(unittest.TestCase):
    def source(self, source_id: str, repository: str, domains: list[str]) -> dict[str, object]:
        return {
            "id": source_id,
            "name": source_id.title(),
            "repository": repository,
            "domains": domains,
            "priority": "P0",
            "ingestion_policy": "index",
            "docs_url": f"https://github.com/{repository}",
            "rationale": f"Canonical {source_id} API.",
        }

    def test_load_snapshot_and_filter_all_terms(self) -> None:
        sources = [
            self.source("paper", "PaperMC/Paper", ["core", "dialog"]),
            self.source("protocol-lib", "dmulloy2/ProtocolLib", ["protocol"]),
        ]
        snapshot_sources = [
            {
                **source,
                "github": {
                    "description": "Packet events" if source["id"] == "protocol-lib" else "Server API",
                    "archived": False,
                    "default_branch_head": {"sha": "0" * 40},
                    "latest_release": None,
                },
            }
            for source in sources
        ]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            catalog = root / "catalog.json"
            snapshot = root / "snapshot.json"
            catalog.write_text(canonical_json({"schema_version": 1, "sources": sources}), encoding="utf-8")
            snapshot.write_text(canonical_json({"schema_version": 1, "sources": snapshot_sources}), encoding="utf-8")
            records = load_records(catalog, snapshot)
        matches = query_records(
            records,
            terms=["packet", "protocol"],
            domain="protocol",
            priority="P0",
            policy="index",
            include_archived=False,
            limit=10,
        )
        self.assertEqual([record["id"] for record in matches], ["protocol-lib"])

    def test_archived_sources_are_hidden_by_default(self) -> None:
        record = {
            **self.source("legacy", "Example/Legacy", ["core"]),
            "github": {"description": "Legacy", "archived": True},
        }
        hidden = query_records(
            [record], terms=[], domain=None, priority=None, policy=None,
            include_archived=False, limit=10,
        )
        visible = query_records(
            [record], terms=[], domain=None, priority=None, policy=None,
            include_archived=True, limit=10,
        )
        self.assertEqual(hidden, [])
        self.assertEqual(visible, [record])


if __name__ == "__main__":
    unittest.main()
