# Salyyy Minecraft Kit CLI

`minecraftkit` is the small npm CLI for **Salyyy Minecraft Kit** by **SalyVn / Salyyy**. It keeps installation convenient while delegating all mutations to the Kit's bundled, checksum-verified GitHub-release installer.

## Install

```powershell
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
minecraftkit doctor [--json]
minecraftkit commands [--json]
minecraftkit wiki
minecraftkit version
```

`install` defaults to `both`. `--dry-run` downloads and validates the selected release but asks the transactional installer to make no global writes. `doctor` checks Node, PowerShell, Python and current Codex/Claude install topology.

## Security model

The CLI executes its locally packaged bootstrap; it does not evaluate a raw GitHub script. The bootstrap downloads the selected GitHub release ZIP plus its checksum, verifies SHA-256, rejects unsafe archives, then invokes the audited transactional installer. No telemetry, token, postinstall hook or background update check exists.

See the [VI/EN wiki](https://salyys1.github.io/minecraftkit/wiki.html), the [repository](https://github.com/SalyyS1/minecraftkit), and `NOTICE.md` for provenance and redistribution limits.
