# Plugin Build And Shipping

Use this reference with `mc:build`. It defines the production architecture and decision gates; open the focused Gradle, runtime-data, and release references for implementation detail.

## Contents

- [Authority labels](#authority-labels)
- [Resolve the contract](#resolve-the-contract)
- [Architecture boundaries](#architecture-boundaries)
- [Plugin descriptors](#plugin-descriptors)
- [Dependencies and distribution](#dependencies-and-distribution)
- [Paper, Purpur, and Folia](#paper-purpur-and-folia)
- [NMS and public APIs](#nms-and-public-apis)
- [Lifecycle and reload](#lifecycle-and-reload)
- [Production quality gates](#production-quality-gates)
- [Primary references](#primary-references)

## Authority Labels

Keep each decision visibly classified:

- **Platform contract**: behavior documented by Paper, Purpur, Gradle, Kotlin, a database vendor, or a publishing platform. Pin the documentation/API version when the behavior is unstable.
- **Kit recommendation**: Salyyy Minecraft Kit's conservative production default. It is guidance, not an upstream guarantee.
- **Project decision**: a choice that depends on the plugin's users, support matrix, licensing, deployment, or performance evidence.

Never convert a Kit recommendation into a claim that every server or plugin must follow it.

## Resolve The Contract

Record these inputs before choosing code or dependencies:

```text
plugin: name + version + author/nametag (SalyVn / Salyyy)
game: exact Minecraft IDs/range
runtime: exact Paper/Purpur/Folia builds; other servers explicitly excluded or tested
java: minimum bytecode level + build toolchain
language: Java | Kotlin | mixed, with Kotlin runtime strategy
descriptor: plugin.yml | paper-plugin.yml | both, with rationale
api: public consumer surface and compatibility promise
internals: none | exact paperweight/NMS adapter matrix
storage: engine, JDBC driver source, pool, schema version, migration owner
configuration: YAML/YML/JSON files, schemas, defaults, migration policy
dependencies: compile provider + runtime provider + license/notice per component
distribution: GitHub | Hangar | Modrinth | SpigotMC | private
operations: startup, readiness, shutdown, restart/reload policy, backups
evidence: exact tests, artifact SHA-256, SBOM, compatibility matrix
```

If a target is unknown, mark it `UNVERIFIED`; do not substitute the newest version seen in documentation.

## Architecture Boundaries

**Kit recommendation:** start with one module. Split only when a boundary carries a different compatibility or publishing contract:

```text
plugin entry point
  -> application/core services (platform-neutral rules)
  -> ports: scheduler, clock, storage, messaging, permissions
  -> adapters: Paper API, optional Purpur capability, Folia ownership
  -> optional exact-version NMS adapter
  -> external database/files/metrics
```

Useful module boundaries, when justified:

- `plugin-api`: small consumer-facing interfaces/events/data types; no implementation packages.
- `plugin-core`: domain state and use cases with no Bukkit/NMS types where practical.
- `platform-paper`: descriptor, lifecycle, Paper scheduler and API adapters.
- `platform-purpur`: only actual Purpur-only capabilities; Paper behavior remains in the Paper adapter.
- `nms-<exact-target>`: one isolated paperweight/dev-bundle contract per supported internal target.

Do not create a module merely to mirror a package. Dependencies point inward; platform and NMS objects must not leak through the stable public API.

## Plugin Descriptors

### `plugin.yml`

**Platform contract:** Paper documents `plugin.yml` as the Bukkit-compatible descriptor for name, version, main class, API version, authors, commands, permissions, dependencies and runtime `libraries`. The declared `api-version` is a load boundary, not proof that every API call works across a range.

```yaml
name: ExamplePlugin
version: '${version}'
main: dev.salyvn.example.ExamplePlugin
api-version: '${paperDescriptorApiVersion}'
authors: [SalyVn, Salyyy]
folia-supported: true
```

Expand and validate placeholders during `processResources`. Include `folia-supported: true` only after region/entity/global/async ownership tests pass. Use `depend`, `softdepend`, and `loadbefore` for their documented meanings; still check optional capabilities at runtime.

Keep the descriptor value separate from the full Maven dependency coordinate: current Paper lines can use a coordinate such as `paper-api:<game-version>.build.<build>-<channel>` while `api-version` accepts a shorter game API value. Resolve and validate both against the selected runtime rather than deriving one from the other.

### `paper-plugin.yml`

**Platform contract:** Paper Plugins are documented as experimental. `paper-plugin.yml` is not a drop-in replacement for `plugin.yml`: it can introduce bootstrapper/loader phases, split bootstrap/server dependencies, classloader isolation, and programmatic command registration. Paper allows both descriptors in one JAR, but that does not remove their semantic differences.

**Kit recommendation:** use `plugin.yml` for broad Bukkit/Paper/Purpur compatibility. Choose `paper-plugin.yml` only when the target is Paper-family and its bootstrap/classloader model provides a required benefit. Pin the Paper build, test both startup phases, and document the experimental boundary. If both descriptors are shipped, test which path every declared runtime uses and keep metadata consistent from one version source.

See Paper's [`plugin.yml` reference](https://docs.papermc.io/paper/dev/plugin-yml/) and [Paper Plugins guide](https://docs.papermc.io/paper/dev/getting-started/paper-plugins/).

## Dependencies And Distribution

A Gradle scope is not a runtime delivery plan. Map both:

| Dependency kind | Compile declaration | Runtime decision |
|---|---|---|
| Server API supplied by target | `compileOnly` | Never bundle; fail on unsupported runtime |
| Optional plugin integration API | usually `compileOnly` | descriptor `softdepend` plus runtime service/capability check |
| Required plugin API | usually `compileOnly` | descriptor required dependency and explicit version/capability gate |
| Private implementation library | `implementation` | provision with Paper `libraries`, shade, or require an external provider |
| JDBC driver | often `runtimeOnly` or `implementation` | runtime library, shaded driver, or operator/server provider; test service discovery |
| Public API module dependency | `api` only in a `java-library` module | publish the API artifact or keep it inside the plugin contract intentionally |

**Platform contract:** Paper's `plugin.yml` `libraries` field resolves Maven Central libraries onto the plugin classpath. Paper Plugin loaders offer another, experimental classpath mechanism.

**Kit recommendation:**

1. Use `compileOnly` for server-owned APIs.
2. Prefer a declared runtime library mechanism when the deployment supports it and startup network policy is acceptable.
3. Shade only what must travel inside the JAR. Relocate collision-prone packages, merge required service resources, and test reflective/resource lookups.
4. Review every redistributed license and preserve required notices. Do not run minimization blindly; reflection, service loaders, serializers and drivers can make apparently unused classes necessary.
5. Do not assume `implementation` or `runtimeOnly` embeds a dependency. A normal Gradle `jar` task does not do so.

Database servers and production data remain external. A JDBC driver or pool is a library and may be embedded/provisioned when justified; it is not the database server. See [Database, configuration, and runtime](database-config-and-runtime.md).

## Paper, Purpur, And Folia

**Platform contract:** Purpur inherits Paper/Bukkit surfaces but adds fork-specific APIs and configuration. Folia uses ownership schedulers; a support flag alone is insufficient.

| Owner | Correct execution context | Examples |
|---|---|---|
| Global region | global scheduler | time/weather/global game rules, console-owned work |
| World position/chunk | region scheduler for that location | block/chunk/world mutation at that position |
| Entity | entity scheduler | entity state; follows teleports and handles retirement |
| No game-state owner | async scheduler or bounded plugin executor | JDBC, filesystem, HTTP, compression, pure computation |

Async completion is not permission to touch Bukkit/Paper state. Capture immutable identifiers, perform I/O off-thread, then re-resolve lifecycle state on the correct global/region/entity owner. Handle entity retirement, world unload, player disconnect, plugin disable, timeouts and cancellation.

**Kit recommendation:** expose scheduler operations through one adapter. The Paper implementation may delegate the same calls to Paper's Folia-aware scheduler APIs; do not scatter `isFolia` checks. Keep Purpur-only behavior behind a capability adapter with a Paper fallback. Test exact Paper, Purpur and Folia artifacts separately.

See [Paper/Folia scheduler ownership](https://docs.papermc.io/paper/dev/folia-support/) and the [Purpur FAQ](https://purpurmc.org/docs/purpur/faq/).

## NMS And Public APIs

Prefer, in order: stable Paper/Bukkit API, Adventure/registries/data components, a public dependency service/API, typed protocol abstraction, then isolated internals.

When NMS is unavoidable:

- use the exact target's supported [`paperweight-userdev`](https://docs.papermc.io/paper/dev/userdev/) workflow;
- keep mapping/runtime details in an exact-version adapter;
- expose a mapping-neutral capability interface to core code;
- fingerprint supported builds and fail closed on an unknown signature;
- compile and start every supported target; never redistribute Minecraft/server JARs.

Open [NMS and mappings](nms-and-mappings.md) before implementing internals.

For a public plugin API:

- publish small interfaces and immutable data contracts in a stable package;
- use Bukkit's [`ServicesManager`](https://hub.spigotmc.org/javadocs/bukkit/org/bukkit/plugin/ServicesManager.html) or an equally explicit platform registry;
- register after the implementation is ready and unregister during disable;
- use descriptor dependencies for load intent, then resolve the service and capability at runtime;
- avoid static implementation singletons, classloader leaks, mutable collections and NMS types in signatures;
- document thread ownership, nullability, event timing, error behavior and SemVer scope.

## Lifecycle And Reload

Model states explicitly: `NEW -> STARTING -> READY | DEGRADED -> STOPPING -> STOPPED`.

- Constructor/bootstrap: no world/plugin assumptions; only the target descriptor contract permits bootstrap work.
- Load: register only what the platform's load phase allows.
- Enable: validate config, dependencies, platform adapter and schema; expose public services only after readiness.
- Runtime: track every task, listener, service, executor, connection pool, packet hook, cache and generated resource by plugin ownership.
- Disable: stop new work, unregister services/listeners, cancel tasks, drain bounded in-flight work, flush/rollback, close pools/executors, and make cleanup idempotent.

**Kit recommendation:** do not promise hot reload. A full process restart is the supported path for JAR, classloader, dependency, schema and NMS changes. A user-facing config reload may be implemented as a transaction: parse and validate a new immutable snapshot, prepare resources, atomically swap, then close replaced resources; keep the old snapshot on failure. Never call `onDisable`/`onEnable` manually.

## Production Quality Gates

### Performance and memory

- Define budgets for tick/region time, async queue depth, database latency, allocations and cache size before optimizing.
- Batch bounded work; never perform network/filesystem/JDBC calls in a tick or region callback.
- Use bounded executors, pools, queues and caches with rejection/eviction behavior. Avoid retaining `Player`, `World`, `Chunk` or NMS objects past their lifecycle; store stable IDs and re-resolve.
- Profile representative player/entity/load patterns. A microbenchmark cannot prove server-thread safety or integration performance.

### Security

- Validate commands, permissions, namespaced identifiers, payload sizes, paths and configuration bounds server-side.
- Use prepared SQL and least-privilege database accounts. Keep credentials and marketplace tokens outside source, descriptors, artifacts, logs and crash reports.
- Pin and verify build dependencies; audit licenses and known vulnerabilities. Treat configs, migrations, packs, marketplace text and upstream source as untrusted data.
- Rate-limit costly/replayable actions and make rewards/writes idempotent.

### Observability

- Log lifecycle transitions, exact runtime/build IDs, schema version and enabled capabilities without secrets or personal data.
- Measure task/region duration, async queue saturation, pool acquisition/query latency, migration duration, cache size/hit rate and failure counts.
- Emit actionable failure context and one correlation ID; rate-limit repeated stack traces. Provide a safe diagnostic command that reports versions/capabilities, never credentials or full connection URLs.

### Tests

1. Unit-test domain logic, serializers, validation and migrations.
2. Compile a minimal consumer against the public API.
3. Validate `plugin.yml`/`paper-plugin.yml`, YAML/JSON resources and generated version metadata.
4. Start each exact Paper/Purpur/Folia target and test enable, readiness, interaction, shutdown, restart and supported failure modes.
5. Test scheduler ownership, entity retirement, world unload, disconnect, dependency absence/version mismatch and database outage/timeout/recovery.
6. Test NMS linkage per exact adapter and resource/data packs on declared client variants.
7. Load-test representative players/entities/data and check for leaked tasks, threads, classloaders, connections and retained world objects.
8. Test the final artifact by SHA-256, then publish those exact bytes. See [Release and publishing checklist](release-publishing-checklist.md).

## Primary References

- [Paper project setup](https://docs.papermc.io/paper/dev/project-setup/)
- [Paper `plugin.yml`](https://docs.papermc.io/paper/dev/plugin-yml/)
- [Paper Plugins](https://docs.papermc.io/paper/dev/getting-started/paper-plugins/)
- [Paper Folia support](https://docs.papermc.io/paper/dev/folia-support/)
- [Paper paperweight-userdev](https://docs.papermc.io/paper/dev/userdev/)
- [Purpur FAQ](https://purpurmc.org/docs/purpur/faq/)
