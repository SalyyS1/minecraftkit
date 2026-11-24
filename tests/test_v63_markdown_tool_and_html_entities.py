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

    def test_bridge_chunks_endpoint_supported(self) -> None:
        import http.server
        import threading

        token = "v64-chunks-tok"

        class H(http.server.BaseHTTPRequestHandler):
            def do_GET(self) -> None:  # noqa: N802
                if self.path != "/api/v1/chunks" or self.headers.get("X-MCKit-Token") != token:
                    self.send_response(401)
                    self.end_headers()
                    return
                body = json.dumps({
                    "worlds": [{"world": "world", "loaded_chunks": 220, "force_loaded_chunks": 4, "entity_count": 440, "entities_per_chunk": 2.0}],
                    "total_loaded_chunks": 220,
                    "total_force_loaded_chunks": 4,
                }).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, format: str, *args: object) -> None:  # noqa: A002
                return

        httpd = http.server.HTTPServer(("127.0.0.1", 0), H)
        port = httpd.server_address[1]
        th = threading.Thread(target=httpd.serve_forever, daemon=True)
        th.start()
        try:
            srv = mcp_server.MinecraftKitMcpServer(ROOT)
            raw = srv.handle_message(json.dumps({
                "jsonrpc": "2.0",
                "id": 64,
                "method": "tools/call",
                "params": {
                    "name": "mc_bridge_plugin_query",
                    "arguments": {"base_url": f"http://127.0.0.1:{port}", "token": token, "endpoint": "chunks"},
                },
            }))
            resp_obj = json.loads(raw or "{}")
            content = resp_obj["result"]["content"]
            payload = json.loads(content[0]["text"])
            self.assertTrue(payload["reachable"])
            self.assertTrue(payload["inline_chart_attached"])
            self.assertEqual(payload["data"]["total_loaded_chunks"], 220)
            self.assertEqual(payload["data"]["total_force_loaded_chunks"], 4)
            import base64
            imgs = [c for c in content if c.get("type") == "image"]
            self.assertEqual(len(imgs), 1)
            self.assertTrue(base64.b64decode(imgs[0]["data"]).startswith(b"\x89PNG\r\n\x1a\n"))
        finally:
            httpd.shutdown()
            httpd.server_close()


if __name__ == "__main__":
    unittest.main()
