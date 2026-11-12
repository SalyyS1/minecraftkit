import { existsSync } from "node:fs";
import { homedir } from "node:os";
import { join, resolve } from "node:path";
import { spawnSync } from "node:child_process";
import { PACKAGE_DIRECTORY } from "./constants.js";

function parsePythonVersion(raw) {
  const match = /Python\s+(\d+)\.(\d+)/i.exec(String(raw || ""));
  if (!match) return null;
  return { major: Number(match[1]), minor: Number(match[2]) };
}

export function resolvePython({ platform = process.platform, spawn = spawnSync } = {}) {
  const candidates = platform === "win32" ? ["python", "python3"] : ["python3", "python"];
  for (const executable of candidates) {
    const result = spawn(executable, ["--version"], {
      encoding: "utf8",
      stdio: "pipe",
      windowsHide: true
    });
    if (result.error || result.status !== 0) continue;
    const rawVersion = String(result.stdout || result.stderr || "").trim();
    const parsed = parsePythonVersion(rawVersion);
    if (parsed && (parsed.major < 3 || (parsed.major === 3 && parsed.minor < 10))) {
      continue;
    }
    return { executable, version: rawVersion || null };
  }
  return null;
}

function isValidKitRoot(candidate) {
  if (!candidate) return false;
  const full = resolve(candidate);
  return (
    existsSync(join(full, "scripts", "mcp_server.py")) &&
    existsSync(join(full, "data", "api-index.json"))
  );
}

export function resolveMcpScript({
  kitRoot,
  cwd = process.cwd(),
  env = process.env,
  home = homedir(),
  packageDir = PACKAGE_DIRECTORY
} = {}) {
  if (kitRoot) {
    const explicitRoot = resolve(kitRoot);
    if (!isValidKitRoot(explicitRoot)) {
      return { error: `Invalid MinecraftKit root (missing scripts/mcp_server.py or data/api-index.json): ${explicitRoot}` };
    }
    return { root: explicitRoot, scriptPath: join(explicitRoot, "scripts", "mcp_server.py") };
  }

  const candidates = [
    env.MINECRAFTKIT_ROOT,
    cwd,
    resolve(packageDir, ".."),
    join(home, ".claude", "skills", "minecraftkit"),
    join(home, ".agents", "skills", "minecraftkit")
  ];

  for (const candidate of candidates) {
    if (!candidate) continue;
    if (isValidKitRoot(candidate)) {
      const root = resolve(candidate);
      return { root, scriptPath: join(root, "scripts", "mcp_server.py") };
    }
  }
  return null;
}

export function formatMcpConfig({ pythonExecutable = null, scriptPath = null } = {}) {
  if (pythonExecutable && scriptPath) {
    return {
      mcpServers: {
        minecraftkit: {
          command: pythonExecutable,
          args: ["-B", scriptPath]
        }
      }
    };
  }
  return {
    mcpServers: {
      minecraftkit: {
        command: "npx",
        args: ["-y", "minecraftkit", "mcp"]
      }
    }
  };
}

export function runMcpCommand(
  options,
  {
    output = console.log,
    error = console.error,
    platform = process.platform,
    spawn = spawnSync,
    cwd = process.cwd(),
    env = process.env,
    home = homedir(),
    packageDir = PACKAGE_DIRECTORY
  } = {}
) {
  const resolved = resolveMcpScript({ kitRoot: options.kitRoot, cwd, env, home, packageDir });
  if (resolved && resolved.error) {
    error(resolved.error);
    return 1;
  }

  const python = resolvePython({ platform, spawn });
  if (options.printConfig) {
    const config = formatMcpConfig({
      pythonExecutable: python ? python.executable : null,
      scriptPath: resolved ? resolved.scriptPath : null
    });
    output(JSON.stringify(config, null, 2));
    return 0;
  }

  if (!resolved) {
    error(
      "MinecraftKit catalogs were not found locally. Run 'npx minecraftkit install --target both' first, or run from a minecraftkit checkout (or pass --root <dir>)."
    );
    return 1;
  }
  if (!python) {
    error("Python 3.10+ was not found on PATH. Install python3, then run 'minecraftkit doctor'.");
    return 1;
  }

  const result = spawn(python.executable, ["-B", resolved.scriptPath, "--root", resolved.root], {
    stdio: "inherit",
    windowsHide: true
  });
  if (result.error) {
    error(result.error.message);
    return 1;
  }
  return result.status ?? 1;
}
