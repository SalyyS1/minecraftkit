"""Tests for v8.0.0 mc_audit_mythic_mmo_yaml (86th MCP tool)."""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import mythic_mmo_auditor  # noqa: E402
from mcp_server import MinecraftKitMcpServer  # noqa: E402


LAG_BOMB_YAML = """
LagBoss:
  Type: WITHER_SKELETON
  Health: 500
  Skills:
  - effect:particles{p=flame;amount=2500} @EIR{r=180} ~onTimer:1
  - damage{amount=50} @PIR{r=120} ~onAttack
BrokenSword:
  base:
    material: NETHERITE_SWORD
    attack-damage: 999999
    mana: -50
"""

CLEAN_SKILL_YAML = """
FrostKnight:
  Type: STRAY
  Health: 180
  Skills:
  - skill{s=FrostNova} @EIR{r=12} ~onTimer:40
FrostNova:
  Cooldown: 6
  Skills:
  - effect:particles{p=snowflake;amount=40} @Self
  - damage{amount=12} @PIR{r=8} ~onAttack
"""


class MythicMmoAuditorV80Tests(unittest.TestCase):
    def test_catches_all_five_rpg_rules(self) -> None:
        rep = mythic_mmo_auditor.audit_mythic_mmo_yaml(LAG_BOMB_YAML)
        self.assertFalse(rep["ok"])
        self.assertEqual(rep["grade"], "F")
        ids = {f["rule_id"] for f in rep["findings"]}
        self.assertEqual(ids, {"RPG-001", "RPG-002", "RPG-003", "RPG-004", "RPG-005"})
        self.assertEqual(rep["badge_json"]["color"], "red")

    def test_clean_mythic_yaml_passes_grade_a(self) -> None:
        rep = mythic_mmo_auditor.audit_mythic_mmo_yaml(CLEAN_SKILL_YAML)
        self.assertTrue(rep["ok"])
        self.assertEqual(rep["grade"], "A")
        self.assertEqual(rep["findings"], [])
        self.assertEqual(rep["badge_json"]["color"], "brightgreen")

    def test_mcp_tool_roundtrip_and_empty_error(self) -> None:
        server = MinecraftKitMcpServer(root=ROOT)
        raw = server.handle_message(json.dumps({
            "jsonrpc": "2.0",
            "id": 86,
            "method": "tools/call",
            "params": {"name": "mc_audit_mythic_mmo_yaml", "arguments": {"yaml_text": LAG_BOMB_YAML}},
        }))
        assert raw is not None
        resp = json.loads(raw)
        self.assertFalse(resp["result"]["isError"])
        payload = json.loads(resp["result"]["content"][0]["text"])
        self.assertEqual(payload["grade"], "F")

        err_raw = server.handle_message(json.dumps({
            "jsonrpc": "2.0",
            "id": 87,
            "method": "tools/call",
            "params": {"name": "mc_audit_mythic_mmo_yaml", "arguments": {"yaml_text": ""}},
        }))
        assert err_raw is not None
        self.assertTrue(json.loads(err_raw)["result"]["isError"])


if __name__ == "__main__":
    unittest.main()