"""Loopback HTTP E2E tests for Crafty Controller v4 & Pelican headless hosting panel actions."""

from __future__ import annotations

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

import hosting_bridge  # noqa: E402


class HostingPanelsLoopbackE2ETests(unittest.TestCase):
    def test_crafty_and_pelican_actions_and_token_redaction(self) -> None:
        secret_tok = "crafty_super_secret_token_987654321"
        seen: list[tuple[str, str, str]] = []

        class PanelHandler(http.server.BaseHTTPRequestHandler):
            def _handle(self, method: str) -> None:
                length = int(self.headers.get("Content-Length", "0"))
                body_str = self.rfile.read(length).decode("utf-8", errors="replace") if length > 0 else ""
                seen.append((method, self.path, body_str))
                auth = self.headers.get("Authorization", "")
                if auth != f"Bearer {secret_tok}":
                    err = json.dumps({"error": f"bad auth {auth}"}).encode("utf-8")
                    self.send_response(401)
                    self.send_header("Content-Type", "application/json")
                    self.send_header("Content-Length", str(len(err)))
                    self.end_headers()
                    self.wfile.write(err)
                    return
                ok_body = json.dumps({"ok": True, "path": self.path, "method": method}).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(ok_body)))
                self.end_headers()
                self.wfile.write(ok_body)

            def do_GET(self) -> None:  # noqa: N802
                self._handle("GET")

            def do_POST(self) -> None:  # noqa: N802
                self._handle("POST")

            def log_message(self, format: str, *args: object) -> None:  # noqa: A002
                return

        httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), PanelHandler)
        port = httpd.server_address[1]
        th = threading.Thread(target=httpd.serve_forever, daemon=True)
        th.start()
        try:
            base = f"http://127.0.0.1:{port}"
            # Crafty v4: status -> restart -> stdin command
            c_stat = hosting_bridge.execute_hosting_action(
                domain=base, panel_type="crafty", server_id="srv-42", action="status", api_key=secret_tok, dry_run=False
            )
            c_rst = hosting_bridge.execute_hosting_action(
                domain=base, panel_type="crafty", server_id="srv-42", action="restart", api_key=secret_tok, dry_run=False
            )
            c_cmd = hosting_bridge.execute_hosting_action(
                domain=base, panel_type="crafty", server_id="srv-42", action="command", command="tps", api_key=secret_tok, dry_run=False
            )
            self.assertTrue(c_stat["ok"])
            self.assertTrue(c_rst["ok"])
            self.assertTrue(c_cmd["ok"])
            self.assertEqual(c_stat["response"]["path"], "/api/v2/servers/srv-42/stats")
            self.assertEqual(c_rst["response"]["path"], "/api/v2/servers/srv-42/action/restart_server")
            self.assertEqual(c_cmd["response"]["path"], "/api/v2/servers/srv-42/stdin")

            # Pelican: resources + power restart
            p_res = hosting_bridge.execute_hosting_action(
                domain=base, panel_type="pelican", server_id="pel-99", action="resources", api_key=secret_tok, dry_run=False
            )
            p_rst = hosting_bridge.execute_hosting_action(
                domain=base, panel_type="pelican", server_id="pel-99", action="restart", api_key=secret_tok, dry_run=False
            )
            self.assertTrue(p_res["ok"])
            self.assertTrue(p_rst["ok"])
            self.assertEqual(p_res["response"]["path"], "/api/client/servers/pel-99/resources")
            self.assertEqual(p_rst["response"]["path"], "/api/client/servers/pel-99/power")

            # Verify token redaction when panel returns 401 echoing Authorization header
            bad = hosting_bridge.execute_hosting_action(
                domain=base, panel_type="crafty", server_id="srv-42", action="status", api_key="wrong_secret_tok_999", dry_run=False
            )
            self.assertFalse(bad["ok"])
            self.assertEqual(bad["status_code"], 401)
            self.assertNotIn("wrong_secret_tok_999", json.dumps(bad))
        finally:
            httpd.shutdown()
            httpd.server_close()


if __name__ == "__main__":
    unittest.main()
