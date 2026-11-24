import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import { spawnSync } from "node:child_process";

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
