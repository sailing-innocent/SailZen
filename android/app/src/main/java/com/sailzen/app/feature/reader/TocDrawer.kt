@file:OptIn(ExperimentalMaterial3Api::class)

package com.sailzen.app.feature.reader

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.ExpandLess
import androidx.compose.material.icons.filled.ExpandMore
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.ModalBottomSheet
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.mutableStateMapOf
import androidx.compose.runtime.remember
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import com.sailzen.app.R
import com.sailzen.app.core.data.db.CachedChapter

/**
 * 目录底部弹层（支持分卷折叠 + 无分卷自动退化扁平目录）：
 * - 打开时自动展开当前章节所在卷并滚动定位；
 * - 已读章节显示次级色圆点；已离线缓存正文的章节显示绿/第三色圆点。
 */
@Composable
fun TocDrawer(
    chapters: List<CachedChapter>,
    currentSortIndex: Int,
    cachedIds: Set<Int> = emptySet(),
    onSelect: (CachedChapter) -> Unit,
    onDismiss: () -> Unit,
) {
    val hasVolumes = remember(chapters) { chapters.any { !it.volumeTitle.isNullOrBlank() } }
    val volumeGroups = remember(chapters, hasVolumes) {
        if (!hasVolumes) emptyList()
        else {
            val grouped = LinkedHashMap<String, MutableList<CachedChapter>>()
            for (ch in chapters) {
                val key = ch.volumeTitle?.takeIf { it.isNotBlank() } ?: "未分卷"
                grouped.getOrPut(key) { mutableListOf() }.add(ch)
            }
            grouped.entries.map { it.key to it.value.toList() }
        }
    }

    val expandedMap = remember(volumeGroups) {
        mutableStateMapOf<String, Boolean>().apply {
            val currentVol = chapters.find { it.sortIndex == currentSortIndex }
                ?.volumeTitle?.takeIf { it.isNotBlank() }
                ?: volumeGroups.firstOrNull()?.first
            if (currentVol != null) put(currentVol, true)
        }
    }

    val listState = rememberLazyListState()
    LaunchedEffect(chapters, currentSortIndex, hasVolumes) {
        if (!hasVolumes) {
            val index = chapters.indexOfFirst { it.sortIndex == currentSortIndex }
            if (index >= 0) listState.scrollToItem(index)
        }
    }

    ModalBottomSheet(onDismissRequest = onDismiss) {
        Text(
            text = if (hasVolumes) {
                "${stringResource(R.string.reader_toc_title)} · ${volumeGroups.size} 卷 / ${chapters.size} 章"
            } else {
                stringResource(R.string.reader_toc_title)
            },
            style = MaterialTheme.typography.titleLarge,
            modifier = Modifier.padding(16.dp),
        )
        LazyColumn(state = listState) {
            if (!hasVolumes) {
                items(chapters, key = { it.id }) { chapter ->
                    TocItem(
                        chapter = chapter,
                        selected = chapter.sortIndex == currentSortIndex,
                        read = chapter.sortIndex < currentSortIndex,
                        cached = cachedIds.contains(chapter.id),
                        indented = false,
                        onClick = { onSelect(chapter) },
                    )
                }
            } else {
                for ((volTitle, volChapters) in volumeGroups) {
                    val isOpen = expandedMap[volTitle] == true
                    item(key = "vol_$volTitle") {
                        Row(
                            verticalAlignment = Alignment.CenterVertically,
                            modifier = Modifier
                                .fillMaxWidth()
                                .background(MaterialTheme.colorScheme.surfaceVariant.copy(alpha = 0.55f))
                                .clickable { expandedMap[volTitle] = !isOpen }
                                .padding(horizontal = 16.dp, vertical = 12.dp),
                        ) {
                            Text(
                                text = "$volTitle (${volChapters.size}章)",
                                style = MaterialTheme.typography.titleSmall,
                                fontWeight = FontWeight.SemiBold,
                                modifier = Modifier.weight(1f),
                            )
                            Icon(
                                imageVector = if (isOpen) Icons.Default.ExpandLess else Icons.Default.ExpandMore,
                                contentDescription = null,
                                tint = MaterialTheme.colorScheme.onSurfaceVariant,
                            )
                        }
                    }
                    if (isOpen) {
                        items(volChapters, key = { it.id }) { chapter ->
                            TocItem(
                                chapter = chapter,
                                selected = chapter.sortIndex == currentSortIndex,
                                read = chapter.sortIndex < currentSortIndex,
                                cached = cachedIds.contains(chapter.id),
                                indented = true,
                                onClick = { onSelect(chapter) },
                            )
                        }
                    }
                }
            }
        }
    }
}

@Composable
private fun TocItem(
    chapter: CachedChapter,
    selected: Boolean,
    read: Boolean,
    cached: Boolean,
    indented: Boolean,
    onClick: () -> Unit,
) {
    Row(
        verticalAlignment = Alignment.CenterVertically,
        modifier = Modifier
            .fillMaxWidth()
            .clickable(onClick = onClick)
            .padding(
                start = if (indented) 28.dp else 16.dp,
                end = 16.dp,
                top = 11.dp,
                bottom = 11.dp,
            ),
    ) {
        if (read) {
            Box(
                modifier = Modifier
                    .size(6.dp)
                    .clip(CircleShape)
                    .background(MaterialTheme.colorScheme.secondary),
            )
            Spacer(modifier = Modifier.width(10.dp))
        }
        Text(
            text = chapter.title.ifBlank { chapter.label },
            style = if (selected) MaterialTheme.typography.bodyLarge else MaterialTheme.typography.bodyMedium,
            color = when {
                selected -> MaterialTheme.colorScheme.primary
                read -> MaterialTheme.colorScheme.onSurfaceVariant
                else -> MaterialTheme.colorScheme.onSurface
            },
            modifier = Modifier.weight(1f),
        )
        if (cached) {
            Box(
                modifier = Modifier
                    .size(7.dp)
                    .clip(CircleShape)
                    .background(MaterialTheme.colorScheme.tertiary),
            )
        }
    }
}
