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

    def test_tools_list_exposes_all_thirty_nine_tools(self) -> None:
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
                "mc_audit_server_properties",
                "mc_validate_item_components",
                "mc_diagnose_crash_report",
                "mc_audit_datapack",
                "mc_audit_spark_flamegraph",
                "mc_analyze_folia_scheduler_trace",
                "mc_audit_packet_codec",
                "mc_audit_sql_persistence",
                "mc_profile_chunk_io_barriers",
                "mc_correlate_spark_jfr_traces",
                "mc_bot_plan_resources",
                "mc_bot_ping_server",
                "mc_bot_run_stages",
                "mc_bot_inspect_session",
                "mc_bot_generate_docker_grid",
                "mc_hosting_connect_plan",
                "mc_hosting_server_action",
                "mc_sftp_operations",
                "mc_suite_catalog",
                "mc_suite_orchestrate",
                "mc_bridge_plugin_query",
                "mc_run_qa_pipeline",
                "mc_ops_profile_vault",
                "mc_bot_session_start",
                "mc_bot_session_action",
                "mc_bot_session_stop",
                "mc_bot_capture_timelapse",
                "mc_bot_visual_diff",
                "mc_bot_ping_bedrock",
                "mc_bot_generate_stage_preset",
                "mc_hosting_console_stream_plan",
                "mc_suite_generate_mcstage_suite",
                "mc_bot_login_handshake_probe",
                "mc_bot_export_stage_yaml",
                "mc_ops_rcon_execute",
                "mc_qa_generate_html_report",
                "mc_hosting_backup_verify",
                "mc_bot_play_command_probe",
                "mc_pack_verify_parity",
                "mc_audit_plugin_matrix",
                "mc_bot_generate_cloud_deploy",
                "mc_bot_stress_benchmark",
                "mc_qa_run_full_lifecycle",
                "mc_audit_server_exploits",
                "mc_kit_self_doctor",
                "mc_world_audit_integrity",
                "mc_audit_proxy_topology",
                "mc_audit_datapack_integrity",
                "mc_bot_generate_ci_workflow",
                "mc_bot_record_stage_gif",
                "mc_ops_vps_ssh_preflight",
                "mc_bot_generate_fabric_capture_script",
                "mc_audit_permissions_rbac",
                "mc_bot_diagnose_auth_plugin",
                "mc_ops_generate_docker_stack",
                "mc_ops_audit_spark_profile",
                "mc_bot_simulate_economy_stress",
                "mc_audit_database_pool",
                "mc_qa_generate_release_notes",
                "mc_audit_shader_pack",
                "mc_bot_compare_stage_runs",
                "mc_bot_probe_protocol_matrix",
                "mc_suite_full_ecosystem_doctor",
            ],
        )
        for tool in tools:
            self.assertIn("readOnlyHint", tool["annotations"])
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
        self.assertEqual(len(json.loads(framed_resp.decode("utf-8"))["result"]["tools"]), 74)

    def test_resources_and_prompts_endpoints_serve_handbooks_and_routes(self) -> None:
        res_list = self.rpc({"jsonrpc": "2.0", "id": 30, "method": "resources/list"})
        assert res_list is not None
        resources = res_list["result"]["resources"]
        uris = {r["uri"] for r in resources}
        self.assertIn("minecraftkit://catalog/overview", uris)
        self.assertIn("minecraftkit://catalog/paper-26.3-item-components", uris)
        self.assertIn("minecraftkit://references/kotlin-java-gradle.md", uris)
        self.assertGreaterEqual(len(resources), 20)

        comp_schema_resp = self.rpc({
            "jsonrpc": "2.0",
            "id": 301,
            "method": "resources/read",
            "params": {"uri": "minecraftkit://catalog/paper-26.3-item-components"},
        })
        assert comp_schema_resp is not None
        comp_schema_data = json.loads(comp_schema_resp["result"]["contents"][0]["text"])
        self.assertEqual(comp_schema_data["target_release"], "26.3")
        self.assertIn("minecraft:tooltip_display", comp_schema_data["components"])
        self.assertIn("minecraft:blocks_attacks", comp_schema_data["components"])

        overview_resp = self.rpc({
            "jsonrpc": "2.0",
            "id": 31,
            "method": "resources/read",
            "params": {"uri": "minecraftkit://catalog/overview"},
        })
        assert overview_resp is not None
        overview_data = json.loads(overview_resp["result"]["contents"][0]["text"])
        self.assertEqual(overview_data["plugin_count"], 10)
        self.assertEqual(len(overview_data["routes"]), 14)

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
        self.assertEqual(len(prompt_names), 14)
        self.assertIn("mc-core", prompt_names)
        self.assertIn("mc-build", prompt_names)
        self.assertIn("mc-bot", prompt_names)
        self.assertIn("mc-ops", prompt_names)
        self.assertIn("mc-qa", prompt_names)
        self.assertIn("mc-suite", prompt_names)

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

    def test_mc_audit_server_properties_detects_compression_netty_proxy_chunk_rcon_and_gc_hazards(self) -> None:
        misconfigured_props = """
        online-mode=false
        network-compression-threshold=16
        view-distance=10
        simulation-distance=16
        sync-chunk-writes=true
        enable-rcon=true
        rcon.password=admin
        pause-when-empty-seconds=60
        resource-pack=http\\://cdn.example.com/pack.zip
        resource-pack-sha1=deadbeef
        motd=First MOTD
        motd=Duplicate MOTD
        """
        old_paper_global = """
        _version: 28
        timings:
          enabled: true
        item-validation:
          book-size:
            page-max: -1
        """
        spigot_yml = """
        settings:
          netty-threads: 1
        """
        bad_jvm = "-Xms2G -Xmx8G -XX:MaxDirectMemorySize=64M -XX:+UseConcMarkSweepGC -XX:+ZGenerational"

        report, is_err = self.call_tool(
            "mc_audit_server_properties",
            {
                "server_properties": misconfigured_props,
                "paper_global_yaml": old_paper_global,
                "spigot_yaml": spigot_yml,
                "jvm_args": bad_jvm,
                "behind_proxy": "none",
                "expected_players": 120,
                "cpu_cores": 8,
            },
        )
        self.assertFalse(is_err)
        self.assertEqual(report["status"], "fail")
        rules = {item["rule_id"] for item in report["findings"]}
        self.assertEqual(
            rules,
            {"PROP-001", "PROP-002", "PROP-003", "PROP-004", "PROP-005", "PROP-006", "PROP-007", "PROP-008"},
        )
        self.assertEqual(report["tuning_recommendations"]["recommended_network_compression_threshold"], 512)
        self.assertGreaterEqual(report["tuning_recommendations"]["recommended_netty_event_loop_threads"], 6)
        self.assertEqual(report["tuning_recommendations"]["chunk_budget_per_player"]["ticked_chunks_per_player"], 1089)

        velocity_double_compress, vel_err = self.call_tool(
            "mc_audit_server_properties",
            {
                "server_properties": "online-mode=true\nnetwork-compression-threshold=256\n",
                "paper_global_yaml": "proxies:\n  velocity:\n    enabled: true\n    secret: ''\n",
                "behind_proxy": "velocity",
            },
        )
        self.assertFalse(vel_err)
        self.assertEqual(velocity_double_compress["status"], "fail")
        vel_rules = {item["rule_id"] for item in velocity_double_compress["findings"]}
        self.assertIn("PROP-001", vel_rules)
        self.assertIn("PROP-002", vel_rules)
        self.assertEqual(
            velocity_double_compress["tuning_recommendations"]["recommended_network_compression_threshold"],
            -1,
        )

        clean_velocity_props = """
        online-mode=false
        server-ip=127.0.0.1
        network-compression-threshold=-1
        view-distance=10
        simulation-distance=8
        sync-chunk-writes=false
        enable-rcon=false
        pause-when-empty-seconds=-1
        resource-pack=https\\://cdn.example.com/rpg-pack.zip
        resource-pack-sha1=0123456789abcdef0123456789abcdef01234567
        resource-pack-id=550e8400-e29b-41d4-a716-446655440000
        """
        clean_paper_global = """
        _version: 30
        proxies:
          velocity:
            enabled: true
            online-mode: true
            secret: 'v9K4mP8xQ2wR7zL5nJ3tB6yH1cF0dG8sA4eU'
        item-validation:
          book-size:
            page-max: 2560
        """
        clean_res, clean_err = self.call_tool(
            "mc_audit_server_properties",
            {
                "server_properties": clean_velocity_props,
                "paper_global_yaml": clean_paper_global,
                "jvm_args": "-Xms8G -Xmx8G -XX:+UseZGC -Dio.netty.eventLoopThreads=8",
                "behind_proxy": "velocity",
                "expected_players": 80,
                "cpu_cores": 8,
            },
        )
        self.assertFalse(clean_err)
        self.assertEqual(clean_res["status"], "pass", clean_res["findings"])
        self.assertEqual(clean_res["finding_count"], 0)

    def test_mc_validate_item_components_enforces_paper_26_3_schemas_and_client_selector_bounds(self) -> None:
        broken_stack = {
            "id": "minecraft:diamond_sword",
            "Count": 1,
            "tag": "{Legacy:1b}",
            "components": {
                "minecraft:hide_tooltip": {},
                "minecraft:custom_model_data": 1001,
                "minecraft:unbreakable": {"show_in_tooltip": False},
                "minecraft:equippable": {"slot": "head", "model": "myplugin:crown"},
                "minecraft:food": {"nutrition": 4, "saturation": 2.4, "eat_seconds": 1.6},
                "minecraft:item_name": '{"text":"Sunblade","italic":false}',
                "minecraft:attribute_modifiers": {
                    "show_in_tooltip": False,
                    "modifiers": [
                        {
                            "type": "minecraft:attack_damage",
                            "uuid": "00000000-0000-0000-0000-000000000001",
                            "name": "bonus",
                            "amount": 12.0,
                            "operation": "ADDITION",
                            "slot": "mainhand",
                        }
                    ],
                },
                "minecraft:max_damage": 500,
                "minecraft:max_stack_size": 64,
                "!minecraft:damage": 0,
            },
        }
        bad_report, bad_err = self.call_tool(
            "mc_validate_item_components",
            {"payload": broken_stack, "target_version": "26.3"},
        )
        self.assertFalse(bad_err)
        self.assertEqual(bad_report["status"], "fail")
        bad_rules = {f["rule_id"] for f in bad_report["findings"]}
        self.assertEqual(bad_rules, {"COMP-001", "COMP-002", "COMP-003", "COMP-004", "COMP-005"})

        mismatch_client_def = {
            "oversized_in_gui": True,
            "model": {
                "type": "minecraft:select",
                "property": "minecraft:custom_model_data",
                "index": 2,
                "cases": [
                    {
                        "when": "awakened",
                        "model": {
                            "type": "minecraft:range_dispatch",
                            "property": "minecraft:custom_model_data",
                            "index": 0,
                            "entries": [
                                {"threshold": 0.8, "model": {"type": "minecraft:model", "model": "myplugin:item/sunblade_full"}},
                                {"threshold": 0.2, "model": {"type": "minecraft:model", "model": "myplugin:item/sunblade_low"}},
                            ],
                        },
                    }
                ],
            },
        }
        cross_report, cross_err = self.call_tool(
            "mc_validate_item_components",
            {
                "payload": {
                    "id": "minecraft:netherite_sword",
                    "components": {
                        "minecraft:item_model": "myplugin:sunblade",
                        "minecraft:custom_model_data": {
                            "floats": [0.9],
                            "strings": ["awakened"],
                        },
                    },
                },
                "target_version": "26.3",
                "client_item_definition": mismatch_client_def,
            },
        )
        self.assertFalse(cross_err)
        self.assertEqual(cross_report["status"], "fail")
        comp6_titles = [f["title"] for f in cross_report["findings"] if f["rule_id"] == "COMP-006"]
        self.assertTrue(any("strings[2]" in t for t in comp6_titles), comp6_titles)
        self.assertTrue(any("Unsorted" in t for t in comp6_titles), comp6_titles)

        clean_stack = {
            "id": "minecraft:netherite_sword",
            "count": 1,
            "components": {
                "minecraft:item_model": "myplugin:sunblade",
                "minecraft:item_name": {"text": "Sunblade", "italic": False},
                "minecraft:lore": [{"text": "Forged in solar fire", "italic": False}],
                "minecraft:custom_model_data": {
                    "floats": [1.0],
                    "flags": [True],
                    "strings": ["awakened"],
                    "colors": [[1.0, 0.85, 0.2]],
                },
                "minecraft:tooltip_display": {
                    "hide_tooltip": False,
                    "hidden_components": ["minecraft:attribute_modifiers", "minecraft:unbreakable"],
                },
                "minecraft:unbreakable": {},
                "minecraft:weapon": {"item_damage_per_attack": 1, "disable_blocking_for_seconds": 2.5},
                "minecraft:blocks_attacks": {"block_delay_seconds": 0.1, "disable_cooldown_scale": 1.0},
                "minecraft:equippable": {"slot": "mainhand", "asset_id": "myplugin:solar_plate"},
                "minecraft:use_cooldown": {"seconds": 1.5, "cooldown_group": "myplugin:solar_slash"},
                "minecraft:attribute_modifiers": [
                    {
                        "type": "minecraft:attack_damage",
                        "id": "myplugin:solar_edge",
                        "amount": 14.0,
                        "operation": "add_value",
                        "slot": "mainhand",
                    }
                ],
                "minecraft:max_damage": 2048,
                "minecraft:max_stack_size": 1,
                "!minecraft:damage": {},
            },
        }
        clean_client_def = {
            "hand_animation_on_swap": True,
            "oversized_in_gui": False,
            "model": {
                "type": "minecraft:select",
                "property": "minecraft:custom_model_data",
                "index": 0,
                "cases": [
                    {
                        "when": "awakened",
                        "model": {
                            "type": "minecraft:condition",
                            "property": "minecraft:custom_model_data",
                            "index": 0,
                            "on_true": {
                                "type": "minecraft:range_dispatch",
                                "property": "minecraft:custom_model_data",
                                "index": 0,
                                "entries": [
                                    {"threshold": 0.25, "model": {"type": "minecraft:model", "model": "myplugin:item/sunblade_1"}},
                                    {"threshold": 0.75, "model": {"type": "minecraft:model", "model": "myplugin:item/sunblade_2", "tints": [{"type": "minecraft:custom_model_data", "index": 0}]}},
                                ],
                            },
                            "on_false": {"type": "minecraft:model", "model": "myplugin:item/sunblade_idle"},
                        },
                    }
                ],
                "fallback": {"type": "minecraft:model", "model": "myplugin:item/sunblade_base"},
            },
        }
        valid_report, valid_err = self.call_tool(
            "mc_validate_item_components",
            {
                "payload": json.dumps(clean_stack),
                "target_version": "26.3",
                "client_item_definition": json.dumps(clean_client_def),
            },
        )
        self.assertFalse(valid_err)
        self.assertEqual(valid_report["status"], "pass", valid_report["findings"])
        self.assertEqual(valid_report["finding_count"], 0)
        self.assertEqual(valid_report["expected_client_item_definition_path"], "assets/myplugin/items/sunblade.json")

    def test_mc_diagnose_crash_report_ticking_entity_and_block_entity(self) -> None:
        entity_crash = """
        ---- Minecraft Crash Report ----
        Time: 2026-11-15 11:20:00 UTC
        Description: Ticking entity

        java.lang.NullPointerException: Cannot invoke Goal.tick()
            at net.minecraft.world.entity.ai.goal.GoalSelector.tick(GoalSelector.java:120)
            at net.minecraft.world.entity.LivingEntity.aiStep(LivingEntity.java:3100)

        -- Entity being ticked --
        Details:
            Entity Type: minecraft:creeper (net.minecraft.world.entity.monster.Creeper)
            Entity ID: 9942
            Entity Name: Creeper
            Entity's Exact location: 200.50, 65.00, -100.50
            Entity's Block location: World: (200,65,-101)

        -- System Details --
        Details:
            Minecraft Version: 1.21.4
            Paper: true
        """
        report, is_err = self.call_tool("mc_diagnose_crash_report", {"crash_report": entity_crash, "sarif": True})
        self.assertFalse(is_err)
        self.assertEqual(report["status"], "fail")
        self.assertEqual(report["root_cause_category"], "TICKING_ENTITY")
        self.assertEqual(report["offending_component"]["name"], "minecraft:creeper")
        self.assertEqual(report["offending_component"]["location"], "World: (200,65,-101)")
        self.assertIn("kill", report["remediation_steps"][0])
        self.assertIn("sarif_report", report)
        self.assertEqual(len(report["sarif_report"]["runs"][0]["results"]), 1)

        block_entity_crash = """
        ---- Minecraft Crash Report ----
        Time: 2026-11-15 11:25:00 UTC
        Description: Ticking block entity

        java.lang.IllegalStateException: Corrupted container inventory
            at net.minecraft.world.level.block.entity.HopperBlockEntity.tryMoveItems(HopperBlockEntity.java:150)

        -- Block entity being ticked --
        Details:
            Block location: World: (12,64,-88)
            Block: minecraft:hopper[facing=down,enabled=true]
            Block Entity Type: minecraft:hopper

        -- System Details --
        Details:
            Minecraft Version: 26.3
            Folia: true
        """
        be_report, be_err = self.call_tool("mc_diagnose_crash_report", {"crash_report": block_entity_crash})
        self.assertFalse(be_err)
        self.assertEqual(be_report["status"], "fail")
        self.assertEqual(be_report["root_cause_category"], "TICKING_BLOCK_ENTITY")
        self.assertEqual(be_report["server_flavor"], "folia")
        self.assertIn("setblock", be_report["remediation_steps"][0])

    def test_mc_diagnose_crash_report_mixin_linkage_and_oom(self) -> None:
        mixin_crash = """
        ---- Minecraft Crash Report ----
        Description: Initializing game
        org.spongepowered.asm.mixin.transformer.throwables.MixinTransformerError: An unexpected critical error was encountered
            at org.spongepowered.asm.mixin.transformer.MixinProcessor.applyMixins(MixinProcessor.java:392)
        Caused by: org.spongepowered.asm.mixin.injection.throwables.InvalidInjectionException: Critical injection failure
            at org.spongepowered.asm.mixin.injection.struct.InjectionInfo.postInject(InjectionInfo.java:468)
        Target class: net.minecraft.client.renderer.LevelRenderer
        failing mixin: com.example.iris.mixin.LevelRendererMixin
        config [iris.mixins.json]
        """
        mix_report, mix_err = self.call_tool("mc_diagnose_crash_report", {"crash_report": mixin_crash})
        self.assertFalse(mix_err)
        self.assertEqual(mix_report["root_cause_category"], "MIXIN_APPLICATION_FAILED")
        self.assertEqual(mix_report["findings"][0]["rule_id"], "CRASH003")

        linkage_crash = """
        ---- Minecraft Crash Report ----
        Description: Exception in server tick loop
        java.lang.NoSuchMethodError: 'void org.bukkit.entity.Player.sendMessage(net.kyori.adventure.text.Component)'
            at com.myrpg.core.CombatListener.onHit(CombatListener.java:45)
            at org.bukkit.plugin.RegisteredListener.execute(RegisteredListener.java:70)
        """
        link_report, link_err = self.call_tool("mc_diagnose_crash_report", {"crash_report": linkage_crash})
        self.assertFalse(link_err)
        self.assertEqual(link_report["root_cause_category"], "LINKAGE_OR_API_MISMATCH")
        self.assertEqual(link_report["findings"][0]["rule_id"], "CRASH004")
        self.assertEqual(link_report["offending_component"]["name"], "myrpg")

        oom_crash = """
        ---- Minecraft Crash Report ----
        Description: Exception in server tick loop
        java.lang.OutOfMemoryError: Java heap space
        -- System Details --
        Details:
            Minecraft Version: 26.3
            Java Version: 25, Oracle Corporation
        """
        oom_report, oom_err = self.call_tool("mc_diagnose_crash_report", {"crash_report": oom_crash})
        self.assertFalse(oom_err)
        self.assertEqual(oom_report["root_cause_category"], "OUT_OF_MEMORY")
        self.assertEqual(oom_report["findings"][0]["rule_id"], "CRASH005")
        self.assertIn("-Xmx", oom_report["remediation_steps"][0])

    def test_mc_audit_datapack_verifies_pack_mcmeta_modern_recipes_and_cyclical_tags(self) -> None:
        clean_mcmeta = json.dumps({"pack": {"pack_format": 97, "description": "Clean Modern Datapack"}})
        clean_files = {
            "data/rpg/recipe/hero_bow.json": json.dumps({
                "type": "minecraft:crafting_shaped",
                "pattern": [" S#", "S #", " S#"],
                "key": {
                    "S": {"item": "minecraft:stick"},
                    "#": {"item": "minecraft:string"},
                },
                "result": {
                    "id": "minecraft:bow",
                    "count": 1,
                    "components": {
                        "minecraft:item_name": "Hero Bow",
                        "minecraft:unbreakable": {},
                    },
                },
            }),
            "data/rpg/tags/item/bows.json": json.dumps({
                "values": ["minecraft:bow", "minecraft:crossbow"],
            }),
            "data/rpg/function/init.mcfunction": "scoreboard objectives add rpg_mana dummy\nsay RPG initialized",
        }
        clean_res, clean_err = self.call_tool("mc_audit_datapack", {"pack_mcmeta": clean_mcmeta, "files": clean_files, "target_version": "26.3"})
        self.assertFalse(clean_err)
        self.assertEqual(clean_res["status"], "pass")
        self.assertEqual(clean_res["finding_count"], 0)

        # Mismatch pack format
        mismatch_res, mismatch_err = self.call_tool("mc_audit_datapack", {"pack_mcmeta": clean_mcmeta, "target_version": "1.21.4"})
        self.assertFalse(mismatch_err)
        self.assertEqual(mismatch_res["status"], "fail")
        self.assertTrue(any(f["rule_id"] == "DP002" for f in mismatch_res["findings"]))

        # Legacy recipe syntax and cyclical tag references
        bad_files = {
            "data/rpg/recipe/legacy_blade.json": json.dumps({
                "type": "minecraft:crafting_shaped",
                "pattern": ["X"],
                "key": {"X": {"item": "minecraft:iron_ingot"}},
                "result": {"item": "minecraft:iron_sword", "tag": "{CustomModelData:42}"},
            }),
            "data/rpg/tags/item/tag_alpha.json": json.dumps({"values": ["#rpg:tag_beta"]}),
            "data/rpg/tags/item/tag_beta.json": json.dumps({"values": ["#rpg:tag_alpha"]}),
            "data/rpg/function/slash_cmd.mcfunction": "/give @p iron_sword",
        }
        bad_res, bad_err = self.call_tool("mc_audit_datapack", {"pack_mcmeta": clean_mcmeta, "files": bad_files, "target_version": "26.3"})
        self.assertFalse(bad_err)
        self.assertEqual(bad_res["status"], "fail")
        rules = [f["rule_id"] for f in bad_res["findings"]]
        self.assertIn("DP003", rules)
        self.assertIn("DP005", rules)
        self.assertIn("DP009", rules)

    def test_mc_audit_spark_flamegraph_collapsed_and_call_tree_with_starvation(self) -> None:
        collapsed_profile = "\n".join([
            "Server thread;net.minecraft.server.MinecraftServer.tickServer;com.myrpg.guild.GuildListener.onJoin;com.zaxxer.hikari.pool.HikariPool.getConnection;com.mysql.cj.jdbc.ClientPreparedStatement.executeQuery 350",
            "Server thread;net.minecraft.server.MinecraftServer.tickServer;net.minecraft.server.level.ServerChunkCache.getChunk;com.myrpg.dungeon.ArenaLoader.loadArena 200",
            "Server thread;net.minecraft.server.MinecraftServer.tickServer;com.ticxo.modelengine.core.tick.ModelTicker.tickBones 150",
            "Server thread;net.minecraft.server.MinecraftServer.tickServer;net.minecraft.world.entity.ai.goal.GoalSelector.tick 100",
            "Craft Async Scheduler Management Thread - 1;java.util.concurrent.ThreadPoolExecutor.runWorker;java.util.concurrent.ThreadPoolExecutor.getTask 200",
        ])
        col_report, col_err = self.call_tool(
            "mc_audit_spark_flamegraph",
            {"profile": collapsed_profile, "hotspot_threshold_pct": 5.0, "sarif": True},
        )
        self.assertFalse(col_err)
        self.assertEqual(col_report["status"], "fail")
        self.assertEqual(col_report["profile_format"], "collapsed")
        self.assertEqual(col_report["async_pool_summary"]["benign_idle_parked_workers"], 1)
        self.assertEqual(len(col_report["async_pool_summary"]["starvation_events"]), 0)
        col_rules = {f["rule_id"] for f in col_report["findings"]}
        self.assertIn("SPARK-001", col_rules)
        self.assertIn("SPARK-002", col_rules)
        self.assertIn("SPARK-003", col_rules)
        self.assertIn("SPARK-007", col_rules)
        plugins_attr = {p["plugin"]: p for p in col_report["plugin_attribution"]}
        self.assertIn("ModelEngine", plugins_attr)
        self.assertTrue(plugins_attr["ModelEngine"]["indexed_in_minecraftkit"])
        self.assertIn("myrpg", plugins_attr)
        self.assertEqual(col_report["sarif_report"]["version"], "2.1.0")

        call_tree_profile = "\n".join([
            "Server thread 100.00% (5000ms)",
            "  |-- net.minecraft.server.MinecraftServer.tickChildren() 86.00% (4300ms)",
            "  |   |-- net.minecraft.world.level.block.entity.HopperBlockEntity.pushItemsTick() 34.00% (1700ms)",
            "  |   `-- net.Indyuce.mmoitems.listener.PlayerListener$$Lambda$0x00007f/0x12ab.lambda$onAttack$0() 18.00% (900ms)",
            "Folia Async Scheduler Thread #2 65.00% (3250ms)",
            "  `-- com.myrpg.economy.LedgerSync.flushBatch() 65.00% (3250ms)",
            "      `-- com.zaxxer.hikari.pool.HikariPool.getConnection() 64.00% (3200ms)",
        ])
        tree_report, tree_err = self.call_tool(
            "mc_audit_spark_flamegraph",
            {"profile": call_tree_profile, "hotspot_threshold_pct": 5.0},
        )
        self.assertFalse(tree_err)
        self.assertEqual(tree_report["status"], "fail")
        self.assertEqual(tree_report["profile_format"], "call_tree")
        tree_rules = {f["rule_id"] for f in tree_report["findings"]}
        self.assertIn("SPARK-004", tree_rules)
        self.assertIn("SPARK-007", tree_rules)
        self.assertIn("SPARK-008", tree_rules)
        self.assertEqual(
            tree_report["async_pool_summary"]["starvation_events"][0]["starvation_type"],
            "HIKARICP_POOL_EXHAUSTION",
        )

    def test_mc_analyze_folia_scheduler_trace_verifies_four_domains_and_netty(self) -> None:
        multi_dump = "\n".join([
            '"Global Region Scheduler" #29 prio=5 runnable',
            "    at net.minecraft.world.level.Level.getBlockAt(Level.java:412)",
            "    at org.bukkit.craftbukkit.block.CraftBlock.setType(CraftBlock.java:198)",
            "    at com.myrpg.events.MeteorBossTask.spawnCrater(MeteorBossTask.java:87)",
            "    at io.papermc.paper.threadedregions.scheduler.FoliaGlobalRegionScheduler$GlobalScheduledTask.run(FoliaGlobalRegionScheduler.java:144)",
            "",
            '"Folia Async Scheduler Thread #3" #41 daemon prio=5 runnable',
            "    at org.bukkit.craftbukkit.entity.CraftPlayer.openInventory(CraftPlayer.java:512)",
            "    at net.Indyuce.mmoitems.gui.CraftingStationView.openAsync(CraftingStationView.java:64)",
            "    at io.papermc.paper.threadedregions.scheduler.FoliaAsyncScheduler$AsyncScheduledTask.run(FoliaAsyncScheduler.java:118)",
            "",
            '"Region Scheduler Thread #1" #24 prio=5 waiting',
            "    at java.base@25.0.1/java.util.concurrent.CompletableFuture.join(CompletableFuture.java:2118)",
            "    at org.bukkit.Bukkit.getOnlinePlayers(Bukkit.java:190)",
            "    at org.bukkit.craftbukkit.entity.CraftEntity.teleport(CraftEntity.java:320)",
            "    at com.myrpg.claim.RegionClaimService.verifyChunkOwner(RegionClaimService.java:103)",
            "    at io.papermc.paper.threadedregions.TickRegions$ConcreteRegionSection.tickRegion(TickRegions.java:390)",
            "",
            '"Netty Epoll Server IO #1" #18 daemon prio=5 runnable',
            "    at org.bukkit.craftbukkit.block.CraftBlock.setBlockData(CraftBlock.java:210)",
            "    at com.myrpg.packet.CustomPacketHandler.channelRead(CustomPacketHandler.java:55)",
            "    at io.netty.channel.epoll.EpollEventLoop.run(EpollEventLoop.java:410)",
        ])
        res, err = self.call_tool("mc_analyze_folia_scheduler_trace", {"trace": multi_dump, "sarif": True})
        self.assertFalse(err)
        self.assertEqual(res["status"], "fail")
        self.assertEqual(res["threads_analyzed"], 4)
        self.assertEqual(set(res["domains_detected"]), {"GLOBAL", "ASYNC", "REGION", "NETTY"})
        codes = {f["rule_id"] for f in res["findings"]}
        self.assertIn("FOLIA-TRC-001", codes)
        self.assertIn("FOLIA-TRC-002", codes)
        self.assertIn("FOLIA-TRC-003", codes)
        self.assertIn("FOLIA-TRC-004", codes)
        self.assertIn("FOLIA-TRC-005", codes)
        self.assertEqual(res["sarif_report"]["version"], "2.1.0")

        # Legacy BukkitScheduler + missing retired callback
        legacy_snippet = "\n".join([
            "at org.bukkit.Bukkit.getScheduler()(Bukkit.java:162)",
            "at io.papermc.paper.threadedregions.scheduler.EntityScheduler.runDelayed(EntityScheduler.java:70)",
            "// entity.getScheduler().runDelayed(plugin, task -> {}, null, 20L)",
        ])
        leg_res, leg_err = self.call_tool(
            "mc_analyze_folia_scheduler_trace",
            {"trace": legacy_snippet, "declared_domain": "entity"},
        )
        self.assertFalse(leg_err)
        leg_codes = {f["rule_id"] for f in leg_res["findings"]}
        self.assertIn("FOLIA-TRC-006", leg_codes)
        self.assertIn("FOLIA-TRC-007", leg_codes)

        # Clean region trace passes
        clean_trace = "\n".join([
            '"Region Scheduler Thread #0" #22 prio=5 runnable',
            "    at com.ticxo.modelengine.core.ModelUpdater.stepRegionModels(ModelUpdater.java:74)",
            "    at io.papermc.paper.threadedregions.TickRegions$ConcreteRegionSection.tickRegion(TickRegions.java:390)",
        ])
        clean_res, clean_err = self.call_tool("mc_analyze_folia_scheduler_trace", {"trace": clean_trace})
        self.assertFalse(clean_err)
        self.assertEqual(clean_res["status"], "pass")
        self.assertEqual(clean_res["finding_count"], 0)

    def test_mc_audit_packet_codec_wire_budget_and_netty_rules(self) -> None:
        bad_codec = "\n".join([
            'public record SpellCastPayload(int spellId, UUID caster, String macro, ItemStack icon) implements CustomPacketPayload {',
            '    public static final Type<SpellCastPayload> TYPE = new Type<>(ResourceLocation.fromNamespaceAndPath("MyRPG", "SpellCast"));',
            "    public static final StreamCodec<FriendlyByteBuf, SpellCastPayload> CODEC = StreamCodec.of(",
            "        (buf, msg) -> { buf.writeVarInt(msg.spellId()); buf.writeUUID(msg.caster()); buf.writeUtf(msg.macro()); },",
            "        buf -> new SpellCastPayload(buf.readUUID().hashCode(), new UUID(0L, 0L), buf.readUtf(), ItemStack.STREAM_CODEC.decode(buf))",
            "    );",
            "    public void onPacketReceive(PacketReceiveEvent event, Player player) {",
            "        ByteBuf scratch = Unpooled.buffer(256);",
            "        ClientboundSetEntityDataPacket pkt = null;",
            "        player.getWorld().getBlockAt(0, 64, 0).setType(Material.DIAMOND_BLOCK);",
            "    }",
            "}",
        ])
        res, err = self.call_tool(
            "mc_audit_packet_codec",
            {"source": bad_codec, "direction": "serverbound", "phase": "configuration", "sarif": True},
        )
        self.assertFalse(err)
        self.assertEqual(res["status"], "fail")
        self.assertEqual(res["wire_budget"]["cap_bytes"], 32767)
        self.assertGreater(res["wire_budget"]["max_total_wire_bytes"], 32767)
        codes = {f["rule_id"] for f in res["findings"]}
        for expected in (
            "NETTY-001",
            "NETTY-002",
            "NETTY-003",
            "NETTY-004",
            "NETTY-005",
            "NETTY-006",
            "NETTY-007",
            "NETTY-008",
        ):
            self.assertIn(expected, codes)
        self.assertEqual(res["sarif_report"]["version"], "2.1.0")
        self.assertEqual(res["sarif_report"]["runs"][0]["tool"]["driver"]["semanticVersion"], "5.3.0")

        # Clean bounded RegistryFriendlyByteBuf codec with exact field wire math
        clean_codec = "\n".join([
            "public static final CustomPacketPayload.Type<RuneSyncPayload> TYPE =",
            '    new CustomPacketPayload.Type<>(ResourceLocation.fromNamespaceAndPath("myrpg", "rune_sync"));',
            "public static final StreamCodec<RegistryFriendlyByteBuf, RuneSyncPayload> CODEC = StreamCodec.composite(",
            "    ByteBufCodecs.VAR_INT, RuneSyncPayload::slot,",
            "    ByteBufCodecs.stringUtf8(64), RuneSyncPayload::runeId,",
            "    RuneSyncPayload::new",
            ");",
        ])
        clean_res, clean_err = self.call_tool(
            "mc_audit_packet_codec",
            {
                "source": clean_codec,
                "direction": "serverbound",
                "fields": [
                    {"name": "slot", "type": "varint"},
                    {"name": "caster", "type": "uuid"},
                    {"name": "rune_id", "type": "utf8", "max_length": 64},
                    {"name": "tags", "type": "collection", "max_count": 8, "element_type": "varint"},
                ],
            },
        )
        self.assertFalse(clean_err)
        self.assertEqual(clean_res["status"], "pass")
        self.assertEqual(clean_res["finding_count"], 0)
        # Channel 'myrpg:rune_sync' = 15 bytes + 1 VarInt = 16
        # slot = 5, caster = 16, rune_id = 64*3 (192) + 2 VarInt = 194, tags = 1 VarInt + 8*5 = 41 -> payload = 256, total = 272
        self.assertEqual(clean_res["wire_budget"]["channel_header_bytes"], 16)
        self.assertEqual(clean_res["wire_budget"]["max_payload_bytes"], 256)
        self.assertEqual(clean_res["wire_budget"]["max_total_wire_bytes"], 272)

    def test_mc_audit_sql_persistence_hikari_sqlite_and_folia_rules(self) -> None:
        bad_dao = "\n".join([
            "HikariConfig cfg = new HikariConfig();",
            'cfg.setJdbcUrl("jdbc:mysql://db.internal:3306/rpg");',
            "@EventHandler",
            "public void onPlayerJoin(PlayerJoinEvent event) {",
            "    Connection conn = dataSource.getConnection();",
            '    PreparedStatement ps = conn.prepareStatement("SELECT * FROM profiles WHERE name = \'" + event.getPlayer().getName() + "\'");',
            "    ps.executeQuery();",
            "    CompletableFuture.supplyAsync(() -> loadKit(event.getPlayer().getUniqueId())).thenAccept(kit -> {",
            "        event.getPlayer().getInventory().addItem(kit);",
            "    });",
            "}",
        ])
        res, err = self.call_tool(
            "mc_audit_sql_persistence",
            {
                "source": bad_dao,
                "hikari_config": {
                    "jdbc_url": "jdbc:mysql://db.internal:3306/rpg",
                    "maximum_pool_size": 20,
                    "max_lifetime_ms": 600_000,
                    "connection_timeout_ms": 15_000,
                    "mysql_wait_timeout_sec": 600,
                    "server_count": 10,
                },
                "folia": True,
                "sarif": True,
            },
        )
        self.assertFalse(err)
        self.assertEqual(res["status"], "fail")
        self.assertEqual(res["pool_sizing_report"]["fleet_total_connections"], 200)
        self.assertEqual(res["pool_sizing_report"]["recommended_max_lifetime_ms"], 540_000)
        codes = {f["rule_id"] for f in res["findings"]}
        for expected in ("SQL-001", "SQL-002", "SQL-004", "SQL-005", "SQL-006", "SQL-007"):
            self.assertIn(expected, codes)
        self.assertEqual(res["sarif_report"]["version"], "2.1.0")

        # SQLite multi-pool contention without WAL
        sqlite_res, sqlite_err = self.call_tool(
            "mc_audit_sql_persistence",
            {"hikari_config": {"jdbc_url": "jdbc:sqlite:plugins/MyRPG/data.db", "maximum_pool_size": 4}},
        )
        self.assertFalse(sqlite_err)
        self.assertEqual(sqlite_res["status"], "fail")
        self.assertIn("SQL-003", {f["rule_id"] for f in sqlite_res["findings"]})

        # Clean Folia async Kotlin .use {} + EntityScheduler hop + tuned MySQL Hikari pool
        clean_dao = "\n".join([
            "CompletableFuture.supplyAsync({",
            '    dataSource.getConnection().use { conn ->',
            '        conn.prepareStatement("SELECT coins FROM accounts WHERE uuid = ?").use { ps ->',
            "            ps.setString(1, player.uniqueId.toString())",
            "            ps.executeQuery()",
            "        }",
            "    }",
            "}, dbExecutor).thenAccept { dto ->",
            "    player.getScheduler().run(plugin, { _ -> player.getInventory().addItem(dto.reward) }, null)",
            "}",
        ])
        clean_res, clean_err = self.call_tool(
            "mc_audit_sql_persistence",
            {
                "source": clean_dao,
                "hikari_config": {
                    "jdbc_url": "jdbc:mysql://db.internal:3306/rpg",
                    "maximum_pool_size": 6,
                    "max_lifetime_ms": 540_000,
                    "connection_timeout_ms": 3_000,
                    "mysql_wait_timeout_sec": 600,
                    "server_count": 8,
                    "cache_prep_stmts": True,
                },
                "folia": True,
            },
        )
        self.assertFalse(clean_err)
        self.assertEqual(clean_res["status"], "pass")
        self.assertEqual(clean_res["finding_count"], 0)

    def test_mc_profile_chunk_io_barriers_rules_and_queueing_math(self) -> None:
        # Empty input is rejected cleanly
        _, empty_err = self.call_tool("mc_profile_chunk_io_barriers", {})
        self.assertTrue(empty_err)

        bad_chunk_src = "\n".join([
            "public void raidTeleport(World world, int cx, int cz, Plugin plugin) {",
            "    Chunk syncChunk = world.getChunkAt(cx + 2, cz);",
            "    world.addPluginChunkTicket(cx, cz, plugin);",
            "    BlockState[] tiles = syncChunk.getTileEntities();",
            "    world.locateNearestStructure(syncChunk.getBlock(0, 64, 0).getLocation(), null, 64, false);",
            "    for (int i = 0; i < 32; i++) {",
            "        world.getChunkAtAsync(cx + i, cz).join();",
            "    }",
            "}",
        ])
        bad_cfg = "\n".join([
            "sync-chunk-writes=true",
            "region-file-compression=zlib",
            "player-max-concurrent-chunk-generates: 16",
        ])
        res, err = self.call_tool(
            "mc_profile_chunk_io_barriers",
            {
                "source": bad_chunk_src,
                "config_text": bad_cfg,
                "workload": {
                    "cpu_cores": 6,
                    "player_count": 80,
                    "simulation_distance": 10,
                    "view_distance": 12,
                    "rtp_burst_per_sec": 12.0,
                    "chunks_per_rtp": 25,
                    "active_plugin_tickets": 100,
                    "ticket_radius": 2,
                    "worldgen_miss_ratio": 0.5,
                },
                "folia": True,
                "sarif": True,
            },
        )
        self.assertFalse(err)
        self.assertEqual(res["status"], "fail")
        model = res["io_barrier_model"]
        self.assertEqual(model["worker_threads"], 2)
        self.assertTrue(model["saturated"])
        self.assertIsNone(model["expected_queue_wait_ms"])
        self.assertGreater(model["backlog_growth_chunks_per_sec"], 0.0)
        self.assertEqual(model["pinned_ticket_chunks"], 2500)
        self.assertAlmostEqual(model["pinned_ticket_ram_mb"], 234.38, places=2)
        codes = {f["rule_id"] for f in res["findings"]}
        for expected in (
            "CHUNK-IO-001",
            "CHUNK-IO-002",
            "CHUNK-IO-003",
            "CHUNK-IO-004",
            "CHUNK-IO-005",
            "CHUNK-IO-006",
            "CHUNK-IO-007",
            "CHUNK-IO-008",
        ):
            self.assertIn(expected, codes)
        self.assertEqual(res["sarif_report"]["runs"][0]["tool"]["driver"]["semanticVersion"], "5.3.0")

        # Healthy sub-critical LZ4 async pipeline passes cleanly
        clean_src = "\n".join([
            "world.getChunkAtAsync(cx, cz, true, false).thenAccept(chunk -> {",
            "    Bukkit.getRegionScheduler().execute(plugin, world, cx, cz, () -> {",
            "        chunk.getTileEntities(b -> b.getType() == Material.HOPPER, false);",
            "    });",
            "});",
        ])
        clean_res, clean_err = self.call_tool(
            "mc_profile_chunk_io_barriers",
            {
                "source": clean_src,
                "config_text": "sync-chunk-writes=false\nregion-file-compression=lz4",
                "workload": {
                    "cpu_cores": 16,
                    "player_count": 30,
                    "view_distance": 10,
                    "simulation_distance": 8,
                    "rtp_burst_per_sec": 0.5,
                    "worldgen_miss_ratio": 0.1,
                },
                "folia": True,
            },
        )
        self.assertFalse(clean_err)
        self.assertEqual(clean_res["status"], "pass")
        self.assertEqual(clean_res["finding_count"], 0)
        self.assertFalse(clean_res["io_barrier_model"]["saturated"])
        self.assertIsNotNone(clean_res["io_barrier_model"]["expected_total_barrier_ms"])

    def test_mc_correlate_spark_jfr_traces_interval_overlap_deadlock_and_skew(self) -> None:
        _, empty_err = self.call_tool("mc_correlate_spark_jfr_traces", {})
        self.assertTrue(empty_err)

        spark_cpu = "\n".join([
            "Region Scheduler Thread #0;io.papermc.paper.threadedregions.TickRegions.tickRegion;com.ticxo.modelengine.core.ModelUpdater.tick;java.util.concurrent.CompletableFuture.waitingGet 450",
            "Region Scheduler Thread #1;io.papermc.paper.threadedregions.TickRegions.tickRegion 25",
            "Region Scheduler Thread #2;io.papermc.paper.threadedregions.TickRegions.tickRegion 25",
        ])
        jfr_text = "\n".join([
            'jdk.JavaMonitorEnter { startTime = 10.020s, duration = 55.0 ms, monitorClass = com.myrpg.cache.VaultLockA, eventThread = "Region Scheduler Thread #0", previousOwner = "Folia Async Scheduler Thread #1" }',
            'jdk.JavaMonitorEnter { startTime = 10.030s, duration = 45.0 ms, monitorClass = com.myrpg.cache.VaultLockB, eventThread = "Folia Async Scheduler Thread #1", previousOwner = "Region Scheduler Thread #0" }',
            'jdk.FileForce { startTime = 10.010s, duration = 60.0 ms, eventThread = "RegionFile I/O #0" }',
            'jdk.ObjectAllocationOutsideTLAB { startTime = 10.050s, duration = 0.0 ms, allocationSize = 16777216, eventThread = "Region Scheduler Thread #0", stack = "net.Indyuce.mmoitems.ItemBuilder.build" }',
            'jdk.VirtualThreadPinned { startTime = 10.060s, duration = 24.0 ms, eventThread = "VirtualThread-9" }',
        ])
        gc_tick_log = "\n".join([
            "[10.200s] Tick #200 took 200.0ms",
            "[10.150s][info][gc] GC(9) Pause Young (Evacuation Failure) 60.0ms",
            "[10.180s][info][safepoint] Safepoint: Reaching safepoint: 18.0 ms",
        ])
        res, err = self.call_tool(
            "mc_correlate_spark_jfr_traces",
            {
                "spark_profile": spark_cpu,
                "sampling_mode": "cpu",
                "jfr_events": jfr_text,
                "gc_or_tick_log": gc_tick_log,
                "tick_budget_ms": 50.0,
                "sarif": True,
            },
        )
        self.assertFalse(err)
        self.assertEqual(res["status"], "fail")
        cm = res["correlation_matrix"]
        self.assertEqual(cm["tick_spike_count"], 1)
        self.assertEqual(cm["worst_tick_ms"], 200.0)
        # Tick interval [10000, 10200] overlaps GC [10090, 10150] (60ms), TTSP [10162, 10180] (18ms), IO [10010, 10070] (60ms), Locks [10020, 10075] (55ms)
        self.assertEqual(cm["overlapping_gc_ms"], 60.0)
        self.assertEqual(cm["overlapping_ttsp_ms"], 18.0)
        self.assertEqual(cm["overlapping_io_ms"], 60.0)
        self.assertEqual(cm["overlapping_lock_ms"], 55.0)
        self.assertTrue(cm["has_lock_cycle"])
        self.assertEqual(cm["outside_tlab_mb"], 16.0)
        self.assertGreater(cm["region_skew"]["gini_coefficient"], 0.45)
        self.assertIn("ModelEngine", cm["plugin_attribution_weights"])
        self.assertIn("MMOItems", cm["plugin_attribution_weights"])
        codes = {f["rule_id"] for f in res["findings"]}
        for expected in (
            "CORR-001",
            "CORR-002",
            "CORR-003",
            "CORR-004",
            "CORR-005",
            "CORR-006",
            "CORR-007",
        ):
            self.assertIn(expected, codes)
        self.assertEqual(res["sarif_report"]["version"], "2.1.0")

        # Structured JSON JFR list + balanced Folia wall profile passes cleanly
        balanced_spark = "\n".join([
            "Region Scheduler Thread #0;io.papermc.paper.threadedregions.TickRegions.tickRegion 100",
            "Region Scheduler Thread #1;io.papermc.paper.threadedregions.TickRegions.tickRegion 98",
        ])
        clean_corr, clean_corr_err = self.call_tool(
            "mc_correlate_spark_jfr_traces",
            {
                "spark_profile": balanced_spark,
                "sampling_mode": "wall",
                "jfr_events": [{"type": "jdk.ExecutionSample", "start_ms": 100.0, "duration_ms": 0.0, "thread": "Region Scheduler Thread #0"}],
                "tick_budget_ms": 50.0,
            },
        )
        self.assertFalse(clean_corr_err)
        self.assertEqual(clean_corr["status"], "pass")
        self.assertEqual(clean_corr["finding_count"], 0)

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
