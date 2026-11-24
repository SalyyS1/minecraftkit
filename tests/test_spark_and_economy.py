#!/usr/bin/env python3
"""Unit tests for mc_ops_audit_spark_profile and mc_bot_simulate_economy_stress (v4.7.0 — 68 MCP tools)."""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import mcp_server  # noqa: E402


class SparkAndEconomyTests(unittest.TestCase):
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

    def test_spark_profile_auditor_catches_blocking_sql_entity_ai_chunk_and_plugin_hog(self) -> None:
        sample = """
        Server thread (100%)
          net.minecraft.server.level.ServerLevel.tickEntities() 38.4%
          com.mysql.cj.jdbc.StatementImpl.executeQuery() 24.5%
          HeavyShop.jar (27.2%)
          ChunkMap.getChunk() 12.1%
          G1 Evacuation Pause (STW)
        """
        res = self._call("mc_ops_audit_spark_profile", {"profile_text": sample, "tps": 14.5, "mspt": 68.0})
        self.assertFalse(res["ok"])
        codes = {f["code"] for f in res["findings"]}
        self.assertIn("TICK-OVERLOAD", codes)
        self.assertIn("TICK-ENTITY", codes)
        self.assertIn("TICK-CHUNK", codes)
        self.assertIn("TICK-GC", codes)
        self.assertIn("TICK-BLOCKING-IO", codes)
        self.assertIn("TICK-PLUGIN", codes)
        self.assertGreaterEqual(res["hotspot_count"], 1)

    def test_economy_stress_sim_detects_direct_and_craft_arbitrage(self) -> None:
        bad = self._call(
            "mc_bot_simulate_economy_stress",
            {
                "shop_items": [
                    {"id": "iron_ingot", "buy_price": 10, "sell_price": 12},
                    {"id": "iron_block", "buy_price": 120, "sell_price": 110},
                    {"id": "glitch_gem", "buy_price": -5, "sell_price": 10},
                ],
                "recipes": [
                    {"output": "iron_block", "output_qty": 1, "ingredients": {"iron_ingot": 9}},
                ],
                "tax_pct": 0.0,
                "concurrent_bots": 6,
            },
        )
        self.assertFalse(bad["ok"])
        codes = {f["code"] for f in bad["findings"]}
        self.assertIn("ECON-ARB-001", codes)
        self.assertIn("ECON-NEG-002", codes)
        self.assertEqual(bad["concurrent_race_qa_plan"]["bot_count"], 6)
        self.assertEqual(bad["concurrent_race_qa_plan"]["estimated_ram_mb"], 6 * 42)

        good = self._call(
            "mc_bot_simulate_economy_stress",
            {
                "shop_items": [
                    {"id": "iron_ingot", "buy_price": 15, "sell_price": 8},
                    {"id": "iron_block", "buy_price": 150, "sell_price": 75},
                ],
                "recipes": [
                    {"output": "iron_block", "output_qty": 1, "ingredients": {"iron_ingot": 9}},
                ],
            },
        )
        self.assertTrue(good["ok"])
        self.assertEqual(good["grade"], "A")


if __name__ == "__main__":
    unittest.main()
