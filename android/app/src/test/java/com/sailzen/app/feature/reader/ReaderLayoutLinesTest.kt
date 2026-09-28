package com.sailzen.app.feature.reader

import com.sailzen.app.core.data.db.CachedAnnotation
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * JVM 假测量器：等宽字符折行（与 ReaderTextEngineTest 同款，
 * StaticLayout 行为差异在验收机比对）。
 */
private class FixedCharMeasurer(
    private val charWidthPx: Float,
    private val lineHeightPx: Float,
) : ReaderTextEngine.TextMeasurer {
    override fun lineAdvance(spec: ReaderTextEngine.LayoutSpec): Float =
        lineHeightPx * spec.lineSpacingMult

    override fun measureLines(
        text: String,
        spec: ReaderTextEngine.LayoutSpec,
    ): List<ReaderTextEngine.LineRange> {
        if (text.isEmpty()) return listOf(ReaderTextEngine.LineRange(0, 0))
        val contentWidth = (spec.widthPx - spec.paddingPx * 2).coerceAtLeast(1)
        val charsPerLine = (contentWidth / charWidthPx).toInt().coerceAtLeast(1)
        val lines = ArrayList<ReaderTextEngine.LineRange>(text.length / charsPerLine + 1)
        var start = 0
        while (start < text.length) {
            val end = (start + charsPerLine).coerceAtMost(text.length)
            lines.add(ReaderTextEngine.LineRange(start, end))
            start = end
        }
        return lines
    }
}

/**
 * 行序排版（滚动模式数据源）测试：行区间覆盖全文、段末标记唯一、
 * 空段产空行，拼接结果与原文一致。
 */
class ReaderLayoutLinesTest {

    private val measurer = FixedCharMeasurer(charWidthPx = 10f, lineHeightPx = 20f)

    private fun spec(
        widthPx: Int = 200,          // 每行 20 字（10px/字）
        heightPx: Int = 480,
        fontSizePx: Float = 16f,
        lineSpacingMult: Float = 1.5f,
        paragraphSpacingPx: Int = 8,
        paddingPx: Int = 0,
    ) = ReaderTextEngine.LayoutSpec(
        widthPx = widthPx,
        heightPx = heightPx,
        fontSizePx = fontSizePx,
        lineSpacingMult = lineSpacingMult,
        paragraphSpacingPx = paragraphSpacingPx,
        paddingPx = paddingPx,
    )

    private fun layout(raw: String, s: ReaderTextEngine.LayoutSpec = spec()) =
        ReaderTextEngine.layoutLines(raw, ParagraphSplitter.split(raw), s, measurer)

    @Test
    fun `lines cover full text and concat equals raw`() {
        val raw = "第一段文字比较长，会折成若干行。\n第二段。\n\n第四段。"
        val lines = layout(raw)
        assertTrue(lines.isNotEmpty())
        // 行区间严格递增且不重叠
        for (i in 1 until lines.size) {
            assertEquals(lines[i - 1].endOffset, lines[i].startOffset)
        }
        assertEquals(0, lines.first().startOffset)
        assertEquals(raw.length, lines.last().endOffset)
        assertEquals(raw, lines.joinToString("") { it.text })
    }

    @Test
    fun `each paragraph has exactly one paragraphEnd line`() {
        val raw = "第一段。\n第二段更长一些，可能会折行哦。\n第三段。"
        val lines = layout(raw)
        val paraCount = ParagraphSplitter.split(raw).size
        val paraEndCount = lines.count { it.paragraphEnd }
        assertEquals(paraCount, paraEndCount)
        // 最后一个段末行即全文末尾
        assertTrue(lines.last().paragraphEnd)
    }

    @Test
    fun `empty paragraph produces single blank line`() {
        val raw = "a\n\nb"
        val lines = layout(raw)
        // 空段行吸收段间换行符，文本为 "\n"（单行渲染为空行）
        val blank = lines.filter { it.text.isBlank() }
        assertEquals(1, blank.size)
        assertTrue(blank.single().paragraphEnd)
        assertEquals(2, blank.single().startOffset)
        assertEquals(raw, lines.joinToString("") { it.text })
    }

    @Test
    fun `long paragraph splits into multiple lines without gaps`() {
        // 20 字/行，40+ 字长段必折多行
        val raw = "这是一段非常非常非常非常非常长的正文内容，用来验证多行排版后的段末标记，确实够长了。"
        val lines = layout(raw)
        assertTrue(lines.size > 2)
        assertEquals(1, lines.count { it.paragraphEnd })
        assertEquals(raw, lines.joinToString("") { it.text })
    }

    @Test
    fun `empty raw text yields empty lines`() {
        assertTrue(layout("").isEmpty())
    }

    @Test
    fun `line clip by ranges maps annotation into line relative range`() {
        val raw = "第一行内容。\n第二行内容。\n第三行内容。"
        val lines = layout(raw)
        val second = lines[1]
        val clip = clipAnnotationsByRanges(
            lines.map { it.startOffset..it.endOffset },
            listOf(
                CachedAnnotation(
                    localId = 1, workId = 1, editionId = 1, nodeId = 1,
                    startOffset = second.startOffset + 1,
                    endOffset = second.startOffset + 3,
                    selectedText = "", note = "", color = "yellow",
                    createdAt = "", updatedAt = "",
                ),
            ),
        )
        val clipped = clip[second.startOffset]!!.single()
        assertEquals(1, clipped.relStart)
        assertEquals(3, clipped.relEnd)
    }
}
