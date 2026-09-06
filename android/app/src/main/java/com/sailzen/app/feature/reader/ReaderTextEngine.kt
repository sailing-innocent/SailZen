package com.sailzen.app.feature.reader

import android.graphics.Paint
import android.text.Layout
import android.text.StaticLayout
import android.text.TextPaint
import android.util.Log
import kotlin.math.floor

/**
 * 阅读排版引擎：以「段」为排版单位做真实测量，将章节文本切分为若干页。
 *
 * 修复点（对照旧实现）：
 * - SP/PX 混用：LayoutSpec 全字段为 PX，字号由调用方用 density 换算后传入；
 * - 不做换行：逐段用 [StaticLayout] 真实排版，长段自动跨页按行拆分；
 * - 页高魔法常量：由 Compose 实测布局高度换算为 spec.heightPx 传入；
 * - 批注定位：Page 携带 paragraphRanges，偏移变化后可用 [findPageForOffset] 二分重映射。
 */
object ReaderTextEngine {

    private const val TAG = "ReaderTextEngine"
    private const val EPS = 0.5f

    /** 全部使用像素单位（调用方负责 sp/dp → px 换算） */
    data class LayoutSpec(
        val widthPx: Int,
        val heightPx: Int,
        val fontSizePx: Float,
        val lineSpacingMult: Float,
        val paragraphSpacingPx: Int,
        val paddingPx: Int,
    )

    data class Page(
        val text: String,
        val startOffset: Int,
        val endOffset: Int,
        /** 页内各段的全局字符区间（供批注二分定位） */
        val paragraphRanges: List<IntRange> = emptyList(),
    )

    /** 一行渲染区间 [start, endExclusive) */
    data class LineRange(val start: Int, val endExclusive: Int)

    /**
     * 文本测量抽象：真机用 [StaticLayoutMeasurer]（StaticLayout 与 TextView
     * 同一排版引擎），JVM 单测注入假实现验证分页算法。
     */
    interface TextMeasurer {
        /** 单行实际行高（已含行距倍数），由两行探针文本测得 */
        fun lineAdvance(spec: LayoutSpec): Float

        /** 测量一段文本折行后的各行字符区间；空文本返回一行（空行） */
        fun measureLines(text: String, spec: LayoutSpec): List<LineRange>
    }

    /** StaticLayout 真机测量（StaticLayout.Builder 需 API 23+，minSdk 26 满足） */
    class StaticLayoutMeasurer : TextMeasurer {

        private val paintCache = HashMap<Long, TextPaint>()

        private fun contentWidth(spec: LayoutSpec): Int =
            (spec.widthPx - spec.paddingPx * 2).coerceAtLeast(1)

        private fun paint(spec: LayoutSpec): TextPaint {
            val key = (spec.fontSizePx.toBits().toLong() shl 32) or
                (spec.lineSpacingMult.toBits().toLong() and 0xFFFFFFFFL)
            return paintCache.getOrPut(key) {
                TextPaint(Paint.ANTI_ALIAS_FLAG).apply {
                    textSize = spec.fontSizePx
                }
            }
        }

        private fun layout(text: String, spec: LayoutSpec): StaticLayout =
            StaticLayout.Builder
                .obtain(text, 0, text.length, paint(spec), contentWidth(spec))
                .setAlignment(Layout.Alignment.ALIGN_NORMAL)
                .setLineSpacing(0f, spec.lineSpacingMult)
                .setIncludePad(false)
                .build()

        override fun lineAdvance(spec: LayoutSpec): Float {
            val probe = "字\n字"
            val l = layout(probe, spec)
            return if (l.lineCount >= 2) {
                (l.getLineTop(1) - l.getLineTop(0)).toFloat()
            } else {
                l.height.toFloat().coerceAtLeast(1f)
            }
        }

        override fun measureLines(text: String, spec: LayoutSpec): List<LineRange> {
            if (text.isEmpty()) return listOf(LineRange(0, 0))
            val l = layout(text, spec)
            val count = l.lineCount
            return ArrayList<LineRange>(count).apply {
                for (i in 0 until count) {
                    add(LineRange(l.getLineStart(i), l.getLineEnd(i)))
                }
            }
        }
    }

    val defaultMeasurer: TextMeasurer = StaticLayoutMeasurer()

    /**
     * 纯函数分页（CPU 密集，调用方应在 Dispatchers.Default 上调用）。
     *
     * 约定：
     * - [paragraphs] 必须按偏移递增且覆盖全文（[ParagraphSplitter.split] 的输出）；
     * - 段间距 [LayoutSpec.paragraphSpacingPx] 作为段间补偿在分页时预留，
     *   ReaderPageView 渲染时对段末行追加等高空白，二者保持一致；
     * - 所有页拼接结果与原文完全一致（自动断言：concat(page.text) == rawText）。
     */
    fun paginate(
        rawText: String,
        paragraphs: List<Paragraph>,
        spec: LayoutSpec,
        measurer: TextMeasurer = defaultMeasurer,
    ): List<Page> {
        if (rawText.isEmpty()) return listOf(Page("", 0, 0))

        val contentWidth = spec.widthPx - spec.paddingPx * 2
        val usableHeight = spec.heightPx - spec.paddingPx * 2
        if (contentWidth <= 0 || usableHeight <= 0 || paragraphs.isEmpty()) {
            return listOf(Page(rawText, 0, rawText.length))
        }
        val lineH = measurer.lineAdvance(spec)
        if (lineH <= 0f) return listOf(Page(rawText, 0, rawText.length))

        val pages = mutableListOf<Page>()
        val pageRanges = mutableListOf<IntRange>()
        var pageStart = 0
        var cursor = 0f
        var hasContent = false

        fun closePage(end: Int) {
            pages.add(
                Page(
                    text = rawText.substring(pageStart, end),
                    startOffset = pageStart,
                    endOffset = end,
                    paragraphRanges = pageRanges.toList(),
                ),
            )
            pageRanges.clear()
            pageStart = end
            cursor = 0f
            hasContent = false
        }

        val work = paragraphs.toMutableList()
        var i = 0
        while (i < work.size) {
            val para = work[i]
            val lines = measurer.measureLines(para.text, spec)
            val paraHeight = lines.size * lineH
            val gap = if (hasContent) spec.paragraphSpacingPx.toFloat() else 0f

            if (cursor + gap + paraHeight <= usableHeight + EPS) {
                cursor += gap + paraHeight
                pageRanges.add(para.startOffset..para.endOffset)
                hasContent = true
                i++
            } else if (!hasContent) {
                // 单段超页：按渲染行边界硬切，保证任何段都能跨页
                val maxLines = floor(usableHeight / lineH).toInt().coerceAtLeast(1)
                if (lines.size <= maxLines) {
                    // 测量/浮点误差兜底：强制收入本页，避免死循环
                    cursor += gap + paraHeight
                    pageRanges.add(para.startOffset..para.endOffset)
                    hasContent = true
                    i++
                } else {
                    val cut = lines[maxLines - 1].endExclusive.coerceIn(1, para.text.length)
                    val head = Paragraph(para.text.substring(0, cut), para.startOffset)
                    val tail = Paragraph(para.text.substring(cut), para.startOffset + cut)
                    work[i] = head
                    work.add(i + 1, tail)
                    // 不递增 i：下一轮处理 head，必走 fits 分支
                }
            } else {
                // 页满：在下一段开头（含上一段结尾换行）封页
                closePage(para.startOffset)
            }
        }
        if (hasContent) closePage(rawText.length)

        if (pages.isEmpty()) {
            pages.add(Page(rawText, 0, rawText.length))
        }

        Log.d(TAG, "paginate: ${pages.size} pages for ${rawText.length} chars")
        return pages
    }

    /** 二分查找包含 charOffset 的页码（页按 startOffset 升序） */
    fun findPageForOffset(pages: List<Page>, charOffset: Int): Int {
        if (pages.isEmpty()) return 0
        var low = 0
        var high = pages.size - 1
        while (low < high) {
            val mid = (low + high + 1) ushr 1
            if (pages[mid].startOffset <= charOffset) low = mid else high = mid - 1
        }
        return low
    }
}
