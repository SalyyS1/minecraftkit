"""Loopback E2E & unit tests for v6.1.0 entity lag PNG chart and redacted Markdown proofs."""

from __future__ import annotations

import base64
import http.server
import json
import sys
import threading
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import bot_engine  # noqa: E402
import mcp_server  # noqa: E402
import visual_capture  # noqa: E402


class EntityChartAndMarkdownV61Tests(unittest.TestCase):
    def test_mcp_bridge_entities_attaches_inline_png_bar_chart(self) -> None:
        token = "v61-bridge-secret"
        payload = {
            "ok": True,
            "worlds": [
                {
                    "world": "world_nether",
                    "total_entities": 775,
                    "top_types": {
                        "ZOMBIFIED_PIGLIN": 420,
                        "ITEM": 310,
                        "VILLAGER": 45,
                    },
                }
            ],
        }

        class Handler(http.server.BaseHTTPRequestHandler):
            def do_GET(self) -> None:  # noqa: N802
                if self.headers.get("X-MCKit-Token") != token:
                    self.send_response(401)
                    self.end_headers()
                    return
                body = json.dumps(payload).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, format: str, *args: object) -> None:  # noqa: A002
                return

        httpd = http.server.HTTPServer(("127.0.0.1", 0), Handler)
        port = httpd.server_address[1]
        t = threading.Thread(target=httpd.serve_forever, daemon=True)
        t.start()
        try:
            srv = mcp_server.MinecraftKitMcpServer(ROOT)
            raw = srv.handle_message(
                json.dumps(
                    {
                        "jsonrpc": "2.0",
                        "id": 61,
                        "method": "tools/call",
                        "params": {
                            "name": "mc_bridge_plugin_query",
                            "arguments": {
                                "base_url": f"http://127.0.0.1:{port}",
                                "token": token,
                                "endpoint": "entities",
                                "attach_chart": True,
                            },
                        },
                    }
                )
            )
            self.assertIsNotNone(raw)
            resp = json.loads(raw or "{}")
            content = resp["result"]["content"]
            text_json = json.loads(content[0]["text"])
            self.assertTrue(text_json["reachable"])
            self.assertTrue(text_json["inline_chart_attached"])
            img_item = [c for c in content if c.get("type") == "image"]
            self.assertEqual(len(img_item), 1)
            self.assertEqual(img_item[0]["mimeType"], "image/png")
            png_bytes = base64.b64decode(img_item[0]["data"])
            self.assertTrue(png_bytes.startswith(b"\x89PNG\r\n\x1a\n"))
        finally:
            httpd.shutdown()
            httpd.server_close()

    def test_redacted_markdown_summary_and_vietnamese_auth_prompts(self) -> None:
        secret = "SuperSecretVN2026!"
        md = bot_engine.export_redacted_markdown_summary(
            {
                "target": "play.salyvn.net:25565",
                "tier": "tier1-protocol",
                "stages": [
                    {"name": "Auto-Auth", "status": "pass", "elapsed_ms": 210, "detail": f"Sent /login {secret}"},
                    {"name": "Shop GUI", "status": "pass", "elapsed_ms": 145, "detail": "27 slots verified"},
                ],
            },
            extra_secrets=(secret,),
        )
        self.assertIn("PASS` (2/2)", md)
        self.assertNotIn(secret, md)
        self.assertIn("[REDACTED_PASSWORD]", md)
        self.assertTrue(any(p.search("Vui lòng nhập mật khẩu để vào server") for p in bot_engine.LOGIN_PATTERNS))
        self.assertTrue(any(p.search("Tạo tài khoản mới với /reg") for p in bot_engine.REGISTER_PATTERNS))

        png = visual_capture.render_entity_bar_chart_png({"top_types": {"ITEM": 320, "ZOMBIE": 40}})
        self.assertTrue(png.startswith(b"\x89PNG\r\n\x1a\n"))


if __name__ == "__main__":
    unittest.main()
