package com.sailzen.app.feature.reader

import android.content.Context
import android.os.Handler
import android.os.Looper
import android.view.ViewGroup
import android.widget.FrameLayout
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.viewinterop.AndroidView
import androidx.core.widget.NestedScrollView
import com.sailzen.app.core.data.db.CachedAnnotation

/**
 * 滚动模式阅读视图：**整章一次性排版进单个原生 TextView**（NestedScrollView 承载），
 * 滚动 = 纯位移，任何距离/方向都零组合成本——即「全部加载好，直接上下滑动」。
 *
 * - 与翻页模式共用 [ReaderTextView]：原生选字/复制/批注菜单、高亮点击、点按分区全部复用；
 * - 批注区间直接使用章节全局偏移（整章即单页，pageStartOffset=0）；
 * - 段间距/行距参数与排版引擎一致（ParagraphSpacingSpan 与 ReaderTextEngine 同源）；
 * - 滚动进度经行高换算为行号/百分比上报，阅读位置持久化体系不变。
 */
@Composable
fun ScrollChapterView(
    text: String,
    annotations: List<CachedAnnotation>,
    paragraphRanges: List<IntRange>,
    fontSizeSp: Float,
    lineSpacing: Float,
    paragraphSpacingPx: Int,
    paddingPx: Int,
    textColor: Int,
    bgColor: Int,
    /** 单行像素高（排版引擎实测），滚动偏移 ↔ 行号换算基准 */
    lineAdvancePx: Float,
    restoreLineIndex: Int,
    chapterId: Int,
    onScrollProgress: (percent: Int, lineIndex: Int, scrolling: Boolean) -> Unit,
    onSelection: (start: Int, end: Int, selectedText: String) -> Unit,
    onAnnotationClick: (CachedAnnotation) -> Unit,
    onTap: (xFraction: Float) -> Unit,
    onViewReady: (ReaderScrollView) -> Unit = {},
    modifier: Modifier = Modifier,
) {
    AndroidView(
        factory = { context -> ReaderScrollView(context).also(onViewReady) },
        update = { view ->
            view.setContent(
                text = text,
                annotations = annotations,
                paragraphRanges = paragraphRanges,
                fontSizeSp = fontSizeSp,
                lineSpacing = lineSpacing,
                paragraphSpacingPx = paragraphSpacingPx,
                paddingPx = paddingPx,
                textColor = textColor,
                bgColor = bgColor,
                lineAdvancePx = lineAdvancePx,
                restoreLineIndex = restoreLineIndex,
                chapterId = chapterId,
            )
            view.onScrollProgress = onScrollProgress
            view.onSelection = onSelection
            view.onAnnotationClick = onAnnotationClick
            view.onPageTap = onTap
        },
        modifier = modifier,
    )
}

/**
 * NestedScrollView + ReaderTextView 组合。
 * 滚动停止判定（延迟清滚动标记）与章节切换/行高变化时的位置恢复在此处理。
 */
class ReaderScrollView(context: Context) : NestedScrollView(context) {

    val textView = ReaderTextView(context)

    var onScrollProgress: ((percent: Int, lineIndex: Int, scrolling: Boolean) -> Unit)? = null
    var onSelection: ((Int, Int, String) -> Unit)? = null
        set(value) {
            field = value
            textView.onPageSelection = value?.let { cb ->
                { _: Int, s: Int, e: Int, t: String -> cb(s, e, t) }
            }
        }
    var onAnnotationClick: ((CachedAnnotation) -> Unit)? = null
        set(value) {
            field = value
            textView.onAnnotationClick = value
        }
    var onPageTap: ((Float) -> Unit)? = null
        set(value) {
            field = value
            textView.onPageTap = value
        }

    private var lineAdvancePx: Float = 0f
    private var lineCount: Int = 0
    private var lastChapterId: Int = -1
    private var pendingRestoreLine: Int = 0
    private val handler = Handler(Looper.getMainLooper())

    private var scrolling = false
    private val scrollEndRunnable = Runnable {
        scrolling = false
        emitProgress()
    }

    init {
        addView(
            textView,
            FrameLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT,
                ViewGroup.LayoutParams.WRAP_CONTENT,
            ),
        )
        setOnScrollChangeListener { _, _, scrollY, _, _ ->
            scrolling = true
            handler.removeCallbacks(scrollEndRunnable)
            handler.postDelayed(scrollEndRunnable, 900)
            emitProgress(scrollY)
        }
    }

    fun setContent(
        text: String,
        annotations: List<CachedAnnotation>,
        paragraphRanges: List<IntRange>,
        fontSizeSp: Float,
        lineSpacing: Float,
        paragraphSpacingPx: Int,
        paddingPx: Int,
        textColor: Int,
        bgColor: Int,
        lineAdvancePx: Float,
        restoreLineIndex: Int,
        chapterId: Int,
    ) {
        val lineAdvanceChanged = this.lineAdvancePx != lineAdvancePx
        this.lineAdvancePx = lineAdvancePx
        this.lineCount = if (lineAdvancePx > 0f) {
            (textView.heightSafe(text) / lineAdvancePx).toInt().coerceAtLeast(1)
        } else {
            0
        }

        textView.setTextColor(textColor)
        textView.setBackgroundColor(bgColor)
        textView.textSize = fontSizeSp
        textView.setLineSpacing(0f, lineSpacing)
        textView.setPadding(paddingPx, paddingPx, paddingPx, paddingPx)
        textView.pageStartOffset = 0
        textView.pageParagraphRanges = paragraphRanges
        textView.paragraphSpacingPx = paragraphSpacingPx
        // 整章即单页：pageIndex 恒 0，选中回调直接给章节绝对偏移
        textView.pageIndex = 0
        textView.refreshIfNeeded(text, annotations.hashCode(), paragraphSpacingPx, annotations)

        if (chapterId != lastChapterId) {
            // 章节切换：排版完成后恢复到上次阅读行
            lastChapterId = chapterId
            pendingRestoreLine = restoreLineIndex
            post { scrollToLine(pendingRestoreLine) }
        } else if (lineAdvanceChanged) {
            // 字号/行距变化：保持在同一阅读行（比例重算由滚动监听自然完成）
            post { scrollToLine(currentLineIndex()) }
        }
    }

    private fun currentLineIndex(): Int =
        if (lineAdvancePx > 0f) (scrollY / lineAdvancePx).toInt().coerceAtLeast(0) else 0

    private fun textViewHeight(): Int =
        if (childCount > 0 && getChildAt(0).height > 0) getChildAt(0).height else textView.height

    /** 目标行数对应的滚动位置（整章已排版，行高恒定） */
    private fun lineToScrollY(lineIndex: Int): Int {
        val maxY = (textViewHeight() - height).coerceAtLeast(0)
        return (lineIndex * lineAdvancePx).toInt().coerceIn(0, maxY)
    }

    fun scrollToLine(lineIndex: Int) {
        if (lineAdvancePx <= 0f) return
        val y = lineToScrollY(lineIndex)
        if (kotlin.math.abs(scrollY - y) > 1) {
            scrollTo(0, y)
        }
    }

    private fun emitProgress(scrollY: Int = this.scrollY) {
        if (lineCount <= 0 || lineAdvancePx <= 0f) return
        val line = (scrollY / lineAdvancePx).toInt().coerceIn(0, lineCount - 1)
        val percent = line * 100 / lineCount
        onScrollProgress?.invoke(percent, line, scrolling)
    }
}

/** TextView 未测量前估算行数用（保守值，仅影响进度百分比分母的上限估计） */
private fun ReaderTextView.heightSafe(text: String): Int {
    val measured = height
    if (measured > 0) return measured
    // 尚未布局：按行高粗估，等首次布局后 emitProgress 会用到真实高度
    val paint = paint
    val lineH = paint.fontMetrics.let { it.descent - it.ascent } * lineSpacingMultiplier
    val charsPerLine = ((width - paddingLeft - paddingRight) / paint.textSize.coerceAtLeast(1f))
        .coerceAtLeast(1f)
    val lines = (text.length / charsPerLine).toInt() + text.count { it == '\n' } + 2
    return (lines * lineH).toInt()
}
