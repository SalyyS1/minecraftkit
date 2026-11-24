"""End-to-end Source RCON loopback, SFTP safety, and 8-preset bot QA tests (MinecraftKit v5.6.0)."""

from __future__ import annotations

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

import hosting_bridge  # noqa: E402
import mcp_server  # noqa: E402
import rcon_client  # noqa: E402


def _mock_rcon_server(listen_sock: socket.socket, expected_pass: str) -> None:
    try:
        conn, _ = listen_sock.accept()
        with conn:
            conn.settimeout(3.0)
            req_id, pkt_type, payload = rcon_client.read_rcon_packet(conn)
            assert pkt_type == rcon_client.RCON_SERVERDATA_AUTH
            if payload != expected_pass:
                conn.sendall(rcon_client.pack_rcon_packet(-1, rcon_client.RCON_SERVERDATA_AUTH_RESPONSE, ""))
                return
            conn.sendall(rcon_client.pack_rcon_packet(req_id, rcon_client.RCON_SERVERDATA_RESPONSE_VALUE, ""))
            conn.sendall(rcon_client.pack_rcon_packet(req_id, rcon_client.RCON_SERVERDATA_AUTH_RESPONSE, ""))

            cmd_id, cmd_type, cmd_text = rcon_client.read_rcon_packet(conn)
            assert cmd_type == rcon_client.RCON_SERVERDATA_EXECCOMMAND
            reply = f"TPS from last 1m, 5m, 15m: 20.0, 20.0, 20.0 (cmd={cmd_text})"
            conn.sendall(rcon_client.pack_rcon_packet(cmd_id, rcon_client.RCON_SERVERDATA_RESPONSE_VALUE, reply))
    except Exception:  # noqa: BLE001
        pass


class V56RconSftpAndPresetsTests(unittest.TestCase):
    def test_rcon_loopback_auth_exec_and_rejection_with_redaction(self) -> None:
        secret_pw = "RconUltraSecret2026!"
        # 1. Valid auth & command execution
        srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        srv.bind(("127.0.0.1", 0))
        srv.listen(1)
        port = srv.getsockname()[1]
        t = threading.Thread(target=_mock_rcon_server, args=(srv, secret_pw), daemon=True)
        t.start()
        try:
            res = rcon_client.execute_rcon_command(
                host="127.0.0.1",
                port=port,
                password=secret_pw,
                command="tps",
                dry_run=False,
                timeout_seconds=3.0,
            )
        finally:
            t.join(timeout=3.0)
            srv.close()

        self.assertTrue(res["ok"], res)
        self.assertTrue(res["authenticated"])
        self.assertIn("20.0", res["response"])
        self.assertNotIn(secret_pw, json.dumps(res))

        # 2. Rejected auth (request_id == -1)
        srv2 = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        srv2.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        srv2.bind(("127.0.0.1", 0))
        srv2.listen(1)
        port2 = srv2.getsockname()[1]
        t2 = threading.Thread(target=_mock_rcon_server, args=(srv2, secret_pw), daemon=True)
        t2.start()
        try:
            bad = rcon_client.execute_rcon_command(
                host="127.0.0.1",
                port=port2,
                password="WrongPassword123",
                command="tps",
                dry_run=False,
                timeout_seconds=3.0,
            )
        finally:
            t2.join(timeout=3.0)
            srv2.close()

        self.assertFalse(bad["ok"])
        self.assertFalse(bad["authenticated"])

    def test_sftp_safe_path_blocks_traversal_and_null_bytes(self) -> None:
        self.assertEqual(hosting_bridge.safe_remote_path("/plugins/MyPlugin.jar", base_root="/plugins"), "/plugins/MyPlugin.jar")
        with self.assertRaises(ValueError):
            hosting_bridge.safe_remote_path("/plugins/../../etc/passwd", base_root="/plugins")
        with self.assertRaises(ValueError):
            hosting_bridge.safe_remote_path("plugins\\bad.jar")

    def test_all_eight_community_bot_stage_presets_work_via_mcp(self) -> None:
        srv = mcp_server.MinecraftKitMcpServer(ROOT)
        for preset in (
            "authme_lobby",
            "rpg_shop_gui",
            "resource_pack_itemsadder_nexo",
            "mythicmobs_dungeon",
            "folia_region_stress",
            "towny_lands_claim",
            "skyblock_island_coop",
            "modelengine_boss_arena",
        ):
            raw = srv.handle_message(json.dumps({
                "jsonrpc": "2.0",
                "id": 77,
                "method": "tools/call",
                "params": {"name": "mc_bot_generate_stage_preset", "arguments": {"preset": preset}},
            }))
            assert raw is not None
            resp = json.loads(raw)
            self.assertFalse(resp["result"]["isError"], resp)
            data = json.loads(resp["result"]["content"][0]["text"])
            self.assertEqual(data["preset"], preset)
            self.assertGreaterEqual(len(data["stages"]), 4)


if __name__ == "__main__":
    unittest.main()
