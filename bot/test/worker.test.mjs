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
