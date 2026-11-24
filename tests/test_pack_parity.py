from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from mcp_server import MinecraftKitMcpServer  # noqa: E402


class PackParityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.server = MinecraftKitMcpServer(root=ROOT)

    def _call(self, args: dict[str, object]) -> dict[str, object]:
        raw = self.server.handle_message(json.dumps({
            "jsonrpc": "2.0",
            "id": 88,
            "method": "tools/call",
            "params": {"name": "mc_pack_verify_parity", "arguments": args},
        }))
        assert raw is not None
        res = json.loads(raw)["result"]
        self.assertFalse(res["isError"], res)
        return json.loads(res["content"][0]["text"])

    def test_filesystem_pack_parity_passes_and_flags_missing_models(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            pack = Path(td)
            (pack / "assets" / "myrpg" / "items").mkdir(parents=True)
            (pack / "assets" / "myrpg" / "models" / "item").mkdir(parents=True)
            (pack / "assets" / "minecraft" / "models" / "item").mkdir(parents=True)

            # Valid 1.21.4+ item_model + referenced model
            (pack / "assets" / "myrpg" / "items" / "flame_blade.json").write_text(
                json.dumps({"model": {"type": "minecraft:model", "model": "myrpg:item/flame_blade"}}),
                encoding="utf-8",
            )
            (pack / "assets" / "myrpg" / "models" / "item" / "flame_blade.json").write_text(
                json.dumps({"parent": "minecraft:item/handheld"}),
                encoding="utf-8",
            )
            # Valid legacy custom_model_data override
            (pack / "assets" / "minecraft" / "models" / "item" / "diamond_sword.json").write_text(
                json.dumps({"overrides": [{"predicate": {"custom_model_data": 1001}, "model": "myrpg:item/flame_blade"}]}),
                encoding="utf-8",
            )

            ok = self._call({
                "resource_pack_dir": td,
                "server_items": [
                    {"id": "FLAME_BLADE", "item_model": "myrpg:flame_blade", "base_material": "DIAMOND_SWORD", "custom_model_data": 1001},
                ],
            })
            self.assertTrue(ok["ok"], ok)
            self.assertEqual(ok["finding_count"], 0)

            # Broken items trigger PARITY-001, PARITY-002, PARITY-004
            bad = self._call({
                "resource_pack_dir": td,
                "server_items": [
                    {"id": "MISSING_ITEM", "item_model": "myrpg:ghost_axe"},
                    {"id": "MISSING_CMD", "base_material": "DIAMOND_SWORD", "custom_model_data": 9999},
                    {"id": "BAD_RL", "item_model": "MyRPG:Invalid Uppercase"},
                ],
            })
            self.assertFalse(bad["ok"])
            codes = {f["rule_id"] for f in bad["findings"]}
            self.assertIn("PARITY-001", codes)
            self.assertIn("PARITY-002", codes)
            self.assertIn("PARITY-004", codes)


if __name__ == "__main__":
    unittest.main()
