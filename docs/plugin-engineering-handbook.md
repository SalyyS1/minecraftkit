# Production Minecraft Plugin Engineering Handbook

Use `/mc:build` for build, runtime, database and release work. This handbook is the production decision map for Salyyy Minecraft Kit v2.1; focused recipes live in the linked root references.

Maintainer identity / nametag: **SalyVn / Salyyy**.

## Contents

- [How to read decisions](#how-to-read-decisions)
- [Start with a target contract](#start-with-a-target-contract)
- [Choose Java, Kotlin, and Gradle intentionally](#choose-java-kotlin-and-gradle-intentionally)
- [Choose the descriptor](#choose-the-descriptor)
- [Map every dependency to runtime](#map-every-dependency-to-runtime)
- [Design platform and scheduler adapters](#design-platform-and-scheduler-adapters)
- [Isolate NMS and publish a stable API](#isolate-nms-and-publish-a-stable-api)
- [Treat config and persistence as data products](#treat-config-and-persistence-as-data-products)
- [Own lifecycle, reload, and failure](#own-lifecycle-reload-and-failure)
- [Prove production quality](#prove-production-quality)
- [Version and ship immutable bytes](#version-and-ship-immutable-bytes)
- [Reference map](#reference-map)

## How To Read Decisions

This handbook uses three authority levels:

- **[PLATFORM]** An upstream contract documented by Paper, Purpur, Gradle, Kotlin, a database vendor, SemVer, or a publishing platform. Version-sensitive contracts still need an exact target.
- **[KIT]** A conservative Salyyy Minecraft Kit recommendation derived from those contracts. It is not an upstream rule.
- **[PROJECT]** A choice that must be made from product scope, deployment, licensing and measured evidence.

If a fact cannot be tied to the selected target, mark it `UNVERIFIED`. Never hard-code a universal “current” Java, Minecraft, Paper, Gradle or plugin version; accept those as compatibility inputs.

## Start With A Target Contract

Fill this before writing the build:

```text
name/version/author: <plugin> / <SemVer> / SalyVn + Salyyy
game: <exact Minecraft IDs or evidence-backed range>
java: <minimum runtime> / <toolchain> / <emitted bytecode>
servers: Paper <builds>, Purpur <builds>, Folia <builds>
source: Java | Kotlin | mixed
build: Gradle Wrapper <version>, Kotlin DSL
descriptor: plugin.yml | paper-plugin.yml | both
public API: <packages/types/events/services and compatibility policy>
internals: none | paperweight adapter per exact target
config: <YAML/YML/JSON files and schema versions>
storage: <engine, driver provider, pool, schema, backup objective>
runtime libraries: <server | Paper libraries | shaded | operator>
distribution: GitHub | Hangar | Modrinth | SpigotMC | private
operations: readiness, shutdown, restart/reload policy, diagnostics
evidence: tests + artifact SHA-256 + SBOM + compatibility matrix
```

The support claim belongs to one artifact hash. “Compiles against Paper” does not prove Purpur, Folia, database, client or NMS compatibility.

## Choose Java, Kotlin, And Gradle Intentionally

**[PROJECT] Language choice:**

- Choose Java for the smallest language-runtime footprint, Java-first public APIs and broad contributor familiarity.
- Choose Kotlin when its null-safety/modeling/coroutines materially benefit a Kotlin-capable team and the Kotlin runtime is explicitly provisioned.
- Choose mixed sources for a Java-facing API plus Kotlin implementation or an incremental migration, accepting two compiler/ABI contracts.

**[KIT]** Keep cross-plugin APIs Java-friendly. Do not leak Kotlin implementation types, coroutines, mutable collections, platform internals or NMS across the public boundary. A plain JAR does not automatically bundle Kotlin stdlib or an `implementation`/`runtimeOnly` dependency.

**[KIT] Gradle baseline:** Wrapper + Kotlin DSL + explicit toolchain + pinned release inputs + locks + verification + tested configuration cache. Parameterized skeleton:

```kotlin
import org.gradle.api.tasks.bundling.AbstractArchiveTask
import org.gradle.api.tasks.compile.JavaCompile
import org.gradle.jvm.toolchain.JavaLanguageVersion
import org.jetbrains.kotlin.gradle.dsl.JvmTarget

plugins {
    java
    alias(libs.plugins.kotlin.jvm) // remove for Java-only
}

val targetJava = providers.gradleProperty("targetJava").map(String::toInt)
val paperApiDependencyVersion = providers.gradleProperty("paperApiDependencyVersion")
val paperDescriptorApiVersion = providers.gradleProperty("paperDescriptorApiVersion")
version = providers.gradleProperty("pluginVersion").get()

repositories {
    mavenCentral()
    maven("https://repo.papermc.io/repository/maven-public/")
}

dependencies {
    compileOnly("io.papermc.paper:paper-api:${paperApiDependencyVersion.get()}")
}

java.toolchain.languageVersion.set(targetJava.map(JavaLanguageVersion::of))
tasks.withType<JavaCompile>().configureEach { options.release.set(targetJava) }

kotlin {
    jvmToolchain(targetJava.get())
    compilerOptions {
        jvmTarget.set(targetJava.map { JvmTarget.fromTarget(it.toString()) })
    }
}

dependencyLocking { lockAllConfigurations() }

tasks.withType<AbstractArchiveTask>().configureEach {
    isPreserveFileTimestamps = false
    isReproducibleFileOrder = true
}
```

**[PLATFORM]** Gradle [toolchains](https://docs.gradle.org/current/userguide/toolchains.html), [dependency locking](https://docs.gradle.org/current/userguide/dependency_locking.html), [dependency verification](https://docs.gradle.org/current/userguide/dependency_verification.html), and [configuration cache](https://docs.gradle.org/current/userguide/configuration_cache.html) are separate mechanisms. Locks select versions; verification checks artifact identity; neither makes changing/SNAPSHOT coordinates immutable. Configuration-cache failures must be fixed or documented, not hidden.

See [Kotlin, Java, and Gradle](../references/kotlin-java-gradle.md) for descriptor expansion, scopes, Shadow, reproducible archives and paperweight snippets.

## Choose The Descriptor

| Descriptor | Upstream contract | Choose when |
|---|---|---|
| `plugin.yml` | Bukkit-compatible Paper descriptor; commands, permissions, load intent, dependencies and `libraries` | broad Paper/Purpur/Bukkit-style compatibility |
| `paper-plugin.yml` | experimental Paper Plugin model; bootstrapper/loader, split dependency graph and classloader differences; not a drop-in replacement | a required Paper-only bootstrap or loader capability justifies the boundary |
| both | Paper permits both resources | every target/path is tested and metadata stays consistent |

**[PLATFORM]** `api-version` is a load boundary, not a complete compatibility proof. `folia-supported: true` admits loading but does not establish scheduler correctness. Paper Plugins are experimental and may change.

**[KIT]** Generate descriptor version/API inputs from reviewed release properties and validate the rendered YAML. Keep the full `paper-api` dependency coordinate separate from the shorter descriptor API value; current Paper version formats do not guarantee they are interchangeable. Use:

```yaml
name: ExamplePlugin
version: '${version}'
main: dev.salyvn.example.ExamplePlugin
api-version: '${paperDescriptorApiVersion}'
authors: [SalyVn, Salyyy]
```

Add `folia-supported: true` only after global, region, entity and async ownership tests pass. Read Paper's [`plugin.yml`](https://docs.papermc.io/paper/dev/plugin-yml/) and [Paper Plugins](https://docs.papermc.io/paper/dev/getting-started/paper-plugins/) contracts for the selected build.

## Map Every Dependency To Runtime

For each coordinate, answer: who provides its classes, to which classloader, at which version, under which license, and what happens if resolution fails?

| Choice | Use for | Required proof |
|---|---|---|
| `compileOnly` + server provider | Paper/Bukkit and documented integration APIs | absent from JAR; exact runtime/API check |
| Paper `libraries` | Maven Central runtime libraries on supported Paper deployments | startup network/cache policy, version, classloader behavior |
| shaded/relocated | self-contained private runtime dependency | final-JAR tests, service resources/native files, notices, collision checks |
| external/operator provider | managed runtime contract | classloader visibility, supported version, clear absence failure |

**[KIT]** Relocate collision-prone private packages, not Paper/Bukkit/public APIs. Merge and test `ServiceLoader` resources such as JDBC drivers. Do not minimize reflective/serialized/service-loaded code without end-to-end proof. Audit every redistributed license and scan final bytes.

A database driver may be provided by Paper, shaded, or supplied by an operator. It should not be categorically excluded. A database server and mutable production database never belong in the plugin JAR.

## Design Platform And Scheduler Adapters

Keep gameplay/application rules behind small ports. Add modules only when the compatibility boundary warrants them:

```text
stable core/API
  -> Paper adapter
  -> optional Purpur capability adapter
  -> Folia-aware scheduler adapter
  -> optional exact-target NMS adapter
  -> database/config/metrics adapters
```

**[PLATFORM] Ownership:**

- global scheduler: global-region state such as time/weather/global rules and console-owned work;
- region scheduler: a location/chunk's world state;
- entity scheduler: that entity's state and retirement; it follows region movement;
- async scheduler or bounded executor: JDBC, filesystem, HTTP, compression and pure computation.

Never touch Bukkit/Paper state directly from an I/O completion. Capture immutable identifiers on the owner, do bounded work off-thread, then re-resolve lifecycle state on the correct owner.

Java adapter surface:

```java
interface PlatformScheduler {
    void global(Runnable task);
    void region(Location location, Runnable task);
    boolean entity(Entity entity, Runnable task, Runnable retired);
    <T> CompletableFuture<T> io(Callable<T> task);
}
```

Kotlin use after repository I/O:

```kotlin
val playerId = player.uniqueId
repository.loadAsync(playerId).whenComplete { profile, failure ->
    if (failure != null) {
        recordStorageFailure(playerId, failure)
    } else {
        scheduler.entity(
            player,
            { if (player.isOnline && player.uniqueId == playerId) apply(player, profile) },
            { recordDiscardedProfile(playerId) },
        )
    }
}
```

The adapter implementation, not the core, owns target API calls. **[KIT]** Keep Purpur-only calls behind a capability adapter and provide a Paper fallback. Do not scatter platform-name checks or assume Paper tests prove Purpur/Folia behavior. Follow [Paper's Folia support contract](https://docs.papermc.io/paper/dev/folia-support/).

## Isolate NMS And Publish A Stable API

Prefer public Paper/Bukkit APIs, Adventure/registries/data components, public plugin services and typed protocol libraries. Use NMS only after documenting the missing capability.

**[PLATFORM]** Paper supports internal development through [`paperweight-userdev`](https://docs.papermc.io/paper/dev/userdev/). Namespaces/remapping changed across Paper/Minecraft epochs.

**[KIT]** Put internals in `nms-<exact-target>` behind a mapping-neutral interface. Record exact game/Paper/dev-bundle/Java/namespaces; fingerprint at startup; fail closed on unknown builds; compile and launch every adapter. Never redistribute Minecraft/server JARs or copied implementation bodies.

Expose cross-plugin capability through a small public interface and Bukkit `ServicesManager`, not a static implementation singleton.

Java provider:

```java
public interface ExampleApi {
    CompletionStage<ProfileView> profile(UUID playerId);
}

public final class ExamplePlugin extends JavaPlugin {
    private ExampleApi api;

    @Override
    public void onEnable() {
        api = createReadyApi();
        getServer().getServicesManager().register(
            ExampleApi.class,
            api,
            this,
            ServicePriority.Normal
        );
    }

    @Override
    public void onDisable() {
        getServer().getServicesManager().unregisterAll(this);
    }
}
```

Kotlin consumer:

```kotlin
val exampleApi = server.servicesManager.load(ExampleApi::class.java)
    ?: return disableExampleIntegration("ExampleApi service is unavailable")

exampleApi.profile(player.uniqueId).whenComplete { view, failure ->
    // Handle failure, then hand game-state mutation to the player's owner.
}
```

Register only after readiness and unregister before resources disappear. Define API nullability, threading, event timing, errors and SemVer surface; keep DTOs immutable and free of NMS/implementation classes.

## Treat Config And Persistence As Data Products

**[PROJECT]** YAML is usually friendlier for operator settings; JSON suits strict machine data and Minecraft resources. `.yml` and `.yaml` are the same language, while platform descriptor filenames are exact.

**[KIT] Configuration transaction:** bounded read -> safe parse -> schema/semantic validation -> sequential migration -> prepare resources -> atomic in-memory swap -> same-directory atomic persistence when intentional. Keep the old snapshot on failure. Reject unsafe YAML tags, duplicate JSON keys, traversal, oversized structures and unresolved references. Do not assume environment interpolation.

**[KIT] Database baseline:**

- external PostgreSQL/MySQL/MariaDB server or external SQLite data file;
- exact JDBC driver delivery and license decision;
- bounded `DataSource`/pool and executor/queue;
- prepared statements, transactions and least-privilege credentials;
- acquisition, connect/network, query, transaction and feature deadlines;
- immutable checksummed migrations with one migrator and readiness gate;
- engine-aware backup plus tested restore before destructive migration;
- async I/O with global/region/entity handoff;
- stop-new-work, bounded drain, pool/executor close on disable.

SQLite's driver/native engine may be a runtime library; its mutable `.db` and backups remain operator data. Many connections do not create many SQLite writers. For shared databases, size the pool against database capacity, not player count.

See [Database, configuration, and runtime](../references/database-config-and-runtime.md) for Java atomic-write, Kotlin pool and Java/Kotlin scheduler-handoff examples.

## Own Lifecycle, Reload, And Failure

Use explicit states:

```text
NEW -> STARTING -> READY | DEGRADED -> STOPPING -> STOPPED
```

- Bootstrap/load: only work allowed by the chosen descriptor contract.
- Enable: validate platform, dependencies, config and schema; expose commands/services after readiness.
- Runtime: track tasks, listeners, callbacks, pools, executors, services, caches, packet hooks and generated resources.
- Disable: reject new work, unregister, cancel producers, drain within a deadline, flush/rollback and close idempotently.

**[KIT]** Support full process restart for JAR, dependency, NMS and schema changes. Do not promise hot reload. A config-only reload can be a tested transactional snapshot replacement. Never call lifecycle methods manually, retain classes/tasks across classloader replacement, or block a tick/region indefinitely while draining.

Define degraded behavior: disable only the failed feature, keep read-only mode, retry bounded transient startup, or fail the plugin. Never continue with a partially migrated schema, unknown NMS adapter or missing required dependency.

## Prove Production Quality

### Performance and memory

- Budget tick/region duration, allocation rate, async queue depth, pool latency and cache size.
- Batch bounded work and apply backpressure/rejection. Profile representative player/entity/data load.
- Store UUIDs/keys/snapshots across async boundaries, not long-lived `Player`, `World`, `Chunk` or NMS objects.
- Verify tasks, threads, connections, services and classloaders disappear after disable/restart tests.

### Security

- Enforce permissions and validate commands, identifiers, payload sizes and resource paths server-side.
- Use prepared SQL, allowlist dynamic identifiers and rate-limit costly/replayable actions.
- Keep database/marketplace credentials out of Git, Gradle properties committed to source, descriptors, artifacts, logs and diagnostics.
- Pin/verify dependencies, audit bundled licenses/vulnerabilities, and treat configs/packs/upstream content as untrusted data.

### Observability

- Log safe plugin/game/platform/build/schema/capability identities and lifecycle transitions.
- Measure owner-task duration, async queue saturation, pool wait/query latency, migration time, cache size and failure/discard counts.
- Use low-cardinality labels and rate-limited errors with correlation IDs. Never emit SQL text with values, credentials, full JDBC URLs or personal data.

### Test ladder

1. Unit: domain rules, serialization, validation, migrations and idempotency.
2. Compile contract: Java/Kotlin, public API consumer, descriptor/resource generation, exact NMS adapters.
3. Integration: exact Paper/Purpur/Folia artifacts, enable/readiness/use/disable/restart.
4. Ownership: global/region/entity/async, teleport/retirement, world unload, disconnect and cancellation.
5. Persistence: fresh schema, every supported upgrade, outage/timeout, duplicate write/reward, backup restore and shutdown.
6. Compatibility: required/optional dependency absence/mismatch, pack/client variants and degraded fallbacks.
7. Load/leak: representative concurrency, queue/pool pressure, memory retention and repeated lifecycle.
8. Release: inspect final JAR, reproduce checksum, install that exact hash and publish without rebuilding.

## Version And Ship Immutable Bytes

**[PLATFORM]** Define the public API to which SemVer applies. Against that API:

- `1.0.0 -> 1.0.1`: compatible fix;
- `1.0.0 -> 1.1.0`: compatible feature/deprecation;
- `1.0.0 -> 2.0.0`: incompatible public API.

**[KIT/PROJECT]** Decide and publish whether configuration, persisted data, required dependencies, supported runtimes, operator actions and observable behavior belong to the declared public product contract. If included, an incompatible change to that contract requires the policy's breaking-change path; changing a dependency alone does not mechanically require MAJOR.

**[PLATFORM]** SemVer says released contents are immutable. **[KIT]** Build one JAR, test its SHA-256, generate SPDX/CycloneDX SBOM + notices + changelog + compatibility matrix, then upload identical bytes to every channel.

Publishing gate:

```text
trusted tag/source
 -> wrapper + locks + verification
 -> checks + exact runtime matrix
 -> one inspected JAR + SHA-256
 -> SBOM/notices/changelog/matrix/provenance
 -> protected secret-scoped promotion
 -> GitHub + Hangar + Modrinth + SpigotMC
 -> download/hash/smoke verification
```

CI build jobs receive no marketplace secrets. Publishing jobs use separate least-privilege tokens, protected environments and immutable action/plugin pins. Fork code never runs with release secrets. Do not rebuild per channel, overwrite released bytes, or automate SpigotMC through scraped sessions/cookies.

See the [release and publishing checklist](../references/release-publishing-checklist.md) for SemVer examples, compatibility fields, CI trust zones, checksums/SBOMs and channel-specific gates.

## Reference Map

- [Plugin build and shipping](../references/plugin-build-and-shipping.md): architecture, descriptors, dependencies, adapters, lifecycle and production gates.
- [Kotlin, Java, and Gradle](../references/kotlin-java-gradle.md): language/runtime decision, Kotlin DSL, Wrapper, toolchains, scopes, locking, verification, Shadow, reproducibility and paperweight.
- [Database, configuration, and runtime](../references/database-config-and-runtime.md): YAML/JSON validation, atomic writes, drivers/pools, async handoff, migrations, backups and shutdown.
- [Release and publishing checklist](../references/release-publishing-checklist.md): SemVer, immutable artifacts, SHA-256, SBOM, compatibility matrix, CI secrets, GitHub, Hangar, Modrinth and SpigotMC.
- [Core platforms and versions](../references/core-platforms-and-versions.md): target/support evidence and scheduler topology.
- [NMS and mappings](../references/nms-and-mappings.md): namespaces, exact-version adapters and redistribution boundary.
- [Resource and data packs](../references/resource-and-data-packs.md): JSON/assets, build staging, delivery hashes and client variants.

Primary official contracts: [Paper developer docs](https://docs.papermc.io/paper/dev/), [Purpur docs](https://purpurmc.org/docs/), [Gradle user manual](https://docs.gradle.org/current/userguide/userguide.html), [Kotlin Gradle docs](https://kotlinlang.org/docs/gradle-configure-project.html), [SemVer](https://semver.org/), [Hangar publishing](https://docs.papermc.io/misc/hangar-publishing/), [Modrinth create-version API](https://docs.modrinth.com/api/operations/createversion/), and [SpigotMC resource guidelines](https://www.spigotmc.org/wiki/resources/).
