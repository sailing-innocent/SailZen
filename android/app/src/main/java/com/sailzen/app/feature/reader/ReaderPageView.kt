package com.sailzen.app.feature.reader

import android.text.SpannableString
import android.text.Spanned
import android.text.style.BackgroundColorSpan
import android.view.ActionMode
import android.view.Menu
import android.view.MenuItem
import android.widget.TextView
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.viewinterop.AndroidView
import androidx.core.content.ContextCompat
import com.sailzen.app.R
import com.sailzen.app.core.data.db.CachedAnnotation

/**
 * 可选择的阅读页：每页一个 TextView，支持原生文字选择与批注菜单。
 */
@Composable
fun ReaderPageView(
    text: String,
    pageIndex: Int,
    annotations: List<CachedAnnotation>,
    fontSizeSp: Float,
    lineSpacing: Float,
    textColor: Int,
    bgColor: Int,
    onSelection: (pageIndex: Int, start: Int, end: Int, selectedText: String) -> Unit,
    modifier: Modifier = Modifier,
) {
    AndroidView(
        factory = { context ->
            TextView(context).apply {
                setTextIsSelectable(true)
                setTextColor(textColor)
                setBackgroundColor(bgColor)
                this.textSize = fontSizeSp
                setLineSpacing(0f, lineSpacing)
                includeFontPadding = true
                setPadding(24, 24, 24, 24)
                customSelectionActionModeCallback = object : ActionMode.Callback {
                    override fun onCreateActionMode(mode: ActionMode?, menu: Menu?): Boolean {
                        menu?.add(Menu.NONE, MENU_ANNOTATE, 0, R.string.action_annotate)
                        return true
                    }

                    override fun onPrepareActionMode(mode: ActionMode?, menu: Menu?): Boolean = false

                    override fun onActionItemClicked(
                        mode: ActionMode?,
                        item: MenuItem?,
                    ): Boolean {
                        if (item?.itemId == MENU_ANNOTATE) {
                            val pageText = this@apply.text.toString()
                            val start = selectionStart.coerceAtLeast(0)
                            val end = selectionEnd.coerceAtLeast(start)
                            val selected = pageText.substring(start, end.coerceAtMost(pageText.length))
                            onSelection(pageIndex, start, end, selected)
                            mode?.finish()
                            return true
                        }
                        return false
                    }

                    override fun onDestroyActionMode(mode: ActionMode?) {}
                }
            }
        },
        update = { view ->
            view.setTextColor(textColor)
            view.setBackgroundColor(bgColor)
            view.textSize = fontSizeSp
            view.setLineSpacing(0f, lineSpacing)
            val spannable = SpannableString(text)
            for (anno in annotations) {
                val s = anno.startOffset.coerceIn(0, text.length)
                val e = anno.endOffset.coerceIn(s, text.length)
                if (s < e) {
                    val color = parseColor(view.context, anno.color)
                    spannable.setSpan(
                        BackgroundColorSpan(color),
                        s,
                        e,
                        Spanned.SPAN_EXCLUSIVE_EXCLUSIVE,
                    )
                }
            }
            view.text = spannable
        },
        modifier = modifier,
    )
}

private const val MENU_ANNOTATE = 1

private fun parseColor(context: android.content.Context, color: String?): Int {
    return when (color?.lowercase()) {
        "yellow" -> 0xFFFFFFE0.toInt()
        "green" -> 0xFFE0FFE0.toInt()
        "blue" -> 0xFFE0F7FF.toInt()
        "pink" -> 0xFFFFE0F0.toInt()
        else -> ContextCompat.getColor(context, R.color.annotation_default)
    }
}
