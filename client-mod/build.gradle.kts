plugins {
    java
}

group = "com.salyvn.mckit"
version = "1.0.0"

java {
    toolchain {
        languageVersion.set(JavaLanguageVersion.of(21))
    }
}

repositories {
    mavenCentral()
    maven("https://maven.fabricmc.net/")
}
