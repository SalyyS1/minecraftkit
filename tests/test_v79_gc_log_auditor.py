"""Tests for v7.9.0 mc_ops_audit_jvm_gc_log (85th MCP tool) & inline GC pause PNG chart."""

from __future__ import annotations

import base64
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import gc_log_auditor  # noqa: E402
from mcp_server import MinecraftKitMcpServer  # noqa: E402


BAD_G1_LOG = """
[10.000s][info][gc] GC(1) Pause Young (Concurrent Start) (G1 Humongous Allocation) 3400M->2900M(4096M) 88.4ms
[11.200s][info][gc] GC(2) To-space exhausted
[11.500s][info][gc] GC(3) Pause Full (System.gc()) 3950M->3100M(4096M) 420.5ms
[12.000s][info][gc] GC(4) Pause Young (Metadata GC Threshold) 3200M->2800M(4096M) 62.1ms
"""

CLEAN_ZGC_LOG = """
[100.000s][info][gc] GC(10) Pause Mark Start 0.08ms
[105.000s][info][gc] GC(10) Pause Mark End 0.12ms
[110.000s][info][gc] GC(10) Pause Relocate Start 0.09ms
[130.000s][info][gc] GC(11) Pause Mark Start 0.07ms
"""


class GcLogAuditorV79Tests(unittest.TestCase):
    def test_detects_all_five_gc_rules(self) -> None:
        report = gc_log_auditor.audit_jvm_gc_log(BAD_G1_LOG)
        self.assertFalse(report["ok"])
        self.assertEqual(report["status"], "fail")
        self.assertEqual(report["grade"], "F")
        self.assertEqual(report["gc_engine"], "G1GC")
        rule_ids = {f["rule_id"] for f in report["findings"]}
        self.assertEqual(rule_ids, {"GC-001", "GC-002", "GC-003", "GC-004", "GC-005"})
        self.assertGreater(report["summary"]["max_pause_ms"], 400.0)
        self.assertEqual(report["badge_json"]["color"], "red")

    def test_clean_zgc_log_passes_grade_a(self) -> None:
        report = gc_log_auditor.audit_jvm_gc_log(CLEAN_ZGC_LOG)
        self.assertTrue(report["ok"])
        self.assertEqual(report["status"], "pass")
        self.assertEqual(report["grade"], "A")
        self.assertEqual(report["gc_engine"], "ZGC")
        self.assertEqual(report["findings"], [])
        self.assertEqual(report["badge_json"]["color"], "brightgreen")

    def test_mcp_tool_attaches_inline_png_chart_and_validates_empty(self) -> None:
        server = MinecraftKitMcpServer(root=ROOT)
        raw = server.handle_message(json.dumps({
            "jsonrpc": "2.0",
            "id": 79,
            "method": "tools/call",
            "params": {
                "name": "mc_ops_audit_jvm_gc_log",
                "arguments": {"log_text": BAD_G1_LOG, "attach_chart": True},
            },
        }))
        assert raw is not None
        resp = json.loads(raw)
        content = resp["result"]["content"]
        self.assertEqual(len(content), 2)
        self.assertEqual(content[1]["type"], "image")
        self.assertEqual(content[1]["mimeType"], "image/png")
        png_bytes = base64.b64decode(content[1]["data"])
        self.assertTrue(png_bytes.startswith(b"\x89PNG\r\n\x1a\n"))

        err_raw = server.handle_message(json.dumps({
            "jsonrpc": "2.0",
            "id": 80,
            "method": "tools/call",
            "params": {"name": "mc_ops_audit_jvm_gc_log", "arguments": {"log_text": "   "}},
        }))
        assert err_raw is not None
        err_resp = json.loads(err_raw)
        self.assertTrue(err_resp["result"]["isError"])


if __name__ == "__main__":
    unittest.main()