"""Tests for v7.1.0 E2E QA orchestrator badge_json, markdown_proof & SFTP rollback recovery plan."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import e2e_qa_orchestrator  # noqa: E402


class TestOrchestratorProofAndRollback(unittest.TestCase):
    def test_passing_lifecycle_emits_badge_and_markdown_proof(self) -> None:
        res = e2e_qa_orchestrator.run_full_qa_lifecycle(
            project_name="DragonSMP",
            preset="itemsadder_nexo_pack",
            patched_config_path="/plugins/ItemsAdder/config.yml",
        )
        self.assertTrue(res["ok"])
        self.assertEqual(res["verdict"], "PASS")
        self.assertEqual(res["badge_json"]["schemaVersion"], 1)
        self.assertEqual(res["badge_json"]["color"], "brightgreen")
        self.assertIn("MinecraftKit Autonomous Bot QA Proof", res["markdown_proof"])
        self.assertFalse(res["rollback_recovery_plan"]["triggered"])

    def test_failing_lifecycle_triggers_sftp_rollback_plan(self) -> None:
        # Conflicting plugins trigger plugin_audit failure
        res = e2e_qa_orchestrator.run_full_qa_lifecycle(
            project_name="ConflictSMP",
            plugins=["AuthMe", "nLogin"],
            patched_config_path="/plugins/AuthMe/config.yml",
        )
        self.assertFalse(res["ok"])
        self.assertEqual(res["verdict"], "FAIL")
        self.assertEqual(res["badge_json"]["color"], "red")
        self.assertTrue(res["rollback_recovery_plan"]["triggered"])
        mcp_call = res["rollback_recovery_plan"]["mcp_call"]
        self.assertEqual(mcp_call["tool"], "mc_sftp_operations")
        self.assertEqual(mcp_call["arguments"]["operation"], "rollback_config")
        self.assertEqual(mcp_call["arguments"]["remote_path"], "/plugins/AuthMe/config.yml")


if __name__ == "__main__":
    unittest.main()
