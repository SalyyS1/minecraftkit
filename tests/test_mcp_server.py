from __future__ import annotations

import io
import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from mcp_server import (  # noqa: E402
    INVALID_PARAMS,
    INVALID_REQUEST,
    METHOD_NOT_FOUND,
    PARSE_ERROR,
    PROTOCOL_VERSION,
    MinecraftKitMcpServer,
    serve_stdio,
)


class MinecraftKitMcpServerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.server = MinecraftKitMcpServer(root=ROOT)

    def rpc(self, payload: dict[str, object]) -> dict[str, object] | None:
        raw = self.server.handle_message(json.dumps(payload))
        if raw is None:
            return None
        return json.loads(raw)

    def call_tool(self, name: str, arguments: dict[str, object] | None = None) -> tuple[dict[str, object], bool]:
        response = self.rpc({
            "jsonrpc": "2.0",
            "id": 42,
            "method": "tools/call",
            "params": {
                "name": name,
                "arguments": arguments or {},
            },
        })
        assert response is not None
        self.assertNotIn("error", response, response)
        result = response["result"]
        assert isinstance(result, dict)
        content = result["content"]
        assert isinstance(content, list) and len(content) == 1
        self.assertEqual(content[0]["type"], "text")
        return json.loads(content[0]["text"]), bool(result["isError"])

    def test_initialize_negotiates_protocol_and_reports_kit_version(self) -> None:
        manifest_version = json.loads((ROOT / "manifest.json").read_text(encoding="utf-8"))["version"]
        response = self.rpc({
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "unit-test", "version": "1.0.0"},
            },
        })
        assert response is not None
        result = response["result"]
        assert isinstance(result, dict)
        self.assertEqual(result["protocolVersion"], "2024-11-05")
        self.assertEqual(result["serverInfo"], {"name": "minecraftkit", "version": manifest_version})
        self.assertEqual(result["capabilities"], {"tools": {"listChanged": False}})
        self.assertIn("mc_route_skill", result["instructions"])

        fallback = self.rpc({
            "jsonrpc": "2.0",
            "id": 2,
            "method": "initialize",
            "params": {"protocolVersion": "1999-01-01"},
        })
        assert fallback is not None
        self.assertEqual(fallback["result"]["protocolVersion"], PROTOCOL_VERSION)

    def test_notifications_and_ping_behave_per_jsonrpc_and_mcp(self) -> None:
        self.assertIsNone(self.rpc({
            "jsonrpc": "2.0",
            "method": "notifications/initialized",
        }))
        ping = self.rpc({"jsonrpc": "2.0", "id": "ping-1", "method": "ping"})
        self.assertEqual(ping, {"jsonrpc": "2.0", "id": "ping-1", "result": {}})

    def test_tools_list_exposes_all_five_readonly_tools(self) -> None:
        response = self.rpc({"jsonrpc": "2.0", "id": 3, "method": "tools/list"})
        assert response is not None
        tools = response["result"]["tools"]
        names = [tool["name"] for tool in tools]
        self.assertEqual(
            names,
            [
                "mc_search_api",
                "mc_list_plugins",
                "mc_search_sources",
                "mc_version_capabilities",
                "mc_route_skill",
            ],
        )
        for tool in tools:
            self.assertEqual(tool["annotations"], {"readOnlyHint": True})
            self.assertEqual(tool["inputSchema"]["type"], "object")
            self.assertFalse(tool["inputSchema"]["additionalProperties"])

    def test_mc_search_api_queries_types_and_members(self) -> None:
        payload, is_error = self.call_tool(
            "mc_search_api",
            {"terms": "ActiveModel", "plugin": "ModelEngine", "kind": "interface", "limit": 5},
        )
        self.assertFalse(is_error)
        self.assertGreaterEqual(payload["total"], 1)
        self.assertLessEqual(payload["returned"], 5)
        self.assertTrue(any("ActiveModel" in item["name"] for item in payload["results"]))

        array_terms, array_err = self.call_tool(
            "mc_search_api",
            {"terms": ["ItemManager"], "plugin": "MMOItems", "limit": 3},
        )
        self.assertFalse(array_err)
        self.assertGreaterEqual(array_terms["total"], 1)

    def test_mc_list_plugins_merges_coverage_and_insights(self) -> None:
        all_plugins, is_error = self.call_tool("mc_list_plugins")
        self.assertFalse(is_error)
        self.assertEqual(all_plugins["plugin_count"], 10)
        self.assertEqual(all_plugins["totals"]["plugin_owned_types"], 4947)
        self.assertEqual(all_plugins["totals"]["plugin_owned_members"], 39262)

        single, single_err = self.call_tool(
            "mc_list_plugins",
            {"plugin": "ModelEngine", "include_insights": True},
        )
        self.assertFalse(single_err)
        self.assertEqual(single["plugin_count"], 1)
        plugin_entry = single["plugins"][0]
        self.assertEqual(plugin_entry["name"], "ModelEngine")
        self.assertIn("insights", plugin_entry)
        self.assertTrue(plugin_entry["insights"]["api_boundaries"])

        missing, missing_err = self.call_tool("mc_list_plugins", {"plugin": "NonExistentPlugin"})
        self.assertTrue(missing_err)
        self.assertIn("available_plugins", missing)

    def test_mc_search_sources_filters_curated_repositories(self) -> None:
        core_sources, is_error = self.call_tool(
            "mc_search_sources",
            {"terms": "Folia", "domain": "core", "priority": "P0", "limit": 5},
        )
        self.assertFalse(is_error)
        self.assertGreaterEqual(core_sources["count"], 1)
        self.assertTrue(
            any("Folia" in item["repository"] for item in core_sources["sources"]),
            core_sources,
        )

    def test_mc_version_capabilities_resolves_specific_and_latest_versions(self) -> None:
        v262, is_error = self.call_tool("mc_version_capabilities", {"version": "26.2"})
        self.assertFalse(is_error)
        self.assertEqual(v262["resolved_id"], "26.2")
        caps = v262["release_capabilities"]
        self.assertIsNotNone(caps)
        self.assertEqual(caps["protocol"], 776)
        self.assertEqual(caps["resource_pack"], {"major": 88, "minor": 0})
        self.assertEqual(caps["data_pack"], {"major": 107, "minor": 1})

        latest, latest_err = self.call_tool("mc_version_capabilities", {"version": "latest"})
        self.assertFalse(latest_err)
        self.assertEqual(latest["resolved_id"], latest["latest"]["release"])

        listing, listing_err = self.call_tool("mc_version_capabilities", {"type": "release", "limit": 4})
        self.assertFalse(listing_err)
        self.assertEqual(len(listing["recent_versions"]), 4)
        self.assertEqual(listing["version_count"], 901)

        unknown, unknown_err = self.call_tool("mc_version_capabilities", {"version": "0.0.0-nope"})
        self.assertTrue(unknown_err)
        self.assertIn("profiled_release_ids", unknown)

    def test_mc_route_skill_recommends_primary_and_secondary_domains(self) -> None:
        folia_route, is_error = self.call_tool(
            "mc_route_skill",
            {
                "task": "Migrate BukkitRunnable and teleport calls to Folia RegionScheduler with Gradle shadowJar relocation",
                "include_checklist": True,
            },
        )
        self.assertFalse(is_error)
        self.assertFalse(folia_route["fallback_to_core"])
        route_ids = {folia_route["primary_route"]["id"], *(r["id"] for r in folia_route["secondary_routes"])}
        self.assertIn("core", route_ids)
        self.assertIn("build", route_ids)
        self.assertIn("references/kotlin-java-gradle.md", folia_route["recommended_references"])
        self.assertTrue(folia_route["contract_checklist"])
        self.assertTrue(folia_route.get("route_workflow"))

        fallback_route, fb_err = self.call_tool("mc_route_skill", {"task": "general server question"})
        self.assertFalse(fb_err)
        self.assertEqual(fallback_route["primary_route"]["route"], "mc:core")

    def test_jsonrpc_and_tool_validation_errors_are_well_formed(self) -> None:
        bad_json = self.server.handle_message("{not-valid-json")
        assert bad_json is not None
        self.assertEqual(json.loads(bad_json)["error"]["code"], PARSE_ERROR)

        bad_req = self.rpc({"jsonrpc": "1.0", "id": 10, "method": "ping"})
        assert bad_req is not None
        self.assertEqual(bad_req["error"]["code"], INVALID_REQUEST)

        unknown_method = self.rpc({"jsonrpc": "2.0", "id": 11, "method": "resources/list"})
        assert unknown_method is not None
        self.assertEqual(unknown_method["error"]["code"], METHOD_NOT_FOUND)

        unknown_tool = self.rpc({
            "jsonrpc": "2.0",
            "id": 12,
            "method": "tools/call",
            "params": {"name": "mc_unknown"},
        })
        assert unknown_tool is not None
        self.assertEqual(unknown_tool["error"]["code"], INVALID_PARAMS)

    def test_bad_tool_argument_returns_tool_is_error_text(self) -> None:
        response = self.rpc({
            "jsonrpc": "2.0",
            "id": 99,
            "method": "tools/call",
            "params": {"name": "mc_search_api", "arguments": {"limit": 999}},
        })
        assert response is not None
        result = response["result"]
        self.assertTrue(result["isError"])
        self.assertIn("between 1 and 200", result["content"][0]["text"])

    def test_stdio_supports_both_newline_and_content_length_framing(self) -> None:
        newline_msg = json.dumps({"jsonrpc": "2.0", "id": 1, "method": "ping"}).encode("utf-8") + b"\n"
        notif_msg = json.dumps({"jsonrpc": "2.0", "method": "notifications/initialized"}).encode("utf-8") + b"\n"
        framed_body = json.dumps({"jsonrpc": "2.0", "id": 2, "method": "tools/list"}).encode("utf-8")
        framed_msg = f"Content-Length: {len(framed_body)}\r\n\r\n".encode("ascii") + framed_body

        inp = io.BytesIO(newline_msg + notif_msg + framed_msg)
        out = io.BytesIO()
        code = serve_stdio(self.server, inp, out)
        self.assertEqual(code, 0)

        raw_out = out.getvalue()
        first_line, remainder = raw_out.split(b"\n", 1)
        self.assertEqual(json.loads(first_line.decode("utf-8")), {"jsonrpc": "2.0", "id": 1, "result": {}})
        self.assertTrue(remainder.startswith(b"Content-Length: "))
        header_part, framed_resp = remainder.split(b"\r\n\r\n", 1)
        declared_len = int(header_part.split(b":", 1)[1].strip())
        self.assertEqual(declared_len, len(framed_resp))
        self.assertEqual(len(json.loads(framed_resp.decode("utf-8"))["result"]["tools"]), 5)

    def test_cli_subprocess_serves_stdio_end_to_end(self) -> None:
        request = json.dumps({"jsonrpc": "2.0", "id": 7, "method": "initialize", "params": {}}) + "\n"
        completed = subprocess.run(
            [sys.executable, "-B", str(SCRIPTS_DIR / "mcp_server.py")],
            input=request,
            text=True,
            encoding="utf-8",
            capture_output=True,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        parsed = json.loads(completed.stdout.strip())
        self.assertEqual(parsed["id"], 7)
        self.assertEqual(parsed["result"]["serverInfo"]["name"], "minecraftkit")


if __name__ == "__main__":
    unittest.main()
