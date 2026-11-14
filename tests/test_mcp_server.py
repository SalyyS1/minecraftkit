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
        self.assertEqual(
            result["capabilities"],
            {
                "tools": {"listChanged": False},
                "resources": {"subscribe": False, "listChanged": False},
                "prompts": {"listChanged": False},
            },
        )
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

    def test_tools_list_exposes_all_eleven_readonly_tools(self) -> None:
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
                "mc_folia_migration_advisor",
                "mc_diagnose_server_log",
                "mc_inspect_type",
                "mc_audit_gradle_build",
                "mc_audit_paper_plugin_yml",
                "mc_generate_pack_overlay",
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

        unknown_method = self.rpc({"jsonrpc": "2.0", "id": 11, "method": "sampling/createMessage"})
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
        self.assertEqual(len(json.loads(framed_resp.decode("utf-8"))["result"]["tools"]), 11)

    def test_resources_and_prompts_endpoints_serve_handbooks_and_routes(self) -> None:
        res_list = self.rpc({"jsonrpc": "2.0", "id": 30, "method": "resources/list"})
        assert res_list is not None
        resources = res_list["result"]["resources"]
        uris = {r["uri"] for r in resources}
        self.assertIn("minecraftkit://catalog/overview", uris)
        self.assertIn("minecraftkit://references/kotlin-java-gradle.md", uris)
        self.assertGreaterEqual(len(resources), 20)

        overview_resp = self.rpc({
            "jsonrpc": "2.0",
            "id": 31,
            "method": "resources/read",
            "params": {"uri": "minecraftkit://catalog/overview"},
        })
        assert overview_resp is not None
        overview_data = json.loads(overview_resp["result"]["contents"][0]["text"])
        self.assertEqual(overview_data["plugin_count"], 10)
        self.assertEqual(len(overview_data["routes"]), 10)

        handbook_resp = self.rpc({
            "jsonrpc": "2.0",
            "id": 32,
            "method": "resources/read",
            "params": {"uri": "minecraftkit://references/kotlin-java-gradle.md"},
        })
        assert handbook_resp is not None
        self.assertEqual(handbook_resp["result"]["contents"][0]["mimeType"], "text/markdown")
        self.assertGreater(len(handbook_resp["result"]["contents"][0]["text"]), 100)

        traversal_resp = self.rpc({
            "jsonrpc": "2.0",
            "id": 33,
            "method": "resources/read",
            "params": {"uri": "minecraftkit://references/../manifest.json"},
        })
        assert traversal_resp is not None
        self.assertEqual(traversal_resp["error"]["code"], INVALID_PARAMS)

        prompts_resp = self.rpc({"jsonrpc": "2.0", "id": 34, "method": "prompts/list"})
        assert prompts_resp is not None
        prompt_names = {p["name"] for p in prompts_resp["result"]["prompts"]}
        self.assertEqual(len(prompt_names), 10)
        self.assertIn("mc-core", prompt_names)
        self.assertIn("mc-build", prompt_names)

        prompt_get = self.rpc({
            "jsonrpc": "2.0",
            "id": 35,
            "method": "prompts/get",
            "params": {"name": "mc:build", "arguments": {"task": "Configure Shadow relocation for HikariCP"}},
        })
        assert prompt_get is not None
        msg_text = prompt_get["result"]["messages"][0]["content"]["text"]
        self.assertIn("/mc:build", msg_text)
        self.assertIn("Configure Shadow relocation for HikariCP", msg_text)

    def test_mc_inspect_type_resolves_hierarchy_subtypes_and_members(self) -> None:
        inspected, is_err = self.call_tool(
            "mc_inspect_type",
            {"type_name": "CoreEvents", "plugin": "CoreTools"},
        )
        self.assertFalse(is_err)
        self.assertEqual(inspected["plugin"], "CoreTools")
        self.assertEqual(inspected["name"], "ranet.coretools.features.eventmanager.CoreEvents")
        self.assertGreaterEqual(inspected["known_subtype_count"], 1)

        active_model, am_err = self.call_tool(
            "mc_inspect_type",
            {"type_name": "ActiveModel", "plugin": "ModelEngine", "member_filter": "Bone"},
        )
        self.assertFalse(am_err)
        self.assertEqual(active_model["plugin"], "ModelEngine")
        self.assertGreaterEqual(active_model["member_counts"]["returned_methods"], 1)
        self.assertTrue(any("Bone" in m["name"] or "Bone" in m["return_type"] for m in active_model["methods"]))

        fqcn_inspect, fqcn_err = self.call_tool(
            "mc_inspect_type",
            {"type_name": "ModelEngine:com.ticxo.modelengine.api.ModelEngineAPI"},
        )
        self.assertFalse(fqcn_err)
        self.assertEqual(fqcn_inspect["plugin"], "ModelEngine")
        self.assertIsNotNone(fqcn_inspect["min_java_version"])
        self.assertTrue(any(m["name"] == "createActiveModel" for m in fqcn_inspect["methods"]))

        missing, missing_err = self.call_tool(
            "mc_inspect_type",
            {"type_name": "NonExistentDragonClass999"},
        )
        self.assertTrue(missing_err)
        self.assertIn("error", missing)

    def test_mc_audit_gradle_build_flags_bundling_relocation_toolchain_and_descriptor_hazards(self) -> None:
        buggy_gradle = """
        plugins {
            java
            id("io.papermc.paperweight.userdev") version "1.7.3"
            id("com.gradleup.shadow") version "8.3.0"
        }
        java {
            toolchain.languageVersion.set(JavaLanguageVersion.of(17))
        }
        repositories {
            maven("http://insecure.example.com/repo")
        }
        dependencies {
            paperweight.paperDevBundle("1.21.4-R0.1-SNAPSHOT")
            implementation("io.papermc.paper:paper-api:1.21.4-R0.1-SNAPSHOT")
            implementation("com.zaxxer:HikariCP:5.1.0")
        }
        paperweight.reobfArtifactConfiguration = io.papermc.paperweight.userdev.ReobfArtifactConfiguration.REOBF_PRODUCTION
        """
        buggy_paper_yml = """
name: DemoPlugin
version: '1.0.0'
main: com.acme.DemoPlugin
dependencies:
  server:
    MMOItems:
      load: BEFORE
      required: true
"""
        report, is_err = self.call_tool(
            "mc_audit_gradle_build",
            {"build_script": buggy_gradle, "descriptor_yaml": buggy_paper_yml},
        )
        self.assertFalse(is_err)
        self.assertEqual(report["status"], "fail")
        rule_ids = {f["rule_id"] for f in report["findings"]}
        self.assertEqual(
            rule_ids,
            {"GRADLE-001", "GRADLE-002", "GRADLE-003", "GRADLE-004", "GRADLE-005", "GRADLE-006", "GRADLE-007"},
        )

        clean_gradle = """
        plugins {
            java
            id("com.gradleup.shadow") version "8.3.5"
        }
        java {
            toolchain.languageVersion.set(JavaLanguageVersion.of(25))
        }
        repositories {
            maven("https://repo.papermc.io/repository/maven-public/")
        }
        dependencies {
            compileOnly("io.papermc.paper:paper-api:26.2-R0.1-SNAPSHOT")
            implementation("com.zaxxer:HikariCP:6.2.1")
        }
        tasks.shadowJar {
            relocate("com.zaxxer.hikari", "com.acme.shaded.hikari")
        }
        """
        clean_paper_yml = """
name: DemoPlugin
version: '1.0.0'
main: com.acme.DemoPlugin
api-version: '26.2'
dependencies:
  server:
    MMOItems:
      load: BEFORE
      required: true
      join-classpath: true
"""
        clean_report, clean_err = self.call_tool(
            "mc_audit_gradle_build",
            {"build_script": clean_gradle, "descriptor_yaml": clean_paper_yml},
        )
        self.assertFalse(clean_err)
        self.assertEqual(clean_report["status"], "pass")
        self.assertEqual(clean_report["finding_count"], 0)

    def test_mc_folia_migration_advisor_and_log_doctor(self) -> None:
        folia, folia_err = self.call_tool(
            "mc_folia_migration_advisor",
            {"code_or_symbol": "Bukkit.getScheduler().runTaskTimer(plugin, () -> player.teleport(loc), 0L, 20L);"},
        )
        self.assertFalse(folia_err)
        rule_ids = {item["rule_id"] for item in folia["findings"]}
        self.assertIn("FOLIA-001", rule_ids)
        self.assertIn("FOLIA-003", rule_ids)

        diag, diag_err = self.call_tool(
            "mc_diagnose_server_log",
            {
                "log_text": (
                    "java.lang.IllegalStateException: Thread failed main thread check: Block set\n"
                    "\tat ca.spottedleaf.moonrise.common.util.TickThread.ensureTickThread(TickThread.java:58)\n"
                    "\tat com.acme.rpg.DungeonListener.onAsyncTick(DungeonListener.java:142)\n"
                    "Caused by: java.lang.UnsupportedClassVersionError: com/acme/Main has been compiled by a more recent version of the Java Runtime (class file version 65.0)"
                )
            },
        )
        self.assertFalse(diag_err)
        cats = {item["category"] for item in diag["diagnoses"]}
        self.assertIn("folia_region_violation", cats)
        self.assertIn("java_bytecode_mismatch", cats)
        self.assertIn("com.acme.rpg.DungeonListener.onAsyncTick(DungeonListener.java:142)", diag["suspect_plugin_frames"])

    def test_mc_audit_paper_plugin_yml_catches_float_truncation_legacy_keys_and_graph_conflicts(self) -> None:
        broken_paper_yml = """
name: Bad Plugin Name
version: '1.0.0'
main: com.acme.rpg.RpgPlugin
bootstrapper: com.acme.rpg.RpgPlugin
api-version: 1.20 # unquoted -> SnakeYAML float 1.2!
commands:
  rpg:
    description: Legacy command block ignored by Paper
dependencies:
  bootstrap:
    MythicMobs:
      load: BEFORE
      required: true
  server:
    MythicMobs:
      load: AFTER
      required: true
    MMOItems:
      load: BEFORE
      required: true
      join-classpath: false
"""
        legacy_yml = """
name: BadPlugin
version: '1.0.0'
main: com.acme.rpg.RpgPlugin
depend: [MMOItems, ModelEngine]
"""
        report, is_err = self.call_tool(
            "mc_audit_paper_plugin_yml",
            {
                "paper_plugin_yaml": broken_paper_yml,
                "legacy_plugin_yaml": legacy_yml,
                "require_folia": True,
            },
        )
        self.assertFalse(is_err)
        self.assertEqual(report["status"], "fail")
        rules = {item["rule_id"] for item in report["findings"]}
        self.assertEqual(
            rules,
            {"PAPER-001", "PAPER-002", "PAPER-003", "PAPER-004", "PAPER-005", "PAPER-006", "PAPER-007"},
        )

        clean_263_yml = """
name: BossArena
version: '2.5.0'
main: com.acme.arena.BossArenaPlugin
bootstrapper: com.acme.arena.BossArenaBootstrap
loader: com.acme.arena.BossArenaLoader
api-version: '26.3'
folia-supported: true
dependencies:
  bootstrap:
    CoreTools:
      load: BEFORE
      required: true
  server:
    ModelEngine:
      load: BEFORE
      required: true
      join-classpath: true
    MMOItems:
      load: BEFORE
      required: false
      join-classpath: true
    ArenaAddon:
      load: AFTER
      required: false
"""
        clean_report, clean_err = self.call_tool(
            "mc_audit_paper_plugin_yml",
            {"paper_plugin_yaml": clean_263_yml, "require_folia": True},
        )
        self.assertFalse(clean_err)
        self.assertEqual(clean_report["status"], "pass")
        self.assertEqual(clean_report["finding_count"], 0)
        self.assertEqual(clean_report["plugin_meta"]["required_java_version"], 25)
        self.assertTrue(clean_report["plugin_meta"]["folia_supported"])
        self.assertEqual(
            clean_report["dependency_graph"]["loads_before_this_plugin"],
            ["CoreTools", "MMOItems", "ModelEngine"],
        )
        self.assertEqual(clean_report["dependency_graph"]["loads_after_this_plugin"], ["ArenaAddon"])

    def test_mc_generate_pack_overlay_builds_dual_era_and_modern_pack_mcmeta(self) -> None:
        hybrid_res, hybrid_err = self.call_tool(
            "mc_generate_pack_overlay",
            {
                "pack_type": "resource",
                "min_version": "1.20.1",
                "max_version": "26.2",
                "description": "Salyyy RPG Assets",
                "auto_split_epochs": True,
            },
        )
        self.assertFalse(hybrid_err)
        self.assertEqual(hybrid_res["format_era"], "dual_era_hybrid")
        pack_obj = hybrid_res["pack_mcmeta"]["pack"]
        self.assertEqual(pack_obj["pack_format"], 15)
        self.assertEqual(pack_obj["supported_formats"], [15, 64])
        self.assertEqual(pack_obj["min_format"], 15)
        self.assertEqual(pack_obj["max_format"], [88, 0])
        entries = hybrid_res["pack_mcmeta"]["overlays"]["entries"]
        self.assertGreaterEqual(len(entries), 3)
        modern_entry = next(e for e in entries if e["directory"] == "overlay_26_1_modern")
        self.assertNotIn("formats", modern_entry)
        self.assertEqual(modern_entry["min_format"], 84)
        self.assertEqual(modern_entry["max_format"], [88, 0])

        modern_data, data_err = self.call_tool(
            "mc_generate_pack_overlay",
            {
                "pack_type": "data",
                "min_version": "26.2..26.3",
                "description": "Wilderness Data Pack",
                "overlays": [
                    {"directory": "overlay_26_3", "min_version": "26.3", "max_version": "26.3"},
                ],
            },
        )
        self.assertFalse(data_err)
        self.assertEqual(modern_data["format_era"], "modern_minor_tuple")
        d_pack = modern_data["pack_mcmeta"]["pack"]
        self.assertNotIn("pack_format", d_pack)
        self.assertNotIn("supported_formats", d_pack)
        self.assertEqual(d_pack["min_format"], [107, 1])
        self.assertEqual(d_pack["max_format"], [121, 0])
        self.assertEqual(
            modern_data["pack_mcmeta"]["overlays"]["entries"][0],
            {"directory": "overlay_26_3", "min_format": [121, 0], "max_format": [121, 0]},
        )

        bad_dir_resp = self.rpc({
            "jsonrpc": "2.0",
            "id": 108,
            "method": "tools/call",
            "params": {
                "name": "mc_generate_pack_overlay",
                "arguments": {
                    "pack_type": "resource",
                    "min_version": "1.21.4",
                    "max_version": "26.2",
                    "overlays": [{"directory": "../UpperBad", "min_version": "26.2"}],
                },
            },
        })
        assert bad_dir_resp is not None
        self.assertTrue(bad_dir_resp["result"]["isError"])
        self.assertIn("OverlayMetadataSection", bad_dir_resp["result"]["content"][0]["text"])

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
