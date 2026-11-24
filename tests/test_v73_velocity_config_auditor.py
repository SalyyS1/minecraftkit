"""Tests for v7.3.0 mc_ops_audit_velocity_config (80th MCP Tool Milestone!)."""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from mcp_server import MinecraftKitMcpServer  # noqa: E402


class TestVelocityConfigAuditor(unittest.TestCase):
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
        return json.loads(res["content"][0]["text"]), bool(res.get("isError", False))

    def test_hardened_velocity_toml_passes_grade_a(self) -> None:
        toml = """
online-mode = true
player-info-forwarding-mode = "modern"
forwarding-secret-file = "forwarding.secret"
kick-existing-players = false
failover-on-unexpected-server-disconnect = true
compression-threshold = 256

[servers]
lobby = "127.0.0.1:25566"
survival = "10.0.0.12:25567"
try = ["lobby"]
"""
        payload, is_err = self._call("mc_ops_audit_velocity_config", {"config_text": toml})
        self.assertFalse(is_err)
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["grade"], "A")
        self.assertEqual(payload["finding_count"], 0)

    def test_catches_all_five_velocity_rules_without_leaking_secret(self) -> None:
        bad_toml = """
online-mode = false
player-info-forwarding-mode = "legacy"
forwarding-secret = "changeme"
kick-existing-players = true
failover-on-unexpected-server-disconnect = false
compression-threshold = 32

[servers]
survival = "203.0.113.55:25567"
"""
        payload, is_err = self._call("mc_ops_audit_velocity_config", {"config_text": bad_toml})
        self.assertFalse(is_err)
        self.assertFalse(payload["ok"])
        self.assertEqual(payload["grade"], "F")
        codes = {f["rule_id"] for f in payload["findings"]}
        for expected in ("VEL-001", "VEL-002", "VEL-003", "VEL-004", "VEL-005"):
            self.assertIn(expected, codes)
        self.assertNotIn("changeme", json.dumps(payload))


if __name__ == "__main__":
    unittest.main()
