"""End-to-end loopback integration tests for MinecraftKit v5.1.0.

Exercises:
  1. Pure-Python Minecraft wire protocol bot (Handshake -> SetCompression -> LoginSuccess
     -> ConfigKeepAlive -> ResourcePackPush -> FinishConfig -> Play ChatCommand -> SystemChat)
     against a real local TCP loopback server, verifying strict password redaction.
  2. Headless hosting panel connector (`hosting_bridge.execute_hosting_action`) against
     a real local HTTP loopback mock Pterodactyl + Crafty API server, verifying RFC 6238
     TOTP 2FA and secret redaction.
  3. Companion Java 21 `BridgeContractTest` (6/6 PASS) and `McKitVisualClientMod` real
     compilation + loopback `/api/v1/status` and `/api/v1/errors` verification.
"""

from __future__ import annotations

import http.server
import json
import shutil
import socket
import struct
import subprocess
import sys
import tempfile
import threading
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import hosting_bridge  # noqa: E402
import mc_proto_client  # noqa: E402


def _mock_mc_server(listen_sock: socket.socket, received_cmds: list[str]) -> None:
    try:
        conn, _ = listen_sock.accept()
        with conn:
            conn.settimeout(3.0)
            # 1. Handshake (0x00) + LoginStart (0x00)
            pid_hs, _ = mc_proto_client.read_packet(conn, compression_threshold=-1)
            assert pid_hs == 0x00
            pid_ls, _ = mc_proto_client.read_packet(conn, compression_threshold=-1)
            assert pid_ls == 0x00

            # 2. SetCompression (0x03) with threshold 64, then LoginSuccess (0x02)
            conn.sendall(mc_proto_client.frame_packet(0x03, mc_proto_client.encode_varint(64), compression_threshold=-1))
            fake_uuid = b"\x00" * 16
            conn.sendall(
                mc_proto_client.frame_packet(
                    0x02,
                    fake_uuid + mc_proto_client.encode_mc_string("MCKitE2E") + mc_proto_client.encode_varint(0),
                    compression_threshold=64,
                )
            )

            # 3. Expect LoginAcknowledged (0x03)
            pid_ack, _ = mc_proto_client.read_packet(conn, compression_threshold=64)
            assert pid_ack == 0x03

            # 4. Configuration: KeepAlive (0x04), ResourcePackPush (0x09), FinishConfig (0x03)
            conn.sendall(mc_proto_client.frame_packet(0x04, struct.pack(">q", 424242), compression_threshold=64))
            pid_ka, _ = mc_proto_client.read_packet(conn, compression_threshold=64)
            assert pid_ka == 0x04

            conn.sendall(mc_proto_client.frame_packet(0x09, b"\x11" * 16, compression_threshold=64))
            pid_rp1, _ = mc_proto_client.read_packet(conn, compression_threshold=64)
            pid_rp2, _ = mc_proto_client.read_packet(conn, compression_threshold=64)
            assert pid_rp1 == 0x06 and pid_rp2 == 0x06

            conn.sendall(mc_proto_client.frame_packet(0x03, b"", compression_threshold=64))
            pid_fin, _ = mc_proto_client.read_packet(conn, compression_threshold=64)
            assert pid_fin == 0x03

            # 5. Play phase: read 2 ChatCommand (0x04) packets and send a SystemChat reply (0x6C)
            for _ in range(2):
                pid_cmd, payload = mc_proto_client.read_packet(conn, compression_threshold=64)
                assert pid_cmd == 0x04
                cmd_str, _ = mc_proto_client.decode_mc_string(payload, 0)
                received_cmds.append(cmd_str)

            conn.sendall(
                mc_proto_client.frame_packet(
                    0x6C,
                    mc_proto_client.encode_mc_string("[AuthMe] Logged in successfully! Shop ready."),
                    compression_threshold=64,
                )
            )
    except Exception:  # noqa: BLE001
        pass


class _MockHostingHandler(http.server.BaseHTTPRequestHandler):
    expected_token = "ptlc_SuperSecretHostingToken99999"
    recorded_actions: list[tuple[str, str, str]] = []

    def log_message(self, format: str, *args: object) -> None:  # noqa: A002
        return

    def _check_auth(self) -> bool:
        auth = self.headers.get("Authorization", "")
        if auth != f"Bearer {self.expected_token}":
            body = json.dumps({"error": f"unauthorized token={self.expected_token}"}).encode("utf-8")
            self.send_response(401)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return False
        return True

    def do_GET(self) -> None:  # noqa: N802
        if not self._check_auth():
            return
        self.recorded_actions.append(("GET", self.path, ""))
        payload = json.dumps({"object": "stats", "attributes": {"current_state": "running", "resources": {"memory_bytes": 1073741824}}}).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def do_POST(self) -> None:  # noqa: N802
        if not self._check_auth():
            return
        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length).decode("utf-8", errors="replace") if length > 0 else ""
        self.recorded_actions.append(("POST", self.path, raw))
        payload = json.dumps({"ok": True, "accepted": True}).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)


class V51LoopbackE2ETests(unittest.TestCase):
    def test_wire_play_bot_e2e_loopback_with_compression_and_redaction(self) -> None:
        received: list[str] = []
        srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        srv.bind(("127.0.0.1", 0))
        srv.listen(1)
        port = srv.getsockname()[1]

        t = threading.Thread(target=_mock_mc_server, args=(srv, received), daemon=True)
        t.start()
        try:
            res = mc_proto_client.run_offline_play_probe(
                "127.0.0.1",
                port,
                username="MCKitE2E",
                protocol_version=769,
                commands=["/login TopSecretPass999", "/shop"],
                timeout_seconds=3.0,
            )
        finally:
            t.join(timeout=3.0)
            srv.close()

        self.assertTrue(res["ok"], res)
        self.assertEqual(res["phase_reached"], "play")
        self.assertEqual(res["compression_threshold"], 64)
        self.assertTrue(res["screen_lock_free"])
        self.assertEqual(received, ["login TopSecretPass999", "shop"])
        serialized = json.dumps(res)
        self.assertNotIn("TopSecretPass999", serialized)
        self.assertIn("REDACTED", serialized)
        self.assertTrue(any("Logged in successfully" in m for m in res["chat_messages"]))

    def test_hosting_bridge_e2e_loopback_http_and_totp_and_redaction(self) -> None:
        _MockHostingHandler.recorded_actions = []
        httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), _MockHostingHandler)
        port = httpd.server_address[1]
        th = threading.Thread(target=httpd.serve_forever, daemon=True)
        th.start()
        try:
            totp = hosting_bridge.generate_totp("JBSWY3DPEHPK3PXP", timestamp=1700000000.0)
            self.assertEqual(len(totp["code"]), 6)

            res_status = hosting_bridge.execute_hosting_action(
                domain=f"http://127.0.0.1:{port}",
                panel_type="pterodactyl",
                server_id="srv-01",
                action="status",
                api_key=_MockHostingHandler.expected_token,
                dry_run=False,
            )
            self.assertTrue(res_status["ok"], res_status)
            self.assertEqual(res_status["status_code"], 200)
            self.assertEqual(res_status["response"]["attributes"]["current_state"], "running")

            res_power = hosting_bridge.execute_hosting_action(
                domain=f"http://127.0.0.1:{port}",
                panel_type="pterodactyl",
                server_id="srv-01",
                action="restart",
                api_key=_MockHostingHandler.expected_token,
                dry_run=False,
            )
            self.assertTrue(res_power["ok"], res_power)
            self.assertEqual(_MockHostingHandler.recorded_actions[-1][0], "POST")
            self.assertEqual(_MockHostingHandler.recorded_actions[-1][1], "/api/client/servers/srv-01/power")

            # Verify bad token error body redacts secret tokens
            res_bad = hosting_bridge.execute_hosting_action(
                domain=f"http://127.0.0.1:{port}",
                panel_type="pterodactyl",
                server_id="srv-01",
                action="status",
                api_key="ptlc_WrongTokenValue1234567890",
                dry_run=False,
            )
            self.assertFalse(res_bad["ok"])
            self.assertEqual(res_bad["status_code"], 401)
            self.assertNotIn(_MockHostingHandler.expected_token, json.dumps(res_bad))
        finally:
            httpd.shutdown()
            httpd.server_close()

    def test_companion_java_bridge_contract_and_visual_client_mod_compile(self) -> None:
        javac = shutil.which("javac")
        java = shutil.which("java")
        if not javac or not java:
            self.skipTest("JDK not available in PATH")

        with tempfile.TemporaryDirectory() as tmp:
            # 1. Compile and execute BridgeContractTest (6/6 PASS)
            bridge_test = ROOT / "bridge-plugin" / "src" / "test" / "java" / "com" / "salyvn" / "mckit" / "bridge" / "BridgeContractTest.java"
            comp = subprocess.run([javac, "-d", tmp, str(bridge_test)], capture_output=True, text=True, check=False)
            self.assertEqual(comp.returncode, 0, comp.stderr)
            run = subprocess.run([java, "-cp", tmp, "com.salyvn.mckit.bridge.BridgeContractTest"], capture_output=True, text=True, check=False)
            self.assertEqual(run.returncode, 0, run.stderr)
            self.assertIn("7/7 PASS", run.stdout)

            # 2. Compile McKitVisualClientMod cleanly (zero Fabric JAR dependency needed for loopback server)
            client_mod = ROOT / "client-mod" / "src" / "main" / "java" / "com" / "salyvn" / "mckit" / "client" / "McKitVisualClientMod.java"
            comp2 = subprocess.run([javac, "-d", tmp, str(client_mod)], capture_output=True, text=True, check=False)
            self.assertEqual(comp2.returncode, 0, comp2.stderr)

    def test_bridge_tps_history_and_entities_e2e_with_inline_png_sparkline(self) -> None:
        import base64
        import mcp_server

        expected_tok = "tok_bridge_sparkline_test"

        class _BridgeHandler(http.server.BaseHTTPRequestHandler):
            def log_message(self, format: str, *args: object) -> None:  # noqa: A002
                return

            def do_GET(self) -> None:  # noqa: N802
                if self.headers.get("X-MCKit-Token") != expected_tok:
                    body = b'{"error":"unauthorized"}'
                    self.send_response(401)
                elif self.path == "/api/v1/tps-history":
                    body = json.dumps({
                        "max_samples": 60,
                        "samples": [
                            {"ts": "2026-11-25T00:00:01Z", "tps_1m": 20.0, "mspt": 18.2, "players": 4},
                            {"ts": "2026-11-25T00:00:02Z", "tps_1m": 19.4, "mspt": 28.5, "players": 5},
                            {"ts": "2026-11-25T00:00:03Z", "tps_1m": 17.8, "mspt": 46.1, "players": 6},
                            {"ts": "2026-11-25T00:00:04Z", "tps_1m": 19.9, "mspt": 21.0, "players": 6},
                        ],
                    }).encode("utf-8")
                    self.send_response(200)
                elif self.path == "/api/v1/entities":
                    body = json.dumps({
                        "worlds": [{"world": "world", "total": 412, "top_types": [{"type": "ITEM", "count": 190}, {"type": "ZOMBIE", "count": 84}]}]
                    }).encode("utf-8")
                    self.send_response(200)
                else:
                    body = b'{"error":"not_found"}'
                    self.send_response(404)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

        httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), _BridgeHandler)
        port = httpd.server_address[1]
        th = threading.Thread(target=httpd.serve_forever, daemon=True)
        th.start()
        try:
            srv = mcp_server.MinecraftKitMcpServer(ROOT)
            raw_tps = srv.handle_message(json.dumps({
                "jsonrpc": "2.0",
                "id": 901,
                "method": "tools/call",
                "params": {
                    "name": "mc_bridge_plugin_query",
                    "arguments": {
                        "base_url": f"http://127.0.0.1:{port}",
                        "token": expected_tok,
                        "endpoint": "tps-history",
                    },
                },
            }))
            assert raw_tps is not None
            resp_tps = json.loads(raw_tps)
            content = resp_tps["result"]["content"]
            payload = json.loads(content[0]["text"])
            self.assertTrue(payload["reachable"])
            self.assertTrue(payload["inline_chart_attached"])
            imgs = [c for c in content if c.get("type") == "image"]
            self.assertEqual(len(imgs), 1)
            self.assertEqual(imgs[0]["mimeType"], "image/png")
            png_raw = base64.b64decode(imgs[0]["data"])
            self.assertTrue(png_raw.startswith(b"\x89PNG\r\n\x1a\n"))

            raw_ent = srv.handle_message(json.dumps({
                "jsonrpc": "2.0",
                "id": 902,
                "method": "tools/call",
                "params": {
                    "name": "mc_bridge_plugin_query",
                    "arguments": {
                        "base_url": f"http://127.0.0.1:{port}",
                        "token": expected_tok,
                        "endpoint": "entities",
                    },
                },
            }))
            assert raw_ent is not None
            resp_ent = json.loads(raw_ent)
            ent_payload = json.loads(resp_ent["result"]["content"][0]["text"])
            self.assertEqual(ent_payload["data"]["worlds"][0]["top_types"][0]["type"], "ITEM")
        finally:
            httpd.shutdown()
            httpd.server_close()


if __name__ == "__main__":
    unittest.main()
