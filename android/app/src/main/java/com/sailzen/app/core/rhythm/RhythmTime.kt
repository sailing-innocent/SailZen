package com.sailzen.app.core.rhythm

import java.time.Duration
import java.time.LocalDate
import java.time.LocalDateTime
import java.time.format.DateTimeFormatter

/**
 * 服务端 rhythm 时间字段一律为 naive 本地时间 ISO-8601 字符串。
 * 这里做容错解析（允许带 Z / 时区偏移 / 毫秒），并统一输出秒级 ISO。
 */
object RhythmTime {

    private val OUTPUT: DateTimeFormatter = DateTimeFormatter.ofPattern("yyyy-MM-dd'T'HH:mm:ss")

    fun parse(raw: String?): LocalDateTime? {
        val text = raw?.trim().orEmpty()
        if (text.isEmpty()) return null
        val normalized = text.removeSuffix("Z").substringBefore('+').let {
            // 处理 "2026-08-18T09:00:00-05:00" 的负偏移（日期部分含 '-'，只截时间段之后的）
            val timeIndex = it.indexOf('T')
            if (timeIndex < 0) it else it.substring(0, timeIndex) + it.substring(timeIndex).substringBefore('-')
        }
        return runCatching { LocalDateTime.parse(normalized) }.getOrNull()
            ?: runCatching { LocalDate.parse(normalized).atStartOfDay() }.getOrNull()
    }

    fun format(value: LocalDateTime): String = value.format(OUTPUT)

    /**
     * 距离截止还有多少**整小时**（截断）；无 ddl 返回 Long.MAX_VALUE，已逾期返回负数。
     * 用整小时而非毫秒级 Double：排序比较时对同一 ddl 的多次求值不会
     * 因微秒级 now() 噪声翻转顺序（ comparator 稳定性缺陷修复）。
     */
    fun hoursUntil(raw: String?, now: LocalDateTime = LocalDateTime.now()): Long {
        val target = parse(raw) ?: return Long.MAX_VALUE
        return Duration.between(now, target).toHours()
    }
}
