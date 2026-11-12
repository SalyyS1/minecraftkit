import test from "node:test";
import assert from "node:assert/strict";
import { resolve } from "node:path";
import { PACKAGE_DIRECTORY } from "../lib/constants.js";
import { runCli } from "../lib/cli.js";
import { formatMcpConfig, resolveMcpScript, runMcpCommand } from "../lib/mcp.js";

const REPO_ROOT = resolve(PACKAGE_DIRECTORY, "..");

test("resolveMcpScript locates scripts/mcp_server.py from kit checkout", () => {
  const resolved = resolveMcpScript({ cwd: REPO_ROOT, env: {} });
  assert.ok(resolved);
  assert.equal(resolved.root, REPO_ROOT);
  assert.ok(resolved.scriptPath.endsWith("mcp_server.py"));
});

test("mcp --print-config emits standard mcpServers JSON", () => {
  const lines = [];
  const code = runCli(["mcp", "--print-config"], {
    output: (line) => lines.push(line),
    error: (msg) => assert.fail(msg)
  });
  assert.equal(code, 0);
  const parsed = JSON.parse(lines.join("\n"));
  assert.ok(parsed.mcpServers);
  assert.ok(parsed.mcpServers.minecraftkit);
  assert.equal(typeof parsed.mcpServers.minecraftkit.command, "string");
  assert.ok(Array.isArray(parsed.mcpServers.minecraftkit.args));
});

test("formatMcpConfig falls back to npx when no local installation is present", () => {
  const fallback = formatMcpConfig({ pythonExecutable: null, scriptPath: null });
  assert.deepEqual(fallback, {
    mcpServers: {
      minecraftkit: {
        command: "npx",
        args: ["-y", "minecraftkit", "mcp"]
      }
    }
  });
});

test("runMcpCommand spawns python with -B and --root", () => {
  let spawned = null;
  const code = runMcpCommand(
    { command: "mcp", kitRoot: REPO_ROOT },
    {
      platform: "linux",
      spawn: (exe, args) => {
        if (args[0] === "--version") {
          return { status: 0, stdout: "Python 3.12.2\n", stderr: "" };
        }
        spawned = { exe, args };
        return { status: 0 };
      }
    }
  );
  assert.equal(code, 0);
  assert.ok(spawned);
  assert.equal(spawned.exe, "python3");
  assert.equal(spawned.args[0], "-B");
  assert.ok(spawned.args[1].endsWith("mcp_server.py"));
  assert.equal(spawned.args[2], "--root");
  assert.equal(spawned.args[3], REPO_ROOT);
});
