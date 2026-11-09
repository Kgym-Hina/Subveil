plugins {
    id("com.android.application") version "9.2.1"
    id("com.chaquo.python") version "17.2.0" apply false
}

// Chaquopy cannot be disabled per flavor, so it is only applied when building the
// standalone edition; otherwise the Home Assistant APK would carry a Python runtime.
val withPython = gradle.startParameter.taskNames.any { it.contains("standalone", ignoreCase = true) }
if (withPython) apply(plugin = "com.chaquo.python")

val appVersion = "0.3.0"
val zeroconfVersion = "0.146.0"

android {
    namespace = "io.github.kgymhina.subveil"
    compileSdk = 34

    defaultConfig {
        applicationId = "io.github.kgymhina.subveil"
        minSdk = 26
        targetSdk = 34
        versionCode = 3
        versionName = appVersion
    }

    buildFeatures {
        buildConfig = true
    }

    flavorDimensions += "edition"
    productFlavors {
        create("ha") {
            dimension = "edition"
            buildConfigField("boolean", "STANDALONE", "false")
        }
        create("standalone") {
            dimension = "edition"
            applicationIdSuffix = ".standalone"
            buildConfigField("boolean", "STANDALONE", "true")
            // Python 3.11 is the newest version Chaquopy builds for 32-bit ARM, which
            // many TVs still use.
            ndk { abiFilters += listOf("armeabi-v7a", "arm64-v8a") }
        }
    }

    sourceSets {
        getByName("main") {
            manifest.srcFile("AndroidManifest.xml")
            java.directories += "src"
            res.directories += "res"
            assets.directories += "assets"
        }
        getByName("ha") {
            java.directories += "variants/ha/java"
        }
        getByName("standalone") {
            java.directories += "variants/standalone/java"
            res.directories += "variants/standalone/res"
            assets.directories += "variants/standalone/assets"
        }
    }

    signingConfigs {
        create("release") {
            val ks = System.getenv("SUBVEIL_KEYSTORE")
            if (ks != null) {
                storeFile = file(ks)
                storePassword = System.getenv("SUBVEIL_KEYSTORE_PASS")
                keyAlias = System.getenv("SUBVEIL_KEY_ALIAS") ?: "subveil"
                keyPassword = System.getenv("SUBVEIL_KEY_PASS") ?: System.getenv("SUBVEIL_KEYSTORE_PASS")
            } else {
                storeFile = file("debug.keystore")
                storePassword = "android"
                keyAlias = "debug"
                keyPassword = "android"
            }
        }
    }

    buildTypes {
        getByName("release") {
            isMinifyEnabled = false
            signingConfig = signingConfigs.getByName("release")
        }
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_1_8
        targetCompatibility = JavaVersion.VERSION_1_8
    }
}

androidComponents {
    beforeVariants { variant ->
        if (withPython && variant.productFlavors.any { it.second == "ha" }) variant.enable = false
    }
}

if (withPython) extensions.configure<com.chaquo.python.ChaquopyExtension> {
    productFlavors {
        getByName("standalone") {
            version = "3.11"
            System.getenv("SUBVEIL_BUILD_PYTHON")?.let { buildPython(it) }
            pip {
                // pyatv's declared requirements ask for newer native packages than
                // Chaquopy provides; these pins are tested to work together.
                options("--no-deps")
                install("-r", "variants/standalone/requirements.txt")
                install("build/wheels/zeroconf-$zeroconfVersion-py3-none-any.whl")
            }
        }
    }
    sourceSets {
        getByName("standalone") { srcDir("variants/standalone/python") }
    }
}
