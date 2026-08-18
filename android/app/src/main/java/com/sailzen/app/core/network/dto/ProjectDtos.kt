package com.sailzen.app.core.network.dto

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable

@Serializable
data class DeleteResponse(
    val id: Int,
    val status: String,
    val message: String? = null,
)

/**
 * 与服务端 sail_server.application.dto.project 以及 site lib/data/project.ts 对齐的网络 DTO。
 * 时间字段统一使用秒级 Unix 时间戳（Double）。
 */

object MissionState {
    const val PENDING = 0
    const val READY = 1
    const val DOING = 2
    const val DONE = 3
    const val CANCELED = 4
}

@Serializable
data class ProjectDto(
    val id: Int,
    val name: String,
    val description: String = "",
    val state: Int? = null,
    @SerialName("start_time_qbw") val startTimeQbw: Int? = null,
    @SerialName("end_time_qbw") val endTimeQbw: Int? = null,
    @SerialName("timespan_id") val timespanId: Int? = null,
    val ctime: Double? = null,
    val mtime: Double? = null,
)

@Serializable
data class ProjectCreateRequest(
    val name: String,
    val description: String = "",
    @SerialName("start_time_qbw") val startTimeQbw: Int? = null,
    @SerialName("end_time_qbw") val endTimeQbw: Int? = null,
    @SerialName("timespan_id") val timespanId: Int? = null,
)

@Serializable
data class ProjectUpdateRequest(
    val name: String? = null,
    val description: String? = null,
    val state: Int? = null,
    @SerialName("start_time_qbw") val startTimeQbw: Int? = null,
    @SerialName("end_time_qbw") val endTimeQbw: Int? = null,
    @SerialName("timespan_id") val timespanId: Int? = null,
)

@Serializable
data class MissionDto(
    val id: Int,
    val name: String,
    val description: String = "",
    @SerialName("parent_id") val parentId: Int? = null,
    @SerialName("project_id") val projectId: Int? = null,
    val state: Int? = null,
    val ddl: Double? = null,
    @SerialName("planned_minutes") val plannedMinutes: Int? = null,
    @SerialName("actual_minutes") val actualMinutes: Int? = null,
    @SerialName("energy_cost") val energyCost: Int? = null,
    @SerialName("day_id") val dayId: Int? = null,
    @SerialName("milestone_id") val milestoneId: Int? = null,
    @SerialName("health_constraint") val healthConstraint: String = "normal",
    val lft: Int? = null,
    val rgt: Int? = null,
    @SerialName("tree_id") val treeId: Int? = null,
    val ctime: Double? = null,
    val mtime: Double? = null,
)

@Serializable
data class MissionCreateRequest(
    val name: String,
    val description: String = "",
    @SerialName("parent_id") val parentId: Int? = null,
    @SerialName("project_id") val projectId: Int? = null,
    val ddl: Double? = null,
    @SerialName("planned_minutes") val plannedMinutes: Int? = null,
    @SerialName("actual_minutes") val actualMinutes: Int? = null,
    @SerialName("energy_cost") val energyCost: Int? = null,
    @SerialName("day_id") val dayId: Int? = null,
    @SerialName("milestone_id") val milestoneId: Int? = null,
    @SerialName("health_constraint") val healthConstraint: String = "normal",
)

@Serializable
data class MissionUpdateRequest(
    val name: String? = null,
    val description: String? = null,
    @SerialName("parent_id") val parentId: Int? = null,
    @SerialName("project_id") val projectId: Int? = null,
    val state: Int? = null,
    val ddl: Double? = null,
    @SerialName("planned_minutes") val plannedMinutes: Int? = null,
    @SerialName("actual_minutes") val actualMinutes: Int? = null,
    @SerialName("energy_cost") val energyCost: Int? = null,
    @SerialName("day_id") val dayId: Int? = null,
    @SerialName("milestone_id") val milestoneId: Int? = null,
    @SerialName("health_constraint") val healthConstraint: String? = null,
)
