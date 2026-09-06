package com.sailzen.app.feature.reader

/**
 * 文本段落切块（移植自 NovelDokusha DelimiterAwareTextSplitter 思路）。
 *
 * 切块策略：
 * 1. 先按 '\n' 切段，保留空段（空段代表一个空行，渲染时占一行高）；
 * 2. 超长非空段（> [LONG_PARAGRAPH_THRESHOLD] 字）在句读附近软切，
 *    避免 LazyColumn item 过大，同时保持全局字符偏移不变。
 *
 * 所有切块都携带全局偏移，批注锚点 (nodeId, startOffset, endOffset) 可二分映射。
 */
data class Paragraph(
    val text: String,
    val startOffset: Int,
) {
    val endOffset: Int get() = startOffset + text.length
}

object ParagraphSplitter {

    /** 超过该长度的段落按句读软切 */
    const val LONG_PARAGRAPH_THRESHOLD = 800

    /** 句读分隔符：中文句号/问号/叹号/分号 + 英文对应符号 */
    private const val SENTENCE_DELIMITERS = "。！？；!?.,;"

    /**
     * 将章节全文切分为带全局偏移的段落块，顺序覆盖全文。
     * 文本末尾的单个换行不产生额外空段（与 TextView 渲染行为一致）。
     */
    fun split(rawText: String): List<Paragraph> {
        if (rawText.isEmpty()) return emptyList()

        val segments = ArrayList<Paragraph>(rawText.length / 40 + 8)
        var start = 0
        for (i in rawText.indices) {
            if (rawText[i] == '\n') {
                segments.add(Paragraph(rawText.substring(start, i), start))
                start = i + 1
            }
        }
        if (start < rawText.length) {
            segments.add(Paragraph(rawText.substring(start), start))
        }

        val result = ArrayList<Paragraph>(segments.size + 4)
        for (seg in segments) {
            if (seg.text.length > LONG_PARAGRAPH_THRESHOLD) {
                result.addAll(splitLongSegment(seg))
            } else {
                result.add(seg)
            }
        }
        return result
    }

    /** 超长段按句读软切；找不到句读时在阈值处硬切 */
    private fun splitLongSegment(seg: Paragraph): List<Paragraph> {
        val text = seg.text
        val chunks = ArrayList<Paragraph>(text.length / LONG_PARAGRAPH_THRESHOLD + 1)
        var base = 0
        while (text.length - base > LONG_PARAGRAPH_THRESHOLD) {
            val windowEnd = base + LONG_PARAGRAPH_THRESHOLD
            var cut = -1
            var i = windowEnd - 1
            while (i > base) {
                if (text[i] in SENTENCE_DELIMITERS) {
                    cut = i + 1
                    break
                }
                i--
            }
            if (cut <= base) cut = windowEnd
            chunks.add(Paragraph(text.substring(base, cut), seg.startOffset + base))
            base = cut
        }
        if (base < text.length) {
            chunks.add(Paragraph(text.substring(base), seg.startOffset + base))
        }
        return chunks
    }
}
