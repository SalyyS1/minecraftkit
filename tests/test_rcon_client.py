from __future__ import annotations

import json
import socket
import sys
import threading
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import rcon_client  # noqa: E402
from mcp_server import MinecraftKitMcpServer  # noqa: E402


class RconClientTests(unittest.TestCase):
    def test_loopback_rcon_auth_command_and_password_redaction(self) -> None:
        srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        srv.bind(("127.0.0.1", 0))
        srv.listen(1)
        port = srv.getsockname()[1]

        def serve() -> None:
            try:
                conn, _ = srv.accept()
                with conn:
                    rid, ptype, pw = rcon_client.read_rcon_packet(conn)
                    assert ptype == rcon_client.RCON_SERVERDATA_AUTH
                    if pw != "RconSuperPass88":
                        conn.sendall(rcon_client.pack_rcon_packet(-1, rcon_client.RCON_SERVERDATA_AUTH_RESPONSE, ""))
                        return
                    conn.sendall(rcon_client.pack_rcon_packet(rid, rcon_client.RCON_SERVERDATA_AUTH_RESPONSE, ""))
                    cid, ctype, cmd = rcon_client.read_rcon_packet(conn)
                    assert ctype == rcon_client.RCON_SERVERDATA_EXECCOMMAND
                    conn.sendall(
                        rcon_client.pack_rcon_packet(
                            cid,
                            rcon_client.RCON_SERVERDATA_RESPONSE_VALUE,
                            f"TPS from last 1m, 5m, 15m: 20.0, 20.0, 20.0 (cmd={cmd})",
                        )
                    )
            finally:
                srv.close()

        t = threading.Thread(target=serve, daemon=True)
        t.start()
        mcp = MinecraftKitMcpServer(root=ROOT)
        raw = mcp.handle_message(json.dumps({
            "jsonrpc": "2.0",
            "id": 77,
            "method": "tools/call",
            "params": {
                "name": "mc_ops_rcon_execute",
                "arguments": {
                    "host": "127.0.0.1",
                    "port": port,
                    "password": "RconSuperPass88",
                    "command": "tps",
                    "dry_run": False,
                },
            },
        }))
        t.join(timeout=3.0)
        assert raw is not None
        self.assertNotIn("RconSuperPass88", raw)
        body = json.loads(json.loads(raw)["result"]["content"][0]["text"])
        self.assertTrue(body["ok"], body)
        self.assertTrue(body["authenticated"])
        self.assertIn("20.0", body["response"])


if __name__ == "__main__":
    unittest.main()
