import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import { spawnSync } from "node:child_process";
import {
  redact,
  classifyAuthPrompt,
  serializeWindow,
  evaluateStageAssertion,
} from "../worker.mjs";
import { percentile, summarizePoolResults } from "../pool-runner.mjs";

const botDir = path.resolve(import.meta.dirname, "..");

test("bot/worker.mjs and bot/pool-runner.mjs pass Node syntax check", () => {
  for (const file of ["worker.mjs", "pool-runner.mjs"]) {
    const full = path.join(botDir, file);
    assert.ok(fs.existsSync(full), `${file} must exist`);
    const res = spawnSync(process.execPath, ["--check", full], { encoding: "utf8" });
    assert.equal(res.status, 0, `${file} syntax error: ${res.stderr}`);
  }
});

test("bot/worker.mjs enforces AuthMe/nLogin password redaction patterns", () => {
  const src = fs.readFileSync(path.join(botDir, "worker.mjs"), "utf8");
  assert.match(src, /REDACTED_PASSWORD/);
  assert.match(src, /REGISTER_RE/);
  assert.match(src, /LOGIN_RE/);
  assert.match(src, /process\.memoryUsage\(\)\.rss/);
});

test("bot/pool-runner.mjs enforces anti-OOM max bot concurrency cap", () => {
  const src = fs.readFileSync(path.join(botDir, "pool-runner.mjs"), "utf8");
  assert.match(src, /Math\.min\(25/);
  assert.match(src, /worker\.mjs/);
});

test("bot/worker.mjs never requires desktop display or GUI launcher", () => {
  const src = fs.readFileSync(path.join(botDir, "worker.mjs"), "utf8");
  assert.doesNotMatch(src, /minecraft-launcher|xvfb|electron/i);
  assert.match(src, /JSON\.stringify/);
});

test("redact() scrubs /login, /register, /cpw and explicit secret substrings", () => {
  assert.equal(redact("/login MySuperSecret99", "MySuperSecret99"), "/login [REDACTED_PASSWORD]");
  assert.equal(redact("/register Pass123 Pass123", "Pass123"), "/register [REDACTED_PASSWORD]");
  assert.equal(redact("Token leaked: MySuperSecret99!", "MySuperSecret99"), "Token leaked: [REDACTED_PASSWORD]!");
});

test("classifyAuthPrompt() detects English and Vietnamese register/login/authenticated prompts", () => {
  assert.equal(classifyAuthPrompt("Vui lòng đăng ký bằng /register <mật khẩu>"), "register");
  assert.equal(classifyAuthPrompt("Please login using /login <password>"), "login");
  assert.equal(classifyAuthPrompt("[AuthMe] Đăng nhập thành công!"), "authenticated");
  assert.equal(classifyAuthPrompt("Welcome to the RPG Lobby!"), "none");
});

test("serializeWindow() extracts non-empty GUI slots, enchant flags, and lore cleanly", () => {
  const win = serializeWindow({
    title: "Mythic RPG Shop",
    type: "minecraft:generic_9x3",
    slots: [
      null,
      { name: "diamond_sword", customName: "Excalibur", count: 1, enchants: [{ name: "sharpness" }], customLore: ["+25 Attack"] },
    ],
  });
  assert.equal(win.title, "Mythic RPG Shop");
  assert.equal(win.slots.length, 1);
  assert.equal(win.slots[0].slot, 1);
  assert.equal(win.slots[0].enchanted, true);
});

test("evaluateStageAssertion() verifies chat, inventory, and scoreboard assertions", () => {
  const snap = {
    chat: ["[Shop] Purchased Excalibur for 500 coins"],
    inventory: [{ item: "diamond_sword", name: "Excalibur", count: 1 }],
    scoreboard: { title: "RPG SKYBLOCK", lines: ["Coins: 1,500", "Rank: MVP"] },
  };
  assert.equal(evaluateStageAssertion("assert_chat", { pattern: "Purchased Excalibur" }, snap).passed, true);
  assert.equal(evaluateStageAssertion("assert_no_chat", { pattern: "NullPointerException" }, snap).passed, true);
  assert.equal(evaluateStageAssertion("assert_inventory", { pattern: "Excalibur", min_count: 1 }, snap).passed, true);
  assert.equal(evaluateStageAssertion("assert_scoreboard", { pattern: "Coins: 1,500" }, snap).passed, true);
  assert.equal(evaluateStageAssertion("assert_inventory", { pattern: "netherite_ingot", min_count: 2 }, snap).passed, false);
});

test("evaluateStageAssertion() verifies assert_title and assert_entity_nearby for Boss/NPC QA", () => {
  const snap = {
    position: { x: 10, y: 64, z: 10 },
    title: "BOSS SPAWNED: Crimson Dragon",
    actionbar: "HP: 2500/2500",
    entities: [
      { name: "Crimson_Dragon", x: 16, y: 64, z: 14 },
      { name: "Far_Villager", x: 200, y: 64, z: 200 },
    ],
  };
  assert.equal(evaluateStageAssertion("assert_title", { pattern: "Crimson Dragon" }, snap).passed, true);
  assert.equal(evaluateStageAssertion("assert_title", { pattern: "HP: 2500" }, snap).passed, true);
  assert.equal(evaluateStageAssertion("assert_entity_nearby", { pattern: "Crimson_Dragon", max_distance: 15 }, snap).passed, true);
  assert.equal(evaluateStageAssertion("assert_entity_nearby", { pattern: "Far_Villager", max_distance: 20 }, snap).passed, false);
});

test("evaluateStageAssertion() verifies assert_health_above and assert_position_near for PvP/Warp QA", () => {
  const snap = {
    health: 18.5,
    position: { x: 102.0, y: 65.0, z: -48.5 },
  };
  assert.equal(evaluateStageAssertion("assert_health_above", { min_health: 15 }, snap).passed, true);
  assert.equal(evaluateStageAssertion("assert_health_above", { min_health: 20 }, snap).passed, false);
  assert.equal(evaluateStageAssertion("assert_position_near", { x: 100, y: 65, z: -50, radius: 5 }, snap).passed, true);
  assert.equal(evaluateStageAssertion("assert_position_near", { x: 500, z: 500, radius: 10 }, snap).passed, false);
});

test("pool-runner summarizePoolResults() calculates p50/p95 latency and enforces RAM budget", () => {
  const summary = summarizePoolResults(
    [
      { username: "Bot1", code: 0, duration_ms: 120, rss_mb: 38.5 },
      { username: "Bot2", code: 0, duration_ms: 180, rss_mb: 41.2 },
      { username: "Bot3", code: 0, duration_ms: 240, rss_mb: 40.3 },
    ],
    512,
  );
  assert.equal(summary.poolSize, 3);
  assert.equal(summary.passed, 3);
  assert.equal(summary.screen_lock_free, true);
  assert.equal(summary.p50_duration_ms, 180);
  assert.equal(summary.p95_duration_ms, 240);
  assert.equal(summary.estimated_total_rss_mb, 120);
  assert.equal(summary.within_ram_budget, true);
  assert.equal(percentile([10, 20, 30, 40], 0.5), 20);
});
