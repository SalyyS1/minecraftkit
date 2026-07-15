# Codex And Claude Compatibility

MinecraftRPG Kit uses one canonical Agent Skills payload for both clients.

## Compatibility Matrix

| Concern | Codex | Claude | Shared implementation |
|---|---|---|---|
| user skill root | `$HOME/.agents/skills` | `$HOME/.claude/skills` | install `minecraft-rpg-kit` as a physical directory |
| required entry | `SKILL.md` | `SKILL.md` | one canonical file |
| discovery metadata | `name`, `description` | `name`, `description` | only common keys in frontmatter |
| progressive disclosure | metadata, body, resources | metadata, body, resources | root router plus direct references and scripts |
| client UI metadata | optional `agents/openai.yaml` | safely ignored as a resource | does not change workflow |
| client-specific agent format | TOML | Markdown/YAML | no bundled agent dependency |
| path resolution | no common client env required | Claude has a skill-dir variable | scripts use `__file__` or explicit root |
| reload/discovery | session/build dependent | existing root often refreshes | smoke test; restart only if discovery is stale |

## Canonical Payload

The project directory `MinecraftRPGKit` is the source of truth. Both global targets include functional docs, data, references, scripts, tests, and web files. They exclude `dist`, caches, temporary stage directories, and machine-specific install records.

Junctions and symlinks are prohibited. Independent copies prevent one client from changing the other and make drift visible through content manifests.

## Install Contract

1. Validate the canonical project kit.
2. Create staging directories beside both final targets.
3. Copy the filtered payload into both stages.
4. Validate each stage and reject every reparse point.
5. Back up an existing target with a timestamped sibling name.
6. Promote both stages.
7. Compare normalized SHA-256 file manifests with the canonical payload.
8. On failure, remove only the invalid new target and restore its backup.

The installer never writes Codex's `.system` directory and never modifies global hooks, rules, agents, MCP settings, or client configuration.

## Discovery Smoke Test

From each global target:

```text
python scripts/query_api.py ActiveModel --plugin ModelEngine --limit 1
python scripts/validate_kit.py .
```

Then ask each client a positive trigger such as “Find the ModelEngine ActiveModel API and explain its lifecycle constraints.” Confirm that an unrelated task, such as editing a generic Python CSV script, does not invoke the RPG kit.

## Drift Detection

The release manifest records hashes for the authoritative generated data and web indexes. During installation, the installer computes sorted SHA-256 content manifests in memory and requires each physical copy to match the filtered canonical payload. A changed global file is drift, not a new canonical version.

## Official References

- OpenAI Codex skill locations and structure: `https://learn.chatgpt.com/docs/build-skills.md`
- Claude Code skill locations and open Agent Skills compatibility: `https://code.claude.com/docs/en/skills`
- Agent Skills authoring guidance: `https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices`

One local legacy document referred to `$CODEX_HOME/skills`; this kit follows the current official Codex root `$HOME/.agents/skills` and confirms it with an installation/discovery smoke test.
