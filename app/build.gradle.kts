plugins { id("com.android.application") }

android {
    namespace = "com.rezox.render"
    compileSdk = 35
    ndkVersion = "27.2.12479018"

    defaultConfig {
        applicationId = "com.rezox.render"
        minSdk = 28
        targetSdk = 35
        versionCode = 2
        versionName = "0.2.0-native-inspection"

        ndk { abiFilters += listOf("arm64-v8a") }
        externalNativeBuild {
            cmake { cppFlags += listOf("-std=c++17", "-Wall", "-Wextra", "-Werror") }
        }
    }
    externalNativeBuild {
        cmake {
            path = file("src/main/cpp/CMakeLists.txt")
            version = "3.22.1"
        }
    }
    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
}

dependencies {
    testImplementation("junit:junit:4.13.2")
}
