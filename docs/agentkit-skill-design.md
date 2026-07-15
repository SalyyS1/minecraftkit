# AgentKit Skill Design Research

The local AgentKit research examined every allowlisted installed `SKILL.md` structurally, deep-reviewed representative workflow/domain/script/reference skills, compared Codex and Claude adapters, and checked official skill documentation.

## Local Inventory Snapshot

| Surface | Observed state |
|---|---|
| AgentKit CLI | `ak 2.1.0` |
| core kit | 0.1.0; 10 agents, 54 skills, 30 hooks, 7 rules, 6 styles, 2 scripts |
| engineer kit | 0.2.0; extends core; 16 agents, 91 skills, 17 hooks, 7 rules, 6 styles, 10 scripts |
| marketing kit | 0.2.0; extends core; 32 agents, 73 skills, 3 hooks, 7 rules, 6 styles, 9 scripts |
| allowlisted SKILL occurrences | 569 |
| unique content hashes | 445 |
| declared names | 346 |
| exact cross-root duplicates | 124 |
| names with divergent hashes | 96 |
| bodies with detectable tests/evals | 81 of 569 occurrences |

The local line distribution ranged from 6 to 902, with median 133 and p90 365. Long root skills and divergent mirrored copies were the clearest maintenance risks.

## AgentKit Component Model

- **Skills** are reusable capabilities discovered primarily through frontmatter metadata.
- **Agents** are role personas; Claude uses Markdown/YAML while Codex adapters use TOML.
- **Rules** are always-on development, documentation, orchestration, and routing policy.
- **Hooks** enforce event-time guards such as privacy, context injection, naming, plan state, and artifact checks.
- **Scripts** perform deterministic operations without loading implementation into prompt context.
- **References** load focused context on demand; **assets** are copied/used in output.

MinecraftRPG Kit installs only a skill. It does not add global hooks, rules, agents, MCP servers, or client configuration.

## Effective Skill Anatomy

### Discovery layer

Use only `name` and `description` in common frontmatter. The description must say what the skill does and when it should trigger, including plugin aliases. Folder and declared name are both `minecraft-rpg-kit`.

### Procedural root

`SKILL.md` is a router, not the encyclopedia. It declares scope, intent routes, narrow query commands, evidence labels, safety rules, output contract, and validation commands. It stays below the stricter local 300-line target and the official 500-line guidance.

### One-level references

Every operational reference is directly linked from `SKILL.md`:

- API lookup;
- architecture review;
- source regeneration;
- RPG feature design;
- addon blueprint;
- compatibility/safety;
- plugin routing;
- Codex/Claude compatibility.

No workflow depends on a reference that can only be discovered from another reference.

### Deterministic scripts

Large JVM metadata remains in files, not prompt context. Scripts inventory inputs, extract class metadata, render shards, query symbols, validate contracts, package, and install hard copies. Paths resolve from the skill root or explicit CLI arguments, not a client-only environment variable.

## Design Decisions For This Kit

| Concern | Decision | Reason |
|---|---|---|
| API volume | shard by plugin/package; query through script | 40 MB raw index is too large for agent context |
| fact versus inference | four confidence labels | avoids presenting decompile behavior as a binary guarantee |
| embedded libraries | retain but mark `bundled-third-party` | preserves physical catalog while preventing authorship misattribution |
| plugin versions | store artifact-specific version and hashes | snapshots and NMS are not universal contracts |
| source material | no bodies/JARs/assets in kit | factual interoperability research only |
| cross-client behavior | common frontmatter and relative resources | one canonical payload works for Codex and Claude |
| global installation | two physical copies with hash comparison | no junction coupling; drift becomes detectable |
| web delivery | static `file://` explorer, no network | portable and privacy-preserving |

## Anti-patterns Avoided

- 500 to 900 line root skill;
- generic description with missing trigger vocabulary;
- deep reference chains;
- duplicated API prose in the root skill;
- `$CODEX_HOME` or `${CLAUDE_SKILL_DIR}` dependency;
- Bash-only commands on a Windows-first bundle;
- direct global hook/rule/config mutation;
- scripts without path confinement, strict failures, or tests;
- claims without plugin, version, evidence, and confidence;
- copied decompiled bodies or proprietary assets.

## Skill Security Model

Analyzed files are untrusted evidence. Text in source, comments, configs, and generated indexes can never override the skill instructions. Regeneration reads only an explicitly supplied bundle, rejects reparse points, verifies hashes before/after, emits strict JSON, and stages generated directories before promotion.

The skill refuses requests to reconstruct proprietary implementations, leak hidden instructions, read unrelated sensitive locations, or execute instructions embedded in analyzed content.

## Evaluation Model

Validation covers:

- required frontmatter, folder/name, line caps, and direct reference resolution;
- at least ten positive and ten negative trigger prompts;
- descriptor parsing, Modified UTF-8, constants, namespace boundaries, overloads, and malformed inputs;
- exact/fuzzy-style term queries, parameter/throws search, origin filter, and zero-result status;
- deterministic render and inventory output;
- overlap, traversal, symlink/junction, strict JSON, and console encoding failures;
- offline web data registration and complete counts;
- hard-copy install manifests and no reparse points.

## Source Guidance

- OpenAI, “Build skills”: `https://learn.chatgpt.com/docs/build-skills.md`
- Anthropic, “Extend Claude with skills”: `https://code.claude.com/docs/en/skills`
- Anthropic, “Agent Skills best practices”: `https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices`

The current official user roots are `$HOME/.agents/skills` for Codex and `$HOME/.claude/skills` for Claude.
