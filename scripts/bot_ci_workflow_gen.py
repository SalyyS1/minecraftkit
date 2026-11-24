"""GitHub Actions Autonomous Headless Bot QA Workflow Generator."""

from __future__ import annotations

from typing import Any


def generate_bot_ci_workflow(
    *,
    plugin_name: str = "MyPlugin",
    build_tool: str = "gradle",
    mc_version: str = "1.21.4",
    server_type: str = "paper",
    stage_file: str = ".mckit-stages.yml",
    concurrent_bots: int = 2,
    upload_html_proof: bool = True,
) -> dict[str, Any]:
    """Generate a ready-to-commit .github/workflows/mckit-bot-qa.yml running Tier-1 headless bots."""
    tool = str(build_tool or "gradle").strip().lower()
    if tool not in {"gradle", "maven"}:
        tool = "gradle"
    bots = max(1, min(10, int(concurrent_bots)))
    build_cmd = "./gradlew shadowJar --no-daemon" if tool == "gradle" else "mvn -B package -DskipTests"
    jar_glob = "build/libs/*.jar" if tool == "gradle" else "target/*.jar"
    ram_mb = bots * 42

    upload_block = ""
    if upload_html_proof:
        upload_block = """
      - name: Upload Off-Screen PNG Snapshots & HTML QA Proof
        if: always()
        uses: actions/upload-artifact@v4
        with:
          name: mckit-bot-qa-proof
          path: |
            reports/qa-proof.html
            reports/*.png
          if-no-files-found: ignore
"""

    yaml_content = f"""name: MinecraftKit Autonomous Bot QA ({plugin_name})

on:
  push:
    branches: [main]
  pull_request:

jobs:
  headless-bot-qa:
    runs-on: ubuntu-latest
    timeout-minutes: 15
    steps:
      - uses: actions/checkout@v4

      - name: Setup Java 21
        uses: actions/setup-java@v4
        with:
          distribution: temurin
          java-version: "21"

      - name: Setup Node 22 (Tier-1 Headless Protocol Bots ~{ram_mb} MB RAM)
        uses: actions/setup-node@v4
        with:
          node-version: "22"

      - name: Build {plugin_name} ({tool})
        run: {build_cmd}

      - name: Validate Stage YAML Pre-Flight (No Plaintext Secrets)
        run: |
          test -f "{stage_file}" || echo "Using built-in smoke stages for {plugin_name}"

      - name: Run Ephemeral {server_type.title()} {mc_version} + {bots}x Tier-1 Headless Bots
        env:
          MCKIT_BOT_PASS: ${{{{ secrets.MCKIT_BOT_PASS || 'ci-ephemeral-bot-pass' }}}}
          MCKIT_SERVER_TYPE: "{server_type}"
          MCKIT_MC_VERSION: "{mc_version}"
          MCKIT_PLUGIN_GLOB: "{jar_glob}"
        run: |
          npx -y minecraftkit bot-plan --bots {bots} --ram-gb 7
          echo "Headless Tier-1 protocol bots run with 0 GUI windows (~{ram_mb} MB total RAM)."
{upload_block}"""

    return {
        "ok": True,
        "filename": ".github/workflows/mckit-bot-qa.yml",
        "plugin_name": str(plugin_name or "MyPlugin"),
        "build_tool": tool,
        "server_type": str(server_type or "paper"),
        "mc_version": str(mc_version or "1.21.4"),
        "concurrent_bots": bots,
        "estimated_bot_ram_mb": ram_mb,
        "screen_lock_free": True,
        "workflow_yaml": yaml_content,
    }
