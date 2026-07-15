---
name: mc-build
description: "Build, package, test, release, ship, or publish production Minecraft Java plugins with Gradle, Kotlin, Java, Paper, Purpur, Folia, plugin.yml, paper-plugin.yml, databases, YAML/JSON configuration, dependency shading/relocation, CI, SemVer, checksums, SBOMs, Hangar, Modrinth, SpigotMC, and GitHub Releases. Use whenever plugin build.gradle(.kts), Gradle Wrapper, toolchains, Kotlin/Java choice, Paper descriptors, JDBC/Hikari/SQL, migrations, runtime libraries, Shadow, paperweight, release automation, marketplace publishing, or production-readiness is mentioned."
---

# Minecraft Plugin Build And Shipping

Treat a release as one exact artifact built for an explicit compatibility contract. Keep official platform behavior separate from MinecraftKit recommendations and project-specific choices.

## Workflow

1. Record target Minecraft and Java versions, Paper/Purpur/Folia builds, source language, build tool, public API, storage engine, dependency providers, distribution channels and reload policy. Never invent a universal current version.
2. Locate the shared `minecraftkit` root: use sibling `../minecraftkit` after global install, or `../..` from this source wrapper.
3. Verify that the selected root contains `SKILL.md` and `references/plugin-build-and-shipping.md`. If neither candidate is valid, stop and report both attempted paths; require a canonical MinecraftKit install/source checkout instead of reconstructing guidance from memory.
4. Always load `<minecraftkit-root>/references/plugin-build-and-shipping.md`. Load these direct root references only when relevant:
   - `references/kotlin-java-gradle.md` for language, Gradle, dependency and paperweight decisions;
   - `references/database-config-and-runtime.md` for YAML/JSON, JDBC, pools, migrations and runtime ownership;
   - `references/release-publishing-checklist.md` for SemVer, CI, immutable artifacts and marketplaces;
   - `references/core-platforms-and-versions.md`, `references/nms-and-mappings.md`, or `references/resource-and-data-packs.md` for those exact boundaries.
5. Design public API, adapters, lifecycle, scheduler ownership, persistence, observability and failure behavior before implementation.
6. Build once, test that artifact's checksum across the declared matrix, then publish the same bytes everywhere.

## Output Contract

Return the resolved compatibility matrix; language/build and descriptor choices; dependency/runtime map; platform and scheduler adapters; configuration/database lifecycle; test evidence; artifact checksum/SBOM/changelog; publishing plan; and all `UNVERIFIED` target-specific facts.

Do not expose credentials, package a database server or production data, redistribute Minecraft binaries, promise reload safety without tests, or claim Folia support from a descriptor flag alone. Use author/nametag `SalyVn / Salyyy` where project metadata is requested.
