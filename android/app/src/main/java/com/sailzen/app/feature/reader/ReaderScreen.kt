@file:OptIn(ExperimentalMaterial3Api::class, ExperimentalFoundationApi::class)

package com.sailzen.app.feature.reader

import androidx.activity.compose.BackHandler
import androidx.compose.animation.AnimatedVisibility
import androidx.compose.animation.fadeIn
import androidx.compose.animation.fadeOut
import androidx.compose.foundation.ExperimentalFoundationApi
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.BoxWithConstraints
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.navigationBarsPadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.statusBarsPadding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.itemsIndexed
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.foundation.pager.HorizontalPager
import androidx.compose.foundation.pager.rememberPagerState
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.filled.List
import androidx.compose.material.icons.filled.MoreVert
import androidx.compose.material.icons.filled.Settings
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.BottomAppBar
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.runtime.snapshotFlow
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.LinkAnnotation
import androidx.compose.ui.text.SpanStyle
import androidx.compose.ui.text.buildAnnotatedString
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewmodel.compose.viewModel
import com.sailzen.app.R
import com.sailzen.app.core.data.db.CachedAnnotation
import com.sailzen.app.feature.reader.ReaderViewModel.ReaderMode
import com.sailzen.app.feature.reader.ReaderViewModel.ReaderTheme

/**
 * 阅读页（对标 NovelDokusha 沉浸式交互）：
 * - 中央 1/3 点按切换顶/底栏，左右 1/3 翻页（修 U6）；
 * - 内容区实测宽高驱动分页，不再使用魔法常量（修 B3）；
 * - pager 单向驱动 + 守卫回写，消除双向绑定回环（修 B5）；
 * - 选中/高亮统一走 AnnotationEditorSheet，保存前不落库（修 U1）。
 */
@Composable
fun ReaderScreen(
    workId: Int,
    workTitle: String,
    onBack: () -> Unit,
    viewModel: ReaderViewModel = viewModel(),
) {
    val state by viewModel.uiState.collectAsStateWithLifecycle()
    var uiVisible by remember { mutableStateOf(false) }
    var showToc by remember { mutableStateOf(false) }
    var showSettings by remember { mutableStateOf(false) }
    var showAnnotations by remember { mutableStateOf(false) }
    var draftAnnotation by remember { mutableStateOf<CachedAnnotation?>(null) }
    var pendingDelete by remember { mutableStateOf<CachedAnnotation?>(null) }

    LaunchedEffect(workId) {
        viewModel.loadWork(workId, workTitle)
    }

    BackHandler { onBack() }

    val bgColor = if (state.settings.theme == ReaderTheme.DARK) Color(0xFF1A1A1A) else Color(0xFFF5F0E6)
    val textColor = if (state.settings.theme == ReaderTheme.DARK) Color(0xFFE0DCC8) else Color(0xFF2B2B2B)

    /** 点按分区：中央切换 UI，左右翻页（滚动模式下左右同样切换 UI） */
    val onContentTap: (Float) -> Unit = { fraction ->
        when {
            fraction in (1f / 3f)..(2f / 3f) -> uiVisible = !uiVisible
            state.settings.mode == ReaderMode.PAGE && fraction < 1f / 3f ->
                viewModel.goToPage(state.currentPage - 1)
            state.settings.mode == ReaderMode.PAGE -> viewModel.goToPage(state.currentPage + 1)
            else -> uiVisible = !uiVisible
        }
    }

    Box(modifier = Modifier.fillMaxSize()) {
        // 内容区：实测宽高（扣除 systemBars）驱动分页
        BoxWithConstraints(
            modifier = Modifier
                .fillMaxSize()
                .background(bgColor)
                .statusBarsPadding()
                .navigationBarsPadding(),
        ) {
            val widthPx = constraints.maxWidth
            val heightPx = constraints.maxHeight
            val density = LocalDensity.current
            LaunchedEffect(
                widthPx,
                heightPx,
                state.settings.fontSize,
                state.settings.lineHeight,
                state.currentChapter?.id,
            ) {
                if (widthPx <= 0 || heightPx <= 0) return@LaunchedEffect
                with(density) {
                    viewModel.setPageSpec(
                        ReaderTextEngine.LayoutSpec(
                            widthPx = widthPx,
                            heightPx = heightPx,
                            fontSizePx = state.settings.fontSize.sp.toPx(),
                            lineSpacingMult = state.settings.lineHeight,
                            paragraphSpacingPx = (8.dp.toPx()).toInt(),
                            paddingPx = (16.dp.toPx()).toInt(),
                        ),
                    )
                }
            }

            when (state.settings.mode) {
                ReaderMode.PAGE -> PageReader(
                    state = state,
                    textColor = textColor,
                    bgColor = bgColor,
                    viewModel = viewModel,
                    onContentTap = onContentTap,
                    onDraftAnnotation = { draftAnnotation = it },
                )
                ReaderMode.SCROLL -> ScrollReader(
                    state = state,
                    textColor = textColor,
                    viewModel = viewModel,
                    onDraftAnnotation = { draftAnnotation = it },
                )
            }
        }

        // 沉浸式顶栏
        AnimatedVisibility(
            visible = uiVisible,
            modifier = Modifier.align(Alignment.TopCenter),
            enter = fadeIn(),
            exit = fadeOut(),
        ) {
            Column {
                ReaderTopBar(
                    title = state.currentChapter?.title ?: workTitle,
                    onBack = onBack,
                    onShowToc = { showToc = true },
                    onShowAnnotations = { showAnnotations = true },
                    onShowSettings = { showSettings = true },
                )
            }
        }

        // 沉浸式底栏
        AnimatedVisibility(
            visible = uiVisible,
            modifier = Modifier.align(Alignment.BottomCenter),
            enter = fadeIn(),
            exit = fadeOut(),
        ) {
            ReaderBottomBar(
                state = state,
                onPrevChapter = { viewModel.previousChapter() },
                onNextChapter = { viewModel.nextChapter() },
            )
        }
    }

    if (showToc) {
        TocDrawer(
            chapters = state.chapters,
            currentSortIndex = state.currentSortIndex,
            onSelect = { chapter ->
                viewModel.loadChapter(chapter, 0)
                showToc = false
            },
            onDismiss = { showToc = false },
        )
    }

    if (showAnnotations) {
        AnnotationSheet(
            annotations = state.annotations,
            onEdit = { annotation ->
                draftAnnotation = annotation
                showAnnotations = false
            },
            onDelete = {
                pendingDelete = it
                showAnnotations = false
            },
            onDismiss = { showAnnotations = false },
        )
    }

    draftAnnotation?.let { annotation ->
        AnnotationEditorSheet(
            annotation = annotation,
            onSave = { note, color ->
                val updated = annotation.copy(note = note, color = color)
                if (annotation.localId == 0L) {
                    viewModel.createAnnotation(updated)
                } else {
                    viewModel.updateAnnotation(updated)
                }
                draftAnnotation = null
            },
            onDelete = if (annotation.localId != 0L) {
                {
                    pendingDelete = annotation
                    draftAnnotation = null
                }
            } else {
                null
            },
            onDismiss = {
                viewModel.discardDraft(annotation)
                draftAnnotation = null
            },
        )
    }

    pendingDelete?.let { annotation ->
        AlertDialog(
            onDismissRequest = { pendingDelete = null },
            title = { Text(stringResource(R.string.annotation_delete_title)) },
            text = { Text(stringResource(R.string.annotation_delete_confirm)) },
            confirmButton = {
                TextButton(
                    onClick = {
                        viewModel.deleteAnnotation(annotation)
                        pendingDelete = null
                    },
                ) {
                    Text(stringResource(R.string.annotation_delete), color = MaterialTheme.colorScheme.error)
                }
            },
            dismissButton = {
                TextButton(onClick = { pendingDelete = null }) {
                    Text(stringResource(R.string.dialog_cancel))
                }
            },
        )
    }

    if (showSettings) {
        ReaderSettingsDialog(
            settings = state.settings,
            onSave = {
                viewModel.updateSettings(it)
                showSettings = false
            },
            onDismiss = { showSettings = false },
        )
    }
}

@Composable
private fun ReaderTopBar(
    title: String,
    onBack: () -> Unit,
    onShowToc: () -> Unit,
    onShowAnnotations: () -> Unit,
    onShowSettings: () -> Unit,
) {
    TopAppBar(
        modifier = Modifier.statusBarsPadding(),
        title = {
            Text(text = title, maxLines = 1, overflow = TextOverflow.Ellipsis)
        },
        navigationIcon = {
            IconButton(onClick = onBack) {
                Icon(Icons.AutoMirrored.Filled.ArrowBack, contentDescription = null)
            }
        },
        actions = {
            IconButton(onClick = onShowToc) {
                Icon(Icons.Default.List, contentDescription = null)
            }
            IconButton(onClick = onShowAnnotations) {
                Icon(Icons.Default.MoreVert, contentDescription = null)
            }
            IconButton(onClick = onShowSettings) {
                Icon(Icons.Default.Settings, contentDescription = null)
            }
        },
    )
}

@Composable
private fun PageReader(
    state: ReaderViewModel.UiState,
    textColor: Color,
    bgColor: Color,
    viewModel: ReaderViewModel,
    onContentTap: (Float) -> Unit,
    onDraftAnnotation: (CachedAnnotation) -> Unit,
) {
    val pages = state.pages
    if (pages.isEmpty()) {
        if (!state.loading) {
            EmptyReader(text = stringResource(R.string.reader_empty_chapter))
        }
        return
    }

    val pagerState = rememberPagerState(pageCount = { pages.size })

    // 章节切换：pager 复位到第 0 页（由 ViewModel 的 currentPage 二次校正）
    LaunchedEffect(state.currentChapter?.id) {
        pagerState.scrollToPage(0)
    }

    // ViewModel 驱动的页码变化（目录选中/进度恢复）：pager 未在滚动时跟随
    LaunchedEffect(state.currentPage) {
        val target = state.currentPage.coerceIn(0, pages.size - 1)
        if (pagerState.currentPage != target && !pagerState.isScrollInProgress) {
            pagerState.scrollToPage(target)
        }
    }

    // 用户滑动单向驱动：仅在 settled 后回写 ViewModel（修 B5 双向回环）。
    // 注意不可捕获组合期的 state（会过期），页码比较在 ViewModel 内做。
    LaunchedEffect(pagerState) {
        snapshotFlow { pagerState.settledPage }.collect { page ->
            viewModel.onPageSettled(page)
        }
    }

    HorizontalPager(
        state = pagerState,
        modifier = Modifier.fillMaxSize(),
    ) { pageIndex ->
        val page = pages[pageIndex]
        val annotations = state.annotations
            .filter { it.startOffset < page.endOffset && it.endOffset > page.startOffset }
            .map {
                it.copy(
                    startOffset = (it.startOffset - page.startOffset).coerceAtLeast(0),
                    endOffset = (it.endOffset - page.startOffset).coerceAtMost(page.text.length),
                )
            }
        ReaderPageView(
            text = page.text,
            pageIndex = pageIndex,
            annotations = annotations,
            paragraphRanges = page.paragraphRanges,
            pageStartOffset = page.startOffset,
            fontSizeSp = state.settings.fontSize.toFloat(),
            lineSpacing = state.settings.lineHeight,
            paragraphSpacingPx = 8.dpToPx(),
            paddingPx = 16.dpToPx(),
            textColor = textColor.toArgbInt(),
            bgColor = bgColor.toArgbInt(),
            onSelection = { pIdx, start, end, selectedText ->
                viewModel.onSelection(pIdx, start, end, selectedText)?.let(onDraftAnnotation)
            },
            onAnnotationClick = onDraftAnnotation,
            onTap = onContentTap,
            modifier = Modifier.fillMaxSize(),
        )
    }
}

/**
 * 滚动模式：与翻页模式共用 ParagraphSplitter 的段落切分与全局偏移体系，
 * 批注高亮用 AnnotatedString + LinkAnnotation 就地点击查看/编辑，
 * 阅读进度以首个可见段落的首字符偏移（全局）持久化。
 */
@Composable
private fun ScrollReader(
    state: ReaderViewModel.UiState,
    textColor: Color,
    viewModel: ReaderViewModel,
    onDraftAnnotation: (CachedAnnotation) -> Unit,
) {
    val text = state.currentChapter?.rawText ?: ""
    val listState = rememberLazyListState()
    val paragraphs = remember(text) { ParagraphSplitter.split(text) }
    val fontSize = state.settings.fontSize
    val lineHeight = state.settings.lineHeight

    // 章节切换恢复阅读位置：charOffset 所属段落（最后一个 startOffset <= 目标偏移的段）
    LaunchedEffect(state.currentChapter?.id, paragraphs) {
        if (paragraphs.isEmpty()) return@LaunchedEffect
        val charOffset = viewModel.uiState.value.charOffset
        val index = paragraphs.indexOfLast { it.startOffset <= charOffset }
            .coerceIn(0, paragraphs.lastIndex)
        listState.scrollToItem(index)
    }

    // 进度上报：首个可见段落的全局起始偏移
    LaunchedEffect(listState, paragraphs) {
        snapshotFlow { listState.firstVisibleItemIndex }.collect { index ->
            paragraphs.getOrNull(index)?.let { viewModel.onScrollCharOffset(it.startOffset) }
        }
    }

    LazyColumn(
        state = listState,
        modifier = Modifier.fillMaxSize(),
    ) {
        itemsIndexed(paragraphs, key = { index, _ -> index }) { _, paragraph ->
            val annotated = remember(
                paragraph.text,
                paragraph.startOffset,
                state.annotations,
            ) {
                buildAnnotatedString {
                    append(paragraph.text)
                    val overlaps = state.annotations.filter {
                        it.startOffset < paragraph.endOffset && it.endOffset > paragraph.startOffset
                    }
                    for (anno in overlaps) {
                        val s = (anno.startOffset - paragraph.startOffset)
                            .coerceIn(0, paragraph.text.length)
                        val e = (anno.endOffset - paragraph.startOffset)
                            .coerceIn(s, paragraph.text.length)
                        if (s >= e) continue
                        addStyle(
                            SpanStyle(background = Color(annotationColorArgb(anno.color, 0xFFFFFFE0.toInt()))),
                            s,
                            e,
                        )
                        addLink(
                            LinkAnnotation.Clickable(
                                tag = "anno_${anno.localId}_${anno.hashCode()}",
                                linkInteractionListener = { onDraftAnnotation(anno) },
                            ),
                            s,
                            e,
                        )
                    }
                }
            }
            Text(
                text = annotated,
                color = textColor,
                fontSize = fontSize.sp,
                lineHeight = (fontSize * lineHeight).sp,
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(horizontal = 16.dp, vertical = 4.dp),
            )
        }
    }
}

@Composable
private fun ReaderBottomBar(
    state: ReaderViewModel.UiState,
    onPrevChapter: () -> Unit,
    onNextChapter: () -> Unit,
) {
    BottomAppBar {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(horizontal = 8.dp),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically,
        ) {
            TextButton(onClick = onPrevChapter, enabled = state.currentSortIndex > 0) {
                Text(stringResource(R.string.reader_prev_chapter))
            }
            if (state.settings.mode == ReaderMode.PAGE && state.pages.isNotEmpty()) {
                Text(
                    text = "${state.currentPage + 1} / ${state.pages.size}",
                    style = MaterialTheme.typography.bodyMedium,
                )
            }
            TextButton(
                onClick = onNextChapter,
                enabled = state.currentSortIndex < state.chapters.size - 1,
            ) {
                Text(stringResource(R.string.reader_next_chapter))
            }
        }
    }
}

@Composable
private fun EmptyReader(text: String) {
    Box(
        modifier = Modifier.fillMaxSize(),
        contentAlignment = Alignment.Center,
    ) {
        Text(text = text, style = MaterialTheme.typography.bodyMedium)
    }
}

private fun Color.toArgbInt(): Int {
    return android.graphics.Color.argb(
        (alpha * 255).toInt(),
        (red * 255).toInt(),
        (green * 255).toInt(),
        (blue * 255).toInt(),
    )
}

/** dp → px 辅助（Compose 环境） */
@Composable
private fun Int.dpToPx(): Int = with(LocalDensity.current) { this@dpToPx.dp.toPx() }.toInt()
