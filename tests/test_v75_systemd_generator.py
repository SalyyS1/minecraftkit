"""Tests for v7.5.0 mc_ops_generate_systemd_unit (81st MCP Tool!)."""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from mcp_server import MinecraftKitMcpServer  # noqa: E402


class TestSystemdGenerator(unittest.TestCase):
    def setUp(self) -> None:
        self.server = MinecraftKitMcpServer(root=ROOT)

    def _call(self, name: str, arguments: dict) -> tuple[dict, bool]:
        raw = self.server.handle_message(json.dumps({
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {"name": name, "arguments": arguments},
        }))
        assert raw is not None
        res = json.loads(raw)["result"]
        txt = res["content"][0]["text"]
        is_err = bool(res.get("isError", False))
        return ({"error": txt} if is_err else json.loads(txt)), is_err

    def test_generates_hardened_folia_zgc_systemd_unit(self) -> None:
        payload, is_err = self._call(
            "mc_ops_generate_systemd_unit",
            {
                "service_name": "mc-folia-rpg",
                "server_type": "folia",
                "work_dir": "/srv/minecraft/folia",
                "jar_name": "folia-1.21.4.jar",
                "heap_gb": 12,
                "gc_engine": "zgc",
            },
        )
        self.assertFalse(is_err)
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["unit_path"], "/etc/systemd/system/mc-folia-rpg.service")
        unit = payload["unit_content"]
        self.assertIn("-XX:+UseZGC", unit)
        self.assertIn("-XX:+ZGenerational", unit)
        self.assertIn("ProtectSystem=strict", unit)
        self.assertIn("NoNewPrivileges=true", unit)
        self.assertIn("MemoryMax=16G", unit)

    def test_rejects_work_dir_path_traversal(self) -> None:
        payload, is_err = self._call(
            "mc_ops_generate_systemd_unit",
            {"work_dir": "/srv/minecraft/../../etc"},
        )
        self.assertTrue(is_err)


if __name__ == "__main__":
    unittest.main()
