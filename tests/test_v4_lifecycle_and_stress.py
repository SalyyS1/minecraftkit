from __future__ import annotations

import json
import socket
import sys
import tempfile
import threading
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import mc_proto_client  # noqa: E402
from mcp_server import MinecraftKitMcpServer  # noqa: E402


class V4LifecycleAndStressTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.server = MinecraftKitMcpServer(root=ROOT)

    def _call_raw(self, name: str, args: dict[str, object]) -> dict[str, object]:
        raw = self.server.handle_message(json.dumps({
            "jsonrpc": "2.0",
            "id": 400,
            "method": "tools/call",
            "params": {"name": name, "arguments": args},
        }))
        assert raw is not None
        res = json.loads(raw)["result"]
        self.assertFalse(res["isError"], res)
        return res

    def test_bot_stress_benchmark_measures_concurrent_loopback_slp_p95(self) -> None:
        srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        srv.bind(("127.0.0.1", 0))
        srv.listen(16)
        port = srv.getsockname()[1]

        status_json = json.dumps({
            "version": {"name": "Paper 1.21.4", "protocol": 769},
            "players": {"max": 100, "online": 3},
            "description": {"text": "MCKit Stress Target"},
        })
        resp_pkt = mc_proto_client.frame_packet(0x00, mc_proto_client.encode_mc_string(status_json))

        def serve_three() -> None:
            try:
                for _ in range(3):
                    conn, _ = srv.accept()
                    with conn:
                        conn.recv(256)
                        conn.sendall(resp_pkt)
            finally:
                srv.close()

        t = threading.Thread(target=serve_three, daemon=True)
        t.start()
        res = self._call_raw("mc_bot_stress_benchmark", {
            "host": "127.0.0.1",
            "port": port,
            "bot_count": 3,
            "mode": "slp",
            "timeout_seconds": 3.0,
        })
        t.join(timeout=3.0)
        payload = json.loads(res["content"][0]["text"])
        self.assertTrue(payload["ok"], payload)
        self.assertEqual(payload["succeeded"], 3)
        self.assertEqual(payload["estimated_total_ram_mb"], 54)
        self.assertTrue(payload["screen_lock_free"])
        self.assertGreaterEqual(payload["latency_ms"]["p95"], 0.0)

    def test_full_lifecycle_orchestrator_chains_all_5_phases_and_writes_html(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            out_html = Path(td) / "lifecycle-proof.html"
            res = self._call_raw("mc_qa_run_full_lifecycle", {
                "project_name": "SalyRPG v4",
                "server_host": "play.salyvn.net",
                "bot_count": 10,
                "host_ram_gb": 8.0,
                "plugins": ["MythicLib-1.6.jar", "MMOItems-6.10.jar", "LuckPerms-5.4.jar"],
                "panel_domain": "panel.salyvn.net",
                "preset": "rpg_shop_gui",
                "html_output_path": str(out_html),
            })
            self.assertEqual(len(res["content"]), 2)
            self.assertEqual(res["content"][1]["type"], "image")
            payload = json.loads(res["content"][0]["text"])
            self.assertTrue(payload["ok"], payload)
            self.assertEqual(payload["verdict"], "PASS")
            self.assertTrue(payload["preview_attached_as_mcp_image"])
            self.assertTrue(out_html.is_file())
            self.assertIn("SalyRPG v4", out_html.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
