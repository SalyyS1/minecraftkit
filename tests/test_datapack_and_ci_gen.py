#!/usr/bin/env python3
"""Unit tests for mc_audit_datapack_integrity and mc_bot_generate_ci_workflow (v4.3.0 — 60 MCP tools!)."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import mcp_server  # noqa: E402


class DatapackAndCiGenTests(unittest.TestCase):
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

    def test_datapack_auditor_flags_121_plural_folders_broken_json_and_unfiltered_selectors(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            dp = Path(td) / "rpg_pack"
            (dp / "data" / "rpg" / "functions").mkdir(parents=True)
            (dp / "data" / "rpg" / "loot_table").mkdir(parents=True)
            (dp / "pack.mcmeta").write_text(json.dumps({"pack": {"pack_format": 61, "description": "RPG"}}), encoding="utf-8")
            (dp / "data" / "rpg" / "functions" / "tick.mcfunction").write_text(
                "execute as @e run say hi\ngive @s diamond_sword{CustomModelData:1001}\n",
                encoding="utf-8",
            )
            (dp / "data" / "rpg" / "loot_table" / "broken.json").write_text("{bad json", encoding="utf-8")

            bad = self._call("mc_audit_datapack_integrity", {"datapack_dir": str(dp), "target_mc_version": "1.21.4"})
            self.assertFalse(bad["ok"])
            codes = {f["code"] for f in bad["findings"]}
            self.assertIn("DP-001", codes)
            self.assertIn("DP-003", codes)
            self.assertIn("DP-004", codes)

            # Fix all issues -> Grade A!
            (dp / "data" / "rpg" / "functions" / "tick.mcfunction").unlink()
            (dp / "data" / "rpg" / "functions").rmdir()
            (dp / "data" / "rpg" / "function").mkdir()
            (dp / "data" / "rpg" / "function" / "tick.mcfunction").write_text(
                "execute as @e[type=minecraft:marker,distance=..16] run say ok\n",
                encoding="utf-8",
            )
            (dp / "data" / "rpg" / "loot_table" / "broken.json").write_text('{"pools": []}', encoding="utf-8")
            good = self._call("mc_audit_datapack_integrity", {"datapack_dir": str(dp), "target_mc_version": "1.21.4"})
            self.assertTrue(good["ok"])
            self.assertEqual(good["grade"], "A")

    def test_ci_workflow_generator_outputs_valid_github_actions_yaml(self) -> None:
        res = self._call(
            "mc_bot_generate_ci_workflow",
            {
                "plugin_name": "OZbanghoi",
                "build_tool": "gradle",
                "platforms": ["paper", "folia", "purpur"],
                "mc_version": "1.21.4",
                "bot_preset": "folia_stress",
                "concurrent_bots": 8,
            },
        )
        self.assertEqual(res["filename"], ".github/workflows/mckit-autonomous-qa.yml")
        self.assertEqual(res["estimated_bot_ram_mb"], 8 * 42)
        self.assertTrue(res["screen_lock_free"])
        self.assertIn("OZbanghoi", res["yaml"])
        self.assertIn("./gradlew build --no-daemon", res["yaml"])
        self.assertIn("upload-sarif", res["yaml"])


if __name__ == "__main__":
    unittest.main()
