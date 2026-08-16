package com.sailzen.app.core.health

import java.time.LocalDate
import java.time.LocalDateTime
import java.time.ZoneId
import java.time.format.DateTimeFormatter

/**
 * 健康模块日期/时间戳转换工具（可独立单元测试）。
 */
object HealthDateUtils {

    private val isoFormatter = DateTimeFormatter.ISO_LOCAL_DATE

    fun isoDate(date: LocalDate): String = date.format(isoFormatter)

    fun epochSeconds(date: LocalDate): Double =
        date.atStartOfDay(ZoneId.systemDefault()).toEpochSecond().toDouble()

    fun epochSecondsEnd(date: LocalDate): Double =
        date.plusDays(1).atStartOfDay(ZoneId.systemDefault()).toEpochSecond().toDouble() - 1

    fun timestampFor(date: LocalDate, hour: Int, minute: Int): Double =
        date.atTime(hour, minute).atZone(ZoneId.systemDefault()).toEpochSecond().toDouble()

    fun parseTime(time: String): Pair<Int, Int> {
        val parts = time.split(":")
        val hour = parts.getOrNull(0)?.toIntOrNull() ?: 0
        val minute = parts.getOrNull(1)?.toIntOrNull() ?: 0
        return hour to minute
    }
}
