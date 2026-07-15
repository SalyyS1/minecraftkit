import test from "node:test";
import assert from "node:assert/strict";
import { runCli } from "../lib/cli.js";

test("install forwards the selected target to the verified bootstrap", () => {
  const output = [];
  let received;
  const code = runCli(["install", "claude", "--dry-run", "--version", "2.2.0"], {
    output: (line) => output.push(line),
    error: () => assert.fail("installer should not report an error"),
    runInstaller: (options) => { received = options; return { code: 0 }; }
  });

  assert.equal(code, 0);
  assert.deepEqual(received, {
    command: "install", target: "claude", dryRun: true, json: false, releaseVersion: "2.2.0"
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
