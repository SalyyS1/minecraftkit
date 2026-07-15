# Codex And Claude Compatibility

Salyyy Minecraft Kit by **SalyVn / Salyyy** installs one canonical knowledge root plus ten thin route skills for both clients. Claude also receives path-based `/mc:*` command wrappers.

## Compatibility Matrix

| Concern | Codex | Claude | Shared implementation |
|---|---|---|---|
| canonical root | `$HOME/.agents/skills/minecraftkit` | `$HOME/.claude/skills/minecraftkit` | validated physical copy |
| focused routes | `$HOME/.agents/skills/mc-*` | `$HOME/.claude/skills/mc-*` | ten sibling `SKILL.md` wrappers |
| slash commands | auto-routing skill descriptions | `$HOME/.claude/commands/mc/*.md` | `/mc:build`, `/mc:core`, `/mc:rpg`, `/mc:shader`, etc. |
| discovery metadata | `name`, `description` | `name`, `description` | only common frontmatter keys |
| progressive disclosure | metadata, wrapper, shared references/data | same | wrappers locate sibling `minecraftkit` |
| client UI metadata | optional `agents/openai.yaml` | ignored safely | does not change workflow |
| path resolution | sibling core or source root | sibling core or source root | scripts use `__file__` or explicit root |

The legacy `$HOME/.../minecraft-rpg-kit` targets are preserved during v2 installation; they are not silently replaced or deleted.

## Canonical Payload

The project repository is the source of truth. Global targets are independent physical copies, never junctions/symlinks. The core includes docs, catalogs, references, scripts, tests and web files; route wrappers remain small enough for automatic discovery without loading the complete knowledge base.

## Install Transaction

`scripts/install-global.ps1`:

1. Validates source paths, the ten-domain catalog and all source trees.
2. Builds only the selected target plan: 11 Codex targets, 12 Claude targets, or 23 combined targets.
3. Stages every payload beside its final target.
4. Validates both staged canonical cores and compares SHA-256 tree manifests for every payload.
5. Moves existing targets to unique timestamp/transaction backups.
6. Promotes all staged targets and rechecks physical trees/hashes.
7. Rolls back promoted targets in reverse order and restores backups on any failure.

It rejects overlapping roots, path escapes, unsafe names and reparse points. It never modifies `.system`, hooks, rules, MCP settings or unrelated client configuration.

Preview without writes:

```text
powershell -ExecutionPolicy Bypass -File scripts/install-global.ps1 -Target both -PlanOnly
```

## Install From GitHub

Run one PowerShell command for the intended client. The bootstrap verifies the release ZIP against its published SHA-256 sidecar before safe extraction and transactional installation.

```powershell
# Codex only
& ([scriptblock]::Create((Invoke-RestMethod 'https://raw.githubusercontent.com/SalyyS1/minecraftkit/main/scripts/install-from-github.ps1'))) -Target codex

# Claude only
& ([scriptblock]::Create((Invoke-RestMethod 'https://raw.githubusercontent.com/SalyyS1/minecraftkit/main/scripts/install-from-github.ps1'))) -Target claude

# Both
& ([scriptblock]::Create((Invoke-RestMethod 'https://raw.githubusercontent.com/SalyyS1/minecraftkit/main/scripts/install-from-github.ps1'))) -Target both
```

## Validation And Discovery Smoke Tests

Run the complete release validator from a source checkout or extracted release package, before installation:

```text
python scripts/validate_kit.py .
```

The installer validates that full staged source first, then intentionally omits the nested `skill-wrappers` directory from each installed canonical root so agents discover exactly one canonical skill plus ten sibling routes. After installation, smoke-test each canonical root with:

```text
python scripts/query_sources.py shader --domain shader --limit 1
python scripts/query_api.py ActiveModel --plugin ModelEngine --limit 1
```

Also verify `.version` in the installed `manifest.json`, one canonical `SKILL.md`, ten sibling `mc-*` skills (including `mc-build`), and—for Claude—ten `commands/mc/*.md` files. Do not run the full source-layout validator against the intentionally filtered canonical install.

Positive triggers should activate the narrow route: “ship this Kotlin Paper plugin” -> `mc:build`; “debug this Iris shader” -> `mc:shader`; “design MMOItems stats” -> `mc:rpg`; “migrate this ProtocolLib packet” -> `mc:protocol`. A generic non-Minecraft task should not invoke the kit.

Claude commands accept the task in `$ARGUMENTS`, activate the matching skill and preserve the same evidence/safety contract. Codex relies on the rich skill descriptions for auto-routing.

## Drift Detection

The release manifest hashes authoritative catalogs and generated web indexes. Installation compares complete filtered payload manifests in memory. A changed global file is drift; edit the canonical repository and reinstall instead.
