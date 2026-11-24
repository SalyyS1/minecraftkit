"""Tests for MinecraftKit v5.8.0 HTML QA proof dual-PNG embedding and Protocol-aware E2E lifecycle."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import e2e_qa_orchestrator  # noqa: E402
import qa_report_html  # noqa: E402


class V58QaHtmlAndLifecycleTests(unittest.TestCase):
    def test_html_report_embeds_hud_and_tps_sparkline_pngs_and_scrubs_secrets(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out_file = Path(tmp) / "qa-proof.html"
            rep = qa_report_html.generate_qa_html_report(
                title="RPG Server QA Proof",
                server_target="127.0.0.1:25565",
                mc_version="1.21.4",
                tps=19.8,
                mspt=14.5,
                chat_log=[
                    "[Bot] /login SuperSecretPw999",
                    "[Panel] token=ptlc_LeakedSecretToken1234567890123",
                ],
                output_path=str(out_file),
            )
            self.assertTrue(rep["ok"])
            self.assertGreaterEqual(rep["snapshot_count"], 2)
            html_text = out_file.read_text(encoding="utf-8")
            self.assertIn("data:image/png;base64,", html_text)
            self.assertIn("TPS / MSPT Telemetry Sparkline", html_text)
            self.assertNotIn("SuperSecretPw999", html_text)
            self.assertNotIn("ptlc_LeakedSecretToken1234567890123", html_text)

    def test_e2e_lifecycle_includes_protocol_matrix_and_dual_visual_proof(self) -> None:
        res = e2e_qa_orchestrator.run_full_qa_lifecycle(
            project_name="SalyVnSkyblock",
            mc_version="26.3",
            platform="folia",
            bot_count=6,
            preset="skyblock_island_coop",
        )
        self.assertTrue(res["ok"])
        self.assertEqual(res["phases"]["0_protocol_matrix"]["recommended_bot_protocol"], 775)
        self.assertGreaterEqual(res["phases"]["5_html_qa_proof"]["snapshot_count"], 2)


if __name__ == "__main__":
    unittest.main()
