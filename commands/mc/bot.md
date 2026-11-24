---
description: Launch resource-optimized headless Minecraft test bots, auto-auth, stage tests, and off-screen visual snapshots through mc:bot.
argument-hint: "[server host/port, bot stage test scenario, or resource optimization task]"
---

# /mc:bot

Activate the installed `mc-bot` skill for the `/mc:bot` route:

<request>$ARGUMENTS</request>

Plan bot concurrency with `mc_bot_plan_resources` and verify protocol compatibility (`1.20.4..26.3`) with `mc_bot_probe_protocol_matrix` before launching multiple bots. Prefer Tier-1 headless protocol bots (~18-42 MB RAM/bot, zero GUI, zero focus lock) or Hybrid 1 Docker/Xvfb Visual + N-1 Protocol bots (`mc_bot_generate_fabric_capture_script`) over desktop tabs, run stage assertions with redacted auto-auth via `mc_bot_run_stages` or `mc_bot_play_command_probe`, diff runs with `mc_bot_compare_stage_runs`, and attach off-screen PNG visual snapshots, pixel diffs (`mc_bot_visual_diff`), or storyboard GIFs (`mc_bot_record_stage_gif`) directly in chat.
