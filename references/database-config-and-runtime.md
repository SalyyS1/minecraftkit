# Database, Configuration, And Runtime

Use this reference with `mc:build` for YAML/JSON files, JDBC, pooling, migrations, backups, asynchronous I/O, scheduler handoff and shutdown. Database servers, production database files and operator secrets remain external to the plugin JAR.

## Contents

- [Authority and ownership](#authority-and-ownership)
- [Configuration formats](#configuration-formats)
- [Validation, migration, and atomic writes](#validation-migration-and-atomic-writes)
- [Database and driver choices](#database-and-driver-choices)
- [Pool and timeout policy](#pool-and-timeout-policy)
- [Async I/O and game-state handoff](#async-io-and-game-state-handoff)
- [Database migrations and backups](#database-migrations-and-backups)
- [Shutdown and recovery](#shutdown-and-recovery)
- [Security and observability](#security-and-observability)

## Authority And Ownership

- **Platform contract:** Paper/Purpur/Folia scheduler APIs define where game state may be touched. JDBC/database libraries do not override that ownership.
- **Kit recommendation:** filesystem, network and database operations run on a bounded plugin-owned executor or documented async scheduler; results return through the correct global, region or entity scheduler.
- **Project decision:** database engine, driver delivery, pool, schema, durability, backup objectives and degraded behavior depend on deployment evidence.

Keep four artifacts distinct:

1. migration/config templates in source control and the plugin JAR;
2. driver/pool/parser libraries provisioned at runtime or bundled lawfully;
3. database server/process managed outside the plugin;
4. mutable configuration, SQLite files, credentials, backups and user data in operator-owned external storage.

## Configuration Formats

| Format | Good fit | Production cautions |
|---|---|---|
| YAML (`.yml` or `.yaml`) | operator-edited settings and Paper-native configuration | indentation/types, aliases/tags, comment preservation, ambiguous scalar coercion |
| JSON | machine-generated strict data, caches/manifests, resource/data-pack assets | no comments, duplicate keys, number bounds, schema/version migration |

`.yml` and `.yaml` are filename extensions for the same YAML language; `plugin.yml` and `paper-plugin.yml` are exact platform filenames. Paper's [configuration guide](https://docs.papermc.io/paper/dev/plugin-configurations/) documents its YAML helpers. JSON or another format is an application choice and requires its own parser and lifecycle.

Every mutable file should declare or imply:

```text
format/schema version
stable namespaced identifiers
required and optional keys
types, ranges, lengths, enum values and cross-field invariants
unknown-key policy
default provenance
migration path and downgrade behavior
secret source (never an artifact default)
```

**Kit recommendations:**

- Parse into an immutable typed snapshot; do not let gameplay code walk mutable parser trees.
- Reject duplicate JSON keys and unsafe YAML tags. Configure alias, nesting, input-size and collection-size limits in the chosen parser.
- Treat unknown keys deliberately: fail for machine-owned files; warn and preserve when forward-compatible operator configuration needs it.
- Keep shipped defaults separate from the operator file. Merge missing defaults in memory and avoid rewriting a valid file merely to reformat it or destroy comments.
- Do not assume `${ENV_VAR}` interpolation. Implement an explicit, allowlisted secret/environment resolver if the product requires it, and redact resolved values.
- Validate all cross-file references before swapping the active snapshot.

## Validation, Migration, And Atomic Writes

Apply configuration transactionally:

1. read bounded bytes without modifying the active file;
2. parse with safe limits;
3. validate schema and semantics;
4. migrate a copy one version at a time;
5. prepare dependent resources (pool, caches, adapters);
6. atomically swap the in-memory snapshot;
7. close replaced resources;
8. persist only when a migration/default materialization is intentional.

On any failure, retain the previous working snapshot and report the file plus safe validation path; never print secrets or the complete document.

Java example for same-directory atomic replacement of already-validated bytes:

```java
static void atomicReplace(Path target, byte[] validatedBytes) throws IOException {
    Path absolute = target.toAbsolutePath().normalize();
    Path directory = Objects.requireNonNull(absolute.getParent());
    Files.createDirectories(directory);
    Path temp = Files.createTempFile(
        directory,
        "." + absolute.getFileName(),
        ".tmp"
    );
    boolean moved = false;
    try {
        try (FileChannel channel = FileChannel.open(
            temp,
            StandardOpenOption.WRITE,
            StandardOpenOption.TRUNCATE_EXISTING
        )) {
            ByteBuffer buffer = ByteBuffer.wrap(validatedBytes);
            while (buffer.hasRemaining()) {
                channel.write(buffer);
            }
            channel.force(true);
        }
        try {
            Files.move(
                temp,
                absolute,
                StandardCopyOption.ATOMIC_MOVE,
                StandardCopyOption.REPLACE_EXISTING
            );
            moved = true;
        } catch (AtomicMoveNotSupportedException unsupported) {
            throw new IOException("Atomic replacement is unavailable", unsupported);
        }
    } finally {
        if (!moved) {
            Files.deleteIfExists(temp);
        }
    }
}
```

Create the temporary file on the target filesystem. Test replacement semantics on every supported OS/filesystem. `force(true)` plus atomic rename reduces risk but is not a universal durability guarantee; directory metadata flush semantics vary. If atomic move is unavailable, choose and document a backup/journal recovery protocol rather than silently falling back to an in-place write. See Java [`Files.move`](https://docs.oracle.com/en/java/javase/25/docs/api/java.base/java/nio/file/Files.html#move(java.nio.file.Path,java.nio.file.Path,java.nio.file.CopyOption...)).

## Database And Driver Choices

| Deployment | Suitable when | Driver/pool notes |
|---|---|---|
| PostgreSQL/MySQL/MariaDB server | multiple servers/nodes, larger datasets, remote administration | external server; vendor JDBC driver; bounded pool; network/TLS/timeouts |
| SQLite file | one server/process, simple local operations, operator accepts file-level concurrency/recovery | external data file; SQLite JDBC/native engine library may be bundled/provisioned; usually one/few connections and one writer path |
| Operator-provided `DataSource`/driver | managed hosting exposes an explicit supported contract | verify classloader visibility, version and lifecycle; fail clearly when absent |

Do not package PostgreSQL/MySQL/MariaDB server software or a live database in the plugin. An SQLite JDBC artifact may contain the SQLite engine as a native library; that is a driver/runtime choice, not permission to package the mutable `.db` file.

A driver is not always excluded. Choose one delivery strategy per supported deployment:

- Paper `plugin.yml` `libraries`: runtime download/classpath with Paper's documented constraints;
- shaded in the plugin: offline/self-contained, but larger artifact, native/service-resource and license obligations;
- external/operator provider: smallest artifact, but only valid with a documented classloader and version contract;
- Paper Plugin loader: custom resolution under an experimental Paper Plugin contract.

If shading a JDBC driver, preserve `META-INF/services/java.sql.Driver`, native resources and license notices, then test from the final JAR. If using `runtimeOnly`, remember a normal Gradle JAR does not embed or provision it.

Official driver sources include [pgJDBC](https://jdbc.postgresql.org/), [MySQL Connector/J](https://dev.mysql.com/doc/connector-j/en/), [MariaDB Connector/J](https://mariadb.com/kb/en/about-mariadb-connector-j/), and [Xerial SQLite JDBC](https://github.com/xerial/sqlite-jdbc). Pin an exact compatible release and verify its license/checksum.

## Pool And Timeout Policy

Use a JDBC `DataSource`; a bounded pool such as [HikariCP](https://github.com/brettwooldridge/HikariCP) is a common project choice, not a Paper requirement. For SQLite, measure whether a pool helps; many connections do not create many concurrent writers.

Kotlin example with all values supplied by validated configuration:

```kotlin
fun openDataSource(config: DatabaseConfig): HikariDataSource {
    require(config.maxConnections > 0)
    require(config.minimumIdle in 0..config.maxConnections)
    require(!config.jdbcUrl.contains('\n'))

    val hikari = HikariConfig().apply {
        poolName = "ExamplePlugin-database"
        jdbcUrl = config.jdbcUrl
        username = config.username
        password = config.password
        maximumPoolSize = config.maxConnections
        minimumIdle = config.minimumIdle
        connectionTimeout = config.connectTimeout.toMillis()
        validationTimeout = config.validationTimeout.toMillis()
        idleTimeout = config.idleTimeout.toMillis()
    }
    return HikariDataSource(hikari)
}
```

Validate library-specific minimum/maximum values before construction. Size the pool from database capacity and measured concurrent queries, not player count alone. Bound the plugin executor too; an unbounded queue in front of a small pool converts overload into stale work and memory growth.

Set multiple limits:

- pool acquisition/connection timeout;
- driver network/connect/socket timeout where supported;
- JDBC statement/query timeout and transaction deadline;
- bounded retry count with jitter only for transient/idempotent work;
- overall feature deadline and cancellation/lifecycle check.

Do not retry authentication, syntax, constraint or migration-checksum failures. Never log the full JDBC URL when it can contain credentials.

## Async I/O And Game-State Handoff

Model ownership, not merely `sync` versus `async`:

| Work/result | Owner |
|---|---|
| SQL, files, HTTP, compression, pure computation | bounded async executor/scheduler |
| block/chunk/location mutation | region scheduler for that location |
| entity/player mutation | that entity's scheduler, including retirement handling |
| time/weather/global rules/console-owned state | global-region scheduler |

Java example for Paper/Folia targets exposing `EntityScheduler`:

```java
private CompletableFuture<PlayerSnapshot> loadSnapshot(UUID playerId) {
    return CompletableFuture
        .supplyAsync(() -> repository.load(playerId), ioExecutor)
        .orTimeout(readTimeout.toMillis(), TimeUnit.MILLISECONDS);
}

void loadAndApply(Player player) {
    UUID expectedId = player.getUniqueId(); // capture on the owning context
    loadSnapshot(expectedId).whenComplete((snapshot, failure) -> {
        if (failure != null) {
            logStorageFailure(expectedId, failure); // no Bukkit state here
            return;
        }
        boolean accepted = player.getScheduler().execute(
            plugin,
            () -> {
                if (player.isOnline() && player.getUniqueId().equals(expectedId)) {
                    applySnapshot(player, snapshot);
                }
            },
            () -> { }, // retired callback: no world/entity mutation
            1L
        );
        if (!accepted) {
            recordDiscardedResult(expectedId);
        }
    });
}
```

Kotlin example for a location-owned result:

```kotlin
fun loadAndApply(targetOnOwnerThread: Location) {
    val target = targetOnOwnerThread.clone()
    val targetWorld = requireNotNull(target.world) { "Target world is unavailable" }
    val lookup = BlockKey(
        targetWorld.uid,
        target.blockX,
        target.blockY,
        target.blockZ,
    )

    CompletableFuture
        .supplyAsync({ repository.loadBlockPlan(lookup) }, ioExecutor)
        .orTimeout(readTimeout.toMillis(), TimeUnit.MILLISECONDS)
        .whenComplete { plan, failure ->
            if (failure != null) {
                logStorageFailure(lookup, failure)
            } else {
                server.regionScheduler.execute(this, target) {
                    val currentWorld = server.getWorld(lookup.worldId)
                    if (currentWorld != null && currentWorld === targetWorld) {
                        applyBlockPlan(currentWorld, lookup, plan)
                    }
                }
            }
        }
}
```

The examples are target-specific patterns, not universal APIs. Compile against the selected Paper artifact. A scheduler adapter should cover older/other targets and encode lifecycle behavior. Never call Bukkit/Paper getters from the I/O callback except the documented thread-safe scheduler entry point; re-resolve state inside the owner callback.

## Database Migrations And Backups

Treat schema migrations as immutable release resources:

- monotonic ID/version, description, exact checksum and supported engine;
- one migration owner at a time; use a database lock/advisory-lock strategy for shared deployments;
- applied-migration table with success/checksum; refuse edited or partially applied history;
- forward-only by default; a rollback is a separately tested migration/restore plan;
- explicit transaction boundary, noting that DDL transaction semantics differ by engine;
- prepared statements and bounded batches for data rewrites;
- readiness remains false until required migrations succeed.

Back up before destructive/data-format migrations. For a remote database, use a vendor-consistent backup/snapshot. For SQLite, quiesce/checkpoint and use a SQLite-aware backup method; do not copy a live file blindly. Define and test recovery point/time objectives, encryption, retention, access control and an actual restore drill.

Run long migrations outside tick/region callbacks. On enable, either complete a bounded bootstrap before exposing features or enter a clear `STARTING/DEGRADED` state while async initialization proceeds. Do not accept writes before schema readiness.

## Shutdown And Recovery

Shutdown order:

1. mark `STOPPING` and reject new work;
2. unregister entry points/services and cancel producers;
3. wait a bounded interval for tracked idempotent operations;
4. cancel/record remaining work and rollback open transactions;
5. close the `DataSource`/pool;
6. shut down plugin executors and confirm no threads remain;
7. persist safe diagnostics/checkpoints without blocking indefinitely.

Do not synchronously save every player on the tick/region thread during disable. Persist continuously or enqueue idempotent writes earlier, then keep the disable drain short and bounded. Test process termination, database loss, partial migration, duplicate reward/write, reconnect, server transfer and restart recovery.

## Security And Observability

- Use least-privilege database accounts, TLS/authentication appropriate to the deployment, prepared statements and allowlists for dynamic identifiers.
- Keep credentials in operator secret storage or restricted external config; exclude them from defaults, Git, logs, metrics, exceptions, SBOMs and diagnostics.
- Normalize paths under the plugin data directory, reject traversal/symlink escape, and set restrictive file permissions where supported.
- Encrypt sensitive backups and document key rotation. Do not invent application encryption without a key-management plan.
- Record schema version, migration duration, pool active/idle/wait counts, acquisition/query latency, timeout/error class, async queue depth and dropped work.
- Use low-cardinality metric labels; never label by player UUID, SQL text, connection URL or secret.
- Health/readiness must distinguish database unavailable, migration pending, pool saturated and platform handoff rejected.

Primary platform sources: [Paper configuration](https://docs.papermc.io/paper/dev/plugin-configurations/) and [Paper/Folia scheduler ownership](https://docs.papermc.io/paper/dev/folia-support/).
