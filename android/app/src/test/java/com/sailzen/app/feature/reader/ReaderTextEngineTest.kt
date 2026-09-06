package com.sailzen.app.feature.reader

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * JVM 假测量器：等宽字符折行（CJK/ASCII 同宽近似），
 * 用于验证分页算法正确性，与 StaticLayout 行为差异在验收机比对。
 */
private class FakeMeasurer(
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

class ReaderTextEngineTest {

    private val measurer = FakeMeasurer(charWidthPx = 10f, lineHeightPx = 20f)

    private fun spec(
        widthPx: Int = 300,
        heightPx: Int = 480,
        fontSizePx: Float = 16f,
        lineSpacingMult: Float = 1.5f,
        paragraphSpacingPx: Int = 0,
        paddingPx: Int = 0,
    ) = ReaderTextEngine.LayoutSpec(
        widthPx = widthPx,
        heightPx = heightPx,
        fontSizePx = fontSizePx,
        lineSpacingMult = lineSpacingMult,
        paragraphSpacingPx = paragraphSpacingPx,
        paddingPx = paddingPx,
    )

    private fun paginate(raw: String, layout: ReaderTextEngine.LayoutSpec = spec()): List<ReaderTextEngine.Page> =
        ReaderTextEngine.paginate(raw, ParagraphSplitter.split(raw), layout, measurer)

    @Test
    fun `多段文本分页拼接与原文一致`() {
        val raw = "第一段内容，若干文字。\n第二段内容，继续若干文字。\n\n第三段带空行分隔".repeat(20)
        val pages = paginate(raw)
        assertTrue(pages.isNotEmpty())
        assertEquals(raw, pages.joinToString("") { it.text })
    }

    @Test
    fun `超长段落跨页拆分不丢字符`() {
        val raw = "这是一个没有句读的超长段落".repeat(400) // 10400 字，> 800 触发软切
        val pages = paginate(raw)
        assertTrue("长文应拆成多页", pages.size > 1)
        assertEquals(raw, pages.joinToString("") { it.text })
        pages.forEach { assertTrue("每页都应有内容", it.text.isNotEmpty()) }
    }

    @Test
    fun `段间距会把后续段落推到下一页`() {
        val raw = "a\nb\nc\nd"
        // 行高 30：无段距 2 行/页 → [a,b] [c,d]；段距 12 时 30+12+30=72 > 64 → [a] [b] [c] [d]
        val noGap = paginate(raw, spec(heightPx = 64))
        val withGap = paginate(raw, spec(heightPx = 64, paragraphSpacingPx = 12))
        assertEquals(2, noGap.size)
        assertEquals(4, withGap.size)
        assertEquals(raw, withGap.joinToString("") { it.text })
    }

    @Test
    fun `空行占用一行高`() {
        // 行高 30，页高 61 恰好容纳 a + 空行
        val pages = paginate("a\n\nb", spec(heightPx = 61))
        assertEquals(2, pages.size)
        assertEquals("a\n\n", pages[0].text)
        assertEquals("b", pages[1].text)
    }

    @Test
    fun `页偏移连续覆盖全文`() {
        val raw = ("窗前明月光，疑是地上霜。\n举头望明月，低头思故乡。").repeat(50)
        val pages = paginate(raw)
        var cursor = 0
        pages.forEachIndexed { index, page ->
            assertEquals("第 $index 页 startOffset 应连续", cursor, page.startOffset)
            assertEquals(page.text.length, page.endOffset - page.startOffset)
            cursor = page.endOffset
        }
        assertEquals(raw.length, cursor)
    }

    @Test
    fun `findPageForOffset 二分定位正确`() {
        val raw = "一".repeat(3000)
        val pages = paginate(raw)
        assertTrue(pages.size > 1)
        assertEquals(0, ReaderTextEngine.findPageForOffset(pages, 0))
        assertEquals(0, ReaderTextEngine.findPageForOffset(pages, pages[0].startOffset))
        assertEquals(pages.lastIndex, ReaderTextEngine.findPageForOffset(pages, pages.last().endOffset - 1))
        assertEquals(pages.lastIndex, ReaderTextEngine.findPageForOffset(pages, pages.last().startOffset))
        // 中间页抽样
        val mid = pages.size / 2
        assertEquals(mid, ReaderTextEngine.findPageForOffset(pages, pages[mid].startOffset))
    }

    @Test
    fun `退化布局参数回退为整章一页`() {
        val raw = "abc\ndef"
        val pages = paginate(raw, spec(widthPx = 0, heightPx = 0))
        assertEquals(1, pages.size)
        assertEquals(raw, pages[0].text)
    }

    @Test
    fun `paragraphRanges 按序覆盖页内各段`() {
        val raw = "甲。乙。丙。\n\n丁。戊。"
        val pages = paginate(raw, spec(heightPx = 35)) // 每页仅 1 行
        assertTrue(pages.size > 1)
        pages.forEach { page ->
            var prevEnd = page.startOffset
            page.paragraphRanges.forEach { range ->
                assertTrue(range.first >= prevEnd)
                prevEnd = range.last
            }
        }
        assertEquals(raw, pages.joinToString("") { it.text })
    }

    @Test
    fun `sp 到 px 换算由调用方负责时不影响纯 Kotlin 算法`() {
        // 模拟 density=3 设备：18sp → 54px
        val layout = spec(widthPx = 540, heightPx = 960, fontSizePx = 54f)
        val raw = "字".repeat(400)
        val pages = paginate(raw, layout)
        assertTrue(pages.isNotEmpty())
        assertEquals(raw, pages.joinToString("") { it.text })
    }
}
