package com.sailzen.app.core.network.dto

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable
import kotlinx.serialization.json.JsonElement
import kotlinx.serialization.json.JsonObject

/**
 * 与服务端 sail_server.application.dto.rhythm 对齐的网络 DTO。
 * 时间字段一律 ISO-8601 字符串（服务端 naive 本地时间），客户端自行解析。
 */

@Serializable
enum class InfoCollectionType {
    weight, meal, exercise, medication, sleep, mood
}

@Serializable
data class AffairDto(
    val id: Int,
    val title: String,
    val description: String = "",
    val domain: String? = null, // life | work | career
    val kind: String, // base_rhythm|precept|habit|fixed_plan|task_oneoff|task_maintenance|venture|buffer|generic
    @SerialName("kind_meta") val kindMeta: JsonObject = JsonObject(emptyMap()),
    val state: String, // INBOX|PLANNED|SCHEDULED|DOING|DONE|DEFERRED|CANCELED|ACTIVE|PAUSED|ARCHIVED
    val importance: Int = 3,
    @SerialName("urgency_ddl") val urgencyDdl: String? = null,
    @SerialName("energy_cost") val energyCost: Int = 10,
    @SerialName("money_cost") val moneyCost: Double = 0.0,
    @SerialName("est_minutes") val estMinutes: Int = 30,
    @SerialName("window_start") val windowStart: String? = null,
    @SerialName("window_end") val windowEnd: String? = null,
    @SerialName("fallback_plan") val fallbackPlan: String = "",
    @SerialName("parent_id") val parentId: Int? = null,
    @SerialName("info_collection_type") val infoCollectionType: String? = null,
    @SerialName("ai_hint") val aiHint: JsonObject = JsonObject(emptyMap()),
    val score: Double = 0.0,
)

@Serializable
data class AffairListResponse(
    val affairs: List<AffairDto> = emptyList(),
    val total: Int = 0,
)

@Serializable
data class AffairCreateRequest(
    val title: String,
    val kind: String = "generic",
    val domain: String? = null,
    val description: String = "",
    @SerialName("kind_meta") val kindMeta: JsonObject = JsonObject(emptyMap()),
    val importance: Int = 3,
    @SerialName("urgency_ddl") val urgencyDdl: String? = null,
    @SerialName("energy_cost") val energyCost: Int = 10,
    @SerialName("est_minutes") val estMinutes: Int = 30,
    @SerialName("parent_id") val parentId: Int? = null,
)

@Serializable
data class AffairUpdateRequest(
    val title: String? = null,
    val description: String? = null,
    val domain: String? = null,
    val kind: String? = null,
    @SerialName("kind_meta") val kindMeta: JsonObject? = null,
    val importance: Int? = null,
    @SerialName("urgency_ddl") val urgencyDdl: String? = null,
    @SerialName("energy_cost") val energyCost: Int? = null,
    @SerialName("est_minutes") val estMinutes: Int? = null,
    @SerialName("parent_id") val parentId: Int? = null,
)

@Serializable
data class VentureMilestoneRequest(
    val title: String,
    @SerialName("urgency_ddl") val urgencyDdl: String? = null,
    @SerialName("est_minutes") val estMinutes: Int? = null,
    val description: String = "",
)

@Serializable
data class DeleteResponse(
    val id: Int,
    val status: String,
    val message: String? = null,
)

@Serializable
data class AffairStateRequest(
    val action: String, // confirm|defer|cancel|start|finish|pause|resume|archive|graduate|dismiss|replan
    @SerialName("defer_to") val deferTo: String? = null,
    @SerialName("defer_end") val deferEnd: String? = null,
    val force: Boolean = false,
)

@Serializable
data class ConfirmHintRequest(
    val accept: Boolean,
    val overrides: JsonObject? = null,
)

@Serializable
data class TimeBlockDto(
    val id: Int,
    @SerialName("day_id") val dayId: Int,
    @SerialName("affair_id") val affairId: Int? = null,
    @SerialName("block_type") val blockType: String,
    @SerialName("start_time") val startTime: String,
    @SerialName("end_time") val endTime: String,
    val status: String = "PLANNED",
    val pinned: Boolean = false,
    @SerialName("plan_version") val planVersion: Int = 1,
    val ref: JsonObject = JsonObject(emptyMap()),
    @SerialName("affair_title") val affairTitle: String? = null,
    @SerialName("affair_kind") val affairKind: String? = null,
    @SerialName("energy_cost") val energyCost: Int = 0,
)

@Serializable
data class DomainMinutesDto(
    val life: Int = 0,
    val work: Int = 0,
    val career: Int = 0,
)

@Serializable
data class DayTimelineDto(
    val date: String,
    @SerialName("day_id") val dayId: Int,
    @SerialName("plan_version") val planVersion: Int = 0,
    @SerialName("ai_rationale") val aiRationale: String = "",
    @SerialName("ai_updated_at") val aiUpdatedAt: String? = null,
    val blocks: List<TimeBlockDto> = emptyList(),
    @SerialName("completed_minutes") val completedMinutes: Int = 0,
    @SerialName("planned_minutes") val plannedMinutes: Int = 0,
    @SerialName("domain_minutes") val domainMinutes: DomainMinutesDto = DomainMinutesDto(),
    val checkins: CheckinTodayDto? = null,
)

@Serializable
data class BlockStatusRequest(
    val status: String, // DONE | SKIPPED | DOING | PLANNED
)

@Serializable
data class BlockMoveRequest(
    @SerialName("start_time") val startTime: String,
    @SerialName("end_time") val endTime: String,
)

@Serializable
data class OccupancyCreateRequest(
    val date: String,
    val start: String? = null,
    val end: String? = null,
    @SerialName("whole_day") val wholeDay: Boolean = false,
    @SerialName("occupancy_type") val occupancyType: String = "meeting",
    val label: String = "",
    val note: String = "",
)

@Serializable
data class OccupancyDto(
    val id: Int,
    val date: String,
    val start: String? = null,
    val end: String? = null,
    @SerialName("whole_day") val wholeDay: Boolean = false,
    @SerialName("occupancy_type") val occupancyType: String = "other",
    val label: String = "",
    val note: String = "",
)

@Serializable
data class OccupancyListResponse(
    val date: String,
    val occupancies: List<OccupancyDto> = emptyList(),
)

@Serializable
data class CheckinRequest(
    @SerialName("affair_id") val affairId: Int,
    val result: String, // kept|violated|exempt|done|missed
    @SerialName("log_date") val logDate: String? = null,
    val note: String = "",
)

@Serializable
data class CheckinLogDto(
    val id: Int,
    @SerialName("affair_id") val affairId: Int,
    @SerialName("log_date") val logDate: String,
    @SerialName("cycle_key") val cycleKey: String,
    val result: String,
    val note: String = "",
    val source: String = "manual",
)

@Serializable
data class CheckinTodayItemDto(
    val affair: AffairDto,
    @SerialName("done_today") val doneToday: Boolean = false,
    @SerialName("last_result") val lastResult: String? = null,
    @SerialName("week_done_count") val weekDoneCount: Int = 0,
    @SerialName("week_target") val weekTarget: Int = 0,
)

@Serializable
data class CheckinTodayDto(
    val date: String,
    val precepts: List<CheckinTodayItemDto> = emptyList(),
    val habits: List<CheckinTodayItemDto> = emptyList(),
)

@Serializable
data class VentureProgressDto(
    @SerialName("affair_id") val affairId: Int,
    val title: String,
    val description: String = "",
    val state: String = "ACTIVE",
    @SerialName("target_date") val targetDate: String? = null,
    @SerialName("days_left") val daysLeft: Int? = null,
    @SerialName("weeks_left") val weeksLeft: Double? = null,
    @SerialName("weekly_budget_hours") val weeklyBudgetHours: Double = 0.0,
    @SerialName("week_consumed_hours") val weekConsumedHours: Double = 0.0,
    @SerialName("recent_14d_hours") val recent14dHours: Double = 0.0,
    @SerialName("total_done_hours") val totalDoneHours: Double = 0.0,
    @SerialName("total_est_hours") val totalEstHours: Double = 0.0,
    val milestones: List<AffairDto> = emptyList(),
    @SerialName("completion_ratio") val completionRatio: Double = 0.0,
)

@Serializable
data class RhythmDashboardDto(
    val date: String,
    val timeline: DayTimelineDto,
    val projects: List<VentureProgressDto> = emptyList(),
    @SerialName("focus_affairs") val focusAffairs: List<AffairDto> = emptyList(),
    @SerialName("overdue_affairs") val overdueAffairs: List<AffairDto> = emptyList(),
    @SerialName("inbox_affairs") val inboxAffairs: List<AffairDto> = emptyList(),
    val occupancies: List<OccupancyDto> = emptyList(),
    @SerialName("today_checkins") val todayCheckins: CheckinTodayDto = CheckinTodayDto(date = ""),
    val degraded: List<String> = emptyList(),
)

@Serializable
data class HealthSignalItemDto(
    @SerialName("signal_type") val signalType: String,
    @SerialName("ref_id") val refId: Int,
    @SerialName("value_json") val valueJson: JsonObject = JsonObject(emptyMap()),
    val htime: String? = null,
)

@Serializable
data class RhythmDayViewDto(
    val date: String,
    @SerialName("day_id") val dayId: Int,
    @SerialName("plan_version") val planVersion: Int = 0,
    @SerialName("ai_rationale") val aiRationale: String = "",
    val blocks: List<TimeBlockDto> = emptyList(),
    @SerialName("domain_minutes") val domainMinutes: DomainMinutesDto = DomainMinutesDto(),
    val checkins: CheckinTodayDto? = null,
    @SerialName("health_signals") val healthSignals: List<HealthSignalItemDto> = emptyList(),
    val insights: List<String> = emptyList(),
)

@Serializable
data class HealthCheckinRequest(
    @SerialName("collection_type") val collectionType: InfoCollectionType,
    @SerialName("log_date") val logDate: String? = null,
    val payload: JsonObject = JsonObject(emptyMap()),
    val note: String = "",
)

@Serializable
data class HealthCheckinResponse(
    val id: Int,
    @SerialName("collection_type") val collectionType: String,
    @SerialName("log_date") val logDate: String,
    @SerialName("ref_id") val refId: Int? = null,
    @SerialName("affair_id") val affairId: Int? = null,
    val note: String = "",
    @SerialName("created_at") val createdAt: String? = null,
)

/** 快速捕获磁贴等场景的可选 kind 列表（与服务端九类对齐） */
val CAPTURE_KINDS = listOf(
    "generic", "habit", "precept", "task_oneoff", "fixed_plan",
    "task_maintenance", "venture", "base_rhythm",
)

/** 事务状态常量（与服务端 AffairState 对齐） */
object AffairStates {
    const val INBOX = "INBOX"
    const val PLANNED = "PLANNED"
    const val SCHEDULED = "SCHEDULED"
    const val DOING = "DOING"
    const val DONE = "DONE"
    const val DEFERRED = "DEFERRED"
    const val CANCELED = "CANCELED"
    const val ACTIVE = "ACTIVE"
    const val PAUSED = "PAUSED"
    const val ARCHIVED = "ARCHIVED"

    val TERMINAL = setOf(DONE, CANCELED, ARCHIVED, "COMPLETED")
}

/** 状态转移动作（与服务端 AffairAction 对齐） */
object AffairActions {
    const val CONFIRM = "confirm"
    const val START = "start"
    const val FINISH = "finish"
    const val CANCEL = "cancel"
    const val DEFER = "defer"
    const val REPLAN = "replan"
    const val PAUSE = "pause"
    const val RESUME = "resume"
    const val ARCHIVE = "archive"
    const val GRADUATE = "graduate"
}

/** 长期流 kind（状态走 ACTIVE/PAUSED/ARCHIVED） */
val LONGTERM_KINDS = setOf(
    "base_rhythm", "precept", "habit", "task_maintenance", "venture", "async_callback",
)

/** state → 中文标签 */
fun stateLabel(state: String): String = when (state) {
    "INBOX" -> "待分拣"
    "PLANNED" -> "已规划"
    "SCHEDULED" -> "已排程"
    "DOING" -> "进行中"
    "DONE" -> "已完成"
    "DEFERRED" -> "已推迟"
    "CANCELED" -> "已取消"
    "ACTIVE" -> "进行中"
    "PAUSED" -> "已暂停"
    "ARCHIVED" -> "已归档"
    else -> state
}

/** domain → 中文标签 */
fun domainLabel(domain: String?): String = when (domain) {
    "life" -> "生活"
    "work" -> "工作"
    "career" -> "事业"
    else -> "未分域"
}

/** kind → 中文标签（UI 展示） */
fun kindLabel(kind: String): String = when (kind) {
    "base_rhythm" -> "基础节奏"
    "precept" -> "戒律"
    "habit" -> "习惯"
    "fixed_plan" -> "刚性规划"
    "task_oneoff" -> "工作任务"
    "task_maintenance" -> "维护任务"
    "venture" -> "长期事业"
    "buffer" -> "缓冲"
    else -> "未分类"
}
