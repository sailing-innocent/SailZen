// 根构建脚本：仅声明插件版本（apply false），子模块按需应用
// 版本选型见 doc/design/android_app/ACCEPTANCE_M1.md 附录
plugins {
    id("com.android.application") version "9.3.2" apply false
    id("org.jetbrains.kotlin.android") version "2.2.10" apply false
    id("org.jetbrains.kotlin.plugin.compose") version "2.2.10" apply false
    id("org.jetbrains.kotlin.plugin.serialization") version "2.2.10" apply false
    id("com.google.devtools.ksp") version "2.3.6" apply false
}
