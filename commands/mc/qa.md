---
description: Run end-to-end automated Minecraft QA (static audits, deploy/mcstage, headless bot stages, visual snapshots, crash triage) through mc:qa.
argument-hint: "[plugin jar, resource pack, server target, or full QA test cycle]"
---

# /mc:qa

Activate the installed `mc-qa` skill for the `/mc:qa` route:

<request>$ARGUMENTS</request>

Execute a closed-loop Minecraft QA pipeline with `mc_run_qa_pipeline`: budget bot resources, run static plugin and pack/shader audits (`pluginscope`, `foliascan`, `shadersmith`, `packmigrate`, `glyphsmith`), boot or deploy (`mcstage`/SFTP/panel), run headless bot stages with off-screen PNG snapshots, and triage server logs (`serverdoctor` / `mckit-bridge-plugin`).
