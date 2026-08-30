@file:OptIn(ExperimentalMaterial3Api::class)

package com.sailzen.app.feature.reader

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.ModalBottomSheet
import androidx.compose.material3.Text
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Delete
import androidx.compose.material.icons.filled.Edit
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.unit.dp
import com.sailzen.app.R
import com.sailzen.app.core.data.db.CachedAnnotation

@Composable
fun AnnotationSheet(
    annotations: List<CachedAnnotation>,
    onEdit: (CachedAnnotation) -> Unit,
    onDelete: (CachedAnnotation) -> Unit,
    onDismiss: () -> Unit,
) {
    ModalBottomSheet(onDismissRequest = onDismiss) {
        Text(
            text = stringResource(R.string.annotation_title),
            style = MaterialTheme.typography.titleLarge,
            modifier = Modifier.padding(16.dp),
        )
        if (annotations.isEmpty()) {
            Text(
                text = stringResource(R.string.annotation_empty),
                style = MaterialTheme.typography.bodyMedium,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
                modifier = Modifier.padding(16.dp),
            )
        } else {
            LazyColumn {
                items(annotations, key = { it.localId }) { annotation ->
                    AnnotationRow(
                        annotation = annotation,
                        onEdit = { onEdit(annotation) },
                        onDelete = { onDelete(annotation) },
                    )
                }
            }
        }
    }
}

@Composable
private fun AnnotationRow(
    annotation: CachedAnnotation,
    onEdit: () -> Unit,
    onDelete: () -> Unit,
) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .clickable(onClick = onEdit)
            .padding(horizontal = 16.dp, vertical = 12.dp),
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.SpaceBetween,
    ) {
        Column(modifier = Modifier.weight(1f)) {
            Text(
                text = annotation.selectedText,
                style = MaterialTheme.typography.bodyMedium,
                maxLines = 2,
            )
            if (annotation.note.isNotBlank()) {
                Text(
                    text = annotation.note,
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                    maxLines = 2,
                )
            }
        }
        IconButton(onClick = onEdit) {
            Icon(Icons.Default.Edit, contentDescription = null)
        }
        IconButton(onClick = onDelete) {
            Icon(Icons.Default.Delete, contentDescription = null)
        }
    }
}
