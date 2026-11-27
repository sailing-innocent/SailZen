@file:OptIn(ExperimentalMaterial3Api::class)

package com.sailzen.app.feature.reader

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.WindowInsets
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.LazyRow
import androidx.compose.foundation.lazy.items
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Book
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material.icons.filled.Settings
import androidx.compose.material3.Card
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.FilterChip
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewmodel.compose.viewModel
import com.sailzen.app.R
import com.sailzen.app.core.data.db.CachedWork
import kotlin.math.roundToInt

private enum class ShelfFilter(val label: String) {
    ALL("全部"),
    READING("在读"),
    MAINLINE("主线"),
    TECH("技术"),
    HISTORY("历史"),
    FICTION("小说"),
}

private fun pillarLabel(pillar: String): String = when (pillar) {
    "tech" -> "技术"
    "history" -> "历史"
    "aesthetics" -> "审美"
    "fiction" -> "小说"
    else -> "综合"
}

private fun workTypeLabel(type: String): String = when (type) {
    "paper" -> "论文"
    "book" -> "书籍"
    "article" -> "长文"
    "web_novel" -> "网文"
    else -> type
}

/**
 * 阅读首页：作品列表 + 素养/主线筛选 + 云端进度条 + 离线缓存管理。
 */
@Composable
fun ReaderHomeScreen(
    onOpenWork: (Int) -> Unit,
    onOpenSettings: () -> Unit = {},
    viewModel: ReaderHomeViewModel = viewModel(),
) {
    val state by viewModel.uiState.collectAsStateWithLifecycle()
    val syncState by viewModel.syncState.collectAsStateWithLifecycle()
    val cacheProgress by viewModel.cacheProgress.collectAsStateWithLifecycle()
    var filter by remember { mutableStateOf(ShelfFilter.ALL) }

    val filteredWorks = remember(state.works, filter) {
        when (filter) {
            ShelfFilter.ALL -> state.works
            ShelfFilter.READING -> state.works.filter { it.readingStatus == "reading" }
            ShelfFilter.MAINLINE -> state.works.filter { it.readingTrack in listOf("mainline", "project") }
            ShelfFilter.TECH -> state.works.filter { it.pillar == "tech" }
            ShelfFilter.HISTORY -> state.works.filter { it.pillar == "history" }
            ShelfFilter.FICTION -> state.works.filter { it.pillar == "fiction" }
        }
    }

    Scaffold(
        contentWindowInsets = WindowInsets(0, 0, 0, 0),
        topBar = {
            TopAppBar(
                title = { Text(stringResource(R.string.reader_title)) },
                actions = {
                    if (state.refreshing) {
                        CircularProgressIndicator(
                            modifier = Modifier
                                .width(22.dp)
                                .padding(end = 4.dp),
                            strokeWidth = 2.dp,
                        )
                    }
                    IconButton(onClick = { viewModel.refresh() }) {
                        Icon(Icons.Default.Refresh, contentDescription = null)
                    }
                    IconButton(onClick = onOpenSettings) {
                        Icon(Icons.Default.Settings, contentDescription = "设置")
                    }
                },
            )
        },
    ) { padding ->
        Column(
            modifier = Modifier
                .padding(padding)
                .fillMaxSize(),
        ) {
            if (!state.configured) {
                Text(
                    text = stringResource(R.string.reader_not_configured),
                    style = MaterialTheme.typography.bodyMedium,
                    color = MaterialTheme.colorScheme.error,
                    modifier = Modifier.padding(16.dp),
                )
            }
            SyncStatusChip(
                state = syncState,
                pendingAnnotations = 0,
                onRetrySync = { viewModel.refresh() },
                modifier = Modifier
                    .align(Alignment.CenterHorizontally)
                    .padding(vertical = 4.dp),
            )

            // 素养/轨道快速筛选条
            LazyRow(
                contentPadding = PaddingValues(horizontal = 16.dp, vertical = 4.dp),
                horizontalArrangement = Arrangement.spacedBy(8.dp),
            ) {
                items(ShelfFilter.entries) { f ->
                    FilterChip(
                        selected = filter == f,
                        onClick = { filter = f },
                        label = { Text(f.label) },
                    )
                }
            }

            cacheProgress?.let { progress ->
                Column(modifier = Modifier.padding(horizontal = 16.dp, vertical = 4.dp)) {
                    LinearProgressIndicator(
                        progress = {
                            if (progress.totalCount > 0) {
                                progress.cachedCount.toFloat() / progress.totalCount
                            } else {
                                0f
                            }
                        },
                        modifier = Modifier.fillMaxWidth(),
                    )
                    Text(
                        text = stringResource(
                            R.string.reader_cache_progress,
                            progress.cachedCount,
                            progress.totalCount,
                            progress.currentTitle,
                        ),
                        style = MaterialTheme.typography.labelSmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                        modifier = Modifier.padding(top = 2.dp),
                    )
                }
            }
            if (filteredWorks.isEmpty()) {
                EmptyWorks()
            } else {
                LazyColumn(modifier = Modifier.fillMaxSize()) {
                    items(filteredWorks, key = { it.id }) { work ->
                        WorkCard(
                            work = work,
                            cacheInfo = state.cacheInfo[work.id],
                            caching = state.cachingWorkId == work.id,
                            onClick = { onOpenWork(work.id) },
                            onCacheWhole = { viewModel.cacheWholeWork(work.id) },
                        )
                    }
                }
            }
        }
    }
}

@Composable
private fun WorkCard(
    work: CachedWork,
    cacheInfo: ReaderHomeViewModel.WorkCacheInfo?,
    caching: Boolean,
    onClick: () -> Unit,
    onCacheWhole: () -> Unit,
) {
    Card(
        modifier = Modifier
            .fillMaxWidth()
            .padding(horizontal = 16.dp, vertical = 4.dp)
            .clickable(onClick = onClick),
    ) {
        Column(modifier = Modifier.padding(12.dp)) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Text(
                    text = work.title,
                    style = MaterialTheme.typography.titleMedium,
                    modifier = Modifier.weight(1f),
                )
                Text(
                    text = "${pillarLabel(work.pillar)} · ${workTypeLabel(work.workType)}",
                    style = MaterialTheme.typography.labelSmall,
                    color = MaterialTheme.colorScheme.primary,
                )
            }
            if (!work.author.isNullOrBlank()) {
                Text(
                    text = work.author,
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
            if (!work.synopsis.isNullOrBlank()) {
                Text(
                    text = work.synopsis,
                    style = MaterialTheme.typography.bodyMedium,
                    modifier = Modifier.padding(top = 4.dp),
                    maxLines = 2,
                )
            }
            // 云端阅读进度条
            if (work.progressPct > 0f) {
                Row(
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(top = 6.dp),
                    verticalAlignment = Alignment.CenterVertically,
                ) {
                    LinearProgressIndicator(
                        progress = { (work.progressPct / 100f).coerceIn(0f, 1f) },
                        modifier = Modifier.weight(1f),
                    )
                    Spacer(modifier = Modifier.width(8.dp))
                    Text(
                        text = "${work.progressPct.roundToInt()}%",
                        style = MaterialTheme.typography.labelSmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                }
            }
            // 缓存概况行
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(top = 4.dp),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                val info = cacheInfo
                if (info != null && info.totalCount > 0) {
                    Text(
                        text = stringResource(
                            R.string.reader_cache_summary,
                            info.cachedCount,
                            info.totalCount,
                        ),
                        style = MaterialTheme.typography.labelSmall,
                        color = if (info.fullyCached) {
                            MaterialTheme.colorScheme.tertiary
                        } else {
                            MaterialTheme.colorScheme.onSurfaceVariant
                        },
                    )
                }
                Spacer(modifier = Modifier.weight(1f))
                if (caching) {
                    CircularProgressIndicator(
                        modifier = Modifier.width(16.dp),
                        strokeWidth = 2.dp,
                    )
                } else if (info != null && info.totalCount > 0 && !info.fullyCached) {
                    TextButton(onClick = onCacheWhole) {
                        Text(stringResource(R.string.reader_cache_whole))
                    }
                }
            }
        }
    }
}

@Composable
private fun EmptyWorks() {
    Column(
        modifier = Modifier.fillMaxSize(),
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.Center,
    ) {
        Icon(
            imageVector = Icons.Filled.Book,
            contentDescription = null,
            tint = MaterialTheme.colorScheme.outline,
        )
        Text(
            text = stringResource(R.string.reader_empty_works),
            style = MaterialTheme.typography.bodyMedium,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
            modifier = Modifier.padding(top = 8.dp),
        )
    }
}
