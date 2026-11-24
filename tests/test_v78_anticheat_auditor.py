"""Tests for v7.8.0 mc_bot_audit_anti_cheat_compat (84th MCP Tool!)."""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from mcp_server import MinecraftKitMcpServer  # noqa: E402


class TestAntiCheatAuditor(unittest.TestCase):
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

    def test_clean_grim_stack_passes_grade_a(self) -> None:
        payload, is_err = self._call(
            "mc_bot_audit_anti_cheat_compat",
            {
                "plugins": ["GrimAC", "PacketEvents", "LuckPerms", "Geyser-Spigot", "Floodgate"],
                "floodgate_exempt_configured": True,
                "bot_bypass_configured": True,
            },
        )
        self.assertFalse(is_err)
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["grade"], "A")
        self.assertIn("grim.exempt", payload["recommended_qa_bot_permissions"])

    def test_catches_stacked_ac_missing_packetevents_rpg_bedrock_and_bot(self) -> None:
        payload, is_err = self._call(
            "mc_bot_audit_anti_cheat_compat",
            {
                "plugins": ["GrimAC", "Vulcan", "MythicMobs", "MMOCore", "Geyser-Spigot"],
                "floodgate_exempt_configured": False,
                "bot_bypass_configured": False,
            },
        )
        self.assertFalse(is_err)
        self.assertFalse(payload["ok"])
        self.assertEqual(payload["grade"], "F")
        codes = {f["rule_id"] for f in payload["findings"]}
        for expected in ("AC-001", "AC-002", "AC-003", "AC-004", "AC-005"):
            self.assertIn(expected, codes)


if __name__ == "__main__":
    unittest.main()
