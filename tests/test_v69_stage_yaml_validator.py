"""Tests for v6.9.0 mc_bot_validate_stage_yaml pre-flight security & anti-OOM validator."""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import bot_engine  # noqa: E402
from mcp_server import MinecraftKitMcpServer  # noqa: E402


class TestStageYamlValidator(unittest.TestCase):
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

    def test_clean_stage_yaml_passes_grade_a(self) -> None:
        clean_yaml = """
tier: tier1-protocol
bots: 10
password: env:MCKIT_BOT_PASSWORD
stages:
  - name: Join Survival
    action: join
  - name: Auto Auth
    action: auth
  - name: Open Shop
    action: command
    command: /shop
  - name: Verify Shop GUI
    action: assert_gui
    pattern: shop|store|market
  - name: Click Slot 13
    action: click_slot
    slot: 13
  - name: Capture Proof
    action: capture
"""
        payload, is_err = self._call("mc_bot_validate_stage_yaml", {"yaml_text": clean_yaml, "host_ram_gb": 8})
        self.assertFalse(is_err)
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["grade"], "A")
        self.assertEqual(payload["parsed_stage_count"], 6)
        self.assertEqual(payload["estimated_ram_mb"], 420)

    def test_catches_plaintext_secret_unknown_action_bad_regex_and_oom(self) -> None:
        bad_yaml = """
tier: desktop-full-client
bots: 10
password: MySuperSecretPassword99
stages:
  - name: Bad Action
    action: teleport_exploit
  - name: Hardcoded Login
    action: command
    command: /login SuperSecret42
  - name: Broken Regex
    action: assert_chat
    pattern: "[unclosed("
  - name: Missing Slot
    action: click_slot
"""
        payload, is_err = self._call("mc_bot_validate_stage_yaml", {"yaml_text": bad_yaml, "host_ram_gb": 8})
        self.assertFalse(is_err)
        self.assertFalse(payload["ok"])
        self.assertEqual(payload["grade"], "F")
        rule_ids = {f["rule_id"] for f in payload["findings"]}
        for expected in ("STAGE-SEC-001", "STAGE-ACT-001", "STAGE-REGEX-001", "STAGE-REQ-001", "STAGE-OOM-001"):
            self.assertIn(expected, rule_ids)
        # Ensure plaintext secrets are NEVER leaked in output
        dumped = json.dumps(payload)
        self.assertNotIn("MySuperSecretPassword99", dumped)
        self.assertNotIn("SuperSecret42", dumped)

    def test_accepts_json_stage_recipe(self) -> None:
        recipe = json.dumps({
            "tier": "tier1-protocol",
            "bots": 2,
            "stages": [
                {"name": "Join", "action": "join"},
                {"name": "Check boss", "action": "assert_entity_nearby", "pattern": "dragon|boss"},
            ],
        })
        res = bot_engine.validate_stage_yaml(recipe, host_ram_gb=8.0)
        self.assertTrue(res["ok"])
        self.assertEqual(res["grade"], "A")
        self.assertEqual(res["parsed_stage_count"], 2)


if __name__ == "__main__":
    unittest.main()
