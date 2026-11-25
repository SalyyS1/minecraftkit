"""Tests for v8.5.0 mc_ops_audit_worldguard_regions (95th) & mc_bot_audit_economy_config (96th)."""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import economy_config_auditor  # noqa: E402
import worldguard_auditor  # noqa: E402
from mcp_server import MinecraftKitMcpServer  # noqa: E402


BAD_WG = """
regions:
  __global__:
    flags:
      build: allow
  spawn:
    priority: 0
    flags:
      use: deny
      console-command-on-entry: "op %username%"
"""

CLEAN_WG = """
regions:
  __global__:
    priority: 0
    flags:
      build: deny
  spawn:
    priority: 100
    flags:
      pvp: deny
      tnt: deny
      creeper-explosion: deny
      fire-spread: deny
      interact: allow
"""

BAD_ECO = """
starting-balance: 250000
max-money: 999999999999999
economy-log-enabled: false
tax: -5
cooldown: 0
diamond_block:
  buyPrice: 100
  sellPrice: 150
"""

CLEAN_ECO = """
starting-balance: 500
max-money: 10000000000
economy-log-enabled: true
tax: 5
cooldown: 2
diamond_block:
  buyPrice: 200
  sellPrice: 120
"""


class WorldGuardAndEconomyV85Tests(unittest.TestCase):
    def test_worldguard_auditor_all_five_rules_and_clean_pass(self) -> None:
        bad = worldguard_auditor.audit_worldguard_regions(BAD_WG, is_hub_world=True)
        self.assertFalse(bad["ok"])
        self.assertEqual(bad["grade"], "F")
        self.assertEqual({f["rule_id"] for f in bad["findings"]}, {"WG-001", "WG-002", "WG-003", "WG-004", "WG-005"})

        good = worldguard_auditor.audit_worldguard_regions(CLEAN_WG, is_hub_world=True)
        self.assertTrue(good["ok"])
        self.assertEqual(good["grade"], "A")
        self.assertEqual(good["findings"], [])

    def test_economy_auditor_all_five_rules_and_clean_pass(self) -> None:
        bad = economy_config_auditor.audit_economy_config(BAD_ECO)
        self.assertFalse(bad["ok"])
        self.assertEqual(bad["grade"], "F")
        self.assertEqual({f["rule_id"] for f in bad["findings"]}, {"ECO-001", "ECO-002", "ECO-003", "ECO-004", "ECO-005"})

        good = economy_config_auditor.audit_economy_config(CLEAN_ECO)
        self.assertTrue(good["ok"])
        self.assertEqual(good["grade"], "A")
        self.assertEqual(good["findings"], [])

    def test_mcp_roundtrip_95_and_96(self) -> None:
        server = MinecraftKitMcpServer(root=ROOT)
        r95 = json.loads(server.handle_message(json.dumps({
            "jsonrpc": "2.0",
            "id": 95,
            "method": "tools/call",
            "params": {"name": "mc_ops_audit_worldguard_regions", "arguments": {"yaml_text": BAD_WG, "is_hub_world": True}},
        })) or "{}")
        self.assertFalse(r95["result"]["isError"])
        self.assertEqual(json.loads(r95["result"]["content"][0]["text"])["grade"], "F")

        r96 = json.loads(server.handle_message(json.dumps({
            "jsonrpc": "2.0",
            "id": 96,
            "method": "tools/call",
            "params": {"name": "mc_bot_audit_economy_config", "arguments": {"config_text": BAD_ECO}},
        })) or "{}")
        self.assertFalse(r96["result"]["isError"])
        self.assertEqual(json.loads(r96["result"]["content"][0]["text"])["grade"], "F")


if __name__ == "__main__":
    unittest.main()