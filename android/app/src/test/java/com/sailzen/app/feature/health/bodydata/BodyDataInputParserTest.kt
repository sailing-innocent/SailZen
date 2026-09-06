package com.sailzen.app.feature.health.bodydata

import com.sailzen.app.core.network.dto.BUILTIN_BODY_METRICS
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * 录入解析语义（纯函数层）：空/非法 = 未测量；min/max 软校验；x_ 自定义键校验。
 */
class BodyDataInputParserTest {

    @Test
    fun extractMeasured_blankInputsAreNotMeasured() {
        val data = BodyDataInputParser.extractMeasured(
            mapOf("weight" to "70.5", "water" to "", "waist" to "   ", "caffeine" to "\t"),
        )
        assertEquals(mapOf("weight" to 70.5), data)
    }

    @Test
    fun extractMeasured_invalidNumbersAreNotMeasured() {
        val data = BodyDataInputParser.extractMeasured(
            mapOf("weight" to "abc", "water" to "12x", "waist" to "80.5"),
        )
        assertEquals(mapOf("waist" to 80.5), data)
    }

    @Test
    fun extractMeasured_trimsAndParses() {
        val data = BodyDataInputParser.extractMeasured(
            mapOf("weight" to "  70.5  ", "creatine" to "3"),
        )
        assertEquals(70.5, data["weight"]!!, 0.0)
        assertEquals(3.0, data["creatine"]!!, 0.0)
    }

    @Test
    fun extractMeasured_emptyMapGivesEmptyData() {
        assertTrue(BodyDataInputParser.extractMeasured(emptyMap()).isEmpty())
    }

    @Test
    fun isValidCustomKey_requiresXPrefixAndLowercase() {
        assertTrue(BodyDataInputParser.isValidCustomKey("x_steps"))
        assertTrue(BodyDataInputParser.isValidCustomKey("x_lean_mass_2"))
        assertFalse(BodyDataInputParser.isValidCustomKey("steps"))       // 缺 x_ 前缀
        assertFalse(BodyDataInputParser.isValidCustomKey("X_Steps"))     // 大写
        assertFalse(BodyDataInputParser.isValidCustomKey("x_"))          // 空主体
        assertFalse(BodyDataInputParser.isValidCustomKey("weight"))      // 内置 key 不走自定义
        assertFalse(BodyDataInputParser.isValidCustomKey("x-Steps"))     // 非法字符
    }

    @Test
    fun validateOutOfRange_flagsMinMaxViolations() {
        val violations = BodyDataInputParser.validateOutOfRange(
            BUILTIN_BODY_METRICS,
            mapOf("weight" to 10.0, "water" to 9000.0, "waist" to 80.0, "unknown_key" to 1.0),
        )
        assertEquals(2, violations.size)
        assertTrue(violations.any { it.startsWith("体重") })
        assertTrue(violations.any { it.startsWith("饮水量") })
    }

    @Test
    fun validateOutOfRange_boundaryValuesPass() {
        val metrics = BUILTIN_BODY_METRICS
        val weightDef = metrics.first { it.key == "weight" }
        val violations = BodyDataInputParser.validateOutOfRange(
            metrics,
            mapOf("weight" to weightDef.min!!, "caffeine" to 1000.0),
        )
        assertTrue(violations.isEmpty())
    }

    @Test
    fun validateOutOfRange_noDefNoViolation() {
        assertNull(
            BodyDataInputParser.validateOutOfRange(BUILTIN_BODY_METRICS, mapOf("x_new_metric" to 99999.0))
                .firstOrNull(),
        )
    }
}
