from __future__ import annotations

import json
import os
import sys
import tempfile
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from mcp_server import MinecraftKitMcpServer  # noqa: E402


class QaReportAndBackupAuditTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.server = MinecraftKitMcpServer(root=ROOT)

    def _call_raw(self, name: str, arguments: dict[str, object]) -> dict[str, object]:
        raw = self.server.handle_message(json.dumps({
            "jsonrpc": "2.0",
            "id": 77,
            "method": "tools/call",
            "params": {"name": name, "arguments": arguments},
        }))
        assert raw is not None
        parsed = json.loads(raw)
        self.assertNotIn("error", parsed, parsed)
        return parsed["result"]

    def test_qa_html_report_redacts_secrets_escapes_html_and_attaches_png(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            out_file = Path(td) / "qa-proof.html"
            result = self._call_raw("mc_qa_generate_html_report", {
                "title": "RPG Release <script>alert(1)</script> QA",
                "server_target": "127.0.0.1:25565",
                "tps": 19.9,
                "mspt": 14.2,
                "stages": [
                    {"name": "Login", "status": "pass", "elapsed_ms": 110, "detail": "ok"},
                    {"name": "Shop GUI", "status": "fail", "elapsed_ms": 240, "detail": "Slot 13 shifted"},
                ],
                "chat_log": [
                    "[Bot] /login SuperSecretPass999",
                    "token=ptlc_1234567890123456789012345",
                ],
                "output_path": str(out_file),
            })
            self.assertFalse(result["isError"])
            content = result["content"]
            self.assertEqual(len(content), 2)
            self.assertEqual(content[1]["type"], "image")
            self.assertEqual(content[1]["mimeType"], "image/png")

            payload = json.loads(content[0]["text"])
            self.assertFalse(payload["ok"])
            self.assertEqual(payload["verdict"], "FAIL")
            self.assertEqual(payload["passed_stages"], 1)
            self.assertEqual(payload["failed_stages"], 1)
            self.assertTrue(payload["preview_attached_as_mcp_image"])
            self.assertTrue(out_file.is_file())

            html_text = out_file.read_text(encoding="utf-8")
            self.assertNotIn("<script>alert(1)</script>", html_text)
            self.assertIn("&lt;script&gt;alert(1)&lt;/script&gt;", html_text)
            self.assertNotIn("SuperSecretPass999", html_text)
            self.assertNotIn("ptlc_1234567890123456789012345", html_text)
            self.assertIn("data:image/png;base64,", html_text)

    def test_hosting_backup_verify_local_dir_and_panel_dry_run(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            good_arc = Path(td) / "world-fresh.tar.gz"
            good_arc.write_bytes(b"0" * 4096)

            res_ok = self._call_raw("mc_hosting_backup_verify", {
                "local_backup_dir": td,
                "max_age_hours": 12.0,
                "min_size_bytes": 1024,
            })
            p_ok = json.loads(res_ok["content"][0]["text"])
            self.assertTrue(p_ok["ok"])
            self.assertEqual(p_ok["backup_count"], 1)
            self.assertEqual(p_ok["issues"], [])

            # Truncated archive + stale timestamp should trigger issues
            tiny_arc = Path(td) / "world-broken.zip"
            tiny_arc.write_bytes(b"xx")
            old_ts = time.time() - 48 * 3600
            os.utime(good_arc, (old_ts, old_ts))
            os.utime(tiny_arc, (old_ts, old_ts))

            res_bad = self._call_raw("mc_hosting_backup_verify", {
                "local_backup_dir": td,
                "max_age_hours": 24.0,
                "min_size_bytes": 1024,
            })
            p_bad = json.loads(res_bad["content"][0]["text"])
            self.assertFalse(p_bad["ok"])
            self.assertGreaterEqual(len(p_bad["issues"]), 2)

        # Panel dry-run redacts API token
        res_dry = self._call_raw("mc_hosting_backup_verify", {
            "domain": "panel.salyvn.net",
            "panel_type": "crafty",
            "server_id": "srv-1",
            "api_key": "ptlc_supersecretkey9999999999",
            "dry_run": True,
        })
        p_dry = json.loads(res_dry["content"][0]["text"])
        self.assertTrue(p_dry["ok"])
        self.assertTrue(p_dry["dry_run"])
        self.assertIn("/api/v2/servers/srv-1/backups", p_dry["endpoint"])
        self.assertNotIn("ptlc_supersecretkey", json.dumps(p_dry))


if __name__ == "__main__":
    unittest.main()
