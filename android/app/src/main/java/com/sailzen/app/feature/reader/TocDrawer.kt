@file:OptIn(ExperimentalMaterial3Api::class)

package com.sailzen.app.feature.reader

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.ModalBottomSheet
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.unit.dp
import com.sailzen.app.R
import com.sailzen.app.core.data.db.CachedChapter

@Composable
fun TocDrawer(
    chapters: List<CachedChapter>,
    currentSortIndex: Int,
    onSelect: (CachedChapter) -> Unit,
    onDismiss: () -> Unit,
) {
    ModalBottomSheet(onDismissRequest = onDismiss) {
        Text(
            text = stringResource(R.string.reader_toc_title),
            style = MaterialTheme.typography.titleLarge,
            modifier = Modifier.padding(16.dp),
        )
        LazyColumn {
            items(chapters, key = { it.id }) { chapter ->
                TocItem(
                    chapter = chapter,
                    selected = chapter.sortIndex == currentSortIndex,
                    onClick = { onSelect(chapter) },
                )
            }
        }
    }
}

@Composable
private fun TocItem(chapter: CachedChapter, selected: Boolean, onClick: () -> Unit) {
    Text(
        text = chapter.title.ifBlank { chapter.label },
        style = if (selected) MaterialTheme.typography.bodyLarge else MaterialTheme.typography.bodyMedium,
        color = if (selected) MaterialTheme.colorScheme.primary else MaterialTheme.colorScheme.onSurface,
        modifier = Modifier
            .fillMaxWidth()
            .clickable(onClick = onClick)
            .padding(horizontal = 16.dp, vertical = 12.dp),
    )
}
