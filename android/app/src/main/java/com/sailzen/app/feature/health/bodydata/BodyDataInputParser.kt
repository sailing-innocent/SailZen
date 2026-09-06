package com.sailzen.app.feature.health.bodydata

import com.sailzen.app.core.network.dto.BodyMetricDefDto

/**
 * 身体数据录入解析（纯函数，JVM 可测）。
 *
 * 核心语义与三端一致：输入为空 = 本次未测量，不参与 data；
 * 非法数字视为未测量（避免把脏输入传给服务端触发 422）。
 * min/max 校验为软校验，返回可读错误列表供 UI 展示。
 */
object BodyDataInputParser {

    /** 合法自定义指标键：x_ 前缀 + 小写字母/数字/下划线（与后端 validate_metric_key 对齐）。 */
    private val CUSTOM_KEY_PATTERN = Regex("^x_[a-z0-9_]+$")

    fun isValidCustomKey(key: String): Boolean = CUSTOM_KEY_PATTERN.matches(key)

    /** 提取已测量指标：空串 / 空白 / 非法数字一律跳过（未测量）。 */
    fun extractMeasured(values: Map<String, String>): Map<String, Double> =
        values.mapNotNull { (key, raw) ->
            val text = raw.trim()
            if (text.isEmpty()) {
                null
            } else {
                text.toDoubleOrNull()?.let { key to it }
            }
        }.toMap()

    /** 软校验：返回每个越界指标的可读错误（未越界/未知指标不出现）。 */
    fun validateOutOfRange(
        metrics: List<BodyMetricDefDto>,
        measured: Map<String, Double>,
    ): List<String> = measured.mapNotNull { (key, value) ->
        val def = metrics.firstOrNull { it.key == key } ?: return@mapNotNull null
        when {
            def.min != null && value < def.min -> "${def.labelZh} 低于下限 ${def.min}"
            def.max != null && value > def.max -> "${def.labelZh} 高于上限 ${def.max}"
            else -> null
        }
    }
}
