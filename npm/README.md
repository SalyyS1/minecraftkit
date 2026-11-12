# Salyyy Minecraft Kit CLI

`minecraftkit` is the small npm CLI for **Salyyy Minecraft Kit** by **SalyVn / Salyyy**. It keeps installation and MCP server startup convenient while delegating all mutations to the Kit's bundled, checksum-verified GitHub-release installer.

## Install

```bash
npx minecraftkit install --target both

# or add it to a project and invoke it with npx
npm install minecraftkit
npx minecraftkit doctor

# or keep the command globally
npm install -g minecraftkit
minecraftkit install --target codex
```

## Commands

```text
minecraftkit install [codex|claude|both] [--dry-run] [--version x.y.z]
minecraftkit update [codex|claude|both]
minecraftkit mcp [--print-config] [--root <dir>]
minecraftkit doctor [--json]
minecraftkit commands [--json]
minecraftkit wiki
minecraftkit version
```

`install` defaults to `both`. `--dry-run` downloads and validates the selected release but asks the transactional installer to make no global writes. `mcp` launches the zero-dependency Python JSON-RPC 2.0 MCP server over stdio (or prints `mcpServers` configuration JSON when `--print-config` is passed). `doctor` checks Node, PowerShell (or the built-in Node POSIX fallback on Linux/macOS), Python, and current Codex/Claude install topology.

## Security model

The CLI executes its locally packaged bootstrap (`lib/install-from-github.ps1` when PowerShell is available, or `lib/posix-installer.js` on Linux/macOS without `pwsh`); it never evaluates a raw remote script. Both paths download the selected GitHub release ZIP plus its `.sha256` checksum, verify SHA-256 in constant time, reject unsafe archives (path traversal, symlinks, case collisions, CRC mismatches), and run the audited transactional physical-copy installer. No telemetry, postinstall hook, or background update check exists.

See the [VI/EN wiki](https://salyys1.github.io/minecraftkit/wiki.html), the [repository](https://github.com/SalyyS1/minecraftkit), and `NOTICE.md` for provenance and redistribution limits.
