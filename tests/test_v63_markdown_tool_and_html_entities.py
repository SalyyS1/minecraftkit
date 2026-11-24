"""Tests for v6.3.0 76th MCP tool (mc_bot_export_markdown_proof) & triple-PNG HTML QA proof."""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import mcp_server  # noqa: E402
import qa_report_html  # noqa: E402


class MarkdownProofAndTriplePngV63Tests(unittest.TestCase):
    def test_mcp_76th_tool_exports_redacted_markdown_proof(self) -> None:
        srv = mcp_server.MinecraftKitMcpServer(ROOT)
        secret = "TopSecretQA2026!"
        raw = srv.handle_message(
            json.dumps(
                {
                    "jsonrpc": "2.0",
                    "id": 76,
                    "method": "tools/call",
                    "params": {
                        "name": "mc_bot_export_markdown_proof",
                        "arguments": {
                            "target": "play.salyvn.net:25565",
                            "tier": "tier1-protocol",
                            "extra_secrets": [secret],
                            "stages": [
                                {"name": "Auto-Auth", "status": "pass", "elapsed_ms": 180, "detail": f"/login {secret}"},
                                {"name": "Shop GUI", "status": "pass", "elapsed_ms": 120, "detail": "27 slots verified"},
                            ],
                        },
                    },
                }
            )
        )
        self.assertIsNotNone(raw)
        resp = json.loads(raw or "{}")
        payload = json.loads(resp["result"]["content"][0]["text"])
        self.assertTrue(payload["ok"])
        self.assertTrue(payload["secrets_redacted"])
        md = payload["markdown"]
        self.assertIn("PASS` (2/2)", md)
        self.assertNotIn(secret, md)
        self.assertIn("[REDACTED_PASSWORD]", md)

    def test_qa_html_report_embeds_triple_png_when_entity_worlds_provided(self) -> None:
        rep = qa_report_html.generate_qa_html_report(
            title="Triple PNG QA Proof",
            tps=19.8,
            mspt=16.5,
            entity_worlds=[
                {"world": "world", "total_entities": 420, "top_types": {"ITEM": 280, "ZOMBIE": 90, "VILLAGER": 50}}
            ],
        )
        self.assertEqual(rep["snapshot_count"], 3)
        self.assertIn("Entity Lag Breakdown Bar Chart", rep["html"])
        self.assertGreaterEqual(rep["html"].count("data:image/png;base64,"), 3)


if __name__ == "__main__":
    unittest.main()
