# API Lookup Workflow

Use this workflow for symbol discovery, overload comparison, event selection, and compile-time integration planning.

## 1. Narrow The Question

Identify:

- plugin and artifact version;
- concept, class, member, or event name;
- whether public and protected members are both acceptable;
- whether a stable API contract or an internal implementation is being requested.

## 2. Query Before Loading Docs

Resolve the skill directory from `SKILL.md`, then run `scripts/query_api.py`. The command performs a streaming-style logical search over the index and prints only the requested result limit.

```text
python <skill-root>/scripts/query_api.py ProfileProvider --plugin MMOProfiles --limit 25
python <skill-root>/scripts/query_api.py register restriction --plugin MMOInventory --limit 50
python <skill-root>/scripts/query_api.py ModelSetupEvent --kind class --json
```

Search is case-insensitive and every positional term must occur in the combined symbol record. `--plugin` is an exact case-insensitive plugin name. `--kind` accepts class, interface, enum, annotation, record, field, method, or constructor.

If there are no matches:

1. remove the plugin filter to catch ownership mistakes;
2. search one distinctive token;
3. search the package or owner name;
4. check aliases in the plugin routing reference;
5. report absence from this artifact, not universal nonexistence.

## 3. Interpret A Record

- `id` is the stable catalog identifier.
- `owner` is the declaring type.
- `descriptor` is the JVM descriptor and disambiguates overloads.
- `return_type` and `parameters` are decoded convenience fields.
- `source_path` points to supporting decompiled evidence when available.
- Generic signatures may be absent even when the descriptor is complete.

Use the package Markdown shard under `docs/api/<plugin>/` when a human needs neighboring types. Generated shards contain signatures, not implementation bodies.

## 4. Rank Stability

Prefer, in order:

1. documented service/provider interfaces and explicit API packages;
2. Bukkit events and registered extension SPIs;
3. public registries/managers designed for addon registration;
4. public implementation singletons;
5. NMS, packet, shaded, proxy-internal, or storage implementation types.

Visibility does not equal vendor support. If no formal API boundary exists, wrap the call behind an addon-owned adapter.

## 5. Report The Result

Include plugin/version, owner, exact member signature, descriptor when overloaded, intended lifecycle phase, thread expectation, and confidence label. Say `UNVERIFIED` when a runtime behavior cannot be proven from metadata.

Never reconstruct a body or quote decompiled implementation to answer an API lookup.
