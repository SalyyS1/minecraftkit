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
            "economy_dupe_race",
            "proxy_velocity_transfer",
            "mmocore_actionbar_hud",
            "geyser_bedrock_crossplay",
            "bedwars_minigame_arena",
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

    def test_sftp_verify_jar_and_pelican_console_hints(self) -> None:
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            jar = Path(td) / "SamplePlugin.jar"
            jar.write_bytes(b"PK\x03\x04fake-jar-bytes")
            plan = hosting_bridge.sftp_operation(
                host="10.0.0.9",
                port=2022,
                username="mcops",
                password="SecretSftpPass!",
                operation="verify_jar",
                remote_path="/plugins/SamplePlugin.jar",
                local_path=str(jar),
                dry_run=True,
            )
            self.assertTrue(plan["dry_run"])
            self.assertTrue(plan["local_artifact_check"]["exists"])
            self.assertTrue(plan["local_artifact_check"]["is_valid_zip_jar"])
            self.assertEqual(len(plan["local_artifact_check"]["sha256"]), 64)
            self.assertNotIn("SecretSftpPass!", json.dumps(plan))

        pelican = hosting_bridge.build_hosting_connection_plan(
            domain="pelican.example.gg",
            panel_type="pelican",
            server_id="srv99",
            has_api_key=True,
        )
        self.assertIn("console_ws", pelican["endpoints"])
        self.assertIn("sftp_details", pelican["endpoints"])

    def test_sftp_stat_world_and_hosting_list_files_via_mcp(self) -> None:
        srv = mcp_server.MinecraftKitMcpServer(ROOT)
        raw_world = srv.handle_message(json.dumps({
            "jsonrpc": "2.0",
            "id": 980,
            "method": "tools/call",
            "params": {
                "name": "mc_sftp_operations",
                "arguments": {
                    "host": "10.0.0.12",
                    "port": 2022,
                    "username": "mcops",
                    "password": "UltraHiddenSftpPassword!",
                    "operation": "stat_world",
                    "remote_path": "/world",
                    "dry_run": True,
                },
            },
        }))
        assert raw_world is not None
        resp_world = json.loads(raw_world)
        self.assertFalse(resp_world["result"]["isError"], resp_world)
        world_data = json.loads(resp_world["result"]["content"][0]["text"])
        self.assertEqual(world_data["stat_world_targets"]["level_dat"], "/world/level.dat")
        self.assertEqual(world_data["stat_world_targets"]["session_lock"], "/world/session.lock")
        self.assertNotIn("UltraHiddenSftpPassword!", raw_world)

        raw_files = srv.handle_message(json.dumps({
            "jsonrpc": "2.0",
            "id": 981,
            "method": "tools/call",
            "params": {
                "name": "mc_hosting_server_action",
                "arguments": {
                    "domain": "panel.example.gg",
                    "panel_type": "pelican",
                    "server_id": "srv42",
                    "action": "list_files",
                    "directory": "/plugins",
                    "api_key": "ptlc_SecretPanelToken999999999999",
                    "dry_run": True,
                },
            },
        }))
        assert raw_files is not None
        resp_files = json.loads(raw_files)
        self.assertFalse(resp_files["result"]["isError"], resp_files)
        files_data = json.loads(resp_files["result"]["content"][0]["text"])
        self.assertIn("/api/client/servers/srv42/files/list?directory=/plugins", files_data["request"]["url"])
        self.assertNotIn("ptlc_SecretPanelToken999999999999", raw_files)


if __name__ == "__main__":
    unittest.main()
