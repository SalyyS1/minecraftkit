"""Unit tests for MinecraftKit Bot QA Engine, Visual Capture, Hosting/2FA/SFTP, and Unified Suite."""

from __future__ import annotations

import base64
import json
import socket
import struct
import sys
import threading
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import bot_engine  # noqa: E402
import hosting_bridge  # noqa: E402
import toolchain_bridge  # noqa: E402
import visual_capture  # noqa: E402
from mcp_server import MinecraftKitMcpServer  # noqa: E402


class BotVisualHostingSuiteTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.server = MinecraftKitMcpServer(root=ROOT)

    def _call_raw(self, name: str, arguments: dict[str, object]) -> dict[str, object]:
        raw = self.server.handle_message(json.dumps({
            "jsonrpc": "2.0",
            "id": 99,
            "method": "tools/call",
            "params": {"name": name, "arguments": arguments},
        }))
        assert raw is not None
        parsed = json.loads(raw)
        self.assertNotIn("error", parsed, parsed)
        return parsed["result"]

    def test_visual_capture_produces_valid_png_magic_and_dimensions(self) -> None:
        png = visual_capture.render_bot_snapshot_png({
            "username": "QA_Bot01",
            "server": "play.example.vn:25565",
            "version": "26.3",
            "auth_state": "AUTHENTICATED",
            "status": "PASSED",
            "open_gui": {
                "title": "§6RPG Shop",
                "slots": [
                    {"slot": 13, "name": "Mythic Blade", "count": 1, "enchanted": True, "lore": ["+45 Attack", "Price: 500G"]},
                ],
            },
            "scoreboard": {"title": "§bSalyVN RPG", "lines": ["Coins: 1,250", "Level: 42"]},
            "chat": ["[Auth] Successfully logged in.", "[Shop] Opened RPG Shop."],
            "entities": [{"x": 4, "z": -3, "hostile": True}, {"x": -6, "z": 5, "hostile": False}],
            "stages": [{"name": "Auto login", "passed": True}, {"name": "Open /shop GUI", "passed": True}],
        })
        self.assertTrue(png.startswith(b"\x89PNG\r\n\x1a\n"))
        w, h = struct.unpack(">II", png[16:24])
        self.assertEqual((w, h), (960, 580))

    def test_bot_resource_planner_prevents_desktop_tab_oom(self) -> None:
        plan = bot_engine.plan_bot_resources(bot_count=10, host_ram_gb=8.0, needs_shader_or_3d_render=True)
        self.assertEqual(plan["recommended_strategy"], "hybrid-1-visual-plus-protocol")
        self.assertTrue(plan["screen_lock_free"])
        mem = plan["memory_comparison_mb"]
        self.assertLess(mem["hybrid_1_visual_plus_protocol"], mem["desktop_minecraft_tabs"])
        self.assertGreater(mem["ram_saved_vs_desktop_pct"], 85.0)
        self.assertTrue(len(plan["warnings"]) >= 1)

    def test_native_slp_ping_against_local_mock_tcp_server(self) -> None:
        payload_json = json.dumps({
            "version": {"name": "Paper 26.3", "protocol": 775},
            "players": {"max": 100, "online": 3},
            "description": {"text": "SalyVN Test Server"},
        }).encode("utf-8")
        body = bot_engine._encode_varint(0x00) + bot_engine._encode_varint(len(payload_json)) + payload_json
        packet = bot_engine._encode_varint(len(body)) + body

        srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        srv.bind(("127.0.0.1", 0))
        port = srv.getsockname()[1]
        srv.listen(1)

        def _serve_once() -> None:
            conn, _ = srv.accept()
            with conn:
                conn.recv(256)
                conn.sendall(packet)
            srv.close()

        t = threading.Thread(target=_serve_once, daemon=True)
        t.start()
        res = bot_engine.ping_minecraft_server("127.0.0.1", port, timeout_seconds=2.0)
        t.join(timeout=2.0)
        self.assertTrue(res["reachable"])
        self.assertEqual(res["version"]["name"], "Paper 26.3")
        self.assertEqual(res["players"]["online"], 3)

    def test_bot_stage_runner_auto_auth_redacts_password_and_returns_mcp_image(self) -> None:
        secret = "SuperSecretPass99!"
        result = self._call_raw("mc_bot_run_stages", {
            "host": "127.0.0.1",
            "port": 25565,
            "username": "TestHero",
            "password": secret,
            "mode": "simulate",
            "initial_state": {
                "chat": ["[AuthMe] Vui long dang ky: /register <password> <password>"],
                "scoreboard": {"title": "RPG Hub", "lines": ["Rank: Warrior"]},
                "tps": 19.9,
            },
            "stages": [
                {"name": "Join", "action": "join"},
                {"name": "Auto Register", "action": "auth"},
                {"name": "Open Shop", "action": "command", "command": "/shop", "mock_gui": {"title": "RPG Shop", "slots": [{"slot": 0, "name": "Sword", "count": 1}]}},
                {"name": "Verify Shop GUI", "action": "assert_gui", "title_pattern": "RPG Shop", "min_populated_slots": 1},
                {"name": "Verify TPS", "action": "assert_tps", "min_tps": 19.0},
                {"name": "Snap", "action": "capture"},
            ],
            "capture_snapshot": True,
        })
        self.assertFalse(result["isError"])
        content = result["content"]
        self.assertEqual(len(content), 2)
        self.assertEqual(content[0]["type"], "text")
        self.assertEqual(content[1]["type"], "image")
        self.assertEqual(content[1]["mimeType"], "image/png")
        decoded_png = base64.b64decode(content[1]["data"])
        self.assertTrue(decoded_png.startswith(b"\x89PNG\r\n\x1a\n"))
        # Password must NEVER leak into the JSON text!
        self.assertNotIn(secret, content[0]["text"])
        body = json.loads(content[0]["text"])
        self.assertTrue(body["ok"])
        self.assertEqual(body["summary"]["auth_state"], "AUTHENTICATED")
        self.assertEqual(body["summary"]["failed"], 0)

    def test_totp_rfc6238_vector_and_hosting_redaction(self) -> None:
        # RFC 6238 standard SHA1 test vector: ASCII "12345678901234567890" -> Base32 GEZDGNBVGY3TQOJQGEZDGNBVGY3TQOJQ
        secret_b32 = "GEZDGNBVGY3TQOJQGEZDGNBVGY3TQOJQ"
        totp_59 = hosting_bridge.generate_totp(secret_b32, timestamp=59, digits=8, period=30, algorithm="SHA1")
        self.assertEqual(totp_59["code"], "94287082")

        plan_res = self._call_raw("mc_hosting_connect_plan", {
            "domain": "panel.example.gg",
            "panel_type": "pterodactyl",
            "username": "admin@example.gg",
            "has_password": True,
            "totp_secret": secret_b32,
            "server_id": "srv-01",
        })
        text = plan_res["content"][0]["text"]
        self.assertNotIn(secret_b32, text)
        parsed = json.loads(text)
        self.assertTrue(parsed["headless"])
        self.assertTrue(parsed["two_factor"]["configured"])

    def test_sftp_path_traversal_guard_and_dry_run_plan(self) -> None:
        self.assertEqual(hosting_bridge.safe_remote_path("/plugins/../plugins/test.jar"), "/plugins/test.jar")
        with self.assertRaises(ValueError):
            hosting_bridge.safe_remote_path("/etc/passwd", base_root="/home/container")

        sftp_res = self._call_raw("mc_sftp_operations", {
            "host": "10.0.0.5",
            "port": 2022,
            "username": "sftpuser",
            "password": "MySftpPassword123",
            "operation": "deploy_jar",
            "remote_path": "/plugins/MyRPG.jar",
            "local_path": "build/libs/MyRPG.jar",
            "dry_run": True,
        })
        text = sftp_res["content"][0]["text"]
        self.assertNotIn("MySftpPassword123", text)
        parsed = json.loads(text)
        self.assertTrue(parsed["dry_run"])
        self.assertTrue(parsed["safety_checks"]["path_traversal_blocked"])

    def test_unified_suite_catalog_and_end_to_end_qa_pipeline(self) -> None:
        catalog_res = self._call_raw("mc_suite_catalog", {})
        cat = json.loads(catalog_res["content"][0]["text"])
        tool_ids = {t["id"] for t in cat["tools"]}
        self.assertEqual(cat["tool_count"], 10)
        for expected in ("mcstage", "shadersmith", "packmigrate", "packmerge", "glyphsmith", "pluginscope", "serverdoctor", "foliascan", "rp-engine", "texlab"):
            self.assertIn(expected, tool_ids)

        qa_res = self._call_raw("mc_run_qa_pipeline", {
            "project_name": "OZbanghoi",
            "target_mc_version": "26.3",
            "plugin_jar": "build/libs/OZbanghoi.jar",
            "resource_pack_dir": "./pack",
            "panel_domain": "panel.salyvn.net",
            "sftp_host": "192.0.2.10",
            "sftp_user": "mcdev",
            "bot_count": 10,
            "needs_visual_render": True,
            "initial_bot_state": {
                "chat": ["[Server] Welcome to OZbanghoi"],
                "tps": 20.0,
            },
            "stages": [
                {"name": "Join", "action": "join"},
                {"name": "Check guild menu", "action": "command", "command": "/guild", "mock_gui": {"title": "Bang Hoi", "slots": [{"slot": 11, "name": "War", "count": 1}]}},
                {"name": "Assert Guild GUI", "action": "assert_gui", "title_pattern": "Bang Hoi"},
            ],
        })
        self.assertEqual(len(qa_res["content"]), 2)
        self.assertEqual(qa_res["content"][1]["type"], "image")
        body = json.loads(qa_res["content"][0]["text"])
        self.assertTrue(body["ok"])
        self.assertEqual(len(body["pipeline_steps"]), 5)

    def test_profile_vault_masks_secrets_and_roundtrips(self) -> None:
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            vpath = str(Path(tmpdir) / "profiles.json")
            saved = self._call_raw("mc_ops_profile_vault", {
                "action": "save",
                "name": "salyvn-rpg",
                "vault_path": vpath,
                "fields": {
                    "mc_host": "play.salyvn.net",
                    "panel_domain": "panel.salyvn.net",
                    "password": "DoNotLeakPassword!",
                    "totp_secret": "GEZDGNBVGY3TQOJQ",
                    "api_key": "env:MCKIT_PANEL_TOKEN",
                },
            })
            txt = saved["content"][0]["text"]
            self.assertNotIn("DoNotLeakPassword!", txt)
            self.assertNotIn("GEZDGNBVGY3TQOJQ", txt)
            self.assertIn("env:MCKIT_PANEL_TOKEN", txt)

            listed = json.loads(self._call_raw("mc_ops_profile_vault", {"action": "list", "vault_path": vpath})["content"][0]["text"])
            self.assertEqual(listed["profile_count"], 1)
            deleted = json.loads(self._call_raw("mc_ops_profile_vault", {"action": "delete", "name": "salyvn-rpg", "vault_path": vpath})["content"][0]["text"])
            self.assertTrue(deleted["deleted"])

    def test_freeform_bot_session_visual_diff_and_timelapse(self) -> None:
        import tempfile
        start = self._call_raw("mc_bot_session_start", {
            "host": "127.0.0.1",
            "username": "FreeTester",
            "password": "MyPassword77",
            "initial_state": {"chat": ["[AuthMe] Please /login <pass>"]},
        })
        self.assertEqual(len(start["content"]), 2)
        self.assertNotIn("MyPassword77", start["content"][0]["text"])
        s_body = json.loads(start["content"][0]["text"])
        sid = s_body["session_id"]

        act = self._call_raw("mc_bot_session_action", {
            "session_id": sid,
            "action": "command",
            "message": "/shop",
            "mock_gui": {"title": "Weapon Shop", "slots": [{"slot": 13, "name": "Excalibur", "count": 1}]},
        })
        self.assertEqual(len(act["content"]), 2)
        a_body = json.loads(act["content"][0]["text"])
        self.assertEqual(a_body["frame_count"], 2)

        with tempfile.TemporaryDirectory() as tmpdir:
            tl = self._call_raw("mc_bot_capture_timelapse", {"session_id": sid, "output_dir": tmpdir, "fps": 2})
            tl_body = json.loads(tl["content"][0]["text"])
            self.assertEqual(tl_body["frame_count"], 2)

        diff = self._call_raw("mc_bot_visual_diff", {
            "baseline_state": s_body["state"],
            "candidate_state": a_body["state"],
        })
        self.assertEqual(len(diff["content"]), 2)
        self.assertEqual(diff["content"][1]["type"], "image")
        d_body = json.loads(diff["content"][0]["text"])
        self.assertFalse(d_body["identical"])
        self.assertGreater(d_body["changed_pixels"], 0)

        stopped = json.loads(self._call_raw("mc_bot_session_stop", {"session_id": sid})["content"][0]["text"])
        self.assertTrue(stopped["stopped"])


if __name__ == "__main__":
    unittest.main()
