import java.io.FileInputStream
import java.util.Properties

plugins {
    id("com.android.application")
    id("kotlin-android")
    id("dev.flutter.flutter-gradle-plugin")
}

// Release signing material lives OUTSIDE the repository
// (default ~/.config/madalean/release-keys/keystore.properties, see docs/SHELLS.md).
val keystorePropertiesPath: String = System.getenv("MADALEAN_KEYSTORE_PROPERTIES")
    ?: "${System.getProperty("user.home")}/.config/madalean/release-keys/keystore.properties"
val keystoreProperties = Properties()
val keystorePropertiesFile = file(keystorePropertiesPath)
val hasReleaseKey = keystorePropertiesFile.exists()
if (hasReleaseKey) {
    FileInputStream(keystorePropertiesFile).use { keystoreProperties.load(it) }
}

android {
    namespace = "mg.madalean.app"
    compileSdk = 36
    ndkVersion = flutter.ndkVersion

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }

    defaultConfig {
        applicationId = "mg.madalean.app"
        minSdk = 26
        targetSdk = 36
        versionCode = flutter.versionCode
        versionName = flutter.versionName
    }

    signingConfigs {
        create("release") {
            if (hasReleaseKey) {
                storeFile = file(keystoreProperties.getProperty("storeFile"))
                storePassword = keystoreProperties.getProperty("storePassword")
                keyAlias = keystoreProperties.getProperty("keyAlias")
                keyPassword = keystoreProperties.getProperty("keyPassword")
            }
        }
    }

    buildTypes {
        getByName("release") {
            // Never fall back to the debug key (see the check task below).
            if (hasReleaseKey) signingConfig = signingConfigs.getByName("release")
            isMinifyEnabled = true
            isShrinkResources = true
            proguardFiles(getDefaultProguardFile("proguard-android-optimize.txt"), "proguard-rules.pro")
        }
        getByName("debug") {
            signingConfig = signingConfigs.getByName("debug")
        }
    }
}

// Refuse to produce a release artefact without the release key.
tasks.configureEach {
    if ((name.startsWith("assemble") || name.startsWith("bundle") || name.startsWith("package")) &&
        name.endsWith("Release")
    ) {
        doFirst {
            if (!hasReleaseKey) {
                throw GradleException(
                    "Release key not found at $keystorePropertiesPath " +
                        "(scripts/build_apk.sh --new-key creates it, or set MADALEAN_KEYSTORE_PROPERTIES)"
                )
            }
        }
    }
}

kotlin {
    compilerOptions {
        jvmTarget.set(org.jetbrains.kotlin.gradle.dsl.JvmTarget.JVM_17)
    }
}

flutter {
    source = "../.."
}

dependencies {
    implementation("androidx.core:core-splashscreen:1.2.0")
    implementation("androidx.core:core-ktx:1.16.0")
}
