# Autonomous Bot Optimization & Anti-OOM Benchmarks (EN / VI)

Opening 10 full desktop Minecraft clients consumes **~26 GB RAM**, maxes out your GPU, and steals mouse/keyboard focus so you cannot work. MinecraftKit solves this with a **3-Tier Off-Screen Architecture** — saving up to **98.4% RAM** with **zero desktop screen hijacking**.

> **Tiếng Việt:** Thay vì mở 10 cửa sổ Minecraft Desktop (~26 GB RAM, giật lag, chiếm toàn bộ màn hình), MinecraftKit sử dụng **kiến trúc 3 tầng chạy ngầm** tiết kiệm tới **98.4% RAM**, không chiếm màn hình, và có thể đẩy lên **Docker / Oracle Cloud Always-Free ($0/tháng)** hoặc **Fly.io 256 MB**.

---

## 1. RAM & CPU Comparison Table (1 to 25 Bots)

| Bot Tier / Architecture | RAM per Bot | 10 Bots Total RAM | Screen Lock? | Best Use Case |
|---|---:|---:|---|---|
| **Tier-0 Pure-Python Wire Probe** (`mc_bot_play_command_probe`) | ~18 MB | **~0.18 GB** | None (0 GUI) | SLP ping, Login -> Config -> Play handshake, command smoke test, CI |
| **Tier-1 Headless Protocol Pool** (`mc_bot_run_stages` / Mineflayer) | ~42 MB | **~0.42 GB** | None (0 GUI) | Auto-register/login (AuthMe/nLogin), chest GUI click, scoreboard, inventory, Folia load |
| **Recommended Hybrid (1 Xvfb Visual + 9 Tier-1 Protocol)** | 1.4 GB + 42 MB | **~1.78 GB** | None (Off-screen Xvfb) | Real 3D shader/resource-pack PNG/GIF/MP4 capture + 9 functional/load bots |
| **All-Visual Docker Xvfb** (`Dockerfile.visual-bot`) | ~1.4 GB | ~14.0 GB | None (Off-screen Xvfb) | Multi-angle shader/pack regression grids on 24 GB cloud hosts |
| **Full Desktop Minecraft Tabs** (Legacy manual testing) | ~2.6 GB | **~26.0 GB (OOM!)** | **YES (Focus Lock)** | Avoid for automated multi-bot testing |

---

## 2. Instant Terminal RAM Planner (`npx minecraftkit bot-plan`)

Compute safe bot counts and cloud offload triggers directly from your terminal without launching Python or Minecraft:

```bash
# Plan 10 bots with 1 off-screen Xvfb visual capture on an 8 GB laptop:
npx minecraftkit bot-plan --bots 10 --ram 8 --visual

# Machine-readable JSON for CI pipelines:
npx minecraftkit bot-plan --bots 15 --ram 8 --visual --json
```

---

## 3. Offloading Visual Grids to Cloud ($0–$5/month)

Use `mc_bot_generate_cloud_deploy` to generate ready-to-run, cgroup `mem_limit`-capped configs:

| Target (`target=...`) | Cost | Capacity | Generated Artifact |
|---|---|---|---|
| `oracle_free_arm64` | **$0/mo** (Always Free 24 GB / 4 OCPU) | 25 protocol bots + 2 Xvfb visual containers | `oracle-arm64-mckit-setup.sh` |
| `github_actions` | **$0/mo** (Public repos) | 10 protocol bots + HTML QA proof artifact | `.github/workflows/mckit-bot-qa.yml` |
| `fly_io` | ~$2/mo (256–512 MB micro-VM) | 4–8 headless Tier-1 protocol bots | `fly.mckit-bot.toml` |
| `hetzner_docker_vps` | ~$4/mo (4 GB VPS) | 6 protocol bots + 1 Xvfb visual container | `docker-compose.hetzner-mckit.yml` |
| `vps_systemd` | Existing VPS | Anti-OOM `MemoryMax` + `CPUQuota` systemd unit | `mckit-bot-pool.service` |
| `kubernetes_job` | Existing K8s | Isolated batch QA Job with `secretKeyRef` | `k8s-mckit-qa-job.yaml` |

---

## 4. Built-in Anti-OOM Guardrails

- **`BOT_MAX_RAM_MB`** in `bot/pool-runner.mjs`: monitors RSS during multi-bot runs and aborts safely before triggering host OOM-killer.
- **`init: true` + `shm_size: "512m"` + `mem_limit`** in `docker/docker-compose.testgrid.yml`: prevents zombie processes and Chromium/Xvfb `/dev/shm` crashes.
- **Zero-Java Inline PNG Proofs**: `scripts/visual_capture.py` renders 800×460 GUI/HUD snapshots and 640×240 Bridge TPS/MSPT sparklines in pure Python (~3 ms, ~0 MB extra GPU).
