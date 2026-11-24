---
description: Run end-to-end automated Minecraft QA (static audits, deploy/mcstage, headless bot stages, visual snapshots, crash triage) through mc:qa.
argument-hint: "[plugin jar, resource pack, server target, or full QA test cycle]"
---

# /mc:qa

Activate the installed `mc-qa` skill for the `/mc:qa` route:

<request>$ARGUMENTS</request>

Execute a closed-loop Minecraft QA pipeline with `mc_qa_run_full_lifecycle` / `mc_run_qa_pipeline`: verify toolchain readiness via `mc_suite_full_ecosystem_doctor`, budget bot resources, run static plugin/security/world/shader/pack audits (`pluginscope`, `foliascan`, `shadersmith`, `packmigrate`, `glyphsmith`, `mc_audit_server_exploits`, `mc_world_audit_integrity`, `mc_audit_proxy_topology`), boot or deploy (`mcstage`/SFTP/panel), run headless bot stages with inline PNG/GIF/HTML proof (`mc_qa_generate_html_report`), and triage server logs & TPS sparklines (`serverdoctor` / `mckit-bridge-plugin`).
