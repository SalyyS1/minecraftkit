import test from "node:test";
import assert from "node:assert/strict";
import { parseCliArguments } from "../lib/arguments.js";

test("install defaults to both targets", () => {
  assert.deepEqual(parseCliArguments(["install"]), { command: "install", target: "both", dryRun: false, json: false });
});

test("install accepts positional target and safe options", () => {
  assert.deepEqual(parseCliArguments(["install", "claude", "--dry-run", "--version", "2.2.1"]), {
    command: "install", target: "claude", dryRun: true, json: false, releaseVersion: "2.2.1"
  });
});

test("mcp command accepts --print-config and --root", () => {
  assert.deepEqual(parseCliArguments(["mcp", "--print-config", "--root", "/opt/minecraftkit"]), {
    command: "mcp",
    target: "both",
    dryRun: false,
    json: false,
    printConfig: true,
    kitRoot: "/opt/minecraftkit"
  });
});

test("bot-plan and showcase commands parse cleanly", () => {
  assert.deepEqual(parseCliArguments(["bot-plan", "--bots", "10", "--ram", "8", "--visual", "--json"]), {
    command: "bot-plan",
    target: "both",
    dryRun: false,
    json: true,
    bots: 10,
    ramGb: 8,
    visual: true
  });
  assert.deepEqual(parseCliArguments(["showcase", "--json"]), {
    command: "showcase",
    target: "both",
    dryRun: false,
    json: true
  });
});

test("invalid targets and versions fail closed", () => {
  assert.throws(() => parseCliArguments(["install", "cursor"]), /Invalid target/);
  assert.throws(() => parseCliArguments(["install", "--version", "latest"]), /SemVer/);
  assert.throws(() => parseCliArguments(["bot-plan", "--bots", "0"]), />= 1/);
});
