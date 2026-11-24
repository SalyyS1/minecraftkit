"""Tests for v8.1.0 mc_qa_generate_discord_webhook_payload (87th) & mc_ops_plan_proxy_migration (88th)."""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import discord_webhook_builder  # noqa: E402
import proxy_migration_planner  # noqa: E402
from mcp_server import MinecraftKitMcpServer  # noqa: E402


class DiscordAndProxyMigrationV81Tests(unittest.TestCase):
    def test_discord_webhook_redacts_secrets_and_formats_fail_mention(self) -> None:
        res = discord_webhook_builder.build_discord_qa_webhook(
            server_name="SalyRPG",
            verdict="FAIL",
            passed_stages=4,
            total_stages=5,
            tps=18.2,
            mspt_ms=42.5,
            bot_ram_mb=42,
            stage_lines=[
                "Auth: /login SuperSecretPass999",
                "Panel key ptla_AbCdEfGhIjKlMnOpQrStUv",
                "Header Bearer eyJhbGciOiJIUzI1NiJ9.payload",
            ],
            report_url="https://salyys1.github.io/minecraftkit/showcase.html",
            fail_mention_role_id="123456789012345678",
        )
        self.assertTrue(res["ok"])
        self.assertTrue(res["secrets_redacted"])
        raw = json.dumps(res["webhook_payload"])
        self.assertNotIn("SuperSecretPass999", raw)
        self.assertNotIn("ptla_AbCdEfGhIjKlMnOpQrStUv", raw)
        self.assertNotIn("eyJhbGciOiJIUzI1NiJ9", raw)
        self.assertIn("[REDACTED_PASSWORD]", raw)
        self.assertIn("[REDACTED_PANEL_KEY]", raw)
        self.assertIn("<@&123456789012345678>", res["webhook_payload"]["content"])
        self.assertEqual(res["webhook_payload"]["embeds"][0]["color"], 0xEF4444)

    def test_proxy_migration_plan_maps_plugins_and_firewall(self) -> None:
        plan = proxy_migration_planner.plan_proxy_migration(
            source_proxy="waterfall",
            backend_servers=["lobby", "survival", "skyblock"],
            plugins=["BungeeGuard.jar", "BungeeTabListPlus.jar", "LuckPerms-Bungee.jar", "AuthMe.jar"],
            has_bedrock_geyser=True,
            mc_version="1.21.4",
        )
        self.assertTrue(plan["ok"])
        self.assertEqual(plan["forwarding_mode"], "modern")
        self.assertEqual(plan["backend_count"], 3)
        self.assertIn('player-info-forwarding-mode = "modern"', plan["velocity_toml_snippet"])
        self.assertIn("enabled: true", plan["paper_global_yml_snippet"])
        self.assertTrue(any("19132/udp" in c for c in plan["firewall_commands"]))
        self.assertGreaterEqual(len(plan["plugin_replacements"]), 4)

    def test_mcp_roundtrip_both_v81_tools(self) -> None:
        server = MinecraftKitMcpServer(root=ROOT)
        for idx, (tool_name, arguments) in enumerate([
            ("mc_qa_generate_discord_webhook_payload", {"server_name": "PaperQA", "verdict": "PASS", "passed_stages": 6, "total_stages": 6}),
            ("mc_ops_plan_proxy_migration", {"source_proxy": "bungeecord", "backend_servers": ["hub", "rpg"], "has_bedrock_geyser": False}),
        ], start=87):
            raw = server.handle_message(json.dumps({
                "jsonrpc": "2.0",
                "id": idx,
                "method": "tools/call",
                "params": {"name": tool_name, "arguments": arguments},
            }))
            assert raw is not None
            resp = json.loads(raw)
            self.assertFalse(resp["result"]["isError"], msg=raw)
            payload = json.loads(resp["result"]["content"][0]["text"])
            self.assertTrue(payload["ok"])


if __name__ == "__main__":
    unittest.main()