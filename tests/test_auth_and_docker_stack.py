#!/usr/bin/env python3
"""Unit tests for mc_bot_diagnose_auth_plugin and mc_ops_generate_docker_stack (v4.6.0 — 66 MCP tools)."""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import mcp_server  # noqa: E402


class AuthAndDockerStackTests(unittest.TestCase):
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

    def test_auth_plugin_auditor_catches_weak_hash_preauth_and_bot_ip_cap(self) -> None:
        bad = self._call(
            "mc_bot_diagnose_auth_plugin",
            {
                "plugin_type": "authme",
                "staging_bot_testing": True,
                "config_yml": "passwordHash: MD5\nallowChat: true\nallowMovement: true\nmaxRegPerIp: 1\nsessions: true\nsessionTimeout: 120\n",
            },
        )
        self.assertFalse(bad["ok"])
        codes = {f["code"] for f in bad["findings"]}
        self.assertIn("AUTH-001", codes)
        self.assertIn("AUTH-002", codes)
        self.assertIn("AUTH-003", codes)
        self.assertIn("AUTH-004", codes)

        good = self._call(
            "mc_bot_diagnose_auth_plugin",
            {
                "plugin_type": "nlogin",
                "staging_bot_testing": True,
                "config_yml": "passwordHash: ARGON2\nallowChat: false\nallowMovement: false\nmaxRegPerIp: 20\n",
            },
        )
        self.assertTrue(good["ok"])
        self.assertEqual(good["grade"], "A")

    def test_docker_stack_generator_enforces_loopback_and_mem_caps(self) -> None:
        res = self._call(
            "mc_ops_generate_docker_stack",
            {
                "server_type": "FOLIA",
                "mc_version": "1.21.4",
                "concurrent_bots": 10,
                "include_velocity": True,
                "include_visual_bot": True,
            },
        )
        self.assertTrue(res["ok"])
        self.assertTrue(res["screen_lock_free"])
        self.assertEqual(res["bot_pool_mem_limit_mb"], 10 * 42 + 128)
        self.assertIn('TYPE: "FOLIA"', res["yaml"])
        self.assertIn("velocity-proxy:", res["yaml"])
        self.assertIn("127.0.0.1:25590:25590", res["yaml"])
        self.assertIn("mem_limit: 1600m", res["yaml"])


if __name__ == "__main__":
    unittest.main()
