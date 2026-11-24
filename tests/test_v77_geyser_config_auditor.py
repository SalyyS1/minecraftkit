"""Tests for v7.7.0 mc_ops_audit_geyser_config (83rd MCP Tool!)."""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from mcp_server import MinecraftKitMcpServer  # noqa: E402


class TestGeyserConfigAuditor(unittest.TestCase):
    def setUp(self) -> None:
        self.server = MinecraftKitMcpServer(root=ROOT)

    def _call(self, name: str, arguments: dict) -> tuple[dict, bool]:
        raw = self.server.handle_message(json.dumps({
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {"name": name, "arguments": arguments},
        }))
        assert raw is not None
        res = json.loads(raw)["result"]
        txt = res["content"][0]["text"]
        is_err = bool(res.get("isError", False))
        return ({"error": txt} if is_err else json.loads(txt)), is_err

    def test_clean_floodgate_geyser_config_passes_grade_a(self) -> None:
        cfg = """
bedrock:
  port: 19132
  compression-level: 6
remote:
  address: auto
  auth-type: floodgate
username-prefix: "."
debug-mode: false
"""
        payload, is_err = self._call("mc_ops_audit_geyser_config", {"config_text": cfg})
        self.assertFalse(is_err)
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["grade"], "A")
        self.assertEqual(payload["finding_count"], 0)

    def test_catches_all_five_geyser_rules(self) -> None:
        bad = """
bedrock:
  port: 19132
  compression-level: 9
remote:
  address: 203.0.113.88
  auth-type: offline
username-prefix: ""
debug-mode: true
"""
        payload, is_err = self._call("mc_ops_audit_geyser_config", {"config_text": bad})
        self.assertFalse(is_err)
        self.assertFalse(payload["ok"])
        self.assertEqual(payload["grade"], "F")
        codes = {f["rule_id"] for f in payload["findings"]}
        for expected in ("GEY-001", "GEY-002", "GEY-003", "GEY-004", "GEY-005"):
            self.assertIn(expected, codes)


if __name__ == "__main__":
    unittest.main()
