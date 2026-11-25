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
import { percentile, checkRssGuard, summarizePoolResults } from "../pool-runner.mjs";

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

test("evaluateStageAssertion() verifies assert_xp_level_above for RPG leveling & quest QA", () => {
  const snap = { xp_level: 30 };
  assert.equal(evaluateStageAssertion("assert_xp_level_above", { min_level: 25 }, snap).passed, true);
  assert.equal(evaluateStageAssertion("assert_xp_level_above", { min_level: 35 }, snap).passed, false);
});

test("evaluateStageAssertion() verifies assert_item_lore across inventory and open MMOItems GUI slots", () => {
  const snap = {
    inventory: [{ item: "netherite_sword", name: "Crimson Fang", lore: ["+42 Attack Damage", "Soulbound"] }],
    open_gui: {
      title: "Mythic Forge",
      slots: [{ slot: 13, item: "amethyst_shard", name: "Starlight Core", lore: ["Tier: Mythic", "Crit +15%"] }],
    },
  };
  assert.equal(evaluateStageAssertion("assert_item_lore", { pattern: "Soulbound" }, snap).passed, true);
  assert.equal(evaluateStageAssertion("assert_item_lore", { pattern: "Tier: Mythic" }, snap).passed, true);
  assert.equal(evaluateStageAssertion("assert_item_lore", { pattern: "Legendary Drop" }, snap).passed, false);
});

test("evaluateStageAssertion() verifies assert_actionbar and assert_gui_title for MMOCore/RPG GUIs", () => {
  const snap = {
    actionbar: "HP: 140/140 | Mana: 85/100 | Stamina: 20/20",
    open_gui: { title: "RPG Blacksmith Forge", slots: [] },
  };
  assert.equal(evaluateStageAssertion("assert_actionbar", { pattern: "Mana:\\s*85/100" }, snap).passed, true);
  assert.equal(evaluateStageAssertion("assert_actionbar", { pattern: "Rage:" }, snap).passed, false);
  assert.equal(evaluateStageAssertion("assert_gui_title", { pattern: "Blacksmith Forge" }, snap).passed, true);
  assert.equal(evaluateStageAssertion("assert_gui_title", { pattern: "Auction House" }, snap).passed, false);
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
  assert.equal(summary.peak_single_bot_rss_mb, 41.2);
  assert.equal(summary.avg_rss_mb, 40);
  assert.ok(summary.ram_saved_vs_desktop_pct > 95);
  assert.equal(summary.within_ram_budget, true);
  assert.equal(percentile([10, 20, 30, 40], 0.5), 20);
});

test("pool-runner checkRssGuard() triggers anti-OOM halt when RSS exceeds budget", () => {
  const ok = checkRssGuard(320, 512);
  assert.equal(ok.within_budget, true);
  assert.equal(ok.action, "continue");
  const over = checkRssGuard(640, 512);
  assert.equal(over.within_budget, false);
  assert.equal(over.action, "halt_spawn_anti_oom");
});

test("evaluateStageAssertion() verifies assert_bossbar title and health threshold", () => {
  const snap = {
    bossbars: [
      { title: "Crimson Dragon [Phase 2] - 02:15", health: 0.72, color: "red" },
    ],
  };
  const pass = evaluateStageAssertion("assert_bossbar", { pattern: "Crimson Dragon", min_health: 0.5 }, snap);
  assert.equal(pass.passed, true);
  const lowHp = evaluateStageAssertion("assert_bossbar", { pattern: "Crimson Dragon", min_health: 0.9 }, snap);
  assert.equal(lowHp.passed, false);
  const miss = evaluateStageAssertion("assert_bossbar", { pattern: "BedWars" }, snap);
  assert.equal(miss.passed, false);
});
