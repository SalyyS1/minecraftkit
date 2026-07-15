import { parseCliArguments, usage } from "./arguments.js";
import { packageMetadata, ROUTES, WIKI_URL } from "./constants.js";
import { collectDoctorReport, doctorExitCode, formatDoctor } from "./doctor.js";
import { runBundledInstaller } from "./powershell.js";

function printCommands(json, output) {
  if (json) return output(JSON.stringify(ROUTES.map(([command, description]) => ({ command, description })), null, 2));
  output(ROUTES.map(([command, description]) => `${command.padEnd(12)} ${description}`).join("\n"));
}

export function runCli(argv, { output = console.log, error = console.error, runInstaller = runBundledInstaller, doctor = collectDoctorReport } = {}) {
  let options;
  try { options = parseCliArguments(argv); } catch (caught) { error(`${caught.message}\n\n${usage()}`); return 2; }

  const metadata = packageMetadata();
  if (options.command === "help") { output(usage()); return 0; }
  if (options.command === "version") { output(`${metadata.name} ${metadata.version}`); return 0; }
  if (options.command === "wiki") { output(WIKI_URL); return 0; }
  if (options.command === "commands") { printCommands(options.json, output); return 0; }
  if (options.command === "doctor") {
    const report = doctor();
    output(options.json ? JSON.stringify(report, null, 2) : formatDoctor(report));
    return doctorExitCode(report);
  }

  output(`${options.dryRun ? "Planning" : "Installing"} MinecraftKit ${metadata.version} for ${options.target} via the bundled verified bootstrap.`);
  const result = runInstaller(options);
  if (result.error) error(result.error);
  return result.code;
}
