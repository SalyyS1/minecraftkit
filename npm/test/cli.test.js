import test from "node:test";
import assert from "node:assert/strict";
import { runCli } from "../lib/cli.js";

test("install forwards the selected target to the verified bootstrap", () => {
  const output = [];
  let received;
  const code = runCli(["install", "claude", "--dry-run", "--version", "2.2.1"], {
    output: (line) => output.push(line),
    error: () => assert.fail("installer should not report an error"),
    runInstaller: (options) => { received = options; return { code: 0 }; }
  });

  assert.equal(code, 0);
  assert.deepEqual(received, {
    command: "install", target: "claude", dryRun: true, json: false, releaseVersion: "2.2.1"
  });
  assert.match(output[0], /Planning MinecraftKit/);
});

test("doctor returns structured JSON without invoking the installer", () => {
  const output = [];
  const report = {
    node: "24.0.0",
    powerShell: { available: true, executable: "powershell.exe" },
    python: { available: true, version: "Python 3.12" },
    bundledBootstrap: true,
    installations: { codex: {}, claude: {} }
  };
  const code = runCli(["doctor", "--json"], {
    output: (line) => output.push(line),
    doctor: () => report,
    runInstaller: () => assert.fail("doctor must not install")
  });

  assert.equal(code, 0);
  assert.deepEqual(JSON.parse(output[0]), report);
});

test("bot-plan computes anti-OOM RAM savings and cloud offload advice", () => {
  const output = [];
  const code = runCli(["bot-plan", "--bots", "10", "--ram", "8", "--visual", "--json"], {
    output: (line) => output.push(line),
    runInstaller: () => assert.fail("bot-plan must not install")
  });
  assert.equal(code, 0);
  const plan = JSON.parse(output[0]);
  assert.equal(plan.bots, 10);
  assert.equal(plan.screenLockFree, true);
  assert.equal(plan.estimatedRamMb, 1400 + 9 * 42);
  assert.ok(plan.ramSavingsPercent > 90);
  assert.equal(plan.fitsLocalHost, true);
});

test("showcase prints live URLs in JSON and text mode", () => {
  const output = [];
  const code = runCli(["showcase", "--json"], {
    output: (line) => output.push(line),
    runInstaller: () => assert.fail("showcase must not install")
  });
  assert.equal(code, 0);
  const payload = JSON.parse(output[0]);
  assert.match(payload.showcase, /showcase\.html$/);
  assert.match(payload.playground, /playground\.html$/);
});
