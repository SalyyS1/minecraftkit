"""Tests for v7.2.0 mc_ops_audit_paper_config Paper/Purpur/Spigot/Folia config auditor."""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from mcp_server import MinecraftKitMcpServer  # noqa: E402


class TestPaperConfigAuditor(unittest.TestCase):
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
        return json.loads(res["content"][0]["text"]), bool(res.get("isError", False))

    def test_optimized_config_passes_grade_a(self) -> None:
        cfg = """
sync-chunk-writes=false
view-distance=10
simulation-distance=6
network-compression-threshold=256
region-file-compression=lz4
per-player-mob-spawns: true
monsters: 42
hopper-check: 3
prevent-moving-into-unloaded-chunks: true
"""
        payload, is_err = self._call(
            "mc_ops_audit_paper_config",
            {"config_text": cfg, "expected_players": 60, "is_folia": True},
        )
        self.assertFalse(is_err)
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["grade"], "A")
        self.assertEqual(payload["finding_count"], 0)

    def test_catches_all_five_lag_and_safety_rules(self) -> None:
        bad_cfg = """
sync-chunk-writes=true
view-distance=16
simulation-distance=12
network-compression-threshold=64
region-file-compression=zlib
monsters: 90
hopper-check: 1
per-player-mob-spawns: false
treasure-maps-find-already-discovered: false
anti-xray:
  enabled: false
prevent-moving-into-unloaded-chunks: false
"""
        payload, is_err = self._call(
            "mc_ops_audit_paper_config",
            {"config_text": bad_cfg, "expected_players": 80, "is_folia": True},
        )
        self.assertFalse(is_err)
        self.assertFalse(payload["ok"])
        self.assertEqual(payload["grade"], "F")
        codes = {f["rule_id"] for f in payload["findings"]}
        for expected in ("CFG-001", "CFG-002", "CFG-003", "CFG-004", "CFG-005"):
            self.assertIn(expected, codes)
        self.assertGreaterEqual(len(payload["recommended_patches"]), 6)


if __name__ == "__main__":
    unittest.main()
