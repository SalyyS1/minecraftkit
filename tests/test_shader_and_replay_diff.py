#!/usr/bin/env python3
"""Unit tests for mc_audit_shader_pack and mc_bot_compare_stage_runs (v4.9.0 — 72 MCP tools)."""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import mcp_server  # noqa: E402


class ShaderAndReplayDiffTests(unittest.TestCase):
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

    def test_shader_auditor_catches_legacy_gl_builtins_std140_vec3_and_heavy_loops(self) -> None:
        bad = self._call(
            "mc_audit_shader_pack",
            {
                "filename": "custom_glow.fsh",
                "source": (
                    "#version 120\n"
                    "layout(std140) uniform Globals {\n"
                    "    vec3 SunDir;\n"
                    "    float Time;\n"
                    "};\n"
                    "void main() {\n"
                    "    vec4 c = texture2D(Sampler0, texCoord0);\n"
                    "    for (int i = 0; i < 256; i++) { c.rgb *= 0.99; }\n"
                    "}\n"
                ),
            },
        )
        self.assertFalse(bad["ok"])
        codes = {f["code"] for f in bad["findings"]}
        self.assertIn("SHD-001", codes)
        self.assertIn("SHD-002", codes)
        self.assertIn("SHD-004", codes)
        self.assertIn("SHD-005", codes)

        good = self._call(
            "mc_audit_shader_pack",
            {
                "filename": "clean.fsh",
                "source": (
                    "#version 150\n"
                    "uniform sampler2D Sampler0;\n"
                    "in vec2 texCoord0;\n"
                    "out vec4 fragColor;\n"
                    "void main() {\n"
                    "    vec4 c = texture(Sampler0, texCoord0);\n"
                    "    if (c.a < 0.1) { discard; }\n"
                    "    fragColor = c;\n"
                    "}\n"
                ),
            },
        )
        self.assertTrue(good["ok"])
        self.assertEqual(good["grade"], "A")

    def test_bot_replay_diff_flags_status_latency_and_error_regressions(self) -> None:
        diff = self._call(
            "mc_bot_compare_stage_runs",
            {
                "baseline_stages": [
                    {"name": "Auto-Auth", "status": "PASS", "elapsed_ms": 120, "server_errors": 0},
                    {"name": "Open /shop", "status": "PASS", "elapsed_ms": 80, "server_errors": 0},
                ],
                "candidate_stages": [
                    {"name": "Auto-Auth", "status": "PASS", "elapsed_ms": 195, "server_errors": 0},
                    {"name": "Open /shop", "status": "FAIL", "elapsed_ms": 90, "server_errors": 2},
                ],
                "max_latency_increase_pct": 30.0,
            },
        )
        self.assertFalse(diff["ok"])
        self.assertGreaterEqual(diff["regression_count"], 3)
        self.assertIn("REGRESSION", diff["markdown"])


if __name__ == "__main__":
    unittest.main()
