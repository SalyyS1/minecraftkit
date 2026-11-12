import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { BUNDLED_BOOTSTRAP_PATH, POSIX_INSTALLER_PATH } from "../lib/constants.js";
import { buildBootstrapInvocation, buildPosixBootstrapInvocation, runBundledInstaller } from "../lib/powershell.js";

test("Windows invocation uses the local bundled bootstrap and forwards safe options", () => {
  const invocation = buildBootstrapInvocation({ target: "codex", releaseVersion: "2.1.1", dryRun: true, platform: "win32", executable: "powershell.exe" });
  assert.equal(invocation.executable, "powershell.exe");
  assert.deepEqual(invocation.args, ["-NoLogo", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", BUNDLED_BOOTSTRAP_PATH, "-Target", "codex", "-Version", "2.1.1", "-PlanOnly"]);
});

test("POSIX fallback invocation uses Node and the bundled posix-installer when pwsh is absent", () => {
  const invocation = buildPosixBootstrapInvocation({
    target: "both",
    releaseVersion: "2.2.1",
    dryRun: true,
    nodeExecutable: "/usr/bin/node"
  });
  assert.equal(invocation.executable, "/usr/bin/node");
  assert.deepEqual(invocation.args, [POSIX_INSTALLER_PATH, "-Target", "both", "-Version", "2.2.1", "-PlanOnly"]);

  const calls = [];
  const result = runBundledInstaller(
    { target: "claude", dryRun: true },
    {
      platform: "linux",
      nodeExecutable: "/usr/bin/node",
      spawn: (exe, args) => {
        calls.push({ exe, args });
        if (exe === "/usr/bin/node") return { status: 0 };
        return { error: new Error("ENOENT"), status: null };
      }
    }
  );
  assert.equal(result.code, 0);
  const lastCall = calls[calls.length - 1];
  assert.equal(lastCall.exe, "/usr/bin/node");
  assert.deepEqual(lastCall.args, [POSIX_INSTALLER_PATH, "-Target", "claude", "-PlanOnly"]);
});

test("bundled bootstrap matches the canonical reviewed script", () => {
  const canonical = readFileSync(fileURLToPath(new URL("../../scripts/install-from-github.ps1", import.meta.url)));
  const bundled = readFileSync(BUNDLED_BOOTSTRAP_PATH);
  assert.deepEqual(bundled, canonical);
});
