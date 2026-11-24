# End-to-End Automated Minecraft QA Pipeline (`mc:qa`)

Orchestrate full-loop server and plugin quality assurance from build to verified fix in one repeatable workflow.

## 5-Stage Closed-Loop QA Workflow

1. **Capacity & Bot Fleet Planning (`mc_bot_plan_resources`)**: Cap RAM and choose Tier-1 Protocol vs Hybrid 1 Visual + N-1 Protocol so testing never starves the host.
2. **Static Plugin & Pack Audits (`mc_suite_orchestrate`)**: Run `pluginscope` + `foliascan` on the compiled JAR, and `shadersmith` + `packmigrate` + `glyphsmith` on the resource pack.
3. **Server Boot or Remote Deploy (`mcstage` / `mc_sftp_operations` / `mc_hosting_server_action`)**: Boot a real Paper/Folia/Purpur test matrix locally via `mcstage` or deploy atomically via SFTP + headless panel restart.
4. **Autonomous Bot Stage Testing (`mc_bot_run_stages`)**: Auto-join, auto-register/login, accept resource pack, execute gameplay stages, assert chat/GUI/scoreboard/TPS, and attach off-screen PNG visual snapshots directly to the main chat.
5. **Post-Test Triage & Auto-Fix (`serverdoctor` / `mc_diagnose_server_log` / `mc_bridge_plugin_query`)**: Inspect grouped stacktraces, correlate with bot failure stages, patch root cause, and re-run the pipeline.
