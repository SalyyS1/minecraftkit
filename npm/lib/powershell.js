import { spawnSync } from "node:child_process";
import { BUNDLED_BOOTSTRAP_PATH } from "./constants.js";

export function resolvePowerShell({ platform = process.platform, spawn = spawnSync } = {}) {
  const candidates = platform === "win32" ? ["powershell.exe", "pwsh.exe"] : ["pwsh", "powershell"];
  for (const executable of candidates) {
    const result = spawn(executable, ["-NoLogo", "-NoProfile", "-Command", "$PSVersionTable.PSVersion.Major"], {
      encoding: "utf8",
      stdio: "pipe",
      windowsHide: true
    });
    if (!result.error && result.status === 0) return executable;
  }
  return null;
}

export function buildBootstrapInvocation({ target, releaseVersion, dryRun, platform = process.platform, executable }) {
  const args = ["-NoLogo", "-NoProfile"];
  if (platform === "win32") args.push("-ExecutionPolicy", "Bypass");
  args.push("-File", BUNDLED_BOOTSTRAP_PATH, "-Target", target);
  if (releaseVersion) args.push("-Version", releaseVersion);
  if (dryRun) args.push("-PlanOnly");
  return { executable, args };
}

export function runBundledInstaller(options, { platform = process.platform, spawn = spawnSync } = {}) {
  const executable = resolvePowerShell({ platform, spawn });
  if (!executable) {
    return {
      code: 1,
      error: "PowerShell was not found. Install PowerShell 7 (pwsh), then run minecraftkit doctor."
    };
  }
  const invocation = buildBootstrapInvocation({ ...options, platform, executable });
  const result = spawn(invocation.executable, invocation.args, { stdio: "inherit", windowsHide: true });
  if (result.error) return { code: 1, error: result.error.message };
  return { code: result.status ?? 1 };
}
