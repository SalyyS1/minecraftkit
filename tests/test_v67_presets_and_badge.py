"""Tests for v6.7.0 10-preset bot catalog and shields.io QA Proof badge JSON."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import bot_engine  # noqa: E402
import qa_report_html  # noqa: E402


class PresetsAndBadgeV67Tests(unittest.TestCase):
    def test_ten_bot_stage_presets_including_itemsadder_and_dungeon_boss(self) -> None:
        self.assertGreaterEqual(len(bot_engine.STAGE_PRESETS), 10)
        ia = bot_engine.build_stage_preset("itemsadder_nexo_pack")
        self.assertEqual(ia["recommended_tier"], "tier2-hybrid")
        self.assertTrue(any(st.get("action") == "accept_pack" for st in ia["stages"]))

        boss = bot_engine.build_stage_preset("dungeon_instance_boss")
        self.assertEqual(boss["recommended_tier"], "tier1-protocol")
        actions = {st.get("action") for st in boss["stages"]}
        self.assertIn("assert_entity_nearby", actions)
        self.assertIn("assert_title", actions)

    def test_qa_html_report_emits_shields_endpoint_badge_json(self) -> None:
        rep = qa_report_html.generate_qa_html_report(
            title="Badge Proof",
            tps=19.9,
            mspt=11.0,
        )
        badge = rep["badge_json"]
        self.assertEqual(badge["schemaVersion"], 1)
        self.assertEqual(badge["label"], "MinecraftKit Bot QA")
        self.assertEqual(badge["color"], "brightgreen")
        self.assertIn("PASS 3/3", badge["message"])


if __name__ == "__main__":
    unittest.main()
