#!/usr/bin/env python3
"""Unit tests for mc_bot_record_stage_gif and mc_ops_vps_ssh_preflight (v4.4.0 — 62 MCP tools)."""

from __future__ import annotations

import base64
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import mcp_server  # noqa: E402


class GifRecorderAndVpsPreflightTests(unittest.TestCase):
    def setUp(self) -> None:
        self.server = mcp_server.MinecraftKitMcpServer(ROOT)

    def _call_raw(self, name: str, arguments: dict) -> dict:
        req = json.dumps({
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {"name": name, "arguments": arguments},
        })
        raw = self.server.handle_message(req)
        assert raw is not None
        resp = json.loads(raw)
        res = resp["result"]
        self.assertFalse(res["isError"], res)
        return res

    def test_stage_gif_recorder_returns_storyboard_mcp_image_and_redacts_passwords(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            gif_path = Path(td) / "bot-walkthrough.gif"
            res = self._call_raw(
                "mc_bot_record_stage_gif",
                {
                    "bot_name": "MCKitQA",
                    "server_target": "127.0.0.1:25565",
                    "output_gif_path": str(gif_path),
                    "stages": [
                        {"name": "Join", "status": "PASS", "chat": ["Joined server"]},
                        {"name": "Auth", "status": "PASS", "chat": ["/login SecretPass999!"]},
                        {"name": "Shop GUI", "status": "PASS", "gui_title": "RPG Shop"},
                    ],
                },
            )
            payload = json.loads(res["content"][0]["text"])
            self.assertTrue(payload["ok"])
            self.assertEqual(payload["frame_count"], 3)
            self.assertTrue(payload["storyboard_attached_as_mcp_image"])
            self.assertNotIn("SecretPass999!", json.dumps(payload))
            # Verify MCP image/png attachment exists and starts with PNG signature
            self.assertEqual(len(res["content"]), 2)
            self.assertEqual(res["content"][1]["type"], "image")
            self.assertEqual(res["content"][1]["mimeType"], "image/png")
            png_bytes = base64.b64decode(res["content"][1]["data"])
            self.assertTrue(png_bytes.startswith(b"\x89PNG\r\n\x1a\n"))
            if payload["ffmpeg_available"]:
                self.assertTrue(gif_path.is_file())
                self.assertGreater(payload["gif_bytes"], 100)

    def test_vps_ssh_preflight_computes_anti_oom_heap_and_ufw_rules(self) -> None:
        res = self._call_raw(
            "mc_ops_vps_ssh_preflight",
            {
                "vps_ram_gb": 16,
                "vps_vcpu": 8,
                "proxy_mode": "velocity-network",
                "server_port": 25566,
                "bridge_port": 25590,
                "rcon_enabled": True,
                "concurrent_bots": 10,
                "enable_visual_docker_bot": True,
            },
        )
        payload = json.loads(res["content"][0]["text"])
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["memory_budget_mb"]["tier1_protocol_bots_mb"], 420)
        self.assertEqual(payload["memory_budget_mb"]["tier2_visual_docker_mb"], 1400)
        self.assertIn("-XX:+UseZGC", payload["recommended_jvm_command"])
        self.assertTrue(any("ufw deny 25566/tcp" in r for r in payload["ufw_firewall_plan"]))
        self.assertTrue(any("ufw deny 25590/tcp" in r for r in payload["ufw_firewall_plan"]))


if __name__ == "__main__":
    unittest.main()
