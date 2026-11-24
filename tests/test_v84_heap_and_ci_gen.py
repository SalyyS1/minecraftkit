"""Tests for v8.4.0 mc_ops_audit_spark_heap_summary (93rd) & mc_bot_generate_ci_matrix_workflow (94th)."""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import bot_ci_workflow_gen  # noqa: E402
import spark_heap_auditor  # noqa: E402
from mcp_server import MinecraftKitMcpServer  # noqa: E402


LEAKY_HEAP = """
1: 120 1850.5 MB [B
2: 245 48.2 MB org.bukkit.craftbukkit.entity.CraftPlayer
3: 9400 320.0 MB net.minecraft.world.level.chunk.LevelChunk
4: 18500 210.4 MB net.minecraft.world.entity.decoration.ArmorStand
5: 1200 18.0 MB com.zaxxer.hikari.pool.HikariProxyConnection
"""

CLEAN_HEAP = """
1: 18 12.0 MB org.bukkit.craftbukkit.entity.CraftPlayer
2: 640 85.0 MB net.minecraft.world.level.chunk.LevelChunk
3: 4500 240.0 MB [B
"""


class HeapAndCiWorkflowV84Tests(unittest.TestCase):
    def test_spark_heap_auditor_catches_all_five_leak_rules(self) -> None:
        bad = spark_heap_auditor.audit_spark_heap_summary(LEAKY_HEAP, online_players=25, total_heap_mb=4096)
        self.assertFalse(bad["ok"])
        self.assertEqual(bad["grade"], "F")
        self.assertEqual({f["rule_id"] for f in bad["findings"]}, {"HEAP-001", "HEAP-002", "HEAP-003", "HEAP-004", "HEAP-005"})

        good = spark_heap_auditor.audit_spark_heap_summary(CLEAN_HEAP, online_players=20, total_heap_mb=4096)
        self.assertTrue(good["ok"])
        self.assertEqual(good["grade"], "A")
        self.assertEqual(good["findings"], [])

    def test_bot_ci_workflow_generator_gradle_and_maven(self) -> None:
        g = bot_ci_workflow_gen.generate_bot_ci_workflow(plugin_name="SalyRPG", build_tool="gradle", concurrent_bots=4)
        self.assertTrue(g["ok"])
        self.assertEqual(g["filename"], ".github/workflows/mckit-bot-qa.yml")
        self.assertIn("./gradlew shadowJar", g["workflow_yaml"])
        self.assertIn("secrets.MCKIT_BOT_PASS", g["workflow_yaml"])

        m = bot_ci_workflow_gen.generate_bot_ci_workflow(plugin_name="QuestCore", build_tool="maven", concurrent_bots=2)
        self.assertIn("mvn -B package", m["workflow_yaml"])

    def test_mcp_roundtrip_93_and_94(self) -> None:
        server = MinecraftKitMcpServer(root=ROOT)
        r93 = json.loads(server.handle_message(json.dumps({
            "jsonrpc": "2.0",
            "id": 93,
            "method": "tools/call",
            "params": {"name": "mc_ops_audit_spark_heap_summary", "arguments": {"heap_text": LEAKY_HEAP, "online_players": 20}},
        })) or "{}")
        self.assertFalse(r93["result"]["isError"])
        self.assertEqual(json.loads(r93["result"]["content"][0]["text"])["grade"], "F")

        r94 = json.loads(server.handle_message(json.dumps({
            "jsonrpc": "2.0",
            "id": 94,
            "method": "tools/call",
            "params": {"name": "mc_bot_generate_ci_matrix_workflow", "arguments": {"plugin_name": "SalyRPG", "concurrent_bots": 3}},
        })) or "{}")
        self.assertFalse(r94["result"]["isError"])
        self.assertTrue(json.loads(r94["result"]["content"][0]["text"])["ok"])


if __name__ == "__main__":
    unittest.main()