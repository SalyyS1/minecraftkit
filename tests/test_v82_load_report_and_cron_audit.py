"""Tests for v8.2.0 90-Tool Milestone: mc_bot_generate_load_test_report (89th) & mc_ops_audit_crontab_backups (90th)."""

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

import backup_cron_auditor  # noqa: E402
import bot_load_test_report  # noqa: E402
from mcp_server import MinecraftKitMcpServer  # noqa: E402


BAD_CRON = """
*/15 * * * * tar -czf /backups/world-$(date +%F).tar.gz /srv/minecraft/world
RESTIC_PASSWORD=myPlaintextBackupPass123
mcrcon -H 127.0.0.1 -p superRconSecret "say backing up"
"""

SAFE_CRON = """
0 */6 * * * /usr/local/bin/mc-backup.sh
# inside mc-backup.sh:
# source /etc/minecraft/backup.env (chmod 0600)
# mcrcon -H 127.0.0.1 -p "$RCON_PASS" "save-off" "save-all flush"
# restic -r s3:https://r2.example/mc backup /srv/minecraft/world
# restic forget --keep-daily 7 --prune && restic check
"""


class LoadTestAndCronV82Tests(unittest.TestCase):
    def test_load_test_report_grades_stress_failure_and_healthy_run(self) -> None:
        bad = bot_load_test_report.generate_bot_load_test_report(
            server_name="LagRPG",
            bot_count=12,
            join_latencies_ms=[400, 900, 1800, 3400],
            tps_samples=[19.8, 17.5, 14.2, 15.1],
            failed_joins=2,
        )
        self.assertFalse(bad["ok"])
        self.assertEqual(bad["grade"], "F")
        self.assertEqual({f["rule_id"] for f in bad["findings"]}, {"LOAD-001", "LOAD-002", "LOAD-003"})

        good = bot_load_test_report.generate_bot_load_test_report(
            server_name="FastFolia",
            bot_count=10,
            join_latencies_ms=[120, 150, 180, 210],
            tps_samples=[20.0, 19.95, 19.9, 20.0],
            failed_joins=0,
        )
        self.assertTrue(good["ok"])
        self.assertEqual(good["grade"], "A")
        self.assertGreater(good["memory_efficiency"]["ram_saved_pct"], 95.0)

    def test_crontab_auditor_catches_all_five_rules_without_leaking_secrets(self) -> None:
        bad = backup_cron_auditor.audit_crontab_backups(BAD_CRON)
        self.assertFalse(bad["ok"])
        self.assertEqual(bad["grade"], "F")
        self.assertEqual({f["rule_id"] for f in bad["findings"]}, {"CRON-001", "CRON-002", "CRON-003", "CRON-004", "CRON-005"})
        self.assertNotIn("myPlaintextBackupPass123", json.dumps(bad))
        self.assertNotIn("superRconSecret", json.dumps(bad))

        safe = backup_cron_auditor.audit_crontab_backups(SAFE_CRON)
        self.assertTrue(safe["ok"])
        self.assertEqual(safe["grade"], "A")
        self.assertEqual(safe["findings"], [])

    def test_mcp_roundtrip_89_with_png_and_90(self) -> None:
        server = MinecraftKitMcpServer(root=ROOT)
        r89 = json.loads(server.handle_message(json.dumps({
            "jsonrpc": "2.0",
            "id": 89,
            "method": "tools/call",
            "params": {
                "name": "mc_bot_generate_load_test_report",
                "arguments": {
                    "server_name": "PaperStress",
                    "bot_count": 10,
                    "join_latencies_ms": [120, 240, 380, 510],
                    "tps_samples": [20.0, 19.8, 19.6, 19.9],
                    "attach_chart": True,
                },
            },
        })) or "{}")
        content = r89["result"]["content"]
        self.assertEqual(len(content), 2)
        self.assertEqual(content[1]["type"], "image")
        self.assertTrue(base64.b64decode(content[1]["data"]).startswith(b"\x89PNG\r\n\x1a\n"))

        r90 = json.loads(server.handle_message(json.dumps({
            "jsonrpc": "2.0",
            "id": 90,
            "method": "tools/call",
            "params": {"name": "mc_ops_audit_crontab_backups", "arguments": {"script_text": BAD_CRON}},
        })) or "{}")
        self.assertFalse(r90["result"]["isError"])
        p90 = json.loads(r90["result"]["content"][0]["text"])
        self.assertEqual(p90["grade"], "F")


if __name__ == "__main__":
    unittest.main()