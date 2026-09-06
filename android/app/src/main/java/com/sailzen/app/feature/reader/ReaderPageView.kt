package com.sailzen.app.feature.reader

import android.content.ClipData
import android.content.Context
import android.graphics.Paint
import android.text.Spannable
import android.text.SpannableString
import android.text.Spanned
import android.text.TextPaint
import android.text.method.ArrowKeyMovementMethod
import android.text.style.BackgroundColorSpan
import android.text.style.ClickableSpan
import android.text.style.LineHeightSpan
import android.view.ActionMode
import android.view.GestureDetector
import android.view.Menu
import android.view.MenuItem
import android.view.MotionEvent
import android.view.View
import android.widget.TextView
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.viewinterop.AndroidView
import com.sailzen.app.R
import com.sailzen.app.core.data.db.CachedAnnotation

/** 批注高亮色，与历史 parseColor 映射保持一致 */
internal fun annotationColorArgb(color: String?, fallback: Int): Int = when (color?.lowercase()) {
    "yellow" -> 0xFFFFFFE0.toInt()
    "green" -> 0xFFE0FFE0.toInt()
    "blue" -> 0xFFE0F7FF.toInt()
    "pink" -> 0xFFFFE0F0.toInt()
    else -> fallback
}

/**
 * 段末行增高 span：在段末行的 descent 上追加段间距，
 * 与 ReaderTextEngine 分页预留的 paragraphSpacingPx 保持一致（真实段间距而非底部留白）。
 */
private class ParagraphSpacingSpan(private val extraPx: Int) : LineHeightSpan {
    override fun chooseHeight(
        text: CharSequence?,
        start: Int,
        end: Int,
        spanstartv: Int,
        v: Int,
        fm: Paint.FontMetricsInt?,
    ) {
        fm ?: return
        fm.descent += extraPx
    }
}

/**
 * 可选择的阅读页：每页一个 TextView。
 *
 * 交互修复：
 * - 文本仅在内容变化且未处于选中态时重置，选择过程不被重组打断（修 U2）；
 * - 自定义 ActionMode：复制 / 批注 / 高亮颜色，选中回调只上抛选区不落库（修 U1/U3）；
 * - 高亮区域可点击，就地查看/编辑/删除批注（修 U5）；
 * - 选中态与 HorizontalPager 手势隔离（修 U4）；中央/左右点按分区上抛（修 U6）。
 */
@Composable
fun ReaderPageView(
    text: String,
    pageIndex: Int,
    annotations: List<CachedAnnotation>,
    paragraphRanges: List<IntRange>,
    pageStartOffset: Int,
    fontSizeSp: Float,
    lineSpacing: Float,
    paragraphSpacingPx: Int,
    paddingPx: Int,
    textColor: Int,
    bgColor: Int,
    onSelection: (pageIndex: Int, start: Int, end: Int, selectedText: String) -> Unit,
    onAnnotationClick: (CachedAnnotation) -> Unit,
    onTap: (xFraction: Float) -> Unit,
    modifier: Modifier = Modifier,
) {
    val annoKey = annotations.hashCode()
    AndroidView(
        factory = { context -> ReaderTextView(context) },
        update = { view ->
            view.setTextColor(textColor)
            view.setBackgroundColor(bgColor)
            view.textSize = fontSizeSp
            view.setLineSpacing(0f, lineSpacing)
            view.setPadding(paddingPx, paddingPx, paddingPx, paddingPx)
            view.pageIndex = pageIndex
            view.pageStartOffset = pageStartOffset
            view.pageParagraphRanges = paragraphRanges
            view.onPageSelection = onSelection
            view.onAnnotationClick = onAnnotationClick
            view.onPageTap = onTap
            view.refreshIfNeeded(text, annoKey, paragraphSpacingPx, annotations)
        },
        modifier = modifier,
    )
}

private const val MENU_COPY = 1
private const val MENU_ANNOTATE = 2
private const val MENU_COLOR = 3

private class ReaderTextView(context: Context) : TextView(context) {

    var pageIndex: Int = 0
    var pageStartOffset: Int = 0
    var paragraphSpacingPx: Int = 0
    var annotations: List<CachedAnnotation> = emptyList()

    var onPageSelection: ((Int, Int, Int, String) -> Unit)? = null
    var onAnnotationClick: ((CachedAnnotation) -> Unit)? = null
    var onPageTap: ((Float) -> Unit)? = null
    var pageParagraphRanges: List<IntRange> = emptyList()

    private var stableText: String? = null
    private var stableAnnoKey: Int = 0

    private val gestureDetector = GestureDetector(
        context,
        object : GestureDetector.SimpleOnGestureListener() {
            override fun onSingleTapUp(e: MotionEvent): Boolean {
                // 命中批注高亮时放行，交给 movement method 处理点击
                if (findClickableSpanAt(e.x, e.y) != null) return false
                val w = width.takeIf { it > 0 } ?: return false
                onPageTap?.invoke((e.x / w).coerceIn(0f, 1f))
                return true
            }
        },
    )

    init {
        setTextIsSelectable(true)
        includeFontPadding = false
        movementMethod = HighlightClickMovementMethod()
        customSelectionActionModeCallback = ReaderActionModeCallback()
        setOnTouchListener { _, event ->
            when (event.actionMasked) {
                MotionEvent.ACTION_DOWN -> if (hasSelection()) disallowParentIntercept(true)
                MotionEvent.ACTION_UP, MotionEvent.ACTION_CANCEL ->
                    disallowParentIntercept(false)
            }
            // 返回值恒 false：不消费事件，TextView 原生选择/滑动不受影响
            gestureDetector.onTouchEvent(event)
            false
        }
    }

    private fun disallowParentIntercept(disallow: Boolean) {
        var p = parent
        while (p != null) {
            p.requestDisallowInterceptTouchEvent(disallow)
            p = p.parent
        }
    }

    /** 选择激活（ActionMode 存活）或内容未变化时跳过文本重置，避免高亮抖动/选择丢失 */
    fun refreshIfNeeded(
        newText: String,
        annoKey: Int,
        spacingPx: Int,
        newAnnotations: List<CachedAnnotation>,
    ) {
        if (hasSelection()) return
        if (stableText == newText && stableAnnoKey == annoKey) return
        stableText = newText
        stableAnnoKey = annoKey
        paragraphSpacingPx = spacingPx
        annotations = newAnnotations
        setText(buildSpanned(newText), BufferType.SPANNABLE)
    }

    private fun buildSpanned(raw: String): SpannableString {
        val spannable = SpannableString(raw)
        val fallback = annotationColorArgb(null, 0xFFFFFFE0.toInt())
        for (anno in annotations) {
            val s = anno.startOffset.coerceIn(0, raw.length)
            val e = anno.endOffset.coerceIn(s, raw.length)
            if (s >= e) continue
            spannable.setSpan(
                BackgroundColorSpan(annotationColorArgb(anno.color, fallback)),
                s,
                e,
                Spanned.SPAN_EXCLUSIVE_EXCLUSIVE,
            )
            spannable.setSpan(
                object : ClickableSpan() {
                    override fun onClick(widget: View) {
                        onAnnotationClick?.invoke(anno)
                    }

                    override fun updateDrawState(ds: TextPaint) {
                        // 保持正文样式，颜色/下划线交给 BackgroundColorSpan
                    }
                },
                s,
                e,
                Spanned.SPAN_EXCLUSIVE_EXCLUSIVE,
            )
        }
        if (paragraphSpacingPx > 0) {
            for (range in pageParagraphRanges) {
                val local = range.last - pageStartOffset
                // 页内非末行的段末行追加段间距；末行跳过（与分页预留一致）
                if (local in 1 until raw.length) {
                    spannable.setSpan(
                        ParagraphSpacingSpan(paragraphSpacingPx),
                        local,
                        local + 1,
                        Spanned.SPAN_EXCLUSIVE_EXCLUSIVE,
                    )
                }
            }
        }
        return spannable
    }

    private fun findClickableSpanAt(x: Float, y: Float): ClickableSpan? {
        val spannable = text as? Spannable ?: return null
        val layout = this.layout ?: return null
        val lx = (x - totalPaddingLeft + scrollX).toInt().coerceAtLeast(0)
        val ly = (y - totalPaddingTop + scrollY).toInt().coerceAtLeast(0)
        val line = layout.getLineForVertical(ly)
        if (line < 0 || line >= layout.lineCount) return null
        val off = layout.getOffsetForHorizontal(line, lx.toFloat()).coerceIn(0, spannable.length)
        return spannable.getSpans(off, off, ClickableSpan::class.java).firstOrNull()
    }

    private fun copySelectionToClipboard() {
        val start = selectionStart.coerceAtLeast(0)
        val end = selectionEnd.coerceAtLeast(start)
        val raw = text?.toString().orEmpty()
        if (start >= end.coerceAtMost(raw.length)) return
        val cm = context.getSystemService(Context.CLIPBOARD_SERVICE) as? android.content.ClipboardManager
        cm?.setPrimaryClip(ClipData.newPlainText(context.getString(R.string.reader_copy), raw.substring(start, end)))
    }

    /** 高亮点击 + 原生选择的复合 MovementMethod（LinkMovementMethod 会破坏文本选择） */
    private inner class HighlightClickMovementMethod : ArrowKeyMovementMethod() {
        private var pressedSpan: ClickableSpan? = null

        override fun onTouchEvent(widget: TextView, buffer: Spannable, event: MotionEvent): Boolean {
            when (event.action) {
                MotionEvent.ACTION_DOWN -> {
                    val span = findSpanAt(widget, buffer, event)
                    if (span != null) {
                        pressedSpan = span
                        return true
                    }
                }
                MotionEvent.ACTION_UP -> {
                    val span = pressedSpan
                    pressedSpan = null
                    if (span != null) {
                        if (findSpanAt(widget, buffer, event) === span) {
                            span.onClick(widget)
                        }
                        return true
                    }
                }
                MotionEvent.ACTION_CANCEL -> pressedSpan = null
            }
            return super.onTouchEvent(widget, buffer, event)
        }

        private fun findSpanAt(widget: TextView, buffer: Spannable, event: MotionEvent): ClickableSpan? {
            val layout = widget.layout ?: return null
            val lx = (event.x - widget.totalPaddingLeft + widget.scrollX).toInt().coerceAtLeast(0)
            val ly = (event.y - widget.totalPaddingTop + widget.scrollY).toInt().coerceAtLeast(0)
            val line = layout.getLineForVertical(ly)
            if (line < 0 || line >= layout.lineCount) return null
            val off = layout.getOffsetForHorizontal(line, lx.toFloat()).coerceIn(0, buffer.length)
            return buffer.getSpans(off, off, ClickableSpan::class.java).firstOrNull()
        }
    }

    private inner class ReaderActionModeCallback : ActionMode.Callback {
        override fun onCreateActionMode(mode: ActionMode?, menu: Menu?): Boolean {
            menu ?: return true
            menu.clear()
            menu.add(Menu.NONE, MENU_COPY, 0, R.string.reader_copy)
            menu.add(Menu.NONE, MENU_ANNOTATE, 1, R.string.reader_annotate)
            menu.add(Menu.NONE, MENU_COLOR, 2, R.string.reader_highlight_color)
            return true
        }

        override fun onPrepareActionMode(mode: ActionMode?, menu: Menu?): Boolean = false

        override fun onActionItemClicked(mode: ActionMode?, item: MenuItem?): Boolean {
            return when (item?.itemId) {
                MENU_COPY -> {
                    copySelectionToClipboard()
                    mode?.finish()
                    true
                }
                MENU_ANNOTATE, MENU_COLOR -> {
                    val start = selectionStart.coerceAtLeast(0)
                    val end = selectionEnd.coerceAtLeast(start)
                    val raw = text?.toString().orEmpty()
                    val safeEnd = end.coerceAtMost(raw.length)
                    if (start < safeEnd) {
                        onPageSelection?.invoke(pageIndex, start, safeEnd, raw.substring(start, safeEnd))
                    }
                    mode?.finish()
                    true
                }
                else -> false
            }
        }

        override fun onDestroyActionMode(mode: ActionMode?) {}
    }
}
