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
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.navigationBarsPadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.statusBarsPadding
import androidx.compose.foundation.pager.HorizontalPager
import androidx.compose.foundation.pager.rememberPagerState
import androidx.compose.foundation.shape.RoundedCornerShape
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
import androidx.compose.material3.Slider
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableFloatStateOf
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.runtime.snapshotFlow
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewmodel.compose.viewModel
import com.sailzen.app.R
import com.sailzen.app.core.data.db.CachedAnnotation
import com.sailzen.app.core.data.db.CachedChapter
import com.sailzen.app.feature.reader.ReaderViewModel.ReaderMode
import com.sailzen.app.feature.reader.ReaderViewModel.ReaderTheme
import kotlin.math.roundToInt

/**
 * 阅读页：
 * - 翻页模式：HorizontalPager + 原生 TextView 单页（可选字/批注/点按分区）；
 * - 滚动模式：**整章一次性排版进单个原生 TextView**（NestedScrollView 承载），
 *   滚动 = 纯位移，任何距离/方向零组合成本——全部加载好，直接上下滑动；
 * - 两种模式共用 ReaderTextView，选字/复制/批注交互一致；
 * - 进度可感知：滚动百分比浮层 + 底栏进度滑块（翻页跳页 / 滚动跳行）；
 * - 首帧渲染 Room 本地快照，网络只在后台刷新（离线优先）。
 */
@Composable
fun ReaderScreen(
    workId: Int,
    workTitle: String,
    onBack: () -> Unit,
    viewModel: ReaderViewModel = viewModel(),
) {
    val state by viewModel.uiState.collectAsStateWithLifecycle()
    val syncState by viewModel.syncState.collectAsStateWithLifecycle()
    val pendingAnnotations by viewModel.pendingAnnotationCount.collectAsStateWithLifecycle()
    var uiVisible by remember { mutableStateOf(false) }
    var showToc by remember { mutableStateOf(false) }
    var showSettings by remember { mutableStateOf(false) }
    var showAnnotations by remember { mutableStateOf(false) }
    var draftAnnotation by remember { mutableStateOf<CachedAnnotation?>(null) }
    var pendingDelete by remember { mutableStateOf<CachedAnnotation?>(null) }

    /** 滚动模式视图引用（底栏滑块跳转用）与进度状态（浮层/滑块共享） */
    val scrollViewRef = remember { mutableStateOf<ReaderScrollView?>(null) }
    var scrollPercent by remember(state.currentChapter?.id) { mutableIntStateOf(0) }
    var isScrolling by remember(state.currentChapter?.id) { mutableStateOf(false) }

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
        // 内容区：实测宽高（扣除 systemBars）驱动分页/行高
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

            val chapter = state.currentChapter
            when {
                // 章节无本地缓存（离线且未预取）：明确提示而非空白
                state.contentMissing && chapter?.rawText.isNullOrEmpty() -> MissingContent(
                    textColor = textColor,
                )

                // 在线拉取中的短暂空档：显示加载中而非空白/误导性空章节
                chapter?.rawText.isNullOrEmpty() -> EmptyReader(
                    text = stringResource(R.string.reader_loading_chapter),
                    color = textColor,
                )

                state.settings.mode == ReaderMode.PAGE -> PageReader(
                    state = state,
                    textColor = textColor,
                    bgColor = bgColor,
                    viewModel = viewModel,
                    swipeEnabled = uiVisible,
                    onContentTap = onContentTap,
                    onDraftAnnotation = { draftAnnotation = it },
                )

                else -> ScrollReader(
                    state = state,
                    chapter = chapter,
                    textColor = textColor,
                    bgColor = bgColor,
                    viewModel = viewModel,
                    onContentTap = onContentTap,
                    onDraftAnnotation = { draftAnnotation = it },
                    onScrollProgress = { percent, lineIndex, scrolling ->
                        isScrolling = scrolling
                        if (percent != scrollPercent) scrollPercent = percent
                        state.scrollLines.getOrNull(lineIndex)
                            ?.let { viewModel.onScrollCharOffset(it.startOffset) }
                    },
                    onViewReady = { scrollViewRef.value = it },
                )
            }

            // 滚动进度浮层（滚动中显示，独立于内容视图）
            if (state.settings.mode == ReaderMode.SCROLL) {
                AnimatedVisibility(
                    visible = isScrolling && state.scrollLines.isNotEmpty(),
                    modifier = Modifier
                        .align(Alignment.BottomEnd)
                        .padding(end = 16.dp, bottom = 24.dp),
                    enter = fadeIn(),
                    exit = fadeOut(),
                ) {
                    Surface(
                        shape = RoundedCornerShape(12.dp),
                        color = MaterialTheme.colorScheme.surfaceVariant.copy(alpha = 0.9f),
                    ) {
                        Text(
                            text = stringResource(R.string.reader_progress_percent, scrollPercent),
                            style = MaterialTheme.typography.labelMedium,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                            modifier = Modifier.padding(horizontal = 10.dp, vertical = 4.dp),
                        )
                    }
                }
            }
        }

        // 沉浸式顶栏 + 同步状态 chip
        AnimatedVisibility(
            visible = uiVisible,
            modifier = Modifier.align(Alignment.TopCenter),
            enter = fadeIn(),
            exit = fadeOut(),
        ) {
            Column {
                ReaderTopBar(
                    title = state.currentChapter?.title ?: state.workTitle,
                    onBack = onBack,
                    onShowToc = { showToc = true },
                    onShowAnnotations = { showAnnotations = true },
                    onShowSettings = { showSettings = true },
                )
                SyncStatusChip(
                    state = syncState,
                    pendingAnnotations = pendingAnnotations,
                    onRetrySync = { viewModel.refreshSync() },
                    modifier = Modifier
                        .align(Alignment.CenterHorizontally)
                        .padding(top = 4.dp),
                )
            }
        }

        // 沉浸式底栏（含进度滑块）
        AnimatedVisibility(
            visible = uiVisible,
            modifier = Modifier.align(Alignment.BottomCenter),
            enter = fadeIn(),
            exit = fadeOut(),
        ) {
            ReaderBottomBar(
                state = state,
                scrollPercent = scrollPercent,
                onJumpToLine = { line -> scrollViewRef.value?.scrollToLine(line) },
                onJumpPage = { viewModel.goToPage(it) },
                onPrevChapter = { viewModel.previousChapter() },
                onNextChapter = { viewModel.nextChapter() },
            )
        }
    }

    if (showToc) {
        TocDrawer(
            chapters = state.chapters,
            currentSortIndex = state.currentSortIndex,
            cachedIds = state.cachedChapterIds,
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
    /** 手势翻页仅在 UI 唤出后可用：沉浸式阅读下禁用，避免斜向滑动手势被
     *  pager 误判为翻页而与手指对抗（实际操作卡顿来源）。点按左右 1/3 翻页始终可用。 */
    swipeEnabled: Boolean,
    onContentTap: (Float) -> Unit,
    onDraftAnnotation: (CachedAnnotation) -> Unit,
) {
    val pages = state.pages
    if (pages.isEmpty()) {
        EmptyReader(text = stringResource(R.string.reader_empty_chapter))
        return
    }

    val pagerState = rememberPagerState(pageCount = { pages.size })

    // 章节切换：pager 复位到第 0 页（由 ViewModel 的 currentPage 二次校正）
    LaunchedEffect(state.currentChapter?.id) {
        pagerState.scrollToPage(0)
    }

    // ViewModel 驱动的页码变化（目录选中/进度恢复/滑块跳转）：pager 未在滚动时跟随
    LaunchedEffect(state.currentPage) {
        val target = state.currentPage.coerceIn(0, pages.size - 1)
        if (pagerState.currentPage != target && !pagerState.isScrollInProgress) {
            pagerState.scrollToPage(target)
        }
    }

    // 用户滑动单向驱动：仅在 settled 后回写 ViewModel（防双向回环）。
    // 页码比较在 ViewModel 内做，避免组合期捕获的 state 过期。
    LaunchedEffect(pagerState) {
        snapshotFlow { pagerState.settledPage }.collect { page ->
            viewModel.onPageSettled(page)
        }
    }

    HorizontalPager(
        state = pagerState,
        userScrollEnabled = swipeEnabled,
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
 * 滚动模式：**整章单视图**。章节全文一次性排版进原生 TextView，
 * 滚动是纯位移（无组合/测量），选字/批注/点按复用 ReaderTextView 原生交互。
 * 进度经行高换算上报（行序列来自排版引擎，行高恒定）。
 */
@Composable
private fun ScrollReader(
    state: ReaderViewModel.UiState,
    chapter: CachedChapter,
    textColor: Color,
    bgColor: Color,
    viewModel: ReaderViewModel,
    onContentTap: (Float) -> Unit,
    onDraftAnnotation: (CachedAnnotation) -> Unit,
    onScrollProgress: (percent: Int, lineIndex: Int, scrolling: Boolean) -> Unit,
    onViewReady: (ReaderScrollView) -> Unit,
) {
    val layout = state.scrollLayout ?: run {
        EmptyReader(text = stringResource(R.string.reader_loading_chapter), color = textColor)
        return
    }
    val paragraphRanges = remember(chapter.id) {
        ParagraphSplitter.split(chapter.rawText).map { it.startOffset..it.endOffset }
    }
    val restoreLineIndex = remember(chapter.id, state.scrollLines) {
        if (state.scrollLines.isEmpty()) {
            0
        } else {
            state.scrollLines
                .indexOfLast { it.startOffset <= state.charOffset }
                .coerceIn(0, state.scrollLines.lastIndex)
        }
    }

    ScrollChapterView(
        text = chapter.rawText,
        annotations = state.annotations,
        paragraphRanges = paragraphRanges,
        fontSizeSp = state.settings.fontSize.toFloat(),
        lineSpacing = state.settings.lineHeight,
        paragraphSpacingPx = 8.dpToPx(),
        paddingPx = 16.dpToPx(),
        textColor = textColor.toArgbInt(),
        bgColor = bgColor.toArgbInt(),
        lineAdvancePx = layout.lineAdvancePx,
        restoreLineIndex = restoreLineIndex,
        chapterId = chapter.id,
        onScrollProgress = onScrollProgress,
        onSelection = { start, end, selectedText ->
            viewModel.onScrollSelection(start, end, selectedText)?.let(onDraftAnnotation)
        },
        onAnnotationClick = onDraftAnnotation,
        onTap = onContentTap,
        onViewReady = onViewReady,
        modifier = Modifier.fillMaxSize(),
    )
}

@Composable
private fun ReaderBottomBar(
    state: ReaderViewModel.UiState,
    scrollPercent: Int,
    onJumpToLine: (Int) -> Unit,
    onJumpPage: (Int) -> Unit,
    onPrevChapter: () -> Unit,
    onNextChapter: () -> Unit,
) {
    BottomAppBar {
        Column(modifier = Modifier.fillMaxWidth()) {
            // 进度滑块：滚动模式按百分比跳行 / 翻页模式按页跳转
            when (state.settings.mode) {
                ReaderMode.PAGE -> {
                    val pageCount = state.pages.size
                    if (pageCount > 1) {
                        var dragValue by remember(pageCount) { mutableFloatStateOf(-1f) }
                        Slider(
                            value = if (dragValue >= 0f) dragValue else state.currentPage.toFloat(),
                            onValueChange = { dragValue = it },
                            onValueChangeFinished = {
                                if (dragValue >= 0f) onJumpPage(dragValue.roundToInt())
                                dragValue = -1f
                            },
                            valueRange = 0f..(pageCount - 1).toFloat(),
                            modifier = Modifier
                                .fillMaxWidth()
                                .height(24.dp),
                        )
                    }
                }

                ReaderMode.SCROLL -> {
                    if (state.scrollLines.size > 1) {
                        var dragValue by remember(state.scrollLines) { mutableFloatStateOf(-1f) }
                        Slider(
                            value = if (dragValue >= 0f) dragValue else scrollPercent / 100f,
                            onValueChange = { value ->
                                dragValue = value
                                val line = (value * (state.scrollLines.size - 1)).roundToInt()
                                onJumpToLine(line)
                            },
                            onValueChangeFinished = { dragValue = -1f },
                            valueRange = 0f..1f,
                            modifier = Modifier
                                .fillMaxWidth()
                                .height(24.dp),
                        )
                    }
                }
            }

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
                when {
                    state.settings.mode == ReaderMode.PAGE && state.pages.isNotEmpty() ->
                        Text(
                            text = "${state.currentPage + 1} / ${state.pages.size}",
                            style = MaterialTheme.typography.bodyMedium,
                        )

                    state.settings.mode == ReaderMode.SCROLL && state.scrollLines.isNotEmpty() ->
                        Text(
                            text = stringResource(R.string.reader_progress_percent, scrollPercent),
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
}

@Composable
private fun EmptyReader(text: String, color: Color? = null) {
    Box(
        modifier = Modifier.fillMaxSize(),
        contentAlignment = Alignment.Center,
    ) {
        Text(
            text = text,
            style = MaterialTheme.typography.bodyMedium,
            color = color ?: MaterialTheme.colorScheme.onSurface,
        )
    }
}

/** 本章无本地缓存（离线且未预取）时的明确提示，避免「空白即卡顿」的误判 */
@Composable
private fun MissingContent(textColor: Color) {
    Box(
        modifier = Modifier.fillMaxSize(),
        contentAlignment = Alignment.Center,
    ) {
        Text(
            text = stringResource(R.string.reader_content_missing),
            style = MaterialTheme.typography.bodyMedium,
            color = textColor,
        )
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
