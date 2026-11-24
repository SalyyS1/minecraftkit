"""Loopback E2E tests for MinecraftKit v5.9.0 75th MCP tool `mc_bot_fingerprint_server`."""

from __future__ import annotations

import http.server
import json
import socket
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


def _mock_slp_server(listen_sock: socket.socket) -> None:
    try:
        conn, _ = listen_sock.accept()
        with conn:
            conn.settimeout(3.0)
            conn.recv(512)
            status_json = json.dumps({
                "version": {"name": "Folia 26.3", "protocol": 775},
                "players": {"max": 100, "online": 12},
                "description": {"text": "SalyVn Folia RPG Cluster"},
            }).encode("utf-8")
            payload = bot_engine._encode_varint(0x00) + bot_engine._encode_varint(len(status_json)) + status_json
            conn.sendall(bot_engine._encode_varint(len(payload)) + payload)
    except Exception:  # noqa: BLE001
        pass


class V59ServerFingerprintTests(unittest.TestCase):
    def test_fingerprint_server_detects_folia_brand_protocol_and_bridge_over_loopback(self) -> None:
        slp_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        slp_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        slp_sock.bind(("127.0.0.1", 0))
        slp_sock.listen(1)
        slp_port = slp_sock.getsockname()[1]
        t_slp = threading.Thread(target=_mock_slp_server, args=(slp_sock,), daemon=True)
        t_slp.start()

        class _HealthHandler(http.server.BaseHTTPRequestHandler):
            def log_message(self, format: str, *args: object) -> None:  # noqa: A002
                return

            def do_GET(self) -> None:  # noqa: N802
                body = b'{"ok":true,"plugin":"MCKitBridge","server":"Folia"}'
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

        httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), _HealthHandler)
        b_port = httpd.server_address[1]
        t_http = threading.Thread(target=httpd.serve_forever, daemon=True)
        t_http.start()

        try:
            srv = mcp_server.MinecraftKitMcpServer(ROOT)
            raw = srv.handle_message(json.dumps({
                "jsonrpc": "2.0",
                "id": 75,
                "method": "tools/call",
                "params": {
                    "name": "mc_bot_fingerprint_server",
                    "arguments": {
                        "host": "127.0.0.1",
                        "port": slp_port,
                        "bridge_url": f"http://127.0.0.1:{b_port}",
                        "bridge_token": "tok_demo",
                    },
                },
            }))
            assert raw is not None
            resp = json.loads(raw)
            self.assertFalse(resp["result"]["isError"], resp)
            data = json.loads(resp["result"]["content"][0]["text"])
            self.assertTrue(data["ok"], data)
            self.assertEqual(data["detected_brand"], "folia")
            self.assertEqual(data["detected_mc_version"], "26.3")
            self.assertEqual(data["detected_protocol"], 775)
            self.assertEqual(data["recommended_bot_config"]["preset"], "folia_region_stress")
            self.assertTrue(data["bridge_plugin"]["reachable"])
        finally:
            t_slp.join(timeout=3.0)
            slp_sock.close()
            httpd.shutdown()
            httpd.server_close()


if __name__ == "__main__":
    unittest.main()
