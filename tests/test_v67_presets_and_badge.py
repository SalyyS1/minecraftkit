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
        self.assertGreaterEqual(len(bot_engine.STAGE_PRESETS), 12)
        ia = bot_engine.build_stage_preset("itemsadder_nexo_pack")
        self.assertEqual(ia["recommended_tier"], "tier2-hybrid")
        self.assertTrue(any(st.get("action") == "accept_pack" for st in ia["stages"]))

        boss = bot_engine.build_stage_preset("dungeon_instance_boss")
        self.assertEqual(boss["recommended_tier"], "tier1-protocol")
        actions = {st.get("action") for st in boss["stages"]}
        self.assertIn("assert_entity_nearby", actions)
        self.assertIn("assert_title", actions)

        eco = bot_engine.build_stage_preset("economy_dupe_race")
        self.assertEqual(eco["recommended_tier"], "tier1-protocol")
        self.assertTrue(any(st.get("action") == "assert_no_chat" for st in eco["stages"]))

        proxy = bot_engine.build_stage_preset("proxy_velocity_transfer")
        self.assertEqual(proxy["recommended_tier"], "tier1-protocol")
        self.assertTrue(any("/server survival" in str(st.get("command", "")) for st in proxy["stages"]))

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

    def test_sftp_rollback_config_plan_and_traversal_guard(self) -> None:
        import hosting_bridge

        plan = hosting_bridge.sftp_operation(
            host="127.0.0.1",
            port=2022,
            username="srv_demo",
            password="SecretSftpPassword99!",
            operation="rollback_config",
            remote_path="/plugins/MyRPG/config.yml",
            dry_run=True,
        )
        self.assertTrue(plan["dry_run"])
        self.assertEqual(plan["operation"], "rollback_config")
        self.assertTrue(any(".mckit.bak" in step for step in plan["rollback_steps"]))
        self.assertNotIn("SecretSftpPassword99!", str(plan))


if __name__ == "__main__":
    unittest.main()
