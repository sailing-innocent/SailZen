package com.sailzen.app.core.network.dto

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable
import kotlinx.serialization.json.JsonArray
import kotlinx.serialization.json.JsonElement
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive

/**
 * 与服务端 sail_server.application.dto.tick 对齐的网络 DTO。
 * 支持：
 * - SailTick 渐进式提问票据（pending -> replied -> resolved / snoozed）
 * - 用户主动静默餐饮/状态上报（无需 AI 即时回复）
 * - 每日睡前体重与健康日报
 * - 健康页 AI 教练聚合摘要
 */

@Serializable
data class TickTicketDto(
    val id: Int,
    @SerialName("tick_id") val tickId: String = "",
    val type: String = "question",
    val topic: String = "",
    val title: String,
    val body: String = "",
    val meta: JsonObject = JsonObject(emptyMap()),
    val status: String = "pending",
    @SerialName("expected_reply_by") val expectedReplyBy: String? = null,
    @SerialName("replied_at") val repliedAt: String? = null,
    val reply: String? = null,
    @SerialName("resolved_at") val resolvedAt: String? = null,
    val resolution: String? = null,
    @SerialName("fallback_assumption") val fallbackAssumption: String = "",
    val priority: String = "normal",
    val channel: String = "mobile",
    @SerialName("created_at") val createdAt: String = "",
    @SerialName("updated_at") val updatedAt: String = "",
) {
    /** 提取票据 meta 中的 quick_replies 列表（如有）。 */
    fun quickReplies(): List<String> {
        val arr = meta["quick_replies"] as? JsonArray ?: return emptyList()
        return arr.mapNotNull { (it as? JsonPrimitive)?.content }.filter { it.isNotBlank() }
    }
}

@Serializable
data class TicketReplyRequest(
    val reply: String,
)

@Serializable
data class TicketResolveRequest(
    val resolution: String = "",
)

@Serializable
data class TicketSnoozeRequest(
    val hours: Int = 24,
)

@Serializable
data class TickMessageCreateRequest(
    val direction: String = "user_to_agent",
    val category: String = "diet",
    val content: String,
    val meta: Map<String, JsonElement> = emptyMap(),
    @SerialName("source_channel") val sourceChannel: String = "android",
    @SerialName("auto_log_diet") val autoLogDiet: Boolean = true,
)

@Serializable
data class TickMessageDto(
    val id: Int,
    val direction: String = "user_to_agent",
    val category: String = "diet",
    val content: String,
    val meta: JsonObject = JsonObject(emptyMap()),
    @SerialName("source_channel") val sourceChannel: String = "android",
    val status: String = "unread",
    @SerialName("ingested_by_tick_id") val ingestedByTickId: String? = null,
    @SerialName("created_at") val createdAt: String = "",
    @SerialName("ingested_at") val ingestedAt: String? = null,
)

@Serializable
data class DailyReportDto(
    val id: Int,
    @SerialName("report_date") val reportDate: String,
    @SerialName("tick_id") val tickId: String = "",
    val title: String,
    val summary: String = "",
    @SerialName("body_markdown") val bodyMarkdown: String = "",
    @SerialName("weight_snapshot") val weightSnapshot: JsonObject = JsonObject(emptyMap()),
    @SerialName("diet_summary") val dietSummary: JsonObject = JsonObject(emptyMap()),
    @SerialName("plan_update") val planUpdate: JsonObject = JsonObject(emptyMap()),
    @SerialName("tomorrow_focus") val tomorrowFocus: List<String> = emptyList(),
    val pushed: Boolean = false,
    @SerialName("created_at") val createdAt: String = "",
    @SerialName("updated_at") val updatedAt: String = "",
)

@Serializable
data class HealthCoachSummaryDto(
    @SerialName("active_plan") val activePlan: WeightPlanDto? = null,
    @SerialName("plan_progress") val planProgress: JsonObject? = null,
    @SerialName("latest_report") val latestReport: DailyReportDto? = null,
    @SerialName("pending_tickets") val pendingTickets: List<TickTicketDto> = emptyList(),
    @SerialName("pending_ticket_count") val pendingTicketCount: Int = 0,
    @SerialName("today_messages") val todayMessages: List<TickMessageDto> = emptyList(),
)
