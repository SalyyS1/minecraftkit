from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from mcp_server import MinecraftKitMcpServer  # noqa: E402


class PluginMatrixAndCloudGridTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.server = MinecraftKitMcpServer(root=ROOT)

    def _call(self, name: str, args: dict[str, object]) -> dict[str, object]:
        raw = self.server.handle_message(json.dumps({
            "jsonrpc": "2.0",
            "id": 91,
            "method": "tools/call",
            "params": {"name": name, "arguments": args},
        }))
        assert raw is not None
        res = json.loads(raw)["result"]
        self.assertFalse(res["isError"], res)
        return json.loads(res["content"][0]["text"])

    def test_plugin_matrix_catches_conflicts_missing_deps_and_folia_cautions(self) -> None:
        res = self._call("mc_audit_plugin_matrix", {
            "platform": "folia",
            "plugins": [
                "AuthMe-5.6.jar",
                "nLogin-10.2.jar",
                "ItemsAdder-4.0.jar",
                "Nexo-1.3.jar",
                "MMOItems-6.10.jar",
                "LuckPerms-5.4.jar",
                "LuckPerms-5.5.jar",
            ],
        })
        self.assertFalse(res["ok"])
        codes = {f["rule_id"] for f in res["findings"]}
        self.assertIn("MATRIX-001", codes)
        self.assertIn("CONFLICT-AUTH", codes)
        self.assertIn("CONFLICT-PACK", codes)
        self.assertIn("MATRIX-002", codes)
        self.assertIn("MATRIX-FOLIA", codes)

        with tempfile.TemporaryDirectory() as td:
            for jar in ("MythicLib-1.6.jar", "MMOItems-6.10.jar", "LuckPerms-5.4.jar"):
                (Path(td) / jar).write_bytes(b"PK")
            clean = self._call("mc_audit_plugin_matrix", {"plugins_dir": td, "platform": "paper"})
            self.assertTrue(clean["ok"], clean)
            self.assertEqual(clean["finding_count"], 0)

    def test_cloud_bot_deploy_generates_all_four_targets(self) -> None:
        for target in ("github_actions", "fly_io", "vps_systemd", "kubernetes_job"):
            out = self._call("mc_bot_generate_cloud_deploy", {
                "target": target,
                "server_host": "staging.salyvn.net",
                "server_port": 25565,
                "bot_count": 6,
            })
            self.assertTrue(out["ok"])
            self.assertTrue(out["screen_lock_free"])
            self.assertIn("staging.salyvn.net", out["content"])
            self.assertGreater(out["anti_oom_limit_mb"], 0)


if __name__ == "__main__":
    unittest.main()
