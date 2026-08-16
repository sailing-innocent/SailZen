package com.sailzen.app.core.health

import java.time.LocalDate
import java.time.ZoneId
import org.junit.Assert.assertEquals
import org.junit.Test

class HealthDateUtilsTest {

    @Test
    fun isoDate_formatsCorrectly() {
        assertEquals("2026-08-10", HealthDateUtils.isoDate(LocalDate.of(2026, 8, 10)))
    }

    @Test
    fun epochSeconds_isStartOfDayInLocalZone() {
        val date = LocalDate.of(2026, 8, 10)
        val expected = date.atStartOfDay(ZoneId.systemDefault()).toEpochSecond().toDouble()
        assertEquals(expected, HealthDateUtils.epochSeconds(date), 0.0)
    }

    @Test
    fun epochSecondsEnd_isJustBeforeNextDay() {
        val date = LocalDate.of(2026, 8, 10)
        val nextDayStart = date.plusDays(1).atStartOfDay(ZoneId.systemDefault()).toEpochSecond().toDouble()
        assertEquals(nextDayStart - 1, HealthDateUtils.epochSecondsEnd(date), 0.0)
    }

    @Test
    fun parseTime_parsesColonSeparated() {
        assertEquals(8 to 30, HealthDateUtils.parseTime("08:30"))
        assertEquals(23 to 5, HealthDateUtils.parseTime("23:05"))
    }

    @Test
    fun parseTime_defaultsToZeroForInvalid() {
        assertEquals(0 to 0, HealthDateUtils.parseTime(""))
    }
}
