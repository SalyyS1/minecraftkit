import { TARGETS } from "./constants.js";

const COMMANDS = new Set(["install", "update", "doctor", "commands", "wiki", "version", "help"]);
const VERSION_PATTERN = /^\d+\.\d+\.\d+$/;

function requireValue(argv, index, flag) {
  const value = argv[index + 1];
  if (!value || value.startsWith("-")) throw new Error(`${flag} requires a value.`);
  return value;
}

export function parseCliArguments(argv) {
  const options = { target: "both", dryRun: false, json: false, command: "help" };
  const positional = [];

  for (let index = 0; index < argv.length; index += 1) {
    const token = argv[index];
    if (token === "--target" || token === "-t") {
      options.target = requireValue(argv, index, token);
      index += 1;
    } else if (token === "--version") {
      options.releaseVersion = requireValue(argv, index, token);
      index += 1;
    } else if (token === "--dry-run") {
      options.dryRun = true;
    } else if (token === "--json") {
      options.json = true;
    } else if (token === "--yes" || token === "-y") {
      options.yes = true;
    } else if (token === "--help" || token === "-h") {
      options.command = "help";
    } else if (token.startsWith("-")) {
      throw new Error(`Unknown option: ${token}`);
    } else {
      positional.push(token);
    }
  }

  if (positional.length) options.command = positional.shift();
  if (positional.length && ["install", "update"].includes(options.command)) {
    options.target = positional.shift();
  }
  if (positional.length) throw new Error(`Unexpected argument: ${positional[0]}`);
  if (!COMMANDS.has(options.command)) throw new Error(`Unknown command: ${options.command}`);
  if (!TARGETS.includes(options.target)) throw new Error(`Invalid target: ${options.target}. Use codex, claude, or both.`);
  if (options.releaseVersion && !VERSION_PATTERN.test(options.releaseVersion)) {
    throw new Error("--version must use x.y.z SemVer format.");
  }
  return options;
}

export function usage() {
  return `Salyyy Minecraft Kit CLI

Usage:
  minecraftkit install [codex|claude|both] [--dry-run] [--version x.y.z]
  minecraftkit update [codex|claude|both]
  minecraftkit doctor [--json]
  minecraftkit commands [--json]
  minecraftkit wiki
  minecraftkit version

Examples:
  npx minecraftkit install --target both
  minecraftkit install codex --dry-run
  minecraftkit doctor --json`;
}
