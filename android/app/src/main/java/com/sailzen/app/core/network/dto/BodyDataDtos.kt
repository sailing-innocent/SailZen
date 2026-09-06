package com.sailzen.app.core.network.dto

import kotlinx.serialization.Serializable

/**
 * 身体数据（Body Data）网络 DTO。
 *
 * 与服务端 sail_server.application.dto.body_data 对齐，字段命名 camelCase。
 * 内置指标清单为后端注册表的 Android 镜像（首屏 fallback），
 * 运行时以 GET /body-data/metrics 动态下发为准。
 *
 * 核心语义：data JSON 中不存在某 key = 本次未测量（与 null/0 严格区分）。
 */

@Serializable
enum class BodyMetricCategory {
    body, intake, fitness
}

@Serializable
data class BodyMetricDefDto(
    val key: String,
    val labelZh: String,
    val labelEn: String,
    val unit: String,
    val category: BodyMetricCategory = BodyMetricCategory.body,
    val precision: Int = 1,
    val min: Double? = null,
    val max: Double? = null,
    val higherIsBetter: Boolean = true,
    val builtin: Boolean = true,
)

/** 内置指标镜像（与后端 BUILTIN_METRICS 保持一致，三端同步修改） */
val BUILTIN_BODY_METRICS: List<BodyMetricDefDto> = listOf(
    BodyMetricDefDto("weight", "体重", "Weight", "kg", BodyMetricCategory.body, 1, 20.0, 300.0, higherIsBetter = false),
    BodyMetricDefDto("height", "身高", "Height", "cm", BodyMetricCategory.body, 1, 100.0, 250.0),
    BodyMetricDefDto("chest", "胸围", "Chest", "cm", BodyMetricCategory.body, 1, 40.0, 200.0),
    BodyMetricDefDto("waist", "腰围", "Waist", "cm", BodyMetricCategory.body, 1, 40.0, 200.0, higherIsBetter = false),
    BodyMetricDefDto("hip", "臀围", "Hip", "cm", BodyMetricCategory.body, 1, 40.0, 250.0, higherIsBetter = false),
    BodyMetricDefDto("body_fat_pct", "体脂率", "Body Fat", "%", BodyMetricCategory.body, 1, 1.0, 70.0, higherIsBetter = false),
    BodyMetricDefDto("muscle_mass", "肌肉量", "Muscle Mass", "kg", BodyMetricCategory.body, 1, 5.0, 150.0),
    BodyMetricDefDto("protein_powder", "蛋白粉", "Protein Powder", "g", BodyMetricCategory.intake, 0, 0.0, 300.0),
    BodyMetricDefDto("creatine", "肌酸", "Creatine", "g", BodyMetricCategory.intake, 1, 0.0, 50.0),
    BodyMetricDefDto("water", "饮水量", "Water", "ml", BodyMetricCategory.intake, 0, 0.0, 8000.0),
    BodyMetricDefDto("caffeine", "咖啡因", "Caffeine", "mg", BodyMetricCategory.intake, 0, 0.0, 1000.0, higherIsBetter = false),
)

@Serializable
data class BodyDataDto(
    val id: Int,
    val htime: Double? = null,
    /** 本次实际测量/记录的指标集合；未测量 key 一律不出现 */
    val data: Map<String, Double> = emptyMap(),
    val tag: String = "raw",
    val description: String = "",
    val source: String = "manual",
    val weightId: Int? = null,
)

@Serializable
data class BodyDataCreateRequest(
    val htime: Double? = null,
    val data: Map<String, Double>,
    val tag: String = "raw",
    val description: String = "",
)

@Serializable
data class BodyDataUpdateRequest(
    val htime: Double? = null,
    val data: Map<String, Double>? = null,
    val tag: String? = null,
    val description: String? = null,
)

@Serializable
data class BodyDataSeriesPointDto(
    val id: Int,
    val htime: Double,
    val value: Double,
)

@Serializable
data class BodyDataSeriesResponse(
    val metric: String,
    val unit: String = "",
    val points: List<BodyDataSeriesPointDto> = emptyList(),
)

/** 删除响应：deleted 表示是否实际删除（记录不存在时为 false）。 */
@Serializable
data class BodyDataDeleteResponse(
    val deleted: Boolean,
    val id: Int,
)
