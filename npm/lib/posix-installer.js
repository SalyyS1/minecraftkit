import { createHash, randomUUID, timingSafeEqual } from "node:crypto";
import {
  copyFileSync,
  existsSync,
  lstatSync,
  mkdirSync,
  readdirSync,
  readFileSync,
  renameSync,
  rmSync,
  writeFileSync
} from "node:fs";
import https from "node:https";
import { homedir, tmpdir } from "node:os";
import { dirname, extname, join, relative, resolve, sep } from "node:path";
import { spawnSync } from "node:child_process";
import { fileURLToPath } from "node:url";
import { inflateRawSync } from "node:zlib";
import { resolvePython } from "./mcp.js";

export const MAX_ARCHIVE_BYTES = 64 * 1024 * 1024;
export const MAX_CHECKSUM_BYTES = 64 * 1024;
export const MAX_ARCHIVE_ENTRIES = 20_000;
export const MAX_EXPANDED_BYTES = 512 * 1024 * 1024;
export const MAX_REDIRECTS = 5;

const ASSET_DOWNLOAD_HOSTS = new Set([
  "github.com",
  "objects.githubusercontent.com",
  "release-assets.githubusercontent.com"
]);
const CANONICAL_SKILL_NAME = "minecraftkit";
const LEGACY_SKILL_NAME = "minecraft-rpg-kit";
const EXCLUDED_NAMES = new Set(["dist", "npm", "__pycache__", ".git", ".gitignore", ".gitattributes"]);
const RESERVED_WINDOWS_SEGMENT = /^(?:con|prn|aux|nul|com[1-9]|lpt[1-9])(?:\.|$)/i;

const CRC32_TABLE = (() => {
  const table = new Uint32Array(256);
  for (let index = 0; index < 256; index += 1) {
    let crc = index;
    for (let bit = 0; bit < 8; bit += 1) {
      crc = (crc & 1) !== 0 ? (0xedb88320 ^ (crc >>> 1)) >>> 0 : (crc >>> 1) >>> 0;
    }
    table[index] = crc >>> 0;
  }
  return table;
})();

export function computeCrc32(buffer) {
  let crc = 0xffffffff;
  for (let index = 0; index < buffer.length; index += 1) {
    crc = (CRC32_TABLE[(crc ^ buffer[index]) & 0xff] ^ (crc >>> 8)) >>> 0;
  }
  return (crc ^ 0xffffffff) >>> 0;
}

function sha256Hex(bufferOrPath) {
  const data = Buffer.isBuffer(bufferOrPath) ? bufferOrPath : readFileSync(bufferOrPath);
  return createHash("sha256").update(data).digest("hex");
}

function isSymbolicLink(targetPath) {
  if (!existsSync(targetPath)) return false;
  return lstatSync(targetPath).isSymbolicLink();
}

export function assertNoSymlinkAncestors(targetPath) {
  let current = resolve(targetPath);
  while (true) {
    if (existsSync(current) && lstatSync(current).isSymbolicLink()) {
      throw new Error(`Symbolic-link path or ancestor is not allowed: ${current}`);
    }
    const parent = dirname(current);
    if (parent === current) break;
    current = parent;
  }
}

export function assertDirectChild(childPath, parentPath) {
  const fullChild = resolve(childPath);
  const fullParent = resolve(parentPath);
  if (dirname(fullChild) !== fullParent) {
    throw new Error(`Unsafe path is not a direct child of ${fullParent}: ${fullChild}`);
  }
}

export function assertPhysicalTree(rootPath) {
  const fullRoot = resolve(rootPath);
  if (!existsSync(fullRoot)) throw new Error(`Directory does not exist: ${fullRoot}`);
  const rootStat = lstatSync(fullRoot);
  if (rootStat.isSymbolicLink() || !rootStat.isDirectory()) {
    throw new Error(`Non-physical directory root is not allowed: ${fullRoot}`);
  }
  const stack = [fullRoot];
  while (stack.length > 0) {
    const dir = stack.pop();
    for (const entry of readdirSync(dir)) {
      const fullEntry = join(dir, entry);
      const stat = lstatSync(fullEntry);
      if (stat.isSymbolicLink()) {
        throw new Error(`Symbolic link is not allowed: ${fullEntry}`);
      }
      if (stat.isDirectory()) {
        stack.push(fullEntry);
      } else if (!stat.isFile()) {
        throw new Error(`Unsupported special file is not allowed: ${fullEntry}`);
      }
    }
  }
}

function pathsOverlap(first, second) {
  const a = resolve(first);
  const b = resolve(second);
  if (a === b) return true;
  const aPrefix = a.endsWith(sep) ? a : `${a}${sep}`;
  const bPrefix = b.endsWith(sep) ? b : `${b}${sep}`;
  return aPrefix.startsWith(bPrefix) || bPrefix.startsWith(aPrefix);
}

function assertSafeName(name, label) {
  if (!/^[a-z0-9]+(?:-[a-z0-9]+)*$/.test(name)) {
    throw new Error(`Unsafe ${label} name: ${name}`);
  }
}

export function assertGitHubHttpsUrl(value, allowedHosts, label) {
  let parsed;
  try {
    parsed = new URL(String(value));
  } catch {
    throw new Error(`${label} is not an absolute URL.`);
  }
  if (
    parsed.protocol !== "https:" ||
    parsed.port !== "" ||
    parsed.username !== "" ||
    parsed.password !== "" ||
    parsed.hash !== ""
  ) {
    throw new Error(`${label} must use default-port HTTPS without credentials or a fragment: ${value}`);
  }
  if (!allowedHosts.has(parsed.hostname.toLowerCase())) {
    throw new Error(`${label} host is not allowed: ${parsed.hostname}`);
  }
  return parsed;
}

function getGitHubHeaders(env = process.env) {
  const headers = {
    Accept: "application/vnd.github+json",
    "User-Agent": "minecraftkit-secure-bootstrap/2.2",
    "X-GitHub-Api-Version": "2022-11-28"
  };
  const token = (env.GITHUB_TOKEN || env.GH_TOKEN || "").trim();
  if (token) {
    if (/[\r\n]/.test(token)) throw new Error("GitHub token contains invalid header characters.");
    headers.Authorization = `Bearer ${token}`;
  }
  return headers;
}

function getBoundedAssetSize(asset, name, maxBytes) {
  if (!asset || typeof asset !== "object" || !Object.hasOwn(asset, "size")) {
    throw new Error(`Release asset metadata is missing size for ${name}.`);
  }
  const size = Number(asset.size);
  if (!Number.isSafeInteger(size) || size <= 0) {
    throw new Error(`Release asset metadata has an invalid size for ${name}.`);
  }
  if (size > maxBytes) {
    throw new Error(`Release asset metadata exceeds the ${maxBytes} byte limit for ${name}.`);
  }
  return size;
}

export function selectReleaseAssets(release, requestedVersion = null) {
  if (!release || typeof release !== "object") {
    throw new Error("Release metadata must be a JSON object.");
  }
  if (!requestedVersion) {
    if (!Object.hasOwn(release, "draft") || !Object.hasOwn(release, "prerelease")) {
      throw new Error("Latest release metadata must declare draft and prerelease state.");
    }
    if (Boolean(release.draft) || Boolean(release.prerelease)) {
      throw new Error("Latest installation refuses draft or prerelease releases; request a named version explicitly.");
    }
  }
  const assets = Array.isArray(release.assets) ? release.assets.filter(Boolean) : [];
  const archives = assets.filter((item) => /^minecraftkit-\d+\.\d+\.\d+\.zip$/.test(String(item.name || "")));
  if (archives.length !== 1) {
    throw new Error(`Release must contain exactly one minecraftkit-X.Y.Z.zip asset; found ${archives.length}.`);
  }
  const archive = archives[0];
  const archiveName = String(archive.name);
  const versionMatch = /^minecraftkit-(\d+\.\d+\.\d+)\.zip$/.exec(archiveName);
  if (!versionMatch) throw new Error(`Unsafe MinecraftKit archive name: ${archiveName}`);
  const assetVersion = versionMatch[1];

  const checksumName = `${archiveName}.sha256`;
  const checksums = assets.filter((item) => String(item.name || "") === checksumName);
  if (checksums.length !== 1) {
    throw new Error(`Release must contain exactly one checksum asset named ${checksumName}; found ${checksums.length}.`);
  }

  const tagMatch = /^v?(\d+\.\d+\.\d+)$/.exec(String(release.tag_name || ""));
  if (!tagMatch) throw new Error(`Release tag does not contain an exact semantic version: ${release.tag_name}`);
  if (tagMatch[1] !== assetVersion) {
    throw new Error(`Release tag version ${tagMatch[1]} does not match archive version ${assetVersion}.`);
  }
  if (requestedVersion && requestedVersion !== assetVersion) {
    throw new Error(`Requested version ${requestedVersion} does not match archive version ${assetVersion}.`);
  }

  return {
    archive,
    archiveName,
    archiveBytes: getBoundedAssetSize(archive, archiveName, MAX_ARCHIVE_BYTES),
    checksum: checksums[0],
    checksumName,
    checksumBytes: getBoundedAssetSize(checksums[0], checksumName, MAX_CHECKSUM_BYTES),
    version: assetVersion
  };
}

export function readStrictChecksum(bytes, archiveName, archiveVersion) {
  for (let index = 0; index < bytes.length; index += 1) {
    if (bytes[index] > 127) throw new Error("Checksum sidecar must contain ASCII only.");
  }
  const text = bytes.toString("ascii");
  const match = /^([0-9A-Fa-f]{64}) {2}(minecraftkit-(\d+\.\d+\.\d+)\.zip)\r?\n$/.exec(text);
  if (!match) {
    throw new Error("Checksum sidecar must be one strict SHA-256 record with the exact archive name.");
  }
  if (match[2] !== archiveName || match[3] !== archiveVersion) {
    throw new Error("Checksum sidecar archive name or version does not match the selected release asset.");
  }
  return match[1].toLowerCase();
}

export function fixedTimeHexEqual(expected, actual) {
  if (typeof expected !== "string" || typeof actual !== "string" || expected.length !== actual.length) {
    return false;
  }
  const a = Buffer.from(expected.toLowerCase(), "ascii");
  const b = Buffer.from(actual.toLowerCase(), "ascii");
  return timingSafeEqual(a, b);
}

function httpsGetOnce(urlObject, headers) {
  return new Promise((resolvePromise, rejectPromise) => {
    const req = https.request(
      urlObject,
      { method: "GET", headers, timeout: 30_000 },
      (res) => resolvePromise(res)
    );
    req.on("timeout", () => req.destroy(new Error(`HTTPS request timed out for ${urlObject.href}`)));
    req.on("error", rejectPromise);
    req.end();
  });
}

async function fetchBoundedHttpsBytes(initialUrl, headers, allowedHosts, maxBytes, expectedBytes, label) {
  let current = assertGitHubHttpsUrl(initialUrl, allowedHosts, label);
  for (let redirectCount = 0; redirectCount <= MAX_REDIRECTS; redirectCount += 1) {
    const res = await httpsGetOnce(current, headers);
    const status = res.statusCode || 0;
    if (status >= 300 && status < 400) {
      res.resume();
      if (redirectCount >= MAX_REDIRECTS) {
        throw new Error(`${label} exceeded the ${MAX_REDIRECTS} redirect limit.`);
      }
      const location = res.headers.location;
      if (!location) throw new Error(`${label} redirect omitted Location header.`);
      current = assertGitHubHttpsUrl(new URL(location, current).href, allowedHosts, `${label} redirect`);
      continue;
    }
    if (status !== 200) {
      res.resume();
      throw new Error(`${label} failed with HTTP ${status}.`);
    }
    const rawLen = res.headers["content-length"];
    if (rawLen !== undefined) {
      const contentLen = Number(rawLen);
      if (Number.isFinite(contentLen) && contentLen >= 0) {
        if (contentLen > maxBytes) throw new Error(`${label} Content-Length exceeds ${maxBytes} byte limit.`);
        if (expectedBytes !== null && contentLen !== expectedBytes) {
          throw new Error(`${label} Content-Length does not match release metadata.`);
        }
      }
    }
    const chunks = [];
    let total = 0;
    for await (const chunk of res) {
      total += chunk.length;
      if (total > maxBytes) {
        res.destroy();
        throw new Error(`${label} download exceeds ${maxBytes} byte limit.`);
      }
      chunks.push(chunk);
    }
    const body = Buffer.concat(chunks, total);
    if (expectedBytes !== null && body.length !== expectedBytes) {
      throw new Error(`${label} downloaded size (${body.length}) does not match metadata (${expectedBytes}).`);
    }
    return body;
  }
  throw new Error(`${label} exceeded redirect limit.`);
}

function parseZipEntries(buffer) {
  if (buffer.length < 22) throw new Error("Archive is too small to be a valid ZIP file.");
  const minEocdOffset = Math.max(0, buffer.length - 65_557);
  let eocdOffset = -1;
  for (let pos = buffer.length - 22; pos >= minEocdOffset; pos -= 1) {
    if (buffer.readUInt32LE(pos) === 0x06054b50) {
      const commentLen = buffer.readUInt16LE(pos + 20);
      if (pos + 22 + commentLen === buffer.length) {
        eocdOffset = pos;
        break;
      }
    }
  }
  if (eocdOffset < 0) throw new Error("Archive End of Central Directory signature was not found.");

  const diskNumber = buffer.readUInt16LE(eocdOffset + 4);
  const cdDisk = buffer.readUInt16LE(eocdOffset + 6);
  const diskEntries = buffer.readUInt16LE(eocdOffset + 8);
  const totalEntries = buffer.readUInt16LE(eocdOffset + 10);
  const cdSize = buffer.readUInt32LE(eocdOffset + 12);
  const cdOffset = buffer.readUInt32LE(eocdOffset + 16);

  if (diskNumber !== 0 || cdDisk !== 0 || diskEntries !== totalEntries) {
    throw new Error("Multi-disk ZIP archives are not supported.");
  }
  if (totalEntries === 0xffff || cdSize === 0xffffffff || cdOffset === 0xffffffff) {
    throw new Error("ZIP64 archives are not supported for MinecraftKit release bundles.");
  }
  if (totalEntries > MAX_ARCHIVE_ENTRIES) {
    throw new Error(`Archive contains too many entries: ${totalEntries}`);
  }
  if (cdOffset + cdSize > eocdOffset) {
    throw new Error("Archive Central Directory bounds are invalid.");
  }

  const entries = [];
  let cursor = cdOffset;
  for (let index = 0; index < totalEntries; index += 1) {
    if (cursor + 46 > cdOffset + cdSize || buffer.readUInt32LE(cursor) !== 0x02014b50) {
      throw new Error("Corrupt Central Directory file header.");
    }
    const flags = buffer.readUInt16LE(cursor + 8);
    if ((flags & 0x0001) !== 0) throw new Error("Encrypted ZIP entries are not allowed.");
    const method = buffer.readUInt16LE(cursor + 10);
    const crc32 = buffer.readUInt32LE(cursor + 16);
    const compSize = buffer.readUInt32LE(cursor + 20);
    const uncompSize = buffer.readUInt32LE(cursor + 24);
    const nameLen = buffer.readUInt16LE(cursor + 28);
    const extraLen = buffer.readUInt16LE(cursor + 30);
    const commentLen = buffer.readUInt16LE(cursor + 32);
    const externalAttr = buffer.readUInt32LE(cursor + 38);
    const localOffset = buffer.readUInt32LE(cursor + 42);

    const headerEnd = cursor + 46 + nameLen + extraLen + commentLen;
    if (headerEnd > cdOffset + cdSize) throw new Error("Truncated Central Directory entry.");
    const name = buffer.subarray(cursor + 46, cursor + 46 + nameLen).toString("utf8");
    entries.push({ name, method, crc32, compSize, uncompSize, externalAttr, localOffset });
    cursor = headerEnd;
  }
  return entries;
}

function readZipEntryPayload(buffer, entry) {
  const offset = entry.localOffset;
  if (offset + 30 > buffer.length || buffer.readUInt32LE(offset) !== 0x04034b50) {
    throw new Error(`Missing Local File Header for ${entry.name}`);
  }
  const nameLen = buffer.readUInt16LE(offset + 26);
  const extraLen = buffer.readUInt16LE(offset + 28);
  const dataStart = offset + 30 + nameLen + extraLen;
  const dataEnd = dataStart + entry.compSize;
  if (dataEnd > buffer.length) throw new Error(`Truncated compressed payload for ${entry.name}`);
  const compressed = buffer.subarray(dataStart, dataEnd);

  let raw;
  if (entry.method === 0) {
    raw = Buffer.from(compressed);
  } else if (entry.method === 8) {
    raw = inflateRawSync(compressed, { maxOutputLength: entry.uncompSize + 1 });
  } else {
    throw new Error(`Unsupported ZIP compression method ${entry.method} in ${entry.name}`);
  }
  if (raw.length !== entry.uncompSize) {
    throw new Error(`Archive entry size does not match its declaration: ${entry.name}`);
  }
  if (computeCrc32(raw) !== entry.crc32) {
    throw new Error(`Archive entry CRC-32 mismatch: ${entry.name}`);
  }
  return raw;
}

export function expandSafeArchive(archivePath, destination) {
  const destinationPath = resolve(destination);
  mkdirSync(destinationPath, { recursive: true });
  assertNoSymlinkAncestors(destinationPath);
  const destinationPrefix = destinationPath.endsWith(sep) ? destinationPath : `${destinationPath}${sep}`;

  const zipBytes = readFileSync(archivePath);
  const entries = parseZipEntries(zipBytes);
  const seenEntries = new Map();
  const requiredDirectories = new Set();
  const validated = [];
  let expandedBytes = 0;

  for (const entry of entries) {
    const entryName = entry.name;
    if (!entryName || !entryName.trim() || entryName.includes("\0")) {
      throw new Error("Archive contains an empty or invalid entry name.");
    }
    const normalized = entryName.replace(/\\/g, "/");
    if (normalized.length >= 240) {
      throw new Error(`Archive entry path exceeds conservative limit: ${entryName}`);
    }
    if (normalized.startsWith("/") || /^[A-Za-z]:/.test(normalized)) {
      throw new Error(`Archive contains an absolute path: ${entryName}`);
    }
    const isDirectory = normalized.endsWith("/");
    const trimmed = normalized.replace(/\/+$/, "");
    const parts = trimmed.split("/");
    if (parts.length === 0 || parts[0] !== CANONICAL_SKILL_NAME) {
      throw new Error(`Archive entry is outside the canonical minecraftkit root: ${entryName}`);
    }
    for (const part of parts) {
      if (!part || !part.trim() || part === "." || part === "..") {
        throw new Error(`Archive contains path traversal or an empty segment: ${entryName}`);
      }
      if (part.includes(":") || part.endsWith(" ") || part.endsWith(".") || RESERVED_WINDOWS_SEGMENT.test(part)) {
        throw new Error(`Archive contains an unsafe path segment: ${entryName}`);
      }
    }

    const candidate = resolve(destinationPath, ...parts);
    if (!candidate.startsWith(destinationPrefix)) {
      throw new Error(`Archive entry expands outside destination directory: ${entryName}`);
    }

    const dosAttributes = entry.externalAttr & 0xffff;
    const unixType = (entry.externalAttr >>> 16) & 0xf000;
    if ((dosAttributes & 0x0400) !== 0 || unixType === 0xa000) {
      throw new Error(`Archive contains a reparse point or symbolic link: ${entryName}`);
    }
    if (unixType !== 0 && unixType !== 0x4000 && unixType !== 0x8000) {
      throw new Error(`Archive contains an unsupported special file: ${entryName}`);
    }
    if ((isDirectory && unixType === 0x8000) || (!isDirectory && unixType === 0x4000)) {
      throw new Error(`Archive entry type conflicts with its path: ${entryName}`);
    }

    const key = trimmed.normalize("NFC").toLowerCase();
    if (seenEntries.has(key)) {
      throw new Error(`Archive contains duplicate or case-colliding entries: ${entryName}`);
    }
    let ancestorPath = parts[0];
    for (let index = 1; index < parts.length; index += 1) {
      const ancestorKey = ancestorPath.normalize("NFC").toLowerCase();
      if (seenEntries.get(ancestorKey) === "file") {
        throw new Error(`Archive path descends through a file: ${entryName}`);
      }
      requiredDirectories.add(ancestorKey);
      ancestorPath = `${ancestorPath}/${parts[index]}`;
    }
    if (!isDirectory && requiredDirectories.has(key)) {
      throw new Error(`Archive file collides with an existing directory path: ${entryName}`);
    }
    seenEntries.set(key, isDirectory ? "directory" : "file");
    if (isDirectory) requiredDirectories.add(key);

    if (!isDirectory) {
      if (entry.uncompSize > MAX_EXPANDED_BYTES - expandedBytes) {
        throw new Error(`Archive expands beyond the ${MAX_EXPANDED_BYTES} byte safety limit.`);
      }
      expandedBytes += entry.uncompSize;
    }
    validated.push({ entry, candidate, isDirectory });
  }

  for (const item of validated) {
    if (item.isDirectory) {
      mkdirSync(item.candidate, { recursive: true });
      continue;
    }
    mkdirSync(dirname(item.candidate), { recursive: true });
    const content = readZipEntryPayload(zipBytes, item.entry);
    writeFileSync(item.candidate, content, { flag: "wx" });
  }

  assertPhysicalTree(destinationPath);
  const canonicalRoot = join(destinationPath, CANONICAL_SKILL_NAME);
  if (
    !existsSync(join(canonicalRoot, "SKILL.md")) ||
    !existsSync(join(canonicalRoot, "scripts", "install-global.ps1"))
  ) {
    throw new Error("Archive must contain a valid canonical minecraftkit package root.");
  }
  assertDirectChild(canonicalRoot, destinationPath);
  return canonicalRoot;
}

function getPayloadFiles(rootPath) {
  const fullRoot = resolve(rootPath);
  const results = [];
  function walk(dir) {
    const entries = readdirSync(dir).sort();
    for (const name of entries) {
      const fullPath = join(dir, name);
      const rel = relative(fullRoot, fullPath);
      const parts = rel.split(sep);
      if (parts.some((p) => EXCLUDED_NAMES.has(p))) continue;
      if (
        parts.some(
          (p) =>
            p.startsWith(".api-stage-") ||
            p.startsWith(".web-stage-") ||
            p.startsWith(".minecraftkit-stage-") ||
            p.startsWith(".minecraftkit-commands-stage-")
        )
      ) {
        continue;
      }
      const stat = lstatSync(fullPath);
      if (stat.isDirectory()) {
        walk(fullPath);
      } else if (stat.isFile() && extname(name) !== ".pyc") {
        results.push({ fullPath, relPosix: parts.join("/"), size: stat.size });
      }
    }
  }
  walk(fullRoot);
  return results.sort((a, b) => a.fullPath.localeCompare(b.fullPath));
}

function copyPayload(source, destination) {
  const files = getPayloadFiles(source);
  if (files.length === 0) throw new Error(`Payload has no files: ${source}`);
  mkdirSync(destination, { recursive: true });
  for (const file of files) {
    const target = join(destination, ...file.relPosix.split("/"));
    mkdirSync(dirname(target), { recursive: true });
    copyFileSync(file.fullPath, target);
  }
}

function getContentManifest(rootPath) {
  return getPayloadFiles(rootPath).map((file) => `${file.relPosix}|${file.size}|${sha256Hex(file.fullPath)}`);
}

function assertManifestMatch(expected, actual, label) {
  if (expected.join("\n") !== actual.join("\n")) {
    throw new Error(`Payload hash mismatch: ${label}`);
  }
}

function removeSafeTree(targetPath, parentPath) {
  if (!existsSync(targetPath)) return;
  assertDirectChild(targetPath, parentPath);
  if (isSymbolicLink(targetPath)) throw new Error(`Refusing to delete symbolic link: ${targetPath}`);
  if (lstatSync(targetPath).isDirectory()) assertPhysicalTree(targetPath);
  rmSync(targetPath, { recursive: true, force: true });
}

function getDomainDefinitions(sourceRoot) {
  const catalogPath = join(sourceRoot, "data", "minecraft-domain-catalog.json");
  if (!existsSync(catalogPath)) throw new Error(`Minecraft domain catalog is missing: ${catalogPath}`);
  const catalog = JSON.parse(readFileSync(catalogPath, "utf8"));
  const domains = Array.isArray(catalog.domains) ? catalog.domains : [];
  if (catalog.schema_version !== 1 || domains.length < 1) {
    throw new Error("Minecraft domain catalog must contain at least one schema-v1 domain.");
  }
  const seenIds = new Set();
  const seenDirs = new Set();
  const definitions = [];
  for (const domain of domains) {
    const id = String(domain.id || "");
    const directory = String(domain.skill_directory || "");
    const route = String(domain.route || "");
    assertSafeName(id, "domain");
    assertSafeName(directory, "skill directory");
    if (route !== `mc:${id}` || directory !== `mc-${id}`) {
      throw new Error(`Domain route/directory mismatch for ${id}`);
    }
    if (seenIds.has(id) || seenDirs.has(directory)) {
      throw new Error(`Duplicate Minecraft domain install name: ${id} / ${directory}`);
    }
    seenIds.add(id);
    seenDirs.add(directory);
    definitions.push({ id, directory, route });
  }
  return definitions.sort((a, b) => a.id.localeCompare(b.id));
}

function makeStamp() {
  const now = new Date();
  const pad = (n) => String(n).padStart(2, "0");
  return `${now.getFullYear()}${pad(now.getMonth() + 1)}${pad(now.getDate())}-${pad(now.getHours())}${pad(now.getMinutes())}${pad(now.getSeconds())}`;
}

function acquireLocks(roots) {
  const ordered = [...new Set(roots.map((r) => resolve(r)))].sort();
  const acquired = [];
  try {
    for (const root of ordered) {
      mkdirSync(root, { recursive: true });
      assertNoSymlinkAncestors(root);
      const lockDir = join(root, ".minecraftkit-install.lock");
      try {
        mkdirSync(lockDir);
        writeFileSync(join(lockDir, "pid"), `${process.pid}\n`, "utf8");
        acquired.push({ root, lockDir });
      } catch {
        throw new Error(`Another MinecraftKit installation is already using root: ${root}`);
      }
    }
    return acquired;
  } catch (err) {
    releaseLocks(acquired);
    throw err;
  }
}

function releaseLocks(locks) {
  for (let index = locks.length - 1; index >= 0; index -= 1) {
    try {
      rmSync(locks[index].lockDir, { recursive: true, force: true });
    } catch {}
  }
}

export function installFromSourceRoot({
  sourceRoot,
  target = "both",
  codexSkillsRoot = join(homedir(), ".agents", "skills"),
  claudeSkillsRoot = join(homedir(), ".claude", "skills"),
  claudeCommandsRoot = join(homedir(), ".claude", "commands"),
  pythonExecutable = null,
  planOnly = false,
  output = console.log,
  spawn = spawnSync
}) {
  const source = resolve(sourceRoot);
  if (!existsSync(join(source, "SKILL.md"))) {
    throw new Error(`Invalid MinecraftKit source: ${source}`);
  }
  assertNoSymlinkAncestors(source);
  assertPhysicalTree(source);

  const installCodex = target === "codex" || target === "both";
  const installClaude = target === "claude" || target === "both";

  const codexRoot = installCodex ? resolve(codexSkillsRoot) : null;
  const claudeRoot = installClaude ? resolve(claudeSkillsRoot) : null;
  const commandsRoot = installClaude ? resolve(claudeCommandsRoot) : null;
  const destinationRoots = [codexRoot, claudeRoot, commandsRoot].filter(Boolean);

  for (let i = 0; i < destinationRoots.length; i += 1) {
    if (pathsOverlap(source, destinationRoots[i])) {
      throw new Error(`The canonical source and destination roots must be disjoint: ${source}; ${destinationRoots[i]}`);
    }
    assertNoSymlinkAncestors(destinationRoots[i]);
    for (let j = i + 1; j < destinationRoots.length; j += 1) {
      if (pathsOverlap(destinationRoots[i], destinationRoots[j])) {
        throw new Error(`Install roots must be disjoint physical directories: ${destinationRoots[i]}; ${destinationRoots[j]}`);
      }
    }
  }

  const domains = getDomainDefinitions(source);
  const wrappersSource = join(source, "skill-wrappers");
  const commandsSource = join(source, "commands", "mc");
  assertPhysicalTree(wrappersSource);
  assertPhysicalTree(commandsSource);
  for (const domain of domains) {
    const wrapper = join(wrappersSource, domain.directory);
    const command = join(commandsSource, `${domain.id}.md`);
    assertDirectChild(wrapper, wrappersSource);
    assertDirectChild(command, commandsSource);
    if (!existsSync(join(wrapper, "SKILL.md"))) throw new Error(`Skill wrapper is missing SKILL.md: ${wrapper}`);
    if (!existsSync(command)) throw new Error(`Claude command is missing: ${command}`);
  }

  const transaction = randomUUID().replace(/-/g, "");
  const stamp = makeStamp();
  const containers = [];
  const records = [];

  function newRecord(client, kind, name, recSource, root, container) {
    assertSafeName(name, "target");
    const recTarget = join(root, name);
    const stage = join(container, name);
    const backup = join(root, `${name}.backup-${stamp}-${transaction}`);
    assertDirectChild(recTarget, root);
    assertDirectChild(stage, container);
    assertDirectChild(backup, root);
    return {
      client,
      kind,
      name,
      source: resolve(recSource),
      root: resolve(root),
      container: resolve(container),
      stage: resolve(stage),
      target: resolve(recTarget),
      backup: resolve(backup),
      expectedManifest: [],
      hadTarget: false,
      promoted: false
    };
  }

  const codexContainer = installCodex ? join(codexRoot, `.minecraftkit-stage-${transaction}`) : null;
  const claudeContainer = installClaude ? join(claudeRoot, `.minecraftkit-stage-${transaction}`) : null;
  const commandsContainer = installClaude ? join(commandsRoot, `.minecraftkit-commands-stage-${transaction}`) : null;

  if (installCodex) {
    assertDirectChild(codexContainer, codexRoot);
    containers.push(codexContainer);
    records.push(newRecord("Codex", "canonical", CANONICAL_SKILL_NAME, source, codexRoot, codexContainer));
  }
  if (installClaude) {
    assertDirectChild(claudeContainer, claudeRoot);
    assertDirectChild(commandsContainer, commandsRoot);
    containers.push(claudeContainer, commandsContainer);
    records.push(newRecord("Claude", "canonical", CANONICAL_SKILL_NAME, source, claudeRoot, claudeContainer));
  }
  for (const domain of domains) {
    const wrapperDir = join(wrappersSource, domain.directory);
    if (installCodex) records.push(newRecord("Codex", "wrapper", domain.directory, wrapperDir, codexRoot, codexContainer));
    if (installClaude) records.push(newRecord("Claude", "wrapper", domain.directory, wrapperDir, claudeRoot, claudeContainer));
  }
  if (installClaude) {
    records.push(newRecord("Claude", "commands", "mc", commandsSource, commandsRoot, commandsContainer));
  }

  const preservedLegacyTargets = [];
  if (installCodex) preservedLegacyTargets.push(join(codexRoot, LEGACY_SKILL_NAME));
  if (installClaude) preservedLegacyTargets.push(join(claudeRoot, LEGACY_SKILL_NAME));

  if (planOnly) {
    const plan = {
      schemaVersion: 1,
      target,
      canonicalSkill: CANONICAL_SKILL_NAME,
      installs: records.map((r) => ({
        client: r.client,
        kind: r.kind,
        name: r.name,
        source: r.source,
        target: r.target,
        backup: r.backup
      })),
      preservedLegacyTargets
    };
    output(JSON.stringify(plan, null, 2));
    return plan;
  }

  const resolvedPython = pythonExecutable || resolvePython({ spawn })?.executable;
  if (!resolvedPython) {
    throw new Error("Python 3.10+ was not found on PATH; install python3 before installing MinecraftKit.");
  }

  const locks = acquireLocks(destinationRoots);
  try {
    for (const container of containers) {
      if (existsSync(container)) throw new Error(`Transaction staging path already exists: ${container}`);
    }
    try {
      for (const record of records) {
        record.expectedManifest = getContentManifest(record.source);
        copyPayload(record.source, record.stage);
        assertPhysicalTree(record.stage);
        assertManifestMatch(record.expectedManifest, getContentManifest(record.stage), `${record.client} ${record.name} stage`);
        if (record.kind === "canonical") {
          const check = spawn(resolvedPython, ["-B", join(record.stage, "scripts", "validate_kit.py"), record.stage], {
            stdio: "inherit",
            windowsHide: true
          });
          if (check.error || check.status !== 0) {
            throw new Error(`${record.client} staged canonical validation failed.`);
          }
          const nestedWrappers = join(record.stage, "skill-wrappers");
          assertDirectChild(nestedWrappers, record.stage);
          removeSafeTree(nestedWrappers, record.stage);
          record.expectedManifest = getContentManifest(record.stage);
        }
      }

      for (const record of records) {
        if (existsSync(record.backup)) throw new Error(`Refusing to overwrite an existing backup: ${record.backup}`);
        if (existsSync(record.target)) {
          if (isSymbolicLink(record.target)) throw new Error(`Existing target is a symbolic link: ${record.target}`);
          if (!lstatSync(record.target).isDirectory()) throw new Error(`Existing target is not a directory: ${record.target}`);
          assertPhysicalTree(record.target);
          renameSync(record.target, record.backup);
          record.hadTarget = true;
        }
      }

      for (const record of records) {
        if (existsSync(record.target)) throw new Error(`Target appeared during transaction: ${record.target}`);
        renameSync(record.stage, record.target);
        record.promoted = true;
        assertPhysicalTree(record.target);
        assertManifestMatch(record.expectedManifest, getContentManifest(record.target), `${record.client} ${record.name} install`);
        if (record.kind === "canonical") {
          const smoke = spawn(
            resolvedPython,
            ["-B", join(record.target, "scripts", "query_api.py"), "ActiveModel", "--plugin", "ModelEngine", "--limit", "1"],
            { stdio: "inherit", windowsHide: true }
          );
          if (smoke.error || smoke.status !== 0) {
            throw new Error(`${record.client} canonical smoke test failed.`);
          }
        }
      }
    } catch (installErr) {
      const rollbackErrors = [];
      for (let idx = records.length - 1; idx >= 0; idx -= 1) {
        const record = records[idx];
        try {
          if (record.promoted && existsSync(record.target)) {
            assertManifestMatch(record.expectedManifest, getContentManifest(record.target), `${record.client} ${record.name} rollback`);
            removeSafeTree(record.target, record.root);
          }
        } catch (cleanupErr) {
          rollbackErrors.push(`${record.client} ${record.name} cleanup failed: ${cleanupErr.message}`);
        }
        try {
          if (record.hadTarget && existsSync(record.backup)) {
            if (existsSync(record.target)) throw new Error(`Cannot restore backup because target exists: ${record.target}`);
            renameSync(record.backup, record.target);
          }
        } catch (restoreErr) {
          rollbackErrors.push(`${record.client} ${record.name} restore failed: ${restoreErr.message}`);
        }
      }
      if (rollbackErrors.length > 0) {
        throw new Error(`Installation failed: ${installErr.message}. Rollback errors: ${rollbackErrors.join("; ")}`);
      }
      throw installErr;
    } finally {
      for (let idx = containers.length - 1; idx >= 0; idx -= 1) {
        if (existsSync(containers[idx])) {
          removeSafeTree(containers[idx], dirname(containers[idx]));
        }
      }
    }

    for (const record of records) {
      const backupSuffix = record.hadTarget ? `; backup=${record.backup}` : "";
      output(`${record.client} ${record.kind}: installed physical copy at ${record.target}${backupSuffix}`);
    }
    output(`Legacy targets preserved: ${preservedLegacyTargets.join("; ")}`);
    return { installed: records.length };
  } finally {
    releaseLocks(locks);
  }
}

export async function runPosixBootstrap({
  target = "both",
  repository = "SalyyS1/minecraftkit",
  version = null,
  codexSkillsRoot = join(homedir(), ".agents", "skills"),
  claudeSkillsRoot = join(homedir(), ".claude", "skills"),
  claudeCommandsRoot = join(homedir(), ".claude", "commands"),
  pythonExecutable = null,
  planOnly = false,
  allowTestSource = false,
  testReleaseDirectory = null,
  output = console.log
} = {}) {
  if (allowTestSource && !testReleaseDirectory) {
    throw new Error("-AllowTestSource requires -TestReleaseDirectory.");
  }
  if (!allowTestSource && testReleaseDirectory) {
    throw new Error("-TestReleaseDirectory is disabled unless -AllowTestSource is explicitly supplied.");
  }
  if (!/^[A-Za-z0-9_.-]+\/[A-Za-z0-9_.-]+$/.test(repository)) {
    throw new Error(`Unsafe GitHub repository name: ${repository}`);
  }
  const repoParts = repository.split("/");
  if (repoParts.length !== 2 || repoParts.includes(".") || repoParts.includes("..")) {
    throw new Error(`Unsafe GitHub repository name: ${repository}`);
  }
  const apiUrl = version
    ? `https://api.github.com/repos/${encodeURIComponent(repoParts[0])}/${encodeURIComponent(repoParts[1])}/releases/tags/v${version}`
    : `https://api.github.com/repos/${encodeURIComponent(repoParts[0])}/${encodeURIComponent(repoParts[1])}/releases/latest`;
  assertGitHubHttpsUrl(apiUrl, new Set(["api.github.com"]), "GitHub release API");

  let fixtureRoot = null;
  if (allowTestSource) {
    fixtureRoot = resolve(testReleaseDirectory);
    assertNoSymlinkAncestors(fixtureRoot);
    assertPhysicalTree(fixtureRoot);
  }

  const apiHeaders = getGitHubHeaders();
  const publicHeaders = { Accept: "application/octet-stream", "User-Agent": apiHeaders["User-Agent"] };

  let release;
  if (fixtureRoot) {
    const metadataPath = join(fixtureRoot, "release.json");
    assertDirectChild(metadataPath, fixtureRoot);
    if (!existsSync(metadataPath) || isSymbolicLink(metadataPath)) {
      throw new Error(`Safe fixture release metadata is missing: ${metadataPath}`);
    }
    release = JSON.parse(readFileSync(metadataPath, "utf8"));
  } else {
    const rawRelease = await fetchBoundedHttpsBytes(
      apiUrl,
      apiHeaders,
      new Set(["api.github.com"]),
      4 * 1024 * 1024,
      null,
      "GitHub release metadata"
    );
    release = JSON.parse(rawRelease.toString("utf8"));
  }

  const selection = selectReleaseAssets(release, version);

  async function obtainAsset(asset, name, expectedBytes, maxBytes, destination) {
    if (fixtureRoot) {
      const source = join(fixtureRoot, name);
      assertDirectChild(source, fixtureRoot);
      if (!existsSync(source) || isSymbolicLink(source)) {
        throw new Error(`Safe fixture asset is missing: ${source}`);
      }
      const stat = lstatSync(source);
      if (stat.size > maxBytes || stat.size !== expectedBytes) {
        throw new Error(`Release asset size does not match metadata for ${name}.`);
      }
      copyFileSync(source, destination);
      return;
    }
    const downloadUrl = assertGitHubHttpsUrl(asset.browser_download_url, new Set(["github.com"]), `Release asset ${name}`);
    const prefix = `/${repository.toLowerCase()}/releases/download/`;
    if (!downloadUrl.pathname.toLowerCase().startsWith(prefix) || !downloadUrl.pathname.endsWith(`/${name}`)) {
      throw new Error(`Release asset URL does not match repository and asset name: ${downloadUrl.href}`);
    }
    const bytes = await fetchBoundedHttpsBytes(
      downloadUrl.href,
      publicHeaders,
      ASSET_DOWNLOAD_HOSTS,
      maxBytes,
      expectedBytes,
      `Release asset ${name}`
    );
    writeFileSync(destination, bytes, { flag: "wx" });
  }

  const tempParent = resolve(tmpdir());
  assertNoSymlinkAncestors(tempParent);
  const tempDir = join(tempParent, `mk-${randomUUID().replace(/-/g, "")}`);
  assertDirectChild(tempDir, tempParent);
  try {
    mkdirSync(tempDir);
    const archivePath = join(tempDir, selection.archiveName);
    const checksumPath = join(tempDir, selection.checksumName);
    assertDirectChild(archivePath, tempDir);
    assertDirectChild(checksumPath, tempDir);

    await obtainAsset(selection.archive, selection.archiveName, selection.archiveBytes, MAX_ARCHIVE_BYTES, archivePath);
    await obtainAsset(selection.checksum, selection.checksumName, selection.checksumBytes, MAX_CHECKSUM_BYTES, checksumPath);

    const expectedHash = readStrictChecksum(readFileSync(checksumPath), selection.archiveName, selection.version);
    const actualHash = sha256Hex(archivePath);
    if (!fixedTimeHexEqual(expectedHash, actualHash)) {
      throw new Error(`SHA-256 checksum mismatch for ${selection.archiveName}.`);
    }

    const extractRoot = join(tempDir, "extracted");
    assertDirectChild(extractRoot, tempDir);
    const packageRoot = expandSafeArchive(archivePath, extractRoot);
    return installFromSourceRoot({
      sourceRoot: packageRoot,
      target,
      codexSkillsRoot,
      claudeSkillsRoot,
      claudeCommandsRoot,
      pythonExecutable,
      planOnly,
      output
    });
  } finally {
    if (existsSync(tempDir)) {
      assertDirectChild(tempDir, tempParent);
      assertPhysicalTree(tempDir);
      rmSync(tempDir, { recursive: true, force: true });
    }
  }
}

function parseBootstrapCliArgs(argv) {
  const opts = { target: "both", repository: "SalyyS1/minecraftkit", planOnly: false, allowTestSource: false };
  for (let i = 0; i < argv.length; i += 1) {
    const token = argv[i];
    if (token === "-Target") opts.target = argv[++i];
    else if (token === "-Version") opts.version = argv[++i];
    else if (token === "-Repository") opts.repository = argv[++i];
    else if (token === "-CodexSkillsRoot") opts.codexSkillsRoot = argv[++i];
    else if (token === "-ClaudeSkillsRoot") opts.claudeSkillsRoot = argv[++i];
    else if (token === "-ClaudeCommandsRoot") opts.claudeCommandsRoot = argv[++i];
    else if (token === "-Python") opts.pythonExecutable = argv[++i];
    else if (token === "-PlanOnly") opts.planOnly = true;
    else if (token === "-AllowTestSource") opts.allowTestSource = true;
    else if (token === "-TestReleaseDirectory") opts.testReleaseDirectory = argv[++i];
    else throw new Error(`Unknown bootstrap argument: ${token}`);
  }
  return opts;
}

if (process.argv[1] && resolve(process.argv[1]) === resolve(fileURLToPath(import.meta.url))) {
  runPosixBootstrap(parseBootstrapCliArgs(process.argv.slice(2))).catch((err) => {
    console.error(err.message || String(err));
    process.exit(1);
  });
}
