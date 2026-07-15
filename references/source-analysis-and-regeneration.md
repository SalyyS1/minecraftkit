# Source Analysis And Regeneration

Use only with local artifacts the user is authorized to analyze. Inputs remain read-only for the entire workflow.

## Preconditions

- Confirm the bundle contains exactly ten expected JARs and ten matching decompiled roots.
- Do not follow arbitrary reparse points or scan credentials, histories, caches, or unrelated home directories.
- Record relative paths, sizes, and SHA-256 hashes before extraction.
- Never place JARs, class files, decompiled bodies, or vendor assets inside the kit.

## Deterministic Workflow

```text
python <skill-root>/scripts/inventory_sources.py --bundle <bundle> --output <skill-root>/data/source-inventory.json
python <skill-root>/scripts/inventory_sources.py --bundle <bundle> --output <skill-root>/data/source-inventory.json --verify
python <skill-root>/scripts/extract_api.py --jars <bundle> --sources <bundle>/decompiled --output <skill-root>/data
python <skill-root>/scripts/render_docs.py --data <skill-root>/data --docs <skill-root>/docs --web <skill-root>/web
python <skill-root>/scripts/build_manifest.py <skill-root>
python <skill-root>/scripts/inventory_sources.py --bundle <bundle> --output <skill-root>/data/source-inventory.json --verify
python <skill-root>/scripts/validate_kit.py <skill-root>
```

The extractor reads JVM class metadata directly and is independent of the locally installed JDK's supported class version. It publishes only plugin-owned public/protected types and members selected by namespace. Multi-release entries are recorded separately when present.

## Coverage Gates

Require:

- ten plugins represented;
- zero class parser errors;
- every included type/member has a stable ID;
- all namespace exclusions are explicit;
- docs and web counts reconcile with the API index;
- generated files use UTF-8 and deterministic ordering;
- a second clean render produces the same normalized hashes;
- input inventory verifies after all work.

## Semantic Review

Bytecode proves symbols, not intent. Review source by plugin family and trace composition root, domain aggregates, storage, schedulers, events, registries, integration adapters, and teardown. Separate authored namespaces from relocated libraries.

If decompiled flow is implausible, record the concern as `UNVERIFIED` and design a runtime test. Never silently repair the vendor logic in documentation.

## Failure Handling

Stop publication when input hashes change, parser errors are unexplained, namespace ownership is ambiguous, or a generated artifact contains bodies/secrets. Keep the previous validated package and report the exact failing path or symbol.
