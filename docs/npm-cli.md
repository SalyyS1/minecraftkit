# MinecraftKit npm CLI

## Overview

The `minecraftkit` npm package provides a short command surface for installing and diagnosing **Salyyy Minecraft Kit**. It is deliberately small and dependency-free: the package contains a byte-synchronized copy of the reviewed PowerShell bootstrap, while the bootstrap remains responsible for GitHub-release SHA-256 verification, bounded archive extraction and transactional installation.

## Public usage after registry publication

```powershell
npx minecraftkit install --target both

npm install minecraftkit
npx minecraftkit doctor

npm install -g minecraftkit
minecraftkit doctor
minecraftkit commands
minecraftkit update claude
```

`install` and `update` accept `codex`, `claude`, or `both`; `both` is the default. Use `--dry-run` to validate the selected release and print the transactional plan without changing global skills. Use `--version x.y.z` only when deliberately pinning a GitHub Kit release.

## Commands

| Command | Purpose |
|---|---|
| `install` | Runs the local bundled bootstrap for the selected target. |
| `update` | Alias for `install`; resolves the latest verified GitHub release. |
| `doctor` | Reports Node, PowerShell, Python and Codex/Claude installation topology. |
| `commands` | Lists the ten `mc:*` routes. |
| `wiki` | Prints the VI/EN wiki URL. |
| `version` | Prints the npm CLI package version. |

## Package maintenance

Run from `npm/`:

```powershell
npm run check
npm run pack:dry-run
```

`npm run check:bootstrap` fails if the bundled bootstrap diverges from `scripts/install-from-github.ps1`. The release tarball contains only CLI code, the bootstrap, README, notice and package metadata; it never contains the large research corpus, credentials, a postinstall hook or telemetry.

## Publication gate

The registry package is not yet published. Before `npm publish --access public`, authenticate the intended npm account, recheck that `minecraftkit` is available, choose a license for original CLI code, run the package checks, and test `npx` against the exact generated tarball. Upstream-derived research remains subject to [NOTICE.md](../NOTICE.md).
