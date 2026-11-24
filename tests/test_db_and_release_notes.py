#!/usr/bin/env python3
"""Unit tests for mc_audit_database_pool and mc_qa_generate_release_notes (v4.8.0 — 70 MCP tools milestone!)."""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import mcp_server  # noqa: E402


class DbPoolAndReleaseNotesTests(unittest.TestCase):
    def setUp(self) -> None:
        self.server = mcp_server.MinecraftKitMcpServer(ROOT)

    def _call(self, name: str, arguments: dict) -> dict:
        req = json.dumps({
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {"name": name, "arguments": arguments},
        })
        raw = self.server.handle_message(req)
        assert raw is not None
        resp = json.loads(raw)
        res = resp["result"]
        self.assertFalse(res["isError"], res)
        return json.loads(res["content"][0]["text"])

    def test_database_pool_auditor_catches_weak_pass_pool_exhaustion_ssl_and_sqlite_network(self) -> None:
        secret = "123456"
        bad = self._call(
            "mc_audit_database_pool",
            {
                "network_server_count": 6,
                "config_text": (
                    "storage-method: sqlite\n"
                    "host: db.prod.example\n"
                    "username: root\n"
                    f"password: {secret}\n"
                    "maximum-pool-size: 30\n"
                    "connection-timeout: 30000\n"
                    "maximum-lifetime: 1800000\n"
                    "useSSL=false\n"
                ),
            },
        )
        self.assertFalse(bad["ok"])
        codes = {f["code"] for f in bad["findings"]}
        self.assertIn("DB-001", codes)
        self.assertIn("DB-002", codes)
        self.assertIn("DB-003", codes)
        self.assertIn("DB-004", codes)
        self.assertIn("DB-005", codes)
        self.assertNotIn(f'"{secret}"', json.dumps(bad))

        good = self._call(
            "mc_audit_database_pool",
            {
                "network_server_count": 4,
                "config_text": (
                    "storage-method: mariadb\n"
                    "host: 127.0.0.1\n"
                    "username: mc_rpg\n"
                    "password: UltraLongRandomSqlPassword_2026_Secure!\n"
                    "maximum-pool-size: 8\n"
                    "connection-timeout: 5000\n"
                    "maximum-lifetime: 1500000\n"
                ),
            },
        )
        self.assertTrue(good["ok"])
        self.assertEqual(good["grade"], "A")

    def test_release_notes_generator_emits_bilingual_markdown_and_discord_copy(self) -> None:
        res = self._call(
            "mc_qa_generate_release_notes",
            {
                "plugin_name": "OZbanghoi",
                "version": "2.4.0",
                "mc_versions": ["1.21.4", "26.3"],
                "platforms": ["Paper", "Folia"],
                "highlights": ["Full Folia RegionScheduler migration", "Zero GUI dupes verified"],
                "qa_passed_stages": 6,
                "qa_total_stages": 6,
                "folia_ready": True,
                "exploit_audit_grade": "A",
            },
        )
        self.assertTrue(res["ok"])
        self.assertIn("OZbanghoi v2.4.0", res["markdown"])
        self.assertIn("Tiếng Việt", res["markdown"])
        self.assertIn("6/6", res["qa_proof_line"])
        self.assertIn("OZbanghoi v2.4.0", res["discord_announcement"])


if __name__ == "__main__":
    unittest.main()
