import { parseCliArguments, usage } from "./arguments.js";
import { ATLAS_URL, packageMetadata, PLAYGROUND_URL, REPOSITORY_URL, ROUTES, SHOWCASE_URL, WIKI_URL } from "./constants.js";
import { collectDoctorReport, doctorExitCode, formatDoctor } from "./doctor.js";
import { runMcpCommand } from "./mcp.js";
import { runBundledInstaller } from "./powershell.js";

function printCommands(json, output) {
  if (json) return output(JSON.stringify(ROUTES.map(([command, description]) => ({ command, description })), null, 2));
  output(ROUTES.map(([command, description]) => `${command.padEnd(12)} ${description}`).join("\n"));
}

export function buildBotPlan({ bots = 10, ramGb = 8, visual = false } = {}) {
  const count = Math.max(1, Math.min(25, bots));
  const hostGb = Math.max(2, Math.min(256, ramGb));
  const tier1Mb = count * 42;
  const recommendedMb = visual ? 1400 + Math.max(0, count - 1) * 42 : tier1Mb;
  const desktopTabsMb = count * 2600;
  const budgetMb = Math.round(hostGb * 1024 * 0.65);
  const fitsLocal = recommendedMb <= budgetMb;
  const savingsPct = Number((((desktopTabsMb - recommendedMb) / desktopTabsMb) * 100).toFixed(1));
  return {
    bots: count,
    hostRamGb: hostGb,
    visualCapture: Boolean(visual),
    strategy: visual
      ? `hybrid-1-xvfb-plus-${Math.max(0, count - 1)}-protocol`
      : "tier1-headless-protocol",
    estimatedRamMb: recommendedMb,
    desktopTabsRamMb: desktopTabsMb,
    ramSavingsPercent: savingsPct,
    safeLocalBudgetMb: budgetMb,
    fitsLocalHost: fitsLocal,
    screenLockFree: true,
    recommendation: fitsLocal
      ? "Run locally with zero screen/focus lock."
      : "Offload visual Docker/Xvfb container to cloud grid (oracle_free_arm64 or fly_io)."
  };
}

function printShowcase(metadata, json, output) {
  const payload = {
    name: metadata.name,
    version: metadata.version,
    showcase: SHOWCASE_URL,
    wiki: WIKI_URL,
    atlas: ATLAS_URL,
    playground: PLAYGROUND_URL,
    repository: REPOSITORY_URL
  };
  if (json) return output(JSON.stringify(payload, null, 2));
  output([
    `MinecraftKit ${metadata.version} — Live Web Suite`,
    `  Showcase : ${SHOWCASE_URL}`,
    `  Wiki     : ${WIKI_URL}`,
    `  Atlas    : ${ATLAS_URL}`,
    `  Lab      : ${PLAYGROUND_URL}`,
    `  GitHub   : ${REPOSITORY_URL}`,
    `Quick MCP  : npx -y minecraftkit mcp --print-config`
  ].join("\n"));
}

export function runCli(
  argv,
  {
    output = console.log,
    error = console.error,
    runInstaller = runBundledInstaller,
    doctor = collectDoctorReport,
    runMcp = runMcpCommand
  } = {}
) {
  let options;
  try { options = parseCliArguments(argv); } catch (caught) { error(`${caught.message}\n\n${usage()}`); return 2; }

  const metadata = packageMetadata();
  if (options.command === "help") { output(usage()); return 0; }
  if (options.command === "version") { output(`${metadata.name} ${metadata.version}`); return 0; }
  if (options.command === "wiki") { output(WIKI_URL); return 0; }
  if (options.command === "showcase") { printShowcase(metadata, options.json, output); return 0; }
  if (options.command === "bot-plan") {
    const plan = buildBotPlan({ bots: options.bots, ramGb: options.ramGb, visual: options.visual });
    if (options.json) {
      output(JSON.stringify(plan, null, 2));
    } else {
      output([
        `MinecraftKit Anti-OOM Bot Plan (${plan.bots} bots on ${plan.hostRamGb} GB host)`,
        `  Strategy       : ${plan.strategy}`,
        `  Estimated RAM  : ${plan.estimatedRamMb} MB (vs ${plan.desktopTabsRamMb} MB desktop tabs — saves ${plan.ramSavingsPercent}%)`,
        `  Safe Budget    : ${plan.safeLocalBudgetMb} MB (${plan.fitsLocalHost ? "FITS LOCALLY" : "OFFLOAD TO CLOUD"})`,
        `  Screen Lock    : none (100% off-screen)`,
        `  Next Step      : ${plan.recommendation}`
      ].join("\n"));
    }
    return 0;
  }
  if (options.command === "commands") { printCommands(options.json, output); return 0; }
  if (options.command === "mcp") { return runMcp(options, { output, error }); }
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
