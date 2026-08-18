package com.sailzen.app.core.reminder

import android.app.NotificationManager
import com.sailzen.app.core.data.SettingsManager
import com.sailzen.app.core.data.db.CachedSourceConfig
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.booleanOrNull
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive

/**
 * 根据提醒来源配置、全局安静时段与提醒优先级，决定通知通道、重要性及呈现方式。
 */
class NotificationDecisionEngine(private val settings: SettingsManager? = null) {

    data class Decision(
        val channelId: String,
        val importance: Int, // NotificationManager.IMPORTANCE_*
        val useFullScreenIntent: Boolean,
        val useAlarm: Boolean,
        val useAod: Boolean,
        val shouldNotify: Boolean,
        val quietSuppressed: Boolean,
    )

    companion object {
        const val CHANNEL_URGENT = "urgent"
        const val CHANNEL_REMINDER = "reminder"
        const val CHANNEL_SILENT = "silent"
        const val CHANNEL_SERVICE = "service"

        private val DEFAULT_ALLOWED_CHANNELS = mapOf(
            "notification" to true,
            "popup" to true,
            "alarm" to true,
            "aod" to true,
        )
    }

    private val json = Json { ignoreUnknownKeys = true }

    fun decide(
        sourceConfig: CachedSourceConfig?,
        priority: String,
        isQuiet: Boolean,
        source: String,
    ): Decision {
        val allowed = parseAllowedChannels(sourceConfig)
        val quietOverride = isQuietHoursOverrideEnabled(sourceConfig)

        // 来源被显式禁用 -> 完全抑制
        if (sourceConfig != null && !sourceConfig.enabled) {
            return Decision(
                channelId = CHANNEL_SILENT,
                importance = NotificationManager.IMPORTANCE_LOW,
                useFullScreenIntent = false,
                useAlarm = false,
                useAod = false,
                shouldNotify = false,
                quietSuppressed = false,
            )
        }

        val isUrgent = priority == "urgent"
        var channelId: String
        var importance: Int
        var useFullScreenIntent = false
        var useAlarm = false

        when (priority) {
            "urgent" -> {
                channelId = CHANNEL_URGENT
                importance = NotificationManager.IMPORTANCE_HIGH
                useFullScreenIntent = true
                useAlarm = true
            }
            "high" -> {
                channelId = CHANNEL_REMINDER
                importance = NotificationManager.IMPORTANCE_DEFAULT
            }
            "low" -> {
                channelId = CHANNEL_SILENT
                importance = NotificationManager.IMPORTANCE_LOW
            }
            else -> {
                channelId = CHANNEL_REMINDER
                importance = NotificationManager.IMPORTANCE_DEFAULT
            }
        }

        var shouldNotify = allowed["notification"] != false

        // allowed_channels 覆盖：popup / alarm 可提升高/普通提醒为强提醒
        if (allowed["popup"] == true) {
            useFullScreenIntent = true
        }
        if (allowed["alarm"] == true) {
            useAlarm = true
        }

        val useAod = allowed["aod"] == true

        // 安静时段降级（urgent 不降；来源配置开启 override 时不降）
        val quietActive = isQuiet && !isUrgent && !quietOverride
        if (quietActive) {
            channelId = CHANNEL_SILENT
            importance = NotificationManager.IMPORTANCE_LOW
            useFullScreenIntent = false
            useAlarm = false
        }

        val quietSuppressed = isQuiet && !isUrgent && !quietOverride && shouldNotify

        return Decision(
            channelId = channelId,
            importance = importance,
            useFullScreenIntent = useFullScreenIntent,
            useAlarm = useAlarm,
            useAod = useAod,
            shouldNotify = shouldNotify,
            quietSuppressed = quietSuppressed,
        )
    }

    private fun parseAllowedChannels(sourceConfig: CachedSourceConfig?): Map<String, Boolean> {
        if (sourceConfig == null) return DEFAULT_ALLOWED_CHANNELS
        val raw = sourceConfig.allowedChannelsJson
        if (raw.isBlank()) return DEFAULT_ALLOWED_CHANNELS
        return try {
            json.decodeFromString<Map<String, Boolean>>(raw)
        } catch (_: Exception) {
            DEFAULT_ALLOWED_CHANNELS
        }
    }

    private fun isQuietHoursOverrideEnabled(sourceConfig: CachedSourceConfig?): Boolean {
        val raw = sourceConfig?.quietHoursOverrideJson ?: return false
        if (raw.isBlank()) return false
        return try {
            json.parseToJsonElement(raw)
                .jsonObject["enabled"]
                ?.jsonPrimitive
                ?.booleanOrNull ?: false
        } catch (_: Exception) {
            false
        }
    }
}
