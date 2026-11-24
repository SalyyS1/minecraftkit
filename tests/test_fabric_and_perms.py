#!/usr/bin/env python3
"""Unit tests for mc_bot_generate_fabric_capture_script and mc_audit_permissions_rbac (v4.5.0 — 64 MCP tools)."""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import mcp_server  # noqa: E402


class FabricCaptureAndPermissionsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.server = mcp_server.MinecraftKitMcpServer(ROOT)

    def _call(self, name: str, arguments: dict) -> dict:
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
        return json.loads(res["content"][0]["text"])

    def test_fabric_capture_recipe_enforces_xvfb_and_memory_cap(self) -> None:
        res = self._call(
            "mc_bot_generate_fabric_capture_script",
            {
                "server_host": "127.0.0.1",
                "server_port": 25565,
                "mc_version": "1.21.4",
                "resolution": "1280x720",
                "memory_limit_mb": 1536,
                "record_mp4": True,
            },
        )
        self.assertTrue(res["ok"])
        self.assertTrue(res["screen_lock_free"])
        self.assertEqual(res["memory_limit_mb"], 1536)
        self.assertIn("Xvfb :99", res["runner_script"])
        self.assertIn("x11grab", res["runner_script"])
        self.assertIn("mckit-fabric-capture/v1", res["manifest_json"])

    def test_permissions_auditor_catches_wildcards_default_true_escalation_and_cycles(self) -> None:
        bad = self._call(
            "mc_audit_permissions_rbac",
            {
                "plugin_yml": "name: Demo\npermissions:\n  demo.admin.reload:\n    default: true\n",
                "groups": {
                    "default": {"permissions": ["*", "minecraft.command.op"], "parents": ["vip"]},
                    "vip": {"permissions": ["demo.fly"], "parents": ["admin", "default"]},
                    "admin": {"permissions": ["*"], "parents": []},
                },
            },
        )
        self.assertFalse(bad["ok"])
        codes = {f["code"] for f in bad["findings"]}
        self.assertIn("PERM-001", codes)
        self.assertIn("PERM-002", codes)
        self.assertIn("PERM-003", codes)
        self.assertIn("PERM-004", codes)
        self.assertIn("PERM-005", codes)

        good = self._call(
            "mc_audit_permissions_rbac",
            {
                "plugin_yml": "name: Demo\npermissions:\n  demo.admin.reload:\n    default: op\n",
                "groups": {
                    "default": {"permissions": ["demo.shop.use"], "parents": []},
                    "vip": {"permissions": ["demo.home.3"], "parents": ["default"]},
                    "admin": {"permissions": ["demo.admin.reload"], "parents": ["vip"]},
                },
            },
        )
        self.assertTrue(good["ok"])
        self.assertEqual(good["grade"], "A")


if __name__ == "__main__":
    unittest.main()
