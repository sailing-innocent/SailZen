import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale
import java.util.Properties

plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
    id("org.jetbrains.kotlin.plugin.compose")
    id("org.jetbrains.kotlin.plugin.serialization")
    id("com.google.devtools.ksp")
}

// 从 android/version.properties 读取版本号（发布脚本自动递增 VERSION_CODE）
val versionPropsFile = rootProject.file("version.properties")
val versionProps = Properties().apply {
    if (versionPropsFile.isFile) {
        versionPropsFile.inputStream().use { load(it) }
    }
}
val appVersionCode = providers.gradleProperty("SAILZEN_VERSION_CODE")
    .map { it.toInt() }
    .orElse(versionProps.getProperty("VERSION_CODE")?.trim()?.toIntOrNull() ?: 1)
    .get()
val appVersionName = providers.gradleProperty("SAILZEN_VERSION_NAME")
    .orElse(versionProps.getProperty("VERSION_NAME")?.trim()?.takeIf { it.isNotEmpty() } ?: "0.2.0")
    .get()

android {
    namespace = "com.sailzen.app"
    compileSdk = 36

    defaultConfig {
        applicationId = "com.sailzen.app"
        minSdk = 26
        targetSdk = 36
        versionCode = appVersionCode
        versionName = appVersionName
    }

    // 项目本地 Release 配置（android/keystore.properties，已在 android/.gitignore 中忽略）
    val keystorePropsFile = rootProject.file("keystore.properties")
    val keystoreProps = Properties().apply {
        if (keystorePropsFile.isFile) {
            keystorePropsFile.inputStream().use { load(it) }
        }
    }

    fun resolveReleaseProp(primary: String, fallback: String? = null): String {
        val candidates = buildList {
            add(providers.gradleProperty(primary).orNull)
            add(providers.environmentVariable(primary).orNull)
            add(keystoreProps.getProperty(primary))
            if (fallback != null) {
                add(providers.gradleProperty(fallback).orNull)
                add(providers.environmentVariable(fallback).orNull)
                add(keystoreProps.getProperty(fallback))
            }
        }
        return candidates.firstOrNull { !it.isNullOrBlank() }?.trim().orEmpty()
    }

    // 远程服务器地址：release 构建从 keystore.properties / gradle 属性 / 环境变量注入，打包后锁定不可修改
    val releaseServerUrl = resolveReleaseProp("SAILZEN_RELEASE_SERVER_URL").trimEnd('/')

    // release 签名证书：Android 发布包本身即使用 keytool 生成的自签名证书（无需向 CA 申请）。
    // 推荐放在 android/keystore/ 并通过 android/keystore.properties 配置（均已 gitignore）。
    val releaseStoreFilePath = resolveReleaseProp("SAILZEN_RELEASE_STORE_FILE", "SAILZEN_STORE_FILE")
    val releaseStorePassword = resolveReleaseProp("SAILZEN_RELEASE_STORE_PASSWORD", "SAILZEN_STORE_PASSWORD")
    val releaseKeyAlias = resolveReleaseProp("SAILZEN_RELEASE_KEY_ALIAS", "SAILZEN_KEY_ALIAS")
    val releaseKeyPassword = resolveReleaseProp("SAILZEN_RELEASE_KEY_PASSWORD", "SAILZEN_KEY_PASSWORD")
    val hasReleaseSigning = releaseStoreFilePath.isNotBlank() && releaseStorePassword.isNotBlank() &&
        releaseKeyAlias.isNotBlank() && releaseKeyPassword.isNotBlank()

    signingConfigs {
        if (hasReleaseSigning) {
            create("release") {
                val rawFile = File(releaseStoreFilePath)
                storeFile = if (rawFile.isAbsolute) rawFile else rootProject.file(releaseStoreFilePath)
                storePassword = releaseStorePassword
                keyAlias = releaseKeyAlias
                keyPassword = releaseKeyPassword
            }
        }
    }

    buildTypes {
        debug {
            // M1 验收构建：不混淆；允许用户修改服务器地址
            buildConfigField("String", "SERVER_URL", "\"\"")
            buildConfigField("boolean", "SERVER_URL_LOCKED", "false")
        }
        release {
            isMinifyEnabled = false
            proguardFiles(
                getDefaultProguardFile("proguard-android-optimize.txt"),
                "proguard-rules.pro",
            )
            // 公网发布包锁定服务器地址，避免用户误改
            buildConfigField("String", "SERVER_URL", "\"$releaseServerUrl\"")
            buildConfigField("boolean", "SERVER_URL_LOCKED", "true")
            // 配置了 release 证书则用它签名；未配置时回退 debug 证书，避免产出未签名包导致安装失败
            signingConfig = if (hasReleaseSigning) {
                signingConfigs.getByName("release")
            } else {
                signingConfigs.getByName("debug")
            }
        }
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
    kotlinOptions {
        jvmTarget = "17"
    }
    buildFeatures {
        compose = true
        buildConfig = true
    }

    testOptions {
        unitTests {
            // android.util.Log 等桩方法在 JVM 单测中返回默认值而非抛异常
            isReturnDefaultValues = true
            all {
                it.jvmArgs(
                    "-XX:+IgnoreUnrecognizedVMOptions",
                    "--add-opens=java.base/java.lang=ALL-UNNAMED",
                    "--add-opens=java.base/java.util=ALL-UNNAMED",
                )
            }
        }
    }
}

// 按构建类型输出带版本、构建类型的 APK 文件名，方便复制到开发机真机验证
androidComponents {
    onVariants { variant ->
        variant.outputs.forEach { output ->
            val buildType = variant.buildType
            val version = android.defaultConfig.versionName ?: "0.0.0"
            val code = android.defaultConfig.versionCode ?: 1
            val timestamp = SimpleDateFormat("MMddHHmm", Locale.getDefault()).format(Date())
            val suffix = if (buildType == "debug") "debug" else "release"
            output.outputFileName.set("SailZen-${version}-vc${code}-${suffix}-${timestamp}.apk")
        }
    }
}

dependencies {
          val composeBom = platform("androidx.compose:compose-bom:2024.09.03")
    implementation(composeBom)

    // AndroidX 基础
    implementation("androidx.core:core-ktx:1.13.1")
    implementation("androidx.activity:activity-compose:1.9.3")
    implementation("androidx.lifecycle:lifecycle-runtime-ktx:2.8.6")
    implementation("androidx.lifecycle:lifecycle-runtime-compose:2.8.6")
    implementation("androidx.lifecycle:lifecycle-viewmodel-compose:2.8.6")
    implementation("androidx.navigation:navigation-compose:2.8.3")

    // Compose
    implementation("androidx.compose.ui:ui")
    implementation("androidx.compose.ui:ui-tooling-preview")
    implementation("androidx.compose.material3:material3")
    implementation("androidx.compose.material:material-icons-core")
    implementation("androidx.compose.material:material-icons-extended")
    debugImplementation("androidx.compose.ui:ui-tooling")

    // 网络
    implementation("com.squareup.retrofit2:retrofit:2.11.0")
    implementation("com.squareup.retrofit2:converter-kotlinx-serialization:2.11.0")
    implementation("com.squareup.okhttp3:okhttp:4.12.0")
    implementation("com.squareup.okhttp3:logging-interceptor:4.12.0")
    implementation("org.jetbrains.kotlinx:kotlinx-serialization-json:1.7.3")
    implementation("org.jetbrains.kotlinx:kotlinx-coroutines-android:1.8.1")

    // 本地存储
    implementation("androidx.room:room-runtime:2.8.2")
    implementation("androidx.room:room-ktx:2.8.2")
    ksp("androidx.room:room-compiler:2.8.2")
    implementation("androidx.datastore:datastore-preferences:1.1.1")

    // 后台任务
    implementation("androidx.work:work-runtime-ktx:2.9.1")

    // 测试
    testImplementation("junit:junit:4.13.2")
    testImplementation("org.jetbrains.kotlinx:kotlinx-coroutines-test:1.8.1")
    testImplementation("org.mockito:mockito-core:5.14.2")
    testImplementation("androidx.arch.core:core-testing:2.2.0")
    testImplementation("app.cash.turbine:turbine:1.2.0")
}
