"""Tests for v8.6.0 — THE 100 MCP TOOLS CENTURY MILESTONE (#97, #98, #99, #100 + PNG scorecard)."""

from __future__ import annotations

import base64
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import bot_soak_planner  # noqa: E402
import plugin_yml_auditor  # noqa: E402
import qa_executive_scorecard  # noqa: E402
import spigot_bukkit_auditor  # noqa: E402
from mcp_server import MinecraftKitMcpServer  # noqa: E402


class Century100ToolsV86Tests(unittest.TestCase):
    def test_spigot_bukkit_and_plugin_yml_auditors(self) -> None:
        bad_spg = """
spawn-limits:
  monsters: 90
entity-activation-range:
  monsters: 40
merge-radius:
  item: 1.5
mob-spawn-range: 8
settings:
  bungeecord: true
"""
        r_spg = spigot_bukkit_auditor.audit_bukkit_spigot_yml(bad_spg)
        self.assertFalse(r_spg["ok"])
        self.assertEqual({f["rule_id"] for f in r_spg["findings"]}, {"SPG-001", "SPG-002", "SPG-003", "SPG-004", "SPG-005"})

        bad_plg = """
name: BrokenPlugin
version: 1.0
commands:
  myadmin:
    description: Admin cmd
permissions:
  myplugin.admin:
    default: true
"""
        r_plg = plugin_yml_auditor.audit_plugin_yml(bad_plg, target_folia=True)
        self.assertFalse(r_plg["ok"])
        self.assertEqual({f["rule_id"] for f in r_plg["findings"]}, {"PLG-001", "PLG-002", "PLG-003", "PLG-004", "PLG-005"})

        good_plg = """
name: CleanFoliaPlugin
version: 1.2.0
main: com.salyvn.clean.CleanPlugin
api-version: '1.21'
folia-supported: true
commands:
  cleaninfo:
    permission: clean.info
permissions:
  clean.admin:
    default: op
"""
        r_good = plugin_yml_auditor.audit_plugin_yml(good_plg, target_folia=True)
        self.assertTrue(r_good["ok"])
        self.assertEqual(r_good["grade"], "A")

    def test_soak_planner_and_executive_scorecard(self) -> None:
        soak = bot_soak_planner.plan_bot_soak_test(duration_hours=12, concurrent_bots=8, sample_interval_sec=60)
        self.assertTrue(soak["ok"])
        self.assertEqual(soak["schedule"]["expected_telemetry_samples"], 720)
        self.assertGreater(soak["memory_efficiency"]["ram_saved_pct"], 95.0)

        sc_go = qa_executive_scorecard.generate_executive_scorecard(
            release_name="SalyRPG v4.0",
            checks=[
                {"name": "Bot QA Stages", "grade": "A", "detail": "8/8 stages PASS"},
                {"name": "Paper/Folia Config", "grade": "A", "detail": "LZ4 + optimal"},
                {"name": "Anti-Cheat Compat", "grade": "B", "detail": "GrimAC tuned"},
            ],
        )
        self.assertEqual(sc_go["decision"], "GO")
        self.assertEqual(sc_go["overall_grade"], "A")

        sc_nogo = qa_executive_scorecard.generate_executive_scorecard(
            release_name="BrokenRelease",
            checks=[
                {"name": "WorldGuard", "grade": "F", "detail": "Spawn PvP open"},
                {"name": "Economy", "grade": "D", "detail": "Arbitrage found"},
            ],
        )
        self.assertEqual(sc_nogo["decision"], "NO-GO")
        self.assertFalse(sc_nogo["ok"])
        self.assertEqual(sc_nogo["blocker_count"], 2)

    def test_mcp_century_100th_tool_attaches_inline_png(self) -> None:
        server = MinecraftKitMcpServer(root=ROOT)
        tools = json.loads(server.handle_message(json.dumps({
            "jsonrpc": "2.0", "id": 1000, "method": "tools/list",
        })) or "{}")["result"]["tools"]
        self.assertEqual(len(tools), 100)

        r100 = json.loads(server.handle_message(json.dumps({
            "jsonrpc": "2.0",
            "id": 100,
            "method": "tools/call",
            "params": {
                "name": "mc_qa_generate_executive_scorecard",
                "arguments": {
                    "release_name": "Paper 1.21.4 Season 5",
                    "checks": [
                        {"name": "Autonomous Bot QA", "grade": "A"},
                        {"name": "Bridge TPS & Heap", "grade": "A"},
                        {"name": "Velocity Proxy", "grade": "B"},
                    ],
                    "attach_chart": True,
                },
            },
        })) or "{}")
        content = r100["result"]["content"]
        self.assertEqual(len(content), 2)
        self.assertEqual(content[1]["type"], "image")
        self.assertTrue(base64.b64decode(content[1]["data"]).startswith(b"\x89PNG\r\n\x1a\n"))


if __name__ == "__main__":
    unittest.main()