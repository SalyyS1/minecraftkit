import test from "node:test";
import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { existsSync, mkdirSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join, resolve } from "node:path";
import { deflateRawSync } from "node:zlib";
import { PACKAGE_DIRECTORY } from "../lib/constants.js";
import {
  computeCrc32,
  expandSafeArchive,
  installFromSourceRoot,
  readStrictChecksum,
  runPosixBootstrap
} from "../lib/posix-installer.js";

const REPO_ROOT = resolve(PACKAGE_DIRECTORY, "..");

function buildZipBuffer(entries) {
  const localParts = [];
  const centralParts = [];
  let offset = 0;

  for (const entry of entries) {
    const nameBytes = Buffer.from(entry.name, "utf8");
    const isDir = entry.name.endsWith("/");
    const raw = isDir ? Buffer.alloc(0) : Buffer.from(entry.content || "", "utf8");
    const method = isDir || entry.store ? 0 : 8;
    const comp = method === 8 ? deflateRawSync(raw) : raw;
    const crc = computeCrc32(raw);
    const extAttr = entry.externalAttr ?? ((isDir ? 0x41ed : 0x81a4) << 16);

    const local = Buffer.alloc(30);
    local.writeUInt32LE(0x04034b50, 0);
    local.writeUInt16LE(20, 4);
    local.writeUInt16LE(0x0800, 6);
    local.writeUInt16LE(method, 8);
    local.writeUInt32LE(crc, 14);
    local.writeUInt32LE(comp.length, 18);
    local.writeUInt32LE(raw.length, 22);
    local.writeUInt16LE(nameBytes.length, 26);
    localParts.push(local, nameBytes, comp);

    const central = Buffer.alloc(46);
    central.writeUInt32LE(0x02014b50, 0);
    central.writeUInt16LE(0x0314, 4);
    central.writeUInt16LE(20, 6);
    central.writeUInt16LE(0x0800, 8);
    central.writeUInt16LE(method, 10);
    central.writeUInt32LE(crc, 16);
    central.writeUInt32LE(comp.length, 20);
    central.writeUInt32LE(raw.length, 24);
    central.writeUInt16LE(nameBytes.length, 28);
    central.writeUInt32LE(extAttr >>> 0, 38);
    central.writeUInt32LE(offset, 42);
    centralParts.push(central, nameBytes);

    offset += 30 + nameBytes.length + comp.length;
  }

  const cdBuffer = Buffer.concat(centralParts);
  const eocd = Buffer.alloc(22);
  eocd.writeUInt32LE(0x06054b50, 0);
  eocd.writeUInt16LE(entries.length, 8);
  eocd.writeUInt16LE(entries.length, 10);
  eocd.writeUInt32LE(cdBuffer.length, 12);
  eocd.writeUInt32LE(offset, 16);

  return Buffer.concat([...localParts, cdBuffer, eocd]);
}

function createReleaseFixture(tempRoot, version = "2.2.1", extraEntries = []) {
  const archiveName = `minecraftkit-${version}.zip`;
  const zipBytes = buildZipBuffer([
    { name: "minecraftkit/" },
    { name: "minecraftkit/SKILL.md", content: "---\nname: minecraftkit\ndescription: test\n---\n" },
    { name: "minecraftkit/scripts/install-global.ps1", content: "# stub\n" },
    {
      name: "minecraftkit/data/minecraft-domain-catalog.json",
      content: JSON.stringify({
        schema_version: 1,
        domains: [{ id: "core", route: "mc:core", skill_directory: "mc-core" }]
      })
    },
    { name: "minecraftkit/skill-wrappers/mc-core/SKILL.md", content: "---\nname: mc-core\ndescription: core\n---\n" },
    { name: "minecraftkit/commands/mc/core.md", content: "# /mc:core\n" },
    ...extraEntries
  ]);

  const archivePath = join(tempRoot, archiveName);
  writeFileSync(archivePath, zipBytes);
  const sha = createHash("sha256").update(zipBytes).digest("hex");
  const checksumName = `${archiveName}.sha256`;
  const checksumBytes = Buffer.from(`${sha}  ${archiveName}\n`, "ascii");
  writeFileSync(join(tempRoot, checksumName), checksumBytes);
  writeFileSync(
    join(tempRoot, "release.json"),
    JSON.stringify({
      tag_name: `v${version}`,
      draft: false,
      prerelease: false,
      assets: [
        { name: archiveName, size: zipBytes.length, browser_download_url: `https://github.com/SalyyS1/minecraftkit/releases/download/v${version}/${archiveName}` },
        { name: checksumName, size: checksumBytes.length, browser_download_url: `https://github.com/SalyyS1/minecraftkit/releases/download/v${version}/${checksumName}` }
      ]
    })
  );
  return { archivePath, archiveName, sha };
}

test("readStrictChecksum enforces strict ASCII SHA-256 format", () => {
  const hash = "a".repeat(64);
  const parsed = readStrictChecksum(Buffer.from(`${hash}  minecraftkit-2.2.1.zip\n`, "ascii"), "minecraftkit-2.2.1.zip", "2.2.1");
  assert.equal(parsed, hash);
  assert.throws(
    () => readStrictChecksum(Buffer.from(`${hash} minecraftkit-2.2.1.zip\n`, "ascii"), "minecraftkit-2.2.1.zip", "2.2.1"),
    /strict SHA-256/
  );
});

test("expandSafeArchive rejects path traversal and symlink entries", () => {
  const work = mkdtempSync(join(tmpdir(), "mk-zip-test-"));
  try {
    const traversalZip = join(work, "traversal.zip");
    writeFileSync(traversalZip, buildZipBuffer([{ name: "minecraftkit/../escape.txt", content: "bad" }]));
    assert.throws(() => expandSafeArchive(traversalZip, join(work, "out1")), /path traversal/);

    const symlinkZip = join(work, "symlink.zip");
    writeFileSync(
      symlinkZip,
      buildZipBuffer([{ name: "minecraftkit/link", content: "/etc/passwd", externalAttr: (0xa1ff << 16) >>> 0 }])
    );
    assert.throws(() => expandSafeArchive(symlinkZip, join(work, "out2")), /symbolic link/);
  } finally {
    rmSync(work, { recursive: true, force: true });
  }
});

test("runPosixBootstrap verifies SHA-256 and supports planOnly dry-run", async () => {
  const work = mkdtempSync(join(tmpdir(), "mk-bootstrap-test-"));
  try {
    const fixtureDir = join(work, "release");
    mkdirSync(fixtureDir);
    const { archivePath } = createReleaseFixture(fixtureDir);

    const outLines = [];
    const plan = await runPosixBootstrap({
      target: "both",
      codexSkillsRoot: join(work, "codex-skills"),
      claudeSkillsRoot: join(work, "claude-skills"),
      claudeCommandsRoot: join(work, "claude-commands"),
      planOnly: true,
      allowTestSource: true,
      testReleaseDirectory: fixtureDir,
      output: (line) => outLines.push(line)
    });
    assert.equal(plan.schemaVersion, 1);
    assert.equal(plan.canonicalSkill, "minecraftkit");
    assert.equal(existsSync(join(work, "codex-skills")), false);

    // Tamper 1 byte in archive and verify SHA-256 mismatch is caught before extraction
    const tampered = readFileSync(archivePath);
    tampered[0] ^= 0xff;
    writeFileSync(archivePath, tampered);
    await assert.rejects(
      () =>
        runPosixBootstrap({
          target: "codex",
          codexSkillsRoot: join(work, "codex-skills"),
          planOnly: true,
          allowTestSource: true,
          testReleaseDirectory: fixtureDir
        }),
      /SHA-256 checksum mismatch/
    );
  } finally {
    rmSync(work, { recursive: true, force: true });
  }
});

test("installFromSourceRoot performs verified transactional install and preserves legacy skill", () => {
  const work = mkdtempSync(join(tmpdir(), "mk-install-test-"));
  try {
    const claudeSkills = join(work, "claude-skills");
    const claudeCommands = join(work, "claude-commands");
    const legacyDir = join(claudeSkills, "minecraft-rpg-kit");
    mkdirSync(legacyDir, { recursive: true });
    writeFileSync(join(legacyDir, "marker.txt"), "keep");

    const logs = [];
    const result = installFromSourceRoot({
      sourceRoot: REPO_ROOT,
      target: "claude",
      claudeSkillsRoot: claudeSkills,
      claudeCommandsRoot: claudeCommands,
      output: (line) => logs.push(line)
    });
    assert.equal(result.installed, 12);
    assert.equal(existsSync(join(claudeSkills, "minecraftkit", "SKILL.md")), true);
    assert.equal(existsSync(join(claudeSkills, "minecraftkit", "skill-wrappers")), false);
    assert.equal(existsSync(join(claudeSkills, "mc-core", "SKILL.md")), true);
    assert.equal(existsSync(join(claudeCommands, "mc", "core.md")), true);
    assert.equal(readFileSync(join(legacyDir, "marker.txt"), "utf8"), "keep");
  } finally {
    rmSync(work, { recursive: true, force: true });
  }
});
