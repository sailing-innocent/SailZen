package com.sailzen.app.core.network.dto

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable
import kotlinx.serialization.json.JsonElement
import kotlinx.serialization.json.JsonObject

@Serializable
data class QuietHoursDto(
    val enabled: Boolean = true,
    val start: String = "23:00",
    val end: String = "08:00",
)

@Serializable
data class UserProfileDto(
    val id: Int = 1,
    val slug: String = "owner",
    @SerialName("display_name") val displayName: String = "SailZen Owner",
    @SerialName("avatar_url") val avatarUrl: String = "",
    val role: String = "owner",
    val status: String = "active",
    @SerialName("is_default") val isDefault: Boolean = true,
    val timezone: String = "Asia/Shanghai",
    val locale: String = "zh-CN",
    @SerialName("quiet_hours") val quietHours: QuietHoursDto = QuietHoursDto(),
    @SerialName("notification_prefs") val notificationPrefs: Map<String, JsonElement> = emptyMap(),
    @SerialName("health_profile") val healthProfile: Map<String, JsonElement> = emptyMap(),
    val preferences: Map<String, JsonElement> = emptyMap(),
    @SerialName("updated_at") val updatedAt: String? = null,
)

@Serializable
data class UserProfileUpdateRequest(
    @SerialName("display_name") val displayName: String? = null,
    @SerialName("quiet_hours") val quietHours: QuietHoursDto? = null,
    @SerialName("notification_prefs") val notificationPrefs: Map<String, JsonElement>? = null,
)

@Serializable
data class UserDeviceRegisterRequest(
    @SerialName("device_id") val deviceId: String,
    @SerialName("device_name") val deviceName: String = "",
    val platform: String = "android",
    @SerialName("client_type") val clientType: String = "android",
    @SerialName("app_version") val appVersion: String = "",
    @SerialName("push_token") val pushToken: String? = null,
    val fingerprint: String = "",
    @SerialName("is_emulator") val isEmulator: Boolean = false,
    val capabilities: Map<String, JsonElement> = emptyMap(),
)

@Serializable
data class UserDeviceDto(
    val id: Int = 0,
    @SerialName("user_id") val userId: Int = 1,
    @SerialName("device_id") val deviceId: String,
    @SerialName("device_name") val deviceName: String = "",
    val platform: String = "android",
    @SerialName("client_type") val clientType: String = "android",
    @SerialName("app_version") val appVersion: String = "",
    @SerialName("is_active") val isActive: Boolean = true,
    @SerialName("is_online") val isOnline: Boolean = false,
    @SerialName("last_sync_seq") val lastSyncSeq: Long = 0L,
    @SerialName("last_seen_at") val lastSeenAt: String? = null,
)

@Serializable
data class UserBootstrapDto(
    @SerialName("auth_mode") val authMode: String = "single_user_auto",
    @SerialName("requires_login") val requiresLogin: Boolean = false,
    val user: UserProfileDto = UserProfileDto(),
    @SerialName("unread_inbox_count") val unreadInboxCount: Int = 0,
    @SerialName("active_inbox_count") val activeInboxCount: Int = 0,
    @SerialName("latest_sync_seq") val latestSyncSeq: Long = 0L,
    @SerialName("online_device_count") val onlineDeviceCount: Int = 0,
    val devices: List<UserDeviceDto> = emptyList(),
)

@Serializable
data class InboxItemDto(
    val id: Int,
    @SerialName("user_id") val userId: Int = 1,
    @SerialName("sync_seq") val syncSeq: Long = 0L,
    @SerialName("source_domain") val sourceDomain: String = "system",
    @SerialName("item_kind") val itemKind: String = "notice",
    val topic: String = "",
    @SerialName("dedup_key") val dedupKey: String = "",
    @SerialName("ref_type") val refType: String = "",
    @SerialName("ref_id") val refId: Int? = null,
    @SerialName("reminder_id") val reminderId: Int? = null,
    @SerialName("ticket_id") val ticketId: Int? = null,
    val title: String,
    val body: String = "",
    val priority: String = "normal",
    val status: String = "delivered",
    @SerialName("is_read") val isRead: Boolean = false,
    @SerialName("action_schema") val actionSchema: JsonObject = JsonObject(emptyMap()),
    @SerialName("reply_text") val replyText: String? = null,
    @SerialName("resolution_source") val resolutionSource: String = "",
    @SerialName("resolution_summary") val resolutionSummary: String = "",
    @SerialName("trigger_at") val triggerAt: String? = null,
    @SerialName("snooze_until") val snoozeUntil: String? = null,
    @SerialName("resolved_at") val resolvedAt: String? = null,
    @SerialName("created_at") val createdAt: String? = null,
    @SerialName("updated_at") val updatedAt: String? = null,
)

@Serializable
data class InboxSyncResponseDto(
    @SerialName("latest_seq") val latestSeq: Long = 0L,
    @SerialName("unread_count") val unreadCount: Int = 0,
    @SerialName("active_count") val activeCount: Int = 0,
    @SerialName("active_ids") val activeIds: List<Int> = emptyList(),
    val changes: List<InboxItemDto> = emptyList(),
)

@Serializable
data class InboxSummaryDto(
    val date: String = "",
    val active: Int = 0,
    val unread: Int = 0,
    val answered: Int = 0,
    val resolved: Int = 0,
    val dismissed: Int = 0,
    val expired: Int = 0,
)

@Serializable
data class InboxReplyRequest(
    val reply: String,
    val source: String = "android:inbox",
)

@Serializable
data class InboxResolveRequest(
    @SerialName("resolution_summary") val resolutionSummary: String = "",
    @SerialName("resolution_source") val resolutionSource: String = "android:inbox",
)

@Serializable
data class InboxSnoozeRequest(
    val option: String? = null,
    val hours: Int? = null,
)

@Serializable
data class InboxDismissRequest(
    val reason: String = "",
)

@Serializable
data class WsInboxResolvedDto(
    @SerialName("inbox_item_id") val inboxItemId: Int = 0,
    @SerialName("reminder_id") val reminderId: Int? = null,
    @SerialName("ticket_id") val ticketId: Int? = null,
    val status: String = "resolved",
    @SerialName("sync_seq") val syncSeq: Long = 0L,
    @SerialName("resolution_source") val resolutionSource: String = "",
    @SerialName("resolution_summary") val resolutionSummary: String = "",
    @SerialName("reply_text") val replyText: String? = null,
)
