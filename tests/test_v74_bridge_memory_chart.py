"""Tests for v7.4.0 Bridge /api/v1/memory endpoint & 4th inline PNG chart (render_memory_gauge_png)."""

from __future__ import annotations

import base64
import http.server
import json
import sys
import threading
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import mcp_server  # noqa: E402


class TestBridgeMemoryChart(unittest.TestCase):
    def test_bridge_memory_attaches_inline_png_gauge(self) -> None:
        tok = "tok_mem_chart_e2e"

        class _MemHandler(http.server.BaseHTTPRequestHandler):
            def log_message(self, format: str, *args: object) -> None:  # noqa: A002
                return

            def do_GET(self) -> None:  # noqa: N802
                if self.headers.get("X-MCKit-Token") != tok or self.path != "/api/v1/memory":
                    body = b'{"error":"unauthorized"}'
                    self.send_response(401)
                else:
                    body = json.dumps({
                        "heap_used_mb": 3420,
                        "heap_committed_mb": 4096,
                        "heap_max_mb": 4096,
                        "heap_pressure_pct": 83.5,
                        "non_heap_used_mb": 182,
                        "gc_count": 48,
                        "gc_time_ms": 640,
                        "thread_count": 64,
                        "daemon_threads": 41,
                    }).encode("utf-8")
                    self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

        httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), _MemHandler)
        port = httpd.server_address[1]
        threading.Thread(target=httpd.serve_forever, daemon=True).start()
        try:
            srv = mcp_server.MinecraftKitMcpServer(ROOT)
            raw = srv.handle_message(json.dumps({
                "jsonrpc": "2.0",
                "id": 740,
                "method": "tools/call",
                "params": {
                    "name": "mc_bridge_plugin_query",
                    "arguments": {
                        "base_url": f"http://127.0.0.1:{port}",
                        "token": tok,
                        "endpoint": "memory",
                    },
                },
            }))
            assert raw is not None
            content = json.loads(raw)["result"]["content"]
            payload = json.loads(content[0]["text"])
            self.assertTrue(payload["reachable"])
            self.assertTrue(payload["inline_chart_attached"])
            self.assertEqual(payload["data"]["heap_used_mb"], 3420)
            imgs = [c for c in content if c.get("type") == "image"]
            self.assertEqual(len(imgs), 1)
            self.assertTrue(base64.b64decode(imgs[0]["data"]).startswith(b"\x89PNG\r\n\x1a\n"))
        finally:
            httpd.shutdown()
            httpd.server_close()


if __name__ == "__main__":
    unittest.main()
