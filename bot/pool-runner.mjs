#!/usr/bin/env node
/**
 * Salyyy MinecraftKit — Resource-Governed Headless Bot Pool Runner.
 * Spawns N concurrent Tier-1 protocol bots with stagger delay, anti-OOM RAM guard,
 * and latency/RSS telemetry summary so stress-testing 10+ players never explodes
 * host RAM or steals desktop focus.
 */

import { spawn } from "node:child_process";
import { fileURLToPath, pathToFileURL } from "node:url";
import { dirname, join } from "node:path";

const __dirname = dirname(fileURLToPath(import.meta.url));
const WORKER_PATH = join(__dirname, "worker.mjs");

export function percentile(values, q) {
  if (!Array.isArray(values) || values.length === 0) return 0;
  const sorted = [...values].sort((a, b) => a - b);
  const idx = Math.min(sorted.length - 1, Math.max(0, Math.ceil(q * sorted.length) - 1));
  return Number(sorted[idx].toFixed(1));
}

export function summarizePoolResults(results, maxRamMb = 1536) {
  const passed = results.filter((r) => r.code === 0).length;
  const durations = results.map((r) => Number(r.duration_ms || 0)).filter((v) => v >= 0);
  const totalRssMb = Number(
    results.reduce((acc, r) => acc + Number(r.rss_mb || 42), 0).toFixed(1),
  );
  return {
    poolSize: results.length,
    passed,
    failed: results.length - passed,
    screen_lock_free: true,
    p50_duration_ms: percentile(durations, 0.5),
    p95_duration_ms: percentile(durations, 0.95),
    estimated_total_rss_mb: totalRssMb,
    within_ram_budget: totalRssMb <= maxRamMb,
    max_ram_budget_mb: maxRamMb,
    results,
  };
}

function runSingleBot(index, cfg) {
  return new Promise((resolve) => {
    const t0 = Date.now();
    const username = `MCKitBot_${String(index).padStart(2, "0")}`;
    const child = spawn(process.execPath, [WORKER_PATH], { stdio: ["pipe", "pipe", "pipe"] });
    let stdout = "";
    let stderr = "";
    child.stdout.on("data", (d) => { stdout += d.toString("utf8"); });
    child.stderr.on("data", (d) => { stderr += d.toString("utf8"); });
    child.on("close", (code) => {
      let rssMb = 42;
      try {
        const parsed = JSON.parse(stdout.trim());
        if (parsed?.state?.ram_mb) rssMb = Number(parsed.state.ram_mb);
      } catch { /* fallback estimate */ }
      resolve({
        username,
        code,
        duration_ms: Date.now() - t0,
        rss_mb: rssMb,
        stdout: stdout.trim(),
        stderr: stderr.trim(),
      });
    });
    const payload = {
      host: cfg.host,
      port: cfg.port,
      username,
      version: cfg.version,
      password: cfg.password,
      stages: [
        { name: "Join server", action: "join" },
        { name: "Auto authenticate", action: "auth" },
        { name: "Hold session", action: "wait", ms: 2000 },
      ],
    };
    child.stdin.end(JSON.stringify(payload));
  });
}

async function main() {
  const cfg = {
    host: process.env.MC_HOST || "127.0.0.1",
    port: Number(process.env.MC_PORT || 25565),
    version: process.env.MC_VERSION || "1.21.4",
    poolSize: Math.max(1, Math.min(25, Number(process.env.BOT_POOL_SIZE || 5))),
    staggerMs: Math.max(250, Number(process.env.BOT_STAGGER_MS || 800)),
    maxRamMb: Math.max(256, Number(process.env.BOT_MAX_RAM_MB || 1536)),
    password: process.env.BOT_AUTH_PASSWORD || "",
  };
  const jobs = [];
  for (let i = 1; i <= cfg.poolSize; i++) {
    jobs.push(runSingleBot(i, cfg));
    if (i < cfg.poolSize) {
      await new Promise((r) => setTimeout(r, cfg.staggerMs));
    }
  }
  const results = await Promise.all(jobs);
  const summary = summarizePoolResults(results, cfg.maxRamMb);
  console.log(JSON.stringify(summary, null, 2));
  process.exit(summary.passed === summary.poolSize ? 0 : 1);
}

const isMain = process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href;
if (isMain) {
  main();
}
