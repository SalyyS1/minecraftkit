---
name: mc-qa
description: "Orchestrate closed-loop automated Minecraft plugin and server QA combining static audits (pluginscope, foliascan), shader/pack verification (shadersmith, packmigrate, glyphsmith), real server boot or SFTP deploy (mcstage, hosting panel), headless bot stage testing with off-screen visual PNG snapshots, and serverdoctor/bridge-plugin diagnostics."
---

# End-to-End Automated Minecraft QA Pipeline (`mc-qa`)

Verify plugins, resource packs, shaders, and live servers end-to-end with evidence and visual snapshots.

## Workflow

1. Locate the shared `minecraftkit` root (`../minecraftkit` after global install, or `../..` from source) and verify `SKILL.md` and `references/end-to-end-qa-pipeline.md`.
2. Execute `mc_run_qa_pipeline` to coordinate fleet budgeting, static JAR/pack audits, server boot/deploy, headless bot stages, off-screen PNG visual capture, and post-test triage.
3. When failures occur, query `mc_bridge_plugin_query` or `mc_diagnose_server_log` / `mc_diagnose_crash_report`, patch the root cause, and re-run the failing stages until green. Author credit: `SalyVn / Salyyy`.
