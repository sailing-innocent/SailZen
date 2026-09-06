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
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.ModalBottomSheet
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.unit.dp
import com.sailzen.app.R
import com.sailzen.app.core.data.db.CachedChapter

/**
 * 目录底部弹层：打开时自动滚动到当前章节（修 U5），
 * 已读章节（sortIndex 小于当前）显示次级色圆点。
 */
@Composable
fun TocDrawer(
    chapters: List<CachedChapter>,
    currentSortIndex: Int,
    onSelect: (CachedChapter) -> Unit,
    onDismiss: () -> Unit,
) {
    val listState = rememberLazyListState()

    LaunchedEffect(chapters, currentSortIndex) {
        val index = chapters.indexOfFirst { it.sortIndex == currentSortIndex }
        if (index >= 0) {
            listState.scrollToItem(index)
        }
    }

    ModalBottomSheet(onDismissRequest = onDismiss) {
        Text(
            text = stringResource(R.string.reader_toc_title),
            style = MaterialTheme.typography.titleLarge,
            modifier = Modifier.padding(16.dp),
        )
        LazyColumn(state = listState) {
            items(chapters, key = { it.id }) { chapter ->
                TocItem(
                    chapter = chapter,
                    selected = chapter.sortIndex == currentSortIndex,
                    read = chapter.sortIndex < currentSortIndex,
                    onClick = { onSelect(chapter) },
                )
            }
        }
    }
}

@Composable
private fun TocItem(chapter: CachedChapter, selected: Boolean, read: Boolean, onClick: () -> Unit) {
    Row(
        verticalAlignment = Alignment.CenterVertically,
        modifier = Modifier
            .fillMaxWidth()
            .clickable(onClick = onClick)
            .padding(horizontal = 16.dp, vertical = 12.dp),
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
        )
    }
}
