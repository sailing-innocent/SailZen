@file:OptIn(ExperimentalMaterial3Api::class, ExperimentalFoundationApi::class)

package com.sailzen.app.feature.reader

import androidx.activity.compose.BackHandler
import androidx.compose.foundation.ExperimentalFoundationApi
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
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
import androidx.compose.animation.AnimatedVisibility
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.BottomAppBar
import androidx.compose.material3.Button
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.platform.LocalContext
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
import com.sailzen.app.feature.reader.ReaderViewModel.ReaderSettings
import com.sailzen.app.feature.reader.ReaderViewModel.ReaderTheme
import kotlinx.coroutines.launch

@Composable
fun ReaderScreen(
    workId: Int,
    workTitle: String,
    onBack: () -> Unit,
    viewModel: ReaderViewModel = viewModel(),
) {
    val state by viewModel.uiState.collectAsStateWithLifecycle()
    var uiVisible by remember { mutableStateOf(true) }
    var showToc by remember { mutableStateOf(false) }
    var showSettings by remember { mutableStateOf(false) }
    var showAnnotations by remember { mutableStateOf(false) }
    var draftAnnotation by remember { mutableStateOf<CachedAnnotation?>(null) }

    LaunchedEffect(workId) {
        viewModel.loadWork(workId, workTitle)
    }

    BackHandler { onBack() }

    val bgColor = if (state.settings.theme == ReaderTheme.DARK) Color(0xFF1A1A1A) else Color(0xFFF5F0E6)
    val textColor = if (state.settings.theme == ReaderTheme.DARK) Color(0xFFE0DCC8) else Color(0xFF2B2B2B)

    Scaffold(
        topBar = {
            AnimatedVisibility(visible = uiVisible) {
                TopAppBar(
                    title = {
                        Text(
                            text = state.currentChapter?.title ?: workTitle,
                            maxLines = 1,
                            overflow = TextOverflow.Ellipsis,
                        )
                    },
                    navigationIcon = {
                        IconButton(onClick = onBack) {
                            Icon(Icons.AutoMirrored.Filled.ArrowBack, contentDescription = null)
                        }
                    },
                    actions = {
                        IconButton(onClick = { showToc = true }) {
                            Icon(Icons.Default.List, contentDescription = null)
                        }
                        IconButton(onClick = { showAnnotations = true }) {
                            Icon(Icons.Default.MoreVert, contentDescription = null)
                        }
                        IconButton(onClick = { showSettings = true }) {
                            Icon(Icons.Default.Settings, contentDescription = null)
                        }
                    },
                )
            }
        },
        bottomBar = {
            AnimatedVisibility(visible = uiVisible) {
                ReaderBottomBar(
                    state = state,
                    onPrevChapter = { viewModel.previousChapter() },
                    onNextChapter = { viewModel.nextChapter() },
                    onPageChanged = { viewModel.goToPage(it) },
                )
            }
        },
    ) { padding ->
        Box(
            modifier = Modifier
                .padding(padding)
                .fillMaxSize()
                .background(bgColor),
        ) {
            when (state.settings.mode) {
                ReaderMode.PAGE -> PageReader(state, textColor, bgColor, viewModel)
                ReaderMode.SCROLL -> ScrollReader(state, textColor, bgColor, viewModel)
            }
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
            onDelete = { viewModel.deleteAnnotation(it) },
            onDismiss = { showAnnotations = false },
        )
    }

    draftAnnotation?.let { annotation ->
        AnnotationEditDialog(
            annotation = annotation,
            onSave = { note ->
                viewModel.saveAnnotation(annotation, note)
                draftAnnotation = null
            },
            onDismiss = { draftAnnotation = null },
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
private fun PageReader(
    state: ReaderViewModel.UiState,
    textColor: Color,
    bgColor: Color,
    viewModel: ReaderViewModel,
) {
    val context = LocalContext.current
    val density = LocalDensity.current
    val pages = state.pages

    LaunchedEffect(state.currentChapter) {
        val chapter = state.currentChapter ?: return@LaunchedEffect
        with(density) {
            val spec = ReaderTextEngine.LayoutSpec(
                widthPx = context.resources.displayMetrics.widthPixels - 48,
                heightPx = context.resources.displayMetrics.heightPixels - 300,
                fontSizeSp = state.settings.fontSize.toFloat(),
                lineSpacing = state.settings.lineHeight,
                paragraphSpacingPx = (8.dp.toPx()).toInt(),
            )
            viewModel.setPageSpec(spec)
        }
    }

    if (pages.isNotEmpty()) {
        val pagerState = rememberPagerState(pageCount = { pages.size })
        LaunchedEffect(state.currentPage) {
            pagerState.scrollToPage(state.currentPage)
        }
        LaunchedEffect(pagerState.currentPage) {
            if (pagerState.currentPage != state.currentPage) {
                viewModel.goToPage(pagerState.currentPage)
            }
        }
        HorizontalPager(
            state = pagerState,
            modifier = Modifier.fillMaxSize(),
        ) { pageIndex ->
            val page = pages[pageIndex]
            val annotations = state.annotations.filter {
                it.startOffset < page.endOffset && it.endOffset > page.startOffset
            }
            ReaderPageView(
                text = page.text,
                pageIndex = pageIndex,
                annotations = annotations.map {
                    it.copy(
                        startOffset = (it.startOffset - page.startOffset).coerceAtLeast(0),
                        endOffset = (it.endOffset - page.startOffset).coerceAtMost(page.text.length),
                    )
                },
                fontSizeSp = state.settings.fontSize.toFloat(),
                lineSpacing = state.settings.lineHeight,
                textColor = textColor.toArgbInt(),
                bgColor = bgColor.toArgbInt(),
                onSelection = { pIdx, start, end, selectedText ->
                    viewModel.onSelection(pIdx, start, end, selectedText)?.let { annotation ->
                        viewModel.saveAnnotation(annotation, "")
                    }
                },
                modifier = Modifier.fillMaxSize(),
            )
        }
    } else if (!state.loading) {
        EmptyReader(text = stringResource(R.string.reader_empty_chapter))
    }
}

@Composable
private fun ScrollReader(
    state: ReaderViewModel.UiState,
    textColor: Color,
    bgColor: Color,
    viewModel: ReaderViewModel,
) {
    val text = state.currentChapter?.rawText ?: ""
    val listState = rememberLazyListState()
    val paragraphs = remember(text) { text.split("\n") }
    LazyColumn(
        state = listState,
        modifier = Modifier.fillMaxSize(),
    ) {
                        itemsIndexed(paragraphs, key = { index, _ -> index }) { _, paragraph ->
            Text(
                text = paragraph,
                color = textColor,
                fontSize = state.settings.fontSize.sp,
                lineHeight = (state.settings.fontSize * state.settings.lineHeight).sp,
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(horizontal = 16.dp, vertical = 8.dp),
            )
        }
    }
}

@Composable
private fun ReaderBottomBar(
    state: ReaderViewModel.UiState,
    onPrevChapter: () -> Unit,
    onNextChapter: () -> Unit,
    onPageChanged: (Int) -> Unit,
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

@Composable
private fun AnnotationEditDialog(
    annotation: CachedAnnotation,
    onSave: (String) -> Unit,
    onDismiss: () -> Unit,
) {
    var note by remember(annotation) { mutableStateOf(annotation.note) }
    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text(stringResource(R.string.annotation_dialog_title)) },
        text = {
            Column {
                Text(
                    text = annotation.selectedText,
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                    maxLines = 3,
                    overflow = TextOverflow.Ellipsis,
                )
                Spacer(modifier = Modifier.height(8.dp))
                OutlinedTextField(
                    value = note,
                    onValueChange = { note = it },
                    label = { Text(stringResource(R.string.annotation_hint)) },
                    singleLine = false,
                    minLines = 3,
                )
            }
        },
        confirmButton = {
            Button(onClick = { onSave(note) }) {
                Text(stringResource(R.string.dialog_confirm))
            }
        },
        dismissButton = {
            TextButton(onClick = onDismiss) {
                Text(stringResource(R.string.dialog_cancel))
            }
        },
    )
}
