#!/usr/bin/env python3
"""Unit tests for mc_world_audit_integrity and mc_audit_proxy_topology (v4.2.0)."""

from __future__ import annotations

import json
import struct
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import mcp_server  # noqa: E402


class WorldAndProxyAuditTests(unittest.TestCase):
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

    def test_world_integrity_valid_and_corrupted_cases(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            world = Path(td) / "world"
            (world / "region").mkdir(parents=True)
            (world / "playerdata").mkdir(parents=True)
            # Valid GZIP level.dat & playerdata
            (world / "level.dat").write_bytes(b"\x1f\x8b" + b"\x00" * 30)
            (world / "level.dat_old").write_bytes(b"\x1f\x8b" + b"\x00" * 30)
            (world / "playerdata" / "00000000-0000-0000-0000-000000000001.dat").write_bytes(b"\x1f\x8b" + b"\x00" * 20)
            # Valid 3-sector (12288 B) Anvil .mca with 1 chunk at sector 2, count 1
            mca = bytearray(4096 * 3)
            struct.pack_into(">I", mca, 0, (2 << 8) | 1)
            (world / "region" / "r.0.0.mca").write_bytes(bytes(mca))

            ok_rep = self._call("mc_world_audit_integrity", {"world_dir": str(world), "require_session_lock_cleared": True})
            self.assertTrue(ok_rep["ok"])
            self.assertEqual(ok_rep["grade"], "A")
            self.assertEqual(ok_rep["valid_chunk_headers"], 1)
            self.assertEqual(ok_rep["playerdata_files_scanned"], 1)

            # Corrupt a region file and add empty playerdata
            (world / "region" / "r.0.1.mca").write_bytes(b"\x00" * 512)
            (world / "playerdata" / "bad.dat").write_bytes(b"NOT_GZIP")
            bad_rep = self._call("mc_world_audit_integrity", {"world_dir": str(world)})
            self.assertFalse(bad_rep["ok"])
            codes = {i["code"] for i in bad_rep["issues"]}
            self.assertIn("WORLD-003", codes)
            self.assertIn("WORLD-004", codes)

    def test_proxy_topology_catches_spoofing_and_redacts_secrets(self) -> None:
        secret = "SuperSecretVelocityToken987654321"
        bad = self._call(
            "mc_audit_proxy_topology",
            {
                "velocity_toml": 'player-info-forwarding-mode = "legacy"\nonline-mode = true\n',
                "forwarding_secret": "short",
                "paper_global_yml": "proxies:\n  velocity:\n    enabled: false\n    secret: different-secret-value\n",
                "backend_server_properties": "online-mode=false\nserver-ip=0.0.0.0\n",
                "geyser_config_yml": "remote:\n  auth-type: offline\n",
            },
        )
        self.assertFalse(bad["ok"])
        codes = {f["code"] for f in bad["findings"]}
        self.assertIn("PROXY-001", codes)
        self.assertIn("PROXY-002", codes)
        self.assertIn("PROXY-003", codes)
        self.assertIn("PROXY-004", codes)
        self.assertIn("PROXY-005", codes)

        good = self._call(
            "mc_audit_proxy_topology",
            {
                "velocity_toml": 'player-info-forwarding-mode = "modern"\nonline-mode = true\n',
                "forwarding_secret": secret,
                "paper_global_yml": f"proxies:\n  velocity:\n    enabled: true\n    online-mode: true\n    secret: '{secret}'\n",
                "backend_server_properties": "online-mode=false\nserver-ip=127.0.0.1\n",
                "geyser_config_yml": "remote:\n  auth-type: floodgate\n",
            },
        )
        self.assertTrue(good["ok"])
        self.assertEqual(good["grade"], "A")
        # Secret must NEVER leak in raw output
        self.assertNotIn(secret, json.dumps(good))


if __name__ == "__main__":
    unittest.main()
