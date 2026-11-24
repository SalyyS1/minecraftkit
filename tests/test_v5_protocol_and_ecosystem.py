#!/usr/bin/env python3
"""Unit tests for mc_bot_probe_protocol_matrix and mc_suite_full_ecosystem_doctor (v5.0.0 — 74 MCP tools!)."""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import mcp_server  # noqa: E402


class V5ProtocolAndEcosystemTests(unittest.TestCase):
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

    def test_protocol_matrix_computes_native_viaversion_and_viabackwards_support(self) -> None:
        res = self._call(
            "mc_bot_probe_protocol_matrix",
            {
                "server_version": "1.21.4",
                "client_versions": ["1.21.1", "1.21.4", "26.3"],
                "has_viaversion": True,
                "has_viabackwards": False,
                "has_geyser": True,
            },
        )
        self.assertTrue(res["ok"])
        self.assertEqual(res["recommended_bot_protocol"], 769)
        by_mc = {row["client_mc"]: row for row in res["client_matrix"]}
        self.assertTrue(by_mc["1.21.4"]["compatible"])
        self.assertTrue(by_mc["26.3"]["compatible"])
        self.assertFalse(by_mc["1.21.1"]["compatible"])
        self.assertTrue(res["bedrock_geyser_enabled"])

    def test_full_ecosystem_doctor_verifies_companion_bridges_and_suite(self) -> None:
        res = self._call("mc_suite_full_ecosystem_doctor", {})
        self.assertTrue(res["ok"])
        self.assertTrue(res["companion_components"]["bridge_plugin_ready"])
        self.assertTrue(res["companion_components"]["fabric_client_mod_ready"])
        self.assertTrue(res["companion_components"]["docker_testgrid_ready"])
        self.assertGreaterEqual(res["suite_tool_count"], 10)


if __name__ == "__main__":
    unittest.main()
