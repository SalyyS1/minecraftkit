# Kotlin, Java, And Gradle

Use this reference with `mc:build` for language, Gradle, dependency and paperweight decisions. Replace every angle-bracket value with a version selected from the target compatibility matrix; none is a universal current value.

## Contents

- [Choose Java, Kotlin, or mixed](#choose-java-kotlin-or-mixed)
- [Gradle project baseline](#gradle-project-baseline)
- [Wrapper, toolchains, and configuration cache](#wrapper-toolchains-and-configuration-cache)
- [Dependency scopes and runtime delivery](#dependency-scopes-and-runtime-delivery)
- [Locking and verification](#locking-and-verification)
- [Shading, relocation, and licenses](#shading-relocation-and-licenses)
- [Reproducible artifacts](#reproducible-artifacts)
- [paperweight and NMS](#paperweight-and-nms)
- [Build validation](#build-validation)

## Choose Java, Kotlin, Or Mixed

This is a project decision, not a Paper rule.

| Choice | Prefer when | Costs to plan |
|---|---|---|
| Java | broad contributor familiarity, Java-first public API, minimal language runtime | more boilerplate; nullability and immutable modeling need discipline |
| Kotlin | team is fluent, null-safety/coroutines/DSLs materially help, runtime provision is controlled | Kotlin stdlib/reflection/coroutine delivery, Java interop, compiler/plugin compatibility |
| Mixed | Kotlin implementation plus Java-facing API, or incremental migration | two compiler contracts, source-set cycles, ABI and toolchain alignment |

**Kit recommendations:**

- Keep a public cross-plugin API Java-friendly: interfaces, records/POJOs, Java collections, explicit nullability and `CompletionStage` where asynchronous results are public.
- Do not expose Kotlin default-argument machinery, `Unit`, implementation coroutines, mutable collections or plugin-owned classloader types unless consumers explicitly share that ABI.
- For Kotlin, choose how stdlib and any coroutine/runtime libraries arrive: Paper `libraries`, loader provisioning, or shaded bytes. The Kotlin Gradle plugin dependency does not make a normal JAR self-contained.
- If shading Kotlin, test metadata, reflection, serialization and Java consumers. Relocation is not an automatic safe default for Kotlin runtime packages.
- Use coroutines only with an explicit plugin-owned scope/dispatcher and a scheduler handoff for game state. Cancel the scope during disable; `Dispatchers.IO` does not grant Bukkit/Paper thread ownership.

## Gradle Project Baseline

**Kit recommendation:** commit the Gradle Wrapper, use Kotlin DSL, keep version inputs centralized, and pin release dependencies. Kotlin DSL is a build-language choice; plugin source may still be Java-only.

Example `gradle.properties` inputs:

```properties
pluginVersion=1.0.0
targetJava=<java-major-required-by-supported-runtime>
paperApiDependencyVersion=<exact-paper-api-coordinate-version>
paperDescriptorApiVersion=<exact-api-version-value-accepted-by-the-target-runtime>
```

Example `gradle/libs.versions.toml` for plugin/tool versions:

```toml
[versions]
kotlin = "<validated-kotlin-plugin-version>"
junit = "<validated-junit-version>"
shadow = "<validated-shadow-plugin-version>"

[plugins]
kotlin-jvm = { id = "org.jetbrains.kotlin.jvm", version.ref = "kotlin" }
shadow = { id = "com.gradleup.shadow", version.ref = "shadow" }

[libraries]
junit-bom = { module = "org.junit:junit-bom", version.ref = "junit" }
junit-jupiter = { module = "org.junit.jupiter:junit-jupiter" }
```

Representative mixed-language `build.gradle.kts`:

```kotlin
import org.gradle.api.tasks.bundling.AbstractArchiveTask
import org.gradle.api.tasks.compile.JavaCompile
import org.gradle.jvm.toolchain.JavaLanguageVersion
import org.jetbrains.kotlin.gradle.dsl.JvmTarget

plugins {
    java
    alias(libs.plugins.kotlin.jvm) // remove for a Java-only project
}

group = "dev.salyvn"

val pluginVersion = providers.gradleProperty("pluginVersion")
val targetJava = providers.gradleProperty("targetJava").map(String::toInt)
val paperApiDependencyVersion = providers.gradleProperty("paperApiDependencyVersion")
val paperDescriptorApiVersion = providers.gradleProperty("paperDescriptorApiVersion")
version = pluginVersion.get()

repositories {
    mavenCentral()
    maven("https://repo.papermc.io/repository/maven-public/") {
        content { includeGroup("io.papermc.paper") }
    }
}

dependencies {
    compileOnly("io.papermc.paper:paper-api:${paperApiDependencyVersion.get()}")
    testImplementation(platform(libs.junit.bom))
    testImplementation(libs.junit.jupiter)
}

java {
    toolchain.languageVersion.set(targetJava.map(JavaLanguageVersion::of))
    withSourcesJar()
}

kotlin {
    jvmToolchain(targetJava.get())
    compilerOptions {
        jvmTarget.set(targetJava.map { JvmTarget.fromTarget(it.toString()) })
        javaParameters.set(true)
    }
}

tasks.withType<JavaCompile>().configureEach {
    options.release.set(targetJava)
}

tasks.processResources {
    val descriptorValues = mapOf(
        "version" to pluginVersion.get(),
        "paperDescriptorApiVersion" to paperDescriptorApiVersion.get(),
    )
    inputs.properties(descriptorValues)
    filesMatching(listOf("plugin.yml", "paper-plugin.yml")) {
        expand(descriptorValues)
    }
}

tasks.test { useJUnitPlatform() }

dependencyLocking { lockAllConfigurations() }

tasks.withType<AbstractArchiveTask>().configureEach {
    isPreserveFileTimestamps = false
    isReproducibleFileOrder = true
}
```

Remove the Kotlin plugin/block for Java-only builds. For a published API module, apply `java-library` there and use `api` only for types intentionally exposed to consumers. Do not apply it merely to make `api(...)` available.

## Wrapper, Toolchains, And Configuration Cache

**Platform contract:** Gradle's [Wrapper](https://docs.gradle.org/current/userguide/gradle_wrapper.html) pins the Gradle distribution; [JVM toolchains](https://docs.gradle.org/current/userguide/toolchains.html) select compilation/runtime tools independently from the shell's JDK. Kotlin can share the JVM toolchain and typed [`compilerOptions`](https://kotlinlang.org/docs/gradle-compiler-options.html).

Create or upgrade the wrapper deliberately:

```text
gradle wrapper --gradle-version <validated-gradle-version> --distribution-type bin
./gradlew --version
```

Commit `gradlew`, `gradlew.bat`, `gradle/wrapper/gradle-wrapper.jar`, and `gradle-wrapper.properties`. Review the distribution URL/checksum and validate wrapper changes in CI. The build JVM may be newer than emitted bytecode; set both the toolchain and `JavaCompile.options.release`, then align Kotlin `jvmTarget`.

**Platform contract:** Gradle's [configuration cache](https://docs.gradle.org/current/userguide/configuration_cache.html) reuses configuration state but requires compatible build logic/plugins.

**Kit recommendation:** exercise it in CI before enabling by default:

```text
./gradlew clean check --configuration-cache
./gradlew check --configuration-cache
```

Fix reported problems rather than suppressing them. Avoid reading mutable files, environment variables or current time imperatively during configuration; model them as declared providers/inputs. If a required plugin is incompatible, document the exception and keep correctness over cache adoption.

## Dependency Scopes And Runtime Delivery

| Gradle scope | Meaning | Common plugin use |
|---|---|---|
| `compileOnly` | compile classpath, absent from runtime/test by default | Paper/server API and server-provided plugin APIs |
| `implementation` | compile/runtime classpath, not exposed by `java-library` | private libraries; still not embedded by normal `jar` |
| `runtimeOnly` | runtime classpath only | driver/runtime implementation selected behind an API |
| `api` | exposed to consumers of a `java-library` module | intentional public API dependencies only |
| `testImplementation` / `testRuntimeOnly` | test-only | test framework, fixtures, launcher |

For every dependency, record:

```text
coordinate + resolved version + checksum
compile scope
runtime provider: server | plugin.yml libraries | Paper loader | shaded | operator
classloader visibility and service resources
license/notices and redistribution permission
failure behavior when absent/incompatible
```

Paper's [`libraries`](https://docs.papermc.io/paper/dev/plugin-yml/#libraries) mechanism can provision Maven Central libraries. This trades a smaller JAR for startup resolution/network/cache policy. An external provider is valid only when the platform actually exposes the dependency to this plugin's classloader. `runtimeOnly` by itself is not a deployment mechanism.

## Locking And Verification

**Platform contract:** [dependency locking](https://docs.gradle.org/current/userguide/dependency_locking.html) records resolved versions; [dependency verification](https://docs.gradle.org/current/userguide/dependency_verification.html) validates checksums/signatures. Locking a changing/SNAPSHOT module does not make its bytes immutable.

**Kit release default:**

1. Use exact release coordinates; reject `+`, ranges, mutable branches and changing/SNAPSHOT modules in a release graph unless the target API only exists as a snapshot and verification pins its exact bytes.
2. Activate locking for the configurations the build resolves, generate lock state, review it, and commit it.
3. Generate verification metadata from a trusted network, verify hashes/signing keys independently, review the diff, and commit it.
4. Update dependencies through an explicit pull request that regenerates locks/verification and reruns the matrix.

Typical bootstrap commands:

```text
./gradlew clean check --write-locks
./gradlew clean check --write-verification-metadata sha256
./gradlew clean check
```

Run all release tasks needed to resolve configurations before considering metadata complete. Do not auto-accept new checksums after a verification failure.

## Shading, Relocation, And Licenses

Shade only after deciding runtime provisioning. Representative Shadow configuration:

```kotlin
plugins {
    alias(libs.plugins.shadow)
}

tasks.shadowJar {
    archiveClassifier.set("")
    relocate(
        "com.acme.collisionprone",
        "dev.salyvn.example.internal.libs.acme",
    )
    mergeServiceFiles()
}

tasks.jar { enabled = false }
tasks.assemble { dependsOn(tasks.shadowJar) }
```

Disabling the thin `jar` task makes the unclassified Shadow output unambiguous. If the project intentionally publishes both thin and bundled artifacts, keep Shadow's non-empty classifier and select the exact `shadowJar.archiveFile` or `jar.archiveFile` in the release job; never let both tasks target the same path.

- Relocate only packages owned by the bundled library; never relocate Paper/Bukkit, public integration APIs, JDK packages or shared DTO/API types.
- Merge service descriptors when JDBC, serializers, logging bridges or other `ServiceLoader` users require them. Inspect duplicate resources instead of blindly taking first/last.
- Test reflection strings, native libraries, multi-release JARs, Kotlin metadata and serialization after relocation.
- Avoid `minimize()` until integration tests prove reflective/service-loaded paths survive.
- Preserve licenses, copyright notices and attribution required for every redistributed component. A permissive license can still require notice preservation.
- Scan the final JAR, not only Gradle metadata: shading changes what is actually distributed.

See the [Shadow documentation](https://gradleup.com/shadow/) for the pinned plugin version's behavior.

## Reproducible Artifacts

**Platform contract:** Gradle documents reproducible archive ordering/timestamps; Gradle 9 enables reproducible archive defaults, while older supported wrappers may need explicit task settings.

**Kit recommendation:** set the controls explicitly when the supported wrapper range needs them, and remove volatile content:

- no build time, workspace path, username, random UUID or unordered map output inside the JAR;
- stable resource generation, line endings, permissions and manifest attributes;
- one version source expanded into descriptors, publication metadata and changelog;
- pinned wrapper/toolchain/plugins/dependencies plus checked lock/verification state;
- two clean builds in isolated directories with identical SHA-256 before claiming byte reproducibility.

Do not rebuild per marketplace. Promote the already-tested JAR by checksum.

## paperweight And NMS

**Platform contract:** Paper documents `paperweight-userdev` as the supported development path for internals.

Minimal target-parameterized form:

```kotlin
plugins {
    id("io.papermc.paperweight.userdev") version "<validated-paperweight-version>"
}

dependencies {
    paperweight.paperDevBundle(
        providers.gradleProperty("paperDevBundleVersion").get(),
    )
}
```

Keep this in an exact-target adapter module. Record development, artifact and runtime namespaces and follow the selected Paper line's remapping/reobfuscation instructions; those rules changed across Minecraft/Paper epochs. Do not wire a universal `reobfJar` rule or copy a dev bundle between targets. Open [NMS and mappings](nms-and-mappings.md), fail closed on unknown builds, and never publish Minecraft/server JARs or generated proprietary sources.

## Build Validation

Run the narrowest useful tasks, then the complete release graph:

```text
./gradlew clean test
./gradlew check --configuration-cache
./gradlew build
```

Then inspect the final JAR:

- descriptor exists once and contains the release version/authors/API target;
- server APIs are absent; intended runtime libraries and service resources are present exactly once;
- no credentials, local paths, production config/data, Minecraft binaries or accidental test fixtures;
- licenses/notices match bundled components;
- bytecode major and NMS namespace match the declared matrix;
- clean rebuild checksum is stable;
- that exact checksum passes server integration and publishing gates.

Primary sources: [Paper project setup](https://docs.papermc.io/paper/dev/project-setup/), [Gradle dependency configurations](https://docs.gradle.org/current/userguide/declaring_configurations.html), [Gradle reproducible archives](https://docs.gradle.org/current/userguide/working_with_files.html#sec:reproducible_archives), and [Kotlin Gradle configuration](https://kotlinlang.org/docs/gradle-configure-project.html).
