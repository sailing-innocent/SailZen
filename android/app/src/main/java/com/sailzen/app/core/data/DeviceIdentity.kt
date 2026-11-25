package com.sailzen.app.core.data

import android.annotation.SuppressLint
import android.content.Context
import android.os.Build
import android.provider.Settings
import java.security.MessageDigest

/**
 * SailZen Android 端稳定终端身份识别（Device Identity v2）：
 * - 基于 Android 8.0+ 应用签名作用域的稳定硬件标识 Settings.Secure.ANDROID_ID，
 *   同一台物理机 + 同一张签名证书，即使卸载重装或清除数据，仍生成完全一致的 device_id 与 fingerprint；
 * - 自动识别模拟器环境，避免本地调试模拟器污染真实终端列表；
 * - 规范化设备显示名称（如 "HONOR PNM-AN10"）。
 */
data class DeviceIdentityInfo(
    val stableDeviceId: String?,
    val fingerprint: String,
    val displayName: String,
    val manufacturer: String,
    val model: String,
    val osVersion: String,
    val isEmulator: Boolean,
)

object DeviceIdentity {

    private const val KNOWN_BAD_ANDROID_ID = "9774d56d682e549c"

    fun sha256Short(input: String, length: Int = 16): String {
        val digest = MessageDigest.getInstance("SHA-256").digest(input.toByteArray(Charsets.UTF_8))
        return digest.joinToString("") { "%02x".format(it) }.take(length)
    }

    fun detectEmulator(
        fingerprint: String = Build.FINGERPRINT.orEmpty(),
        model: String = Build.MODEL.orEmpty(),
        hardware: String = Build.HARDWARE.orEmpty(),
        product: String = Build.PRODUCT.orEmpty(),
        brand: String = Build.BRAND.orEmpty(),
    ): Boolean {
        val fp = fingerprint.lowercase()
        val m = model.lowercase()
        val hw = hardware.lowercase()
        val p = product.lowercase()
        val b = brand.lowercase()
        return fp.startsWith("generic") ||
            fp.contains("emulator") ||
            fp.contains("sdk_gphone") ||
            m.contains("sdk_gphone") ||
            m.contains("emulator") ||
            m.contains("android sdk built for") ||
            hw.contains("goldfish") ||
            hw.contains("ranchu") ||
            p.contains("sdk_gphone") ||
            p.contains("emulator") ||
            p.contains("vbox86p") ||
            (b.startsWith("generic") && m.startsWith("generic"))
    }

    fun formatDisplayName(
        manufacturer: String,
        model: String,
        isEmulator: Boolean,
    ): String {
        val cleanModel = model.trim().ifBlank { "Android" }
        if (isEmulator) {
            return "模拟器 ($cleanModel)"
        }
        val cleanMfg = manufacturer.trim()
        if (cleanMfg.isBlank()) return cleanModel
        return if (cleanModel.startsWith(cleanMfg, ignoreCase = true)) {
            cleanModel
        } else {
            "$cleanMfg $cleanModel"
        }
    }

    fun buildStableIds(
        androidId: String?,
        manufacturer: String,
        model: String,
    ): Pair<String?, String> {
        val cleanAid = androidId?.trim()?.lowercase().orEmpty()
        if (cleanAid.length < 8 || cleanAid == KNOWN_BAD_ANDROID_ID) {
            return null to ""
        }
        val seed = "$cleanAid|${manufacturer.trim().lowercase()}|${model.trim().lowercase()}"
        val shortHash = sha256Short(seed, 16)
        return "android-$shortHash" to "android:$shortHash"
    }

    @SuppressLint("HardwareIds")
    fun resolve(context: Context): DeviceIdentityInfo {
        val androidId = runCatching {
            Settings.Secure.getString(context.contentResolver, Settings.Secure.ANDROID_ID)
        }.getOrNull()
        val manufacturer = Build.MANUFACTURER.orEmpty().trim()
        val model = Build.MODEL.orEmpty().trim()
        val isEmu = detectEmulator()
        val (stableId, fp) = buildStableIds(androidId, manufacturer, model)
        return DeviceIdentityInfo(
            stableDeviceId = stableId,
            fingerprint = fp,
            displayName = formatDisplayName(manufacturer, model, isEmu),
            manufacturer = manufacturer,
            model = model,
            osVersion = "Android ${Build.VERSION.RELEASE.orEmpty()} (API ${Build.VERSION.SDK_INT})".trim(),
            isEmulator = isEmu,
        )
    }
}
