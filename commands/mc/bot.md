---
description: Launch resource-optimized headless Minecraft test bots, auto-auth, stage tests, and off-screen visual snapshots through mc:bot.
argument-hint: "[server host/port, bot stage test scenario, or resource optimization task]"
---

# /mc:bot

Activate the installed `mc-bot` skill for the `/mc:bot` route:

<request>$ARGUMENTS</request>

Plan bot concurrency with `mc_bot_plan_resources` before launching multiple bots, prefer Tier-1 headless protocol bots (~42 MB RAM/bot) or Hybrid 1 Docker/Xvfb Visual + N-1 Protocol bots over desktop tabs, run stage assertions with redacted auto-auth via `mc_bot_run_stages`, and return off-screen PNG visual snapshots directly in chat.
