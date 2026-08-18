package com.sailzen.app.core.network.dto

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable
import kotlinx.serialization.json.JsonElement

/**
 * 与服务端 sail_server.application.dto.reminder 对齐的网络 DTO。
 * 时间字段一律 ISO-8601 字符串（服务端 naive 本地时间），客户端自行解析。
 */

@Serializable
data class ReminderDto(
    val id: Int,
    val type: String,
    val title: String,
    val body: String = "",
    val priority: String = "normal",
    val source: String = "manual",
    val state: String = "PENDING",
    @SerialName("trigger_time") val triggerTime: String,
    @SerialName("expire_after_minutes") val expireAfterMinutes: Int = 240,
    @SerialName("snooze_count") val snoozeCount: Int = 0,
    @SerialName("retry_count") val retryCount: Int = 0,
    @SerialName("next_trigger_time") val nextTriggerTime: String? = null,
    @SerialName("last_delivered_at") val lastDeliveredAt: String? = null,
    val payload: Map<String, JsonElement> = emptyMap(),
    @SerialName("rule_id") val ruleId: Int? = null,
    @SerialName("created_at") val createdAt: String? = null,
    @SerialName("updated_at") val updatedAt: String? = null,
)

@Serializable
data class FeedbackRequest(
    val action: String, // dismiss | snooze | open | resolve
    val option: String? = null, // snooze: 15m | 1h | tonight | tomorrow
    @SerialName("client_event_ts") val clientEventTs: String? = null,
)

@Serializable
data class AckRequest(
    @SerialName("reminder_id") val reminderId: Int,
    @SerialName("device_id") val deviceId: String,
    @SerialName("client_event_ts") val clientEventTs: String? = null,
)

@Serializable
data class DeviceRegisterRequest(
    @SerialName("device_id") val deviceId: String,
    @SerialName("device_name") val deviceName: String,
    @SerialName("app_version") val appVersion: String = "",
    @SerialName("push_token") val pushToken: String? = null,
)

@Serializable
data class DeviceDto(
    val id: Int,
    @SerialName("device_id") val deviceId: String,
    @SerialName("device_name") val deviceName: String = "",
    val platform: String = "android",
    @SerialName("app_version") val appVersion: String = "",
    @SerialName("push_token") val pushToken: String? = null,
    @SerialName("last_seen_at") val lastSeenAt: String? = null,
)

@Serializable
data class SummaryDto(
    val date: String,
    val pending: Int = 0,
    val resolved: Int = 0,
    val ignored: Int = 0,
    val expired: Int = 0,
    @SerialName("delivered_total") val deliveredTotal: Int = 0,
)

@Serializable
data class OkResponse(
    val ok: Boolean = false,
)

/** WebSocket 下行报文：{"type": "reminder.delivered", "data": {...}, "timestamp": "..."} */
@Serializable
data class WsMessage(
    val type: String,
    val data: JsonElement? = null,
    val timestamp: String? = null,
)

@Serializable
data class SourceConfigDto(
    val id: Int? = null,
    val source: String,
    @SerialName("source_type") val sourceType: String = "",
    val enabled: Boolean = true,
    @SerialName("default_priority") val defaultPriority: String = "normal",
    @SerialName("allowed_channels") val allowedChannels: Map<String, Boolean> = emptyMap(),
    @SerialName("quiet_hours_override") val quietHoursOverride: Map<String, JsonElement>? = null,
    val description: String = "",
    @SerialName("created_at") val createdAt: String? = null,
    @SerialName("updated_at") val updatedAt: String? = null,
)
