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

test("invalid targets and versions fail closed", () => {
  assert.throws(() => parseCliArguments(["install", "cursor"]), /Invalid target/);
  assert.throws(() => parseCliArguments(["install", "--version", "latest"]), /SemVer/);
});
