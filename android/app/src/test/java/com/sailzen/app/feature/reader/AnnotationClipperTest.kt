package com.sailzen.app.feature.reader

import com.sailzen.app.core.data.db.CachedAnnotation
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * 批注裁剪测试：全局偏移 → 段落相对区间的映射正确性。
 */
class AnnotationClipperTest {

    private fun anno(start: Int, end: Int, id: Long = 1) = CachedAnnotation(
        localId = id,
        workId = 1,
        editionId = 1,
        nodeId = 10,
        startOffset = start,
        endOffset = end,
        selectedText = "",
        note = "",
        color = "yellow",
        createdAt = "",
        updatedAt = "",
    )

    @Test
    fun `annotation inside single paragraph clips to relative range`() {
        val paragraphs = ParagraphSplitter.split("第一段文字。\n第二段文字。")
        // "第一段文字。" = 0..6，"第二段文字。" startOffset = 7
        val result = clipAnnotationsByParagraph(paragraphs, listOf(anno(8, 11)))

        assertEquals(1, result.size)
        val clipped = result[paragraphs[1].startOffset]!!
        assertEquals(1, clipped.size)
        assertEquals(8 - paragraphs[1].startOffset, clipped[0].relStart)
        assertEquals(11 - paragraphs[1].startOffset, clipped[0].relEnd)
    }

    @Test
    fun `annotation spanning paragraphs clips into both`() {
        val paragraphs = ParagraphSplitter.split("第一段文字。\n第二段文字。")
        val result = clipAnnotationsByParagraph(paragraphs, listOf(anno(3, 12)))

        assertEquals(2, result.size)
        val first = result[paragraphs[0].startOffset]!!.single()
        assertEquals(3, first.relStart)
        assertEquals(paragraphs[0].text.length, first.relEnd)
        val second = result[paragraphs[1].startOffset]!!.single()
        assertEquals(0, second.relStart)
        assertEquals(12 - paragraphs[1].startOffset, second.relEnd)
    }

    @Test
    fun `empty annotation list returns empty map`() {
        val paragraphs = ParagraphSplitter.split("abc\ndef")
        assertTrue(clipAnnotationsByParagraph(paragraphs, emptyList()).isEmpty())
    }

    @Test
    fun `zero length annotation is dropped`() {
        val paragraphs = ParagraphSplitter.split("abc\ndef")
        val result = clipAnnotationsByParagraph(paragraphs, listOf(anno(1, 1)))
        assertNull(result[paragraphs[0].startOffset])
    }

    @Test
    fun `annotation at exact paragraph start includes that paragraph only from zero`() {
        val paragraphs = ParagraphSplitter.split("abc\ndef")
        val result = clipAnnotationsByParagraph(paragraphs, listOf(anno(4, 6)))
        val clipped = result[paragraphs[1].startOffset]!!.single()
        assertEquals(0, clipped.relStart)
        assertEquals(2, clipped.relEnd)
    }

    @Test
    fun `empty paragraphs are skipped`() {
        // "a\n\nb"：中段是空行段落（startOffset=2，长度为 0）
        val paragraphs = ParagraphSplitter.split("a\n\nb")
        assertEquals(3, paragraphs.size)
        val result = clipAnnotationsByParagraph(paragraphs, listOf(anno(0, 4)))
        // 空行段不产生裁剪项，首尾两段各一项
        assertEquals(2, result.size)
        assertNull(result[paragraphs[1].startOffset])
        assertEquals(0, result[paragraphs[0].startOffset]!!.single().relStart)
        assertEquals(0, result[paragraphs[2].startOffset]!!.single().relStart)
    }
}
