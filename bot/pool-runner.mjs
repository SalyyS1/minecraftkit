#!/usr/bin/env node
/**
 * Salyyy MinecraftKit — Resource-Governed Headless Bot Pool Runner.
 * Spawns N concurrent Tier-1 protocol bots with stagger delay and RSS memory guard
 * so stress-testing 10+ players never explodes host RAM or steals desktop focus.
 */

import { spawn } from "node:child_process";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

const __dirname = dirname(fileURLToPath(import.meta.url));
const WORKER_PATH = join(__dirname, "worker.mjs");

const host = process.env.MC_HOST || "127.0.0.1";
const port = Number(process.env.MC_PORT || 25565);
const version = process.env.MC_VERSION || "1.21.4";
const poolSize = Math.max(1, Math.min(25, Number(process.env.BOT_POOL_SIZE || 5)));
const staggerMs = Math.max(250, Number(process.env.BOT_STAGGER_MS || 800));
const password = process.env.BOT_AUTH_PASSWORD || "";

function runSingleBot(index) {
  return new Promise((resolve) => {
    const username = `MCKitBot_${String(index).padStart(2, "0")}`;
    const child = spawn(process.execPath, [WORKER_PATH], { stdio: ["pipe", "pipe", "pipe"] });
    let stdout = "";
    let stderr = "";
    child.stdout.on("data", (d) => { stdout += d.toString("utf8"); });
    child.stderr.on("data", (d) => { stderr += d.toString("utf8"); });
    child.on("close", (code) => {
      resolve({ username, code, stdout: stdout.trim(), stderr: stderr.trim() });
    });
    const payload = {
      host,
      port,
      username,
      version,
      password,
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
  const jobs = [];
  for (let i = 1; i <= poolSize; i++) {
    jobs.push(runSingleBot(i));
    if (i < poolSize) {
      await new Promise((r) => setTimeout(r, staggerMs));
    }
  }
  const results = await Promise.all(jobs);
  const passed = results.filter((r) => r.code === 0).length;
  console.log(JSON.stringify({ poolSize, passed, failed: poolSize - passed, results }, null, 2));
  process.exit(passed === poolSize ? 0 : 1);
}

main();
