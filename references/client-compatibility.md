# Codex And Claude Compatibility

MinecraftRPG Kit uses the shared Agent Skills contract: one directory, one `SKILL.md`, and common `name` plus `description` frontmatter.

## Install Roots

| Client | User skill root | Installed directory |
|---|---|---|
| Codex | `$HOME/.agents/skills` | `$HOME/.agents/skills/minecraft-rpg-kit` |
| Claude | `$HOME/.claude/skills` | `$HOME/.claude/skills/minecraft-rpg-kit` |

The project `MinecraftRPGKit` directory is canonical. Both global targets must be independent physical copies. Do not use junctions, symlinks, or Codex's `.system` directory.

## Shared Design Rules

- Keep discovery language in the frontmatter description.
- Keep the root skill procedural and concise.
- Link every operational reference directly from `SKILL.md`.
- Resolve scripts relative to the skill file, not `$CODEX_HOME` or `${CLAUDE_SKILL_DIR}`.
- Do not require a client-specific agent, hook, rule, MCP server, or invocation field.
- Optional `agents/openai.yaml` changes Codex display metadata only and does not alter the workflow.

## Discovery Smoke Test

After installation:

1. confirm both target directories exist and are not reparse points;
2. compare their normalized file manifests with the canonical project copy;
3. run `scripts/query_api.py ActiveModel --plugin ModelEngine --limit 1` from each target;
4. ask each client a positive trigger such as “find the ModelEngine ActiveModel API”;
5. ask an unrelated negative trigger and confirm the RPG kit is not selected;
6. restart the client only when its current session does not refresh skill discovery.

Official location references used for this design:

- OpenAI, “Build skills”: `https://learn.chatgpt.com/docs/build-skills.md`
- Anthropic, “Extend Claude with skills”: `https://code.claude.com/docs/en/skills`
- Anthropic, “Agent Skills best practices”: `https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices`
