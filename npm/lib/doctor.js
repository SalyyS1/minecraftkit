import { existsSync, readFileSync, readdirSync } from "node:fs";
import { homedir } from "node:os";
import { join } from "node:path";
import { spawnSync } from "node:child_process";
import { BUNDLED_BOOTSTRAP_PATH, POSIX_INSTALLER_PATH } from "./constants.js";
import { resolvePowerShell } from "./powershell.js";

function probePython(platform, spawn) {
  const candidates = platform === "win32" ? ["python", "python3"] : ["python3", "python"];
  for (const command of candidates) {
    const result = spawn(command, ["--version"], { encoding: "utf8", stdio: "pipe", windowsHide: true });
    if (!result.error && result.status === 0) {
      return { available: true, executable: command, version: String(result.stdout || result.stderr).trim() || null };
    }
  }
  return { available: false, executable: null, version: null };
}

function installedSkillState(skillsRoot) {
  const canonical = join(skillsRoot, "minecraftkit");
  const wrappers = existsSync(skillsRoot)
    ? readdirSync(skillsRoot, { withFileTypes: true }).filter((entry) => entry.isDirectory() && /^mc-[a-z]+$/.test(entry.name)).length
    : 0;
  let version = null;
  try { version = JSON.parse(readFileSync(join(canonical, "manifest.json"), "utf8")).version; } catch {}
  return { canonical: existsSync(canonical), wrappers, version };
}

export function collectDoctorReport({ home = homedir(), platform = process.platform, spawn = spawnSync } = {}) {
  const powerShell = resolvePowerShell({ platform, spawn });
  const python = probePython(platform, spawn);
  const nodeFallback = platform !== "win32" && existsSync(POSIX_INSTALLER_PATH);
  const codex = installedSkillState(join(home, ".agents", "skills"));
  const claude = installedSkillState(join(home, ".claude", "skills"));
  const claudeCommands = join(home, ".claude", "commands", "mc");
  return {
    node: process.versions.node,
    powerShell: { available: Boolean(powerShell), executable: powerShell },
    nodeFallback,
    python,
    bundledBootstrap: existsSync(BUNDLED_BOOTSTRAP_PATH),
    installations: {
      codex,
      claude: { ...claude, commands: existsSync(claudeCommands) ? readdirSync(claudeCommands).filter((name) => name.endsWith(".md")).length : 0 }
    }
  };
}

export function doctorExitCode(report) {
  const runtimeReady = Boolean(report.powerShell?.available || report.nodeFallback);
  return runtimeReady && report.python.available && report.bundledBootstrap ? 0 : 1;
}

export function formatDoctor(report) {
  const psLabel = report.powerShell.available
    ? report.powerShell.executable
    : (report.nodeFallback ? "missing (using Node POSIX fallback)" : "missing");
  const lines = [
    `Node: ${report.node}`,
    `PowerShell: ${psLabel}`,
    `Python: ${report.python.available ? report.python.version : "missing"}`,
    `Bundled bootstrap: ${report.bundledBootstrap ? "present" : "missing"}`,
    `Codex: ${report.installations.codex.canonical ? `v${report.installations.codex.version} (${report.installations.codex.wrappers} routes)` : "not installed"}`,
    `Claude: ${report.installations.claude.canonical ? `v${report.installations.claude.version} (${report.installations.claude.wrappers} routes, ${report.installations.claude.commands} commands)` : "not installed"}`
  ];
  return lines.join("\n");
}
