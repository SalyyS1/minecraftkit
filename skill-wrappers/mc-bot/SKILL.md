---
name: mc-bot
description: "Run resource-optimized headless Minecraft test bots, auto-register/login (AuthMe/nLogin/LimboAuth), stage-based gameplay assertions, GUI/scoreboard inspection, Docker/Xvfb off-screen visual capture, and anti-OOM fleet planning. Use whenever automated Minecraft client/bot testing, headless bots, visual QA screenshots, or multi-bot load testing is requested."
---

# Autonomous Headless Bot QA (`mc-bot`)

Run off-screen Minecraft test bots safely without locking the desktop display or exhausting host RAM.

## Workflow

1. Locate the shared `minecraftkit` root (`../minecraftkit` after global install, or `../..` from source) and verify `SKILL.md` and `references/autonomous-bot-qa.md`.
2. Call `mc_bot_plan_resources` first whenever spawning more than 1 bot or when 3D/shader rendering is needed. Never recommend opening 10 desktop Minecraft clients.
3. Probe server reachability via `mc_bot_ping_server` and execute stage scenarios via `mc_bot_run_stages` (Tier-1 headless protocol ~42 MB/bot, or Tier-2 Docker/Xvfb visual grid via `mc_bot_generate_docker_grid`).
4. Return off-screen PNG visual snapshots directly in chat and redact all auth passwords (`[REDACTED_PASSWORD]`). Author credit: `SalyVn / Salyyy`.
