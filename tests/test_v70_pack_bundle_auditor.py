"""Tests for v7.0.0 mc_pack_audit_bundle resource pack auditor."""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from mcp_server import MinecraftKitMcpServer  # noqa: E402


class TestPackBundleAuditor(unittest.TestCase):
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

    def test_clean_1214_pack_passes_grade_a(self) -> None:
        files = {
            "pack.mcmeta": {"pack": {"pack_format": 46, "description": "MyRPG Pack"}},
            "assets/myrpg/items/sunblade.json": {
                "model": {"type": "minecraft:model", "model": "myrpg:item/sunblade"}
            },
            "assets/myrpg/font/hud.json": {
                "providers": [
                    {"type": "bitmap", "file": "myrpg:font/hp.png", "height": 12, "ascent": 9, "chars": ["\ue001\ue002"]}
                ]
            },
        }
        payload, is_err = self._call("mc_pack_audit_bundle", {"files": files, "target_mc_version": "1.21.4"})
        self.assertFalse(is_err)
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["grade"], "A")
        self.assertEqual(payload["unique_glyphs_indexed"], 2)
        self.assertEqual(payload["finding_count"], 0)

    def test_detects_all_five_pack_rules(self) -> None:
        files = {
            "pack.mcmeta": {"pack": {"pack_format": 15, "description": "Old 1.20.1 Pack"}},
            "assets/MyRPG/items/BadSword.json": {"type": "minecraft:model"},
            "assets/myrpg/font/a.json": {
                "providers": [
                    {"type": "bitmap", "file": "myrpg:font/a.png", "height": 8, "ascent": 12, "chars": ["\ue100"]}
                ]
            },
            "assets/myrpg/font/b.json": {
                "providers": [
                    {"type": "bitmap", "file": "myrpg:font/b.png", "height": 8, "ascent": 7, "chars": ["\ue100"]}
                ]
            },
            "assets/minecraft/models/item/diamond_sword.json": {
                "parent": "minecraft:item/handheld",
                "overrides": [{"predicate": {"custom_model_data": 1001}, "model": "myrpg:item/sword"}],
            },
        }
        payload, is_err = self._call("mc_pack_audit_bundle", {"files": files, "target_mc_version": "1.21.4"})
        self.assertFalse(is_err)
        self.assertFalse(payload["ok"])
        codes = {f["rule_id"] for f in payload["findings"]}
        for expected in ("PACK-001", "PACK-002", "PACK-003", "PACK-004", "PACK-005"):
            self.assertIn(expected, codes)


if __name__ == "__main__":
    unittest.main()
