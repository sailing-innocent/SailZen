package com.sailzen.app.feature.reader

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.unit.dp
import com.sailzen.app.R
import com.sailzen.app.core.text.ReaderSyncState
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

/**
 * 阅读页同步状态 chip：离线 / 同步中 / 已同步(时间) / 失败(可点按重试)，
 * 并附带未同步批注数。让用户在弱网/断网下明确知道当前内容的可信来源。
 */
@Composable
fun SyncStatusChip(
    state: ReaderSyncState,
    pendingAnnotations: Int,
    onRetrySync: () -> Unit,
    modifier: Modifier = Modifier,
) {
    val display = state.display
    val (dotColor, labelRes) = when (display) {
        ReaderSyncState.Display.Offline -> Color(0xFF9E9E9E) to R.string.sync_status_offline
        ReaderSyncState.Display.Syncing -> MaterialTheme.colorScheme.primary to R.string.sync_status_syncing
        is ReaderSyncState.Display.Error -> MaterialTheme.colorScheme.error to R.string.sync_status_error
        is ReaderSyncState.Display.Synced -> Color(0xFF4CAF50) to null
        ReaderSyncState.Display.Idle -> Color(0xFF9E9E9E) to R.string.sync_status_idle
    }

    val timeText = (display as? ReaderSyncState.Display.Synced)?.atMillis?.let {
        SimpleDateFormat("HH:mm", Locale.getDefault()).format(Date(it))
    }

    Row(
        modifier = modifier
            .clip(RoundedCornerShape(50))
            .background(MaterialTheme.colorScheme.surfaceVariant.copy(alpha = 0.85f))
            .clickable(enabled = display is ReaderSyncState.Display.Error) { onRetrySync() }
            .padding(horizontal = 10.dp, vertical = 4.dp),
        horizontalArrangement = Arrangement.Center,
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Box(
            modifier = Modifier
                .size(6.dp)
                .clip(CircleShape)
                .background(dotColor),
        )
        val text = buildString {
            if (labelRes != null) {
                append(stringResource(labelRes))
            } else if (timeText != null) {
                append(stringResource(R.string.sync_status_synced_at, timeText))
            }
            if (pendingAnnotations > 0) {
                append(" · ")
                append(stringResource(R.string.sync_status_pending_annotations, pendingAnnotations))
            }
        }
        Text(
            text = text,
            style = MaterialTheme.typography.labelSmall,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
            modifier = Modifier.padding(start = 6.dp),
        )
    }
}
