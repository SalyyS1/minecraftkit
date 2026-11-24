import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { join } from "node:path";

export const PACKAGE_DIRECTORY = fileURLToPath(new URL("../", import.meta.url));
export const BUNDLED_BOOTSTRAP_PATH = join(PACKAGE_DIRECTORY, "lib", "install-from-github.ps1");
export const POSIX_INSTALLER_PATH = join(PACKAGE_DIRECTORY, "lib", "posix-installer.js");
export const WIKI_URL = "https://salyys1.github.io/minecraftkit/wiki.html";
export const SHOWCASE_URL = "https://salyys1.github.io/minecraftkit/showcase.html";
export const ATLAS_URL = "https://salyys1.github.io/minecraftkit/ecosystem.html";
export const PLAYGROUND_URL = "https://salyys1.github.io/minecraftkit/playground.html";
export const REPOSITORY_URL = "https://github.com/SalyyS1/minecraftkit";
export const TARGETS = ["codex", "claude", "both"];

export const ROUTES = [
  ["mc:bot", "Run headless test bots, auto-auth, stage tests & off-screen captures."],
  ["mc:build", "Build, test, version and ship Kotlin/Java plugins."],
  ["mc:core", "Resolve game, Java, fork, loader and API contracts."],
  ["mc:rpg", "Design RPG systems and verified plugin integrations."],
  ["mc:shader", "Work with core shaders, GLSL and render boundaries."],
  ["mc:dialog", "Build dialogs, client actions and validated payloads."],
  ["mc:client", "Plan client mods and vanilla-client projections."],
  ["mc:pack", "Build resource/data packs and delivery contracts."],
  ["mc:model", "Plan Blockbench models, rigs and animation pipelines."],
  ["mc:protocol", "Handle packets, codecs and version-safe wire contracts."],
  ["mc:nms", "Isolate mapped internals and exact-version adapters."],
  ["mc:ops", "Connect headlessly to hosting panels (2FA) and VPS SFTP."],
  ["mc:qa", "Orchestrate end-to-end plugin & server QA pipelines."],
  ["mc:suite", "Coordinate all 10 integrated SalyyS1 Minecraft CLI tools."]
];

export function packageMetadata() {
  return JSON.parse(readFileSync(join(PACKAGE_DIRECTORY, "package.json"), "utf8"));
}
