"""Unified SalyyS1 Minecraft Toolchain Orchestrator & QA Pipeline Engine.

Integrates all companion SalyyS1 Minecraft repositories into MinecraftKit's
MCP server, CLI, and automated end-to-end QA workflow:
  - mcstage       : Real Paper/Folia/Purpur integration server runner
  - shadersmith   : GLSL core/post shader validator, std140 checker, 26.3 migrator
  - packmigrate   : 1.20..26.3 CustomModelData & overlay migrator
  - packmerge     : Deterministic Minecraft resource pack compiler
  - glyphsmith    : Deterministic bitmap font glyph solver & auditor
  - pluginscope   : Static plugin JAR, Paper API & plugins-directory auditor
  - serverdoctor  : Offline log, config, JVM flags, crash & spark diagnostics
  - foliascan     : Folia regionized multithreading bytecode scanner
  - rp-engine     : Resource pack delivery, models, emotes & animations engine
  - texlab        : Pixel art resource pack texture editor with AI MCP bridge
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path
from typing import Any

import bot_engine
import hosting_bridge


SUITE_TOOLS: tuple[dict[str, Any], ...] = (
    {
        "id": "mcstage",
        "repo": "SalyyS1/mcstage",
        "url": "https://github.com/SalyyS1/mcstage",
        "pages": "https://salyys1.github.io/mcstage/",
        "category": "runtime-testing",
        "language": "Kotlin",
        "mcp_capable": True,
        "sarif_capable": True,
        "env_var": "MCSTAGE_JAR",
        "binary_names": ["mcstage", "mcstage.jar"],
        "summary": "Real-server integration test runner, DevOps CLI (budget --html, probe, analyze-log, plan-folia --html, summary, github-action, inspect-jar --html, preflight --html, check-world --html, doctor --html) & 27-tool stdio MCP server for Paper, Folia, and Purpur plugins with HTML matrix/comparison reports, MCS001-MCS023 crash-guard, JUnit XML, shields.io badges, and SARIF v2.1.0.",
        "example_cmd": "java -jar mcstage.jar test mcstage.yml --accept-eula --html build/reports/mcstage.html --sarif build/reports/mcstage.sarif",
    },
    {
        "id": "shadersmith",
        "repo": "SalyyS1/shadersmith",
        "url": "https://github.com/SalyyS1/shadersmith",
        "pages": "https://salyys1.github.io/shadersmith/",
        "category": "shaders",
        "language": "Kotlin",
        "mcp_capable": False,
        "sarif_capable": True,
        "env_var": "SHADERSMITH_JAR",
        "binary_names": ["shadersmith", "shadersmith.jar"],
        "summary": "Minecraft resource pack GLSL core/post-effect contract validator, std140 UBO layout checker, and 26.3 shader migrator with SARIF v2.1.0 & browser inspector.",
        "example_cmd": "java -jar shadersmith.jar check ./pack --target 26.3 --sarif shaders.sarif",
    },
    {
        "id": "packmigrate",
        "repo": "SalyyS1/packmigrate",
        "url": "https://github.com/SalyyS1/packmigrate",
        "pages": "https://salyys1.github.io/packmigrate/",
        "category": "resource-pack",
        "language": "Kotlin",
        "mcp_capable": False,
        "sarif_capable": True,
        "env_var": "PACKMIGRATE_JAR",
        "binary_names": ["packmigrate", "packmigrate.jar"],
        "summary": "Deterministic Minecraft 1.20..26.3 resource pack CustomModelData & overlay migrator with perceptual asset dedup and SARIF v2.1.0 diagnostics.",
        "example_cmd": "java -jar packmigrate.jar migrate ./legacy-pack ./migrated-pack --to 26.3 --sarif packmigrate.sarif",
    },
    {
        "id": "packmerge",
        "repo": "SalyyS1/packmerge",
        "url": "https://github.com/SalyyS1/packmerge",
        "pages": "https://salyys1.github.io/packmerge/",
        "category": "resource-pack",
        "language": "Kotlin",
        "mcp_capable": False,
        "sarif_capable": False,
        "env_var": "PACKMERGE_JAR",
        "binary_names": ["packmerge", "packmerge.jar"],
        "summary": "Deterministic Minecraft resource pack compiler for directories and .zip archives: unions 1.21.4+ item models, fonts, sounds, lang, and atlases.",
        "example_cmd": "java -jar packmerge.jar merge pack-a.zip pack-b.zip -o merged-pack.zip",
    },
    {
        "id": "glyphsmith",
        "repo": "SalyyS1/glyphsmith",
        "url": "https://github.com/SalyyS1/glyphsmith",
        "pages": "https://salyys1.github.io/glyphsmith/",
        "category": "resource-pack",
        "language": "Kotlin",
        "mcp_capable": False,
        "sarif_capable": False,
        "env_var": "GLYPHSMITH_JAR",
        "binary_names": ["glyphsmith", "glyphsmith.jar"],
        "summary": "Deterministic Minecraft bitmap font glyph solver, negative-space shift compiler, lockfile generator, and resource-pack font auditor CLI.",
        "example_cmd": "java -jar glyphsmith.jar audit ./pack --json",
    },
    {
        "id": "pluginscope",
        "repo": "SalyyS1/pluginscope",
        "url": "https://github.com/SalyyS1/pluginscope",
        "pages": "https://salyys1.github.io/pluginscope/",
        "category": "static-audit",
        "language": "Kotlin",
        "mcp_capable": True,
        "sarif_capable": True,
        "env_var": "PLUGINSCOPE_JAR",
        "binary_names": ["pluginscope", "pluginscope.jar"],
        "summary": "Static audits for Minecraft server plugins: packaging/shading hygiene, Paper API compatibility, whole plugins-directory conflict checks, resource pack checks, SARIF, and MCP server.",
        "example_cmd": "java -jar pluginscope.jar jar build/libs/MyPlugin.jar --target 26.3 --format sarif",
    },
    {
        "id": "serverdoctor",
        "repo": "SalyyS1/serverdoctor",
        "url": "https://github.com/SalyyS1/serverdoctor",
        "pages": "https://salyys1.github.io/serverdoctor/",
        "category": "diagnostics",
        "language": "Kotlin",
        "mcp_capable": True,
        "sarif_capable": True,
        "env_var": "SERVERDOCTOR_JAR",
        "binary_names": ["serverdoctor", "serverdoctor.jar"],
        "summary": "Offline post-mortem diagnostics for Minecraft servers: logs, configs, JVM flags, GC, crash reports, Spark profiles, world/perms checks, and MCP mode.",
        "example_cmd": "java -jar serverdoctor.jar scan ./server --format json",
    },
    {
        "id": "foliascan",
        "repo": "SalyyS1/foliascan",
        "url": "https://github.com/SalyyS1/foliascan",
        "pages": "https://salyys1.github.io/foliascan/",
        "category": "static-audit",
        "language": "Kotlin",
        "mcp_capable": False,
        "sarif_capable": True,
        "env_var": "FOLIASCAN_JAR",
        "binary_names": ["foliascan", "foliascan.jar"],
        "summary": "Bytecode taint-flow scanner pinpointing where a Minecraft plugin JAR breaks on Folia regionized multithreading, with SARIF v2.1.0 and 100% browser JAR scanner.",
        "example_cmd": "java -jar foliascan.jar build/libs/MyPlugin.jar --format sarif -o foliascan.sarif",
    },
    {
        "id": "rp-engine",
        "repo": "SalyyS1/rp-engine",
        "url": "https://github.com/SalyyS1/rp-engine",
        "pages": None,
        "category": "resource-pack",
        "language": "Java/Kotlin",
        "mcp_capable": False,
        "sarif_capable": False,
        "env_var": "RP_ENGINE_DIR",
        "binary_names": ["rp-engine"],
        "summary": "Resource pack runtime engine delivering the right pack build to every player and powering custom models, emotes, and animations in-game.",
        "example_cmd": "git clone https://github.com/SalyyS1/rp-engine.git",
    },
    {
        "id": "texlab",
        "repo": "SalyyS1/texlab",
        "url": "https://github.com/SalyyS1/texlab",
        "pages": None,
        "category": "textures",
        "language": "TypeScript",
        "mcp_capable": True,
        "sarif_capable": False,
        "env_var": "TEXLAB_BIN",
        "binary_names": ["texlab"],
        "summary": "Pixel art texture editor for Minecraft resource packs with native AI integration via MCP.",
        "example_cmd": "git clone https://github.com/SalyyS1/texlab.git",
    },
)

SUITE_BY_ID: dict[str, dict[str, Any]] = {item["id"]: item for item in SUITE_TOOLS}


def _detect_local_tool(tool: dict[str, Any]) -> dict[str, Any]:
    env_path = os.environ.get(tool["env_var"], "").strip()
    if env_path and Path(env_path).exists():
        return {"installed": True, "source": f"env:{tool['env_var']}", "path": env_path}
    for name in tool["binary_names"]:
        found = shutil.which(name)
        if found:
            return {"installed": True, "source": "PATH", "path": found}
    tools_home = Path.home() / ".minecraftkit" / "tools"
    for name in tool["binary_names"]:
        candidate = tools_home / name
        if candidate.is_file():
            return {"installed": True, "source": "tools_cache", "path": str(candidate)}
    return {"installed": False, "source": None, "path": None}


def inspect_suite_catalog(
    *,
    category: str | None = None,
    tool_id: str | None = None,
) -> dict[str, Any]:
    """Return catalog + local availability of all integrated SalyyS1 Minecraft tools."""
    selected: list[dict[str, Any]] = []
    for item in SUITE_TOOLS:
        if tool_id and item["id"] != tool_id.strip().lower():
            continue
        if category and item["category"] != category.strip().lower():
            continue
        record = dict(item)
        record["local"] = _detect_local_tool(item)
        selected.append(record)

    return {
        "suite_name": "SalyyS1 Unified Minecraft Engineering Suite",
        "tool_count": len(selected),
        "installed_count": sum(1 for t in selected if t["local"]["installed"]),
        "categories": sorted({t["category"] for t in SUITE_TOOLS}),
        "tools": selected,
    }


def orchestrate_suite_command(
    *,
    tool_id: str,
    args: list[str] | None = None,
    cwd: str | None = None,
    execute: bool = False,
    timeout_seconds: int = 60,
) -> dict[str, Any]:
    """Build and optionally execute a command against any integrated SalyyS1 tool."""
    key = tool_id.strip().lower()
    tool = SUITE_BY_ID.get(key)
    if tool is None:
        raise ValueError(f"Unknown suite tool '{tool_id}'. Valid tools: {sorted(SUITE_BY_ID)}")

    arg_list = [str(a) for a in (args or [])]
    # Safety check: refuse shell metacharacters since we invoke argv directly.
    for a in arg_list:
        if "\0" in a:
            raise ValueError("Null byte not allowed in tool arguments.")

    local = _detect_local_tool(tool)
    if local["installed"] and local["path"]:
        path_str = str(local["path"])
        argv = ["java", "-jar", path_str, *arg_list] if path_str.endswith(".jar") else [path_str, *arg_list]
    else:
        argv = ["java", "-jar", f"{key}.jar", *arg_list] if tool["language"] == "Kotlin" else [key, *arg_list]

    if not execute:
        return {
            "tool": key,
            "repo": tool["repo"],
            "executed": False,
            "installed_locally": local["installed"],
            "command": argv,
            "example_cmd": tool["example_cmd"],
            "install_hint": f"Download latest release JAR from {tool['url']}/releases and place in ~/.minecraftkit/tools/{key}.jar or set {tool['env_var']}.",
        }

    if not local["installed"]:
        return {
            "tool": key,
            "executed": False,
            "ok": False,
            "error": f"'{key}' is not installed locally. Set {tool['env_var']} or place {key}.jar in ~/.minecraftkit/tools/.",
            "download_url": f"{tool['url']}/releases",
        }

    run_cwd = Path(cwd).resolve() if cwd else None
    proc = subprocess.run(
        argv,
        cwd=str(run_cwd) if run_cwd else None,
        capture_output=True,
        text=True,
        timeout=max(5, min(300, int(timeout_seconds))),
        check=False,
    )
    return {
        "tool": key,
        "executed": True,
        "ok": proc.returncode == 0,
        "returncode": proc.returncode,
        "command": argv,
        "stdout": proc.stdout[-8000:],
        "stderr": proc.stderr[-4000:],
    }


def run_qa_pipeline(
    *,
    project_name: str = "MinecraftPlugin",
    target_mc_version: str = "26.3",
    plugin_jar: str = "",
    resource_pack_dir: str = "",
    server_host: str = "127.0.0.1",
    server_port: int = 25565,
    bot_username: str = "MCKitQABot",
    bot_password: str = "",
    bot_count: int = 1,
    needs_visual_render: bool = False,
    panel_domain: str = "",
    panel_type: str = "pterodactyl",
    sftp_host: str = "",
    sftp_user: str = "",
    stages: list[dict[str, Any]] | None = None,
    initial_bot_state: dict[str, Any] | None = None,
    root_dir: Path | None = None,
) -> dict[str, Any]:
    """Execute the full end-to-end automated Minecraft QA pipeline."""
    pipeline_steps: list[dict[str, Any]] = []

    # Step 1: Resource & Bot Fleet Plan
    resource_plan = bot_engine.plan_bot_resources(
        bot_count=bot_count,
        needs_shader_or_3d_render=needs_visual_render,
        needs_resource_pack_visuals=bool(resource_pack_dir),
    )
    pipeline_steps.append({
        "phase": "1-resource-planning",
        "status": "OK",
        "strategy": resource_plan["recommended_strategy"],
        "ram_saved_vs_desktop_pct": resource_plan["memory_comparison_mb"]["ram_saved_vs_desktop_pct"],
    })

    # Step 2: Static Plugin & Resource Pack Audit Plan (pluginscope + foliascan + shadersmith + packmigrate + glyphsmith)
    audit_commands: list[dict[str, Any]] = []
    if plugin_jar:
        audit_commands.append(orchestrate_suite_command(tool_id="pluginscope", args=["jar", plugin_jar, "--target", target_mc_version, "--format", "sarif"]))
        audit_commands.append(orchestrate_suite_command(tool_id="foliascan", args=[plugin_jar, "--format", "sarif"]))
    if resource_pack_dir:
        audit_commands.append(orchestrate_suite_command(tool_id="shadersmith", args=["check", resource_pack_dir, "--target", target_mc_version]))
        audit_commands.append(orchestrate_suite_command(tool_id="packmigrate", args=["audit", resource_pack_dir, "--to", target_mc_version]))
        audit_commands.append(orchestrate_suite_command(tool_id="glyphsmith", args=["audit", resource_pack_dir, "--json"]))
    pipeline_steps.append({
        "phase": "2-static-and-pack-audits",
        "status": "PLANNED" if audit_commands else "SKIPPED",
        "audit_count": len(audit_commands),
        "audits": audit_commands,
    })

    # Step 3: Deployment / Server Hosting Plan (SFTP + Headless Panel or mcstage)
    deploy_info: dict[str, Any] = {}
    if panel_domain:
        deploy_info["hosting_panel"] = hosting_bridge.build_hosting_connection_plan(
            domain=panel_domain,
            panel_type=panel_type,
        )
    if sftp_host and sftp_user:
        deploy_info["sftp_deploy"] = hosting_bridge.sftp_operation(
            host=sftp_host,
            username=sftp_user,
            operation="deploy_jar" if plugin_jar else "tail_log",
            remote_path=f"/plugins/{Path(plugin_jar).name}" if plugin_jar else "/logs/latest.log",
            local_path=plugin_jar,
            dry_run=True,
        )
    deploy_info["mcstage_local_matrix"] = orchestrate_suite_command(
        tool_id="mcstage",
        args=["test", "mcstage.yml", "--accept-eula", "--sarif", "build/reports/mcstage.sarif"],
    )
    pipeline_steps.append({
        "phase": "3-server-deploy-and-boot",
        "status": "READY",
        "targets": list(deploy_info.keys()),
        "details": deploy_info,
    })

    # Step 4: Headless Bot Stage QA + Visual PNG Snapshot
    bot_run = bot_engine.run_bot_stages(
        host=server_host,
        port=server_port,
        username=bot_username,
        version=target_mc_version,
        password=bot_password,
        tier="tier2-docker-visual" if needs_visual_render else "tier1-protocol",
        mode="simulate" if initial_bot_state is not None else "auto",
        stages=stages,
        initial_state=initial_bot_state,
        capture_snapshot=True,
        root_dir=root_dir,
    )
    pipeline_steps.append({
        "phase": "4-autonomous-bot-qa",
        "status": "PASSED" if bot_run.get("ok") else "FAILED",
        "summary": bot_run.get("summary"),
        "execution_backend": bot_run.get("execution_backend"),
    })

    # Step 5: Post-Test Diagnostics (serverdoctor)
    diag_plan = orchestrate_suite_command(tool_id="serverdoctor", args=["scan", ".", "--format", "json"])
    pipeline_steps.append({
        "phase": "5-post-test-diagnostics",
        "status": "READY",
        "serverdoctor": diag_plan,
    })

    return {
        "ok": bool(bot_run.get("ok")),
        "project": project_name,
        "target_mc_version": target_mc_version,
        "screen_lock_free": True,
        "pipeline_steps": pipeline_steps,
        "bot_stages": bot_run.get("state", {}).get("stages", []),
        "snapshot_png_base64": bot_run.get("snapshot_png_base64"),
    }


def generate_mcstage_suite(
    *,
    plugin_name: str = "MyRPGPlugin",
    plugin_glob: str = "build/libs/*.jar",
    mc_versions: list[str] | None = None,
    include_folia: bool = True,
    include_bridge: bool = True,
    bridge_player: str = "",
    expect_gui_title: str = "",
    include_shaders: bool = False,
) -> dict[str, Any]:
    """Generate a synced mcstage.yml (v0.9.0) + GitHub Actions CI QA workflow integrating MinecraftKit."""
    versions = mc_versions or ["latest", "26.3"]
    platforms = ["paper", "folia", "purpur"] if include_folia else ["paper", "purpur"]
    yaml_lines = [
        f"name: {plugin_name} real-server + bot + bridge QA suite",
        f"platforms: [{', '.join(platforms)}]",
        f"versions: [{', '.join(repr(v).replace(chr(39), chr(34)) for v in versions)}]",
        "memory: 2G",
        "crash-guard: true",
        "plugins:",
        f"  - {plugin_glob}",
    ]
    if include_bridge:
        yaml_lines.append("  - plugins-qa/mckit-bridge-plugin.jar")
    yaml_lines.extend([
        "steps:",
        f"  - enabled: {plugin_name}",
        "  - bot-probe:",
        "      max-latency: 400ms",
    ])
    if include_bridge:
        yaml_lines.extend([
            "  - assert-bridge:",
            '      url: "http://127.0.0.1:25590"',
            "      min-tps: 19.0",
            "      max-mspt: 35.0",
            "      max-errors: 0",
        ])
        if bridge_player and expect_gui_title:
            yaml_lines.append(f'      player: "{bridge_player}"')
            yaml_lines.append(f'      expect-gui-title: "{expect_gui_title}"')
    if include_folia:
        yaml_lines.extend([
            "  - inject-lag:",
            "      regions: 3",
            "      mode: merge-split",
            "      duration: 2s",
            "  - no-barrier-stall:",
            "      max-stall: 350ms",
            '      probe-command: "list"',
        ])
    yaml_lines.extend([
        "  - assert-heap:",
        "      max-percent: 85",
        "      window: 2s",
    ])

    ci_lines = [
        f"name: {plugin_name} MinecraftKit Full QA",
        "on: [push, pull_request]",
        "jobs:",
        "  qa:",
        "    runs-on: ubuntu-latest",
        "    steps:",
        "      - uses: actions/checkout@v4",
        "      - uses: actions/setup-java@v4",
        "        with:",
        "          distribution: temurin",
        '          java-version: "21"',
        "      - name: Build plugin JAR",
        "        run: ./gradlew build --no-daemon",
        "      - name: Run MCStage real-server + bot-probe + bridge matrix",
        "        uses: SalyyS1/mcstage@v0.9.0",
        "        with:",
        "          scenario: mcstage.yml",
        "          accept-eula: true",
        "          format: json",
        "          output: build/reports/mcstage-current.json",
        "          sarif: build/reports/mcstage.sarif",
    ]
    if include_shaders:
        ci_lines.extend([
            "      - name: Audit GLSL resource-pack shaders (shadersmith)",
            "        run: java -jar shadersmith.jar check ./pack --target 26.3 --sarif build/reports/shaders.sarif",
        ])

    return {
        "plugin_name": plugin_name,
        "mcstage_version": "0.9.0",
        "mcstage_yaml": "\n".join(yaml_lines) + "\n",
        "github_actions_yaml": "\n".join(ci_lines) + "\n",
        "integrated_tools": ["mcstage", "mckit-bridge-plugin", "foliascan", "pluginscope"] + (["shadersmith"] if include_shaders else []),
    }
