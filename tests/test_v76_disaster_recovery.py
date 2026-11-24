"""Tests for v7.6.0 mc_ops_plan_disaster_recovery (82nd MCP Tool!)."""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from mcp_server import MinecraftKitMcpServer  # noqa: E402


class TestDisasterRecoveryPlanner(unittest.TestCase):
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

    def test_plans_anvil_safe_r2_backup_and_restore_drill(self) -> None:
        payload, is_err = self._call(
            "mc_ops_plan_disaster_recovery",
            {
                "server_name": "SkyRPG",
                "world_size_gb": 20.0,
                "retention_days": 7,
                "backup_interval_hours": 6,
                "offsite_target": "r2",
            },
        )
        self.assertFalse(is_err)
        self.assertTrue(payload["ok"])
        self.assertTrue(payload["anvil_safe_save_flush"])
        self.assertTrue(payload["secrets_from_env_only"])
        self.assertEqual(payload["rpo_hours"], 6)
        self.assertEqual(payload["total_retained_snapshots"], 28)
        self.assertIn("save-off", payload["backup_script_sh"])
        self.assertIn("save-all flush", payload["backup_script_sh"])
        self.assertIn("trap cleanup EXIT", payload["backup_script_sh"])
        self.assertIn("mcstage check-world", json.dumps(payload["restore_verification_drill"]))


if __name__ == "__main__":
    unittest.main()
