package com.sailzen.app.core.reminder

import android.app.NotificationManager
import com.sailzen.app.core.data.db.CachedSourceConfig
import kotlinx.serialization.encodeToString
import kotlinx.serialization.json.Json
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class NotificationDecisionEngineTest {

    private val json = Json { ignoreUnknownKeys = true }
    private val engine = NotificationDecisionEngine()

    @Test
    fun normalPriority_nonQuiet_reminderChannel() {
        val config = makeConfig()
        val d = engine.decide(config, "normal", false, "test")

        assertEquals(NotificationDecisionEngine.CHANNEL_REMINDER, d.channelId)
        assertEquals(NotificationManager.IMPORTANCE_DEFAULT, d.importance)
        assertTrue(d.shouldNotify)
        assertFalse(d.useAlarm)
        assertFalse(d.useFullScreenIntent)
        assertFalse(d.quietSuppressed)
    }

    @Test
    fun urgentPriority_urgentChannel_fullScreenAndAlarm() {
        val config = makeConfig()
        val d = engine.decide(config, "urgent", false, "test")

        assertEquals(NotificationDecisionEngine.CHANNEL_URGENT, d.channelId)
        assertEquals(NotificationManager.IMPORTANCE_HIGH, d.importance)
        assertTrue(d.shouldNotify)
        assertTrue(d.useAlarm)
        assertTrue(d.useFullScreenIntent)
        assertFalse(d.quietSuppressed)
    }

    @Test
    fun quietHours_normalPriority_downgradesToSilent() {
        val config = makeConfig()
        val d = engine.decide(config, "normal", true, "test")

        assertEquals(NotificationDecisionEngine.CHANNEL_SILENT, d.channelId)
        assertEquals(NotificationManager.IMPORTANCE_LOW, d.importance)
        assertTrue(d.shouldNotify)
        assertFalse(d.useAlarm)
        assertFalse(d.useFullScreenIntent)
        assertTrue(d.quietSuppressed)
    }

    @Test
    fun sourceDisabled_suppressesNotification() {
        val config = makeConfig(enabled = false)
        val d = engine.decide(config, "normal", false, "test")

        assertFalse(d.shouldNotify)
        assertFalse(d.useAlarm)
        assertFalse(d.useFullScreenIntent)
        assertFalse(d.quietSuppressed)
    }

    @Test
    fun allowedPopup_enablesFullScreen() {
        val config = makeConfig(
            allowedChannels = mapOf(
                "notification" to true,
                "popup" to true,
                "alarm" to false,
                "aod" to false,
            )
        )
        val d = engine.decide(config, "normal", false, "test")

        assertTrue(d.useFullScreenIntent)
        assertFalse(d.useAlarm)
        assertTrue(d.shouldNotify)
    }

    private fun makeConfig(
        source: String = "test",
        enabled: Boolean = true,
        allowedChannels: Map<String, Boolean> = mapOf(
            "notification" to true,
            "popup" to false,
            "alarm" to false,
            "aod" to false,
        ),
        quietOverrideEnabled: Boolean? = null,
    ): CachedSourceConfig {
        val quietOverrideJson = quietOverrideEnabled?.let { """{"enabled":$it}""" }
        return CachedSourceConfig(
            source = source,
            sourceType = "test",
            enabled = enabled,
            defaultPriority = "normal",
            allowedChannelsJson = json.encodeToString(allowedChannels),
            quietHoursOverrideJson = quietOverrideJson,
            description = "",
            updatedAt = "2024-01-01T00:00:00",
        )
    }
}
