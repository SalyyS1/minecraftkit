"""Tests for v8.3.0 mc_ops_audit_skript_code (91st) & mc_bot_plan_multiserver_mesh (92nd)."""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import multiserver_mesh_planner  # noqa: E402
import skript_auditor  # noqa: E402
from mcp_server import MinecraftKitMcpServer  # noqa: E402


BAD_SKRIPT = """
every 1 tick:
    loop all entities:
        add loop-entity to {tracked::*}
command /reward <text>:
    trigger:
        execute console command "give %arg-1% diamond 1"
        send request to "https://api.example.com/log"
"""

CLEAN_SKRIPT = """
every 20 ticks:
    loop all players:
        set {_loc} to location of loop-player
command /ping:
    trigger:
        send "&aPong!" to player
"""


class SkriptAndMeshV83Tests(unittest.TestCase):
    def test_skript_auditor_catches_all_five_rules_and_passes_clean(self) -> None:
        bad = skript_auditor.audit_skript_code(BAD_SKRIPT)
        self.assertFalse(bad["ok"])
        self.assertEqual(bad["grade"], "F")
        self.assertEqual({f["rule_id"] for f in bad["findings"]}, {"SK-001", "SK-002", "SK-003", "SK-004", "SK-005"})

        clean = skript_auditor.audit_skript_code(CLEAN_SKRIPT)
        self.assertTrue(clean["ok"])
        self.assertEqual(clean["grade"], "A")
        self.assertEqual(clean["findings"], [])

    def test_multiserver_mesh_planner_budgets_ram_and_stages(self) -> None:
        mesh = multiserver_mesh_planner.plan_multiserver_mesh(
            proxy_host="play.salyvn.net",
            backends=["lobby", "survival", "dungeons", "skyblock"],
            bots_per_backend=2,
            include_visual_xvfb=True,
            has_bedrock_geyser=True,
        )
        self.assertTrue(mesh["ok"])
        self.assertEqual(mesh["fleet"]["total_bots"], 8)
        self.assertEqual(mesh["fleet"]["tier1_protocol_bots"], 7)
        self.assertEqual(mesh["fleet"]["tier2_xvfb_visual_bots"], 1)
        self.assertTrue(mesh["fleet"]["screen_lock_free"])
        self.assertGreater(mesh["fleet"]["ram_saved_pct"], 90.0)
        self.assertEqual(len(mesh["backends"]), 4)
        self.assertEqual(mesh["backends"][3]["bridge_loopback_url"], "http://127.0.0.1:25593")

    def test_mcp_roundtrip_91_and_92(self) -> None:
        server = MinecraftKitMcpServer(root=ROOT)
        r91 = json.loads(server.handle_message(json.dumps({
            "jsonrpc": "2.0",
            "id": 91,
            "method": "tools/call",
            "params": {"name": "mc_ops_audit_skript_code", "arguments": {"skript_text": BAD_SKRIPT}},
        })) or "{}")
        self.assertFalse(r91["result"]["isError"])
        self.assertEqual(json.loads(r91["result"]["content"][0]["text"])["grade"], "F")

        r92 = json.loads(server.handle_message(json.dumps({
            "jsonrpc": "2.0",
            "id": 92,
            "method": "tools/call",
            "params": {
                "name": "mc_bot_plan_multiserver_mesh",
                "arguments": {"proxy_host": "play.salyvn.net", "backends": ["lobby", "rpg"]},
            },
        })) or "{}")
        self.assertFalse(r92["result"]["isError"])
        self.assertTrue(json.loads(r92["result"]["content"][0]["text"])["ok"])


if __name__ == "__main__":
    unittest.main()