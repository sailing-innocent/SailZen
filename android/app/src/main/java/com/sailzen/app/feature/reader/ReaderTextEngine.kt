package com.sailzen.app.feature.reader

import android.content.Context
import android.graphics.Paint
import android.graphics.Rect
import android.text.TextPaint
import android.util.Log
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import kotlin.math.ceil
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext

/**
 * 阅读排版引擎：将章节文本按页面尺寸切分为若干页。
 */
object ReaderTextEngine {

    private const val TAG = "ReaderTextEngine"

    data class Page(
        val text: String,
        val startOffset: Int,
        val endOffset: Int,
    )

    data class LayoutSpec(
        val widthPx: Int,
        val heightPx: Int,
        val fontSizeSp: Float,
        val lineSpacing: Float,
        val paragraphSpacingPx: Int,
    )

    /**
     * 后台线程分页。返回每页包含的文本与全局偏移。
     */
    suspend fun paginate(
        rawText: String,
        spec: LayoutSpec,
    ): List<Page> = withContext(Dispatchers.Default) {
        if (rawText.isEmpty()) return@withContext listOf(Page("", 0, 0))

        val paint = TextPaint(Paint.ANTI_ALIAS_FLAG).apply {
            textSize = spec.fontSizeSp
        }
        val lineHeight = paint.fontMetrics.run { descent - ascent + leading }
        val usableHeight = spec.heightPx
        val effectiveLineHeight = lineHeight * spec.lineSpacing
        val maxLines = ceil(usableHeight / effectiveLineHeight).toInt().coerceAtLeast(1)

        val pages = mutableListOf<Page>()
        var offset = 0
        var pageStart = 0
        var linesInPage = 0f
        var lastBreak = 0

        var i = 0
        while (i <= rawText.length) {
            val ch = if (i < rawText.length) rawText[i] else '\n'
            val isParaEnd = ch == '\n' || i == rawText.length
            val charWidth = if (i < rawText.length) paint.measureText(rawText, i, i + 1) else 0f
            val wouldExceed = (linesInPage + 1) * effectiveLineHeight > usableHeight &&
                (charWidth > 0 || isParaEnd)

            if (wouldExceed && lastBreak > pageStart) {
                pages.add(Page(rawText.substring(pageStart, lastBreak), pageStart, lastBreak))
                pageStart = lastBreak
                linesInPage = 0f
                lastBreak = pageStart
            }

            if (isParaEnd) {
                linesInPage += 1f
                if ((linesInPage + 1) * effectiveLineHeight > usableHeight) {
                    pages.add(Page(rawText.substring(pageStart, i), pageStart, i))
                    pageStart = i
                    linesInPage = 0f
                }
                linesInPage += spec.paragraphSpacingPx / effectiveLineHeight
                lastBreak = i
            }
            i++
        }

        if (pageStart < rawText.length) {
            pages.add(Page(rawText.substring(pageStart), pageStart, rawText.length))
        }

        // 兜底：如果分页逻辑产生空结果，整章作为一页
        if (pages.isEmpty()) {
            pages.add(Page(rawText, 0, rawText.length))
        }

        Log.d(TAG, "paginate: ${pages.size} pages for ${rawText.length} chars")
        pages
    }

    fun dpToPx(context: Context, dp: Dp): Int =
        (dp.value * context.resources.displayMetrics.density).toInt()

    fun spToPx(context: Context, sp: Float): Float =
        sp * context.resources.displayMetrics.scaledDensity
}
