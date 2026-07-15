import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { BUNDLED_BOOTSTRAP_PATH } from "../lib/constants.js";
import { buildBootstrapInvocation } from "../lib/powershell.js";

test("Windows invocation uses the local bundled bootstrap and forwards safe options", () => {
  const invocation = buildBootstrapInvocation({ target: "codex", releaseVersion: "2.1.1", dryRun: true, platform: "win32", executable: "powershell.exe" });
  assert.equal(invocation.executable, "powershell.exe");
  assert.deepEqual(invocation.args, ["-NoLogo", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", BUNDLED_BOOTSTRAP_PATH, "-Target", "codex", "-Version", "2.1.1", "-PlanOnly"]);
});

test("bundled bootstrap matches the canonical reviewed script", () => {
  const canonical = readFileSync(fileURLToPath(new URL("../../scripts/install-from-github.ps1", import.meta.url)));
  const bundled = readFileSync(BUNDLED_BOOTSTRAP_PATH);
  assert.deepEqual(bundled, canonical);
});
