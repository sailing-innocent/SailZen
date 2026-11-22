@file:OptIn(ExperimentalMaterial3Api::class)

package com.sailzen.app.feature.inbox

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.WindowInsets
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.LazyListState
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material.icons.filled.Settings
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.AssistChip
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Tab
import androidx.compose.material3.TabRow
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
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
import com.sailzen.app.core.data.db.CachedReminder
import com.sailzen.app.core.network.ApiClient
import com.sailzen.app.core.network.dto.ReminderDto
import kotlinx.serialization.json.intOrNull
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun InboxScreen(
    highlightReminderId: Int,
    onOpenSettings: () -> Unit,
    onOpenHealthCoach: () -> Unit = {},
    viewModel: InboxViewModel = viewModel(),
) {
    val state by viewModel.uiState.collectAsStateWithLifecycle()
    var selectedTab by remember { mutableIntStateOf(0) }
    var snoozeTarget by remember { mutableStateOf<CachedReminder?>(null) }
    val listState = rememberLazyListState()

    // 通知"处理"跳入：滚动到对应卡片
    LaunchedEffect(highlightReminderId, state.pending) {
        if (highlightReminderId > 0) {
            val index = state.pending.indexOfFirst { it.id == highlightReminderId }
            if (index >= 0) {
                listState.animateScrollToItem(index)
            }
        }
    }

    Scaffold(
        contentWindowInsets = WindowInsets(0, 0, 0, 0),
        topBar = {
            TopAppBar(
                title = { Text(stringResource(R.string.inbox_title)) },
                actions = {
                    IconButton(onClick = { viewModel.refresh() }) {
                        Icon(Icons.Default.Refresh, contentDescription = null)
                    }
                    IconButton(onClick = onOpenSettings) {
                        Icon(Icons.Default.Settings, contentDescription = null)
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
            SummaryCard(
                pending = state.summary?.pending,
                resolved = state.summary?.resolved,
                ignored = state.summary?.ignored,
                expired = state.summary?.expired,
            )
            TabRow(selectedTabIndex = selectedTab) {
                Tab(
                    selected = selectedTab == 0,
                    onClick = { selectedTab = 0 },
                    text = { Text(stringResource(R.string.inbox_tab_pending)) },
                )
                Tab(
                    selected = selectedTab == 1,
                    onClick = { selectedTab = 1 },
                    text = { Text(stringResource(R.string.inbox_tab_history)) },
                )
            }
            if (selectedTab == 0) {
                PendingList(
                    pending = state.pending,
                    listState = listState,
                    highlightReminderId = highlightReminderId,
                    onOpen = { viewModel.open(it.id) },
                    onResolve = { viewModel.resolve(it.id) },
                    onSnooze = { snoozeTarget = it },
                    onDismiss = { viewModel.dismiss(it.id) },
                    onReplyAgentTicket = { rem, ticketId, reply ->
                        viewModel.replyAgentTicket(rem.id, ticketId, reply)
                    },
                    onOpenHealthCoach = onOpenHealthCoach,
                )
            } else {
                HistoryList(history = state.history)
            }
        }
    }

    snoozeTarget?.let { target ->
        SnoozeOptionDialog(
            onSelect = { option ->
                viewModel.snooze(target.id, option)
                snoozeTarget = null
            },
            onDismiss = { snoozeTarget = null },
        )
    }
}

@Composable
private fun SummaryCard(
    pending: Int?,
    resolved: Int?,
    ignored: Int?,
    expired: Int?,
) {
    Card(
        modifier = Modifier
            .fillMaxWidth()
            .padding(horizontal = 16.dp, vertical = 8.dp),
    ) {
        Column(modifier = Modifier.padding(16.dp)) {
            Text(
                text = stringResource(R.string.inbox_summary_title),
                style = MaterialTheme.typography.titleMedium,
            )
            Spacer(modifier = Modifier.height(8.dp))
            Text(
                text = "待处理 ${pending ?: 0} · 已完成 ${resolved ?: 0} · " +
                    "已忽略 ${ignored ?: 0} · 已过期 ${expired ?: 0}",
                style = MaterialTheme.typography.bodyMedium,
            )
        }
    }
}

private fun extractTicketId(payloadJson: String): Int? = runCatching {
    ApiClient.json.parseToJsonElement(payloadJson).jsonObject["ticket_id"]?.jsonPrimitive?.intOrNull
}.getOrNull()

@Composable
private fun PendingList(
    pending: List<CachedReminder>,
    listState: LazyListState,
    highlightReminderId: Int,
    onOpen: (CachedReminder) -> Unit,
    onResolve: (CachedReminder) -> Unit,
    onSnooze: (CachedReminder) -> Unit,
    onDismiss: (CachedReminder) -> Unit,
    onReplyAgentTicket: (CachedReminder, Int, String) -> Unit,
    onOpenHealthCoach: () -> Unit,
) {
    if (pending.isEmpty()) {
        EmptyText(stringResource(R.string.inbox_empty_pending))
        return
    }
    LazyColumn(state = listState, modifier = Modifier.fillMaxSize()) {
        items(pending, key = { it.id }) { reminder ->
            ReminderCard(
                reminder = reminder,
                highlighted = reminder.id == highlightReminderId,
                onOpen = { onOpen(reminder) },
                onResolve = { onResolve(reminder) },
                onSnooze = { onSnooze(reminder) },
                onDismiss = { onDismiss(reminder) },
                onReplyAgentTicket = { ticketId, reply ->
                    onReplyAgentTicket(reminder, ticketId, reply)
                },
                onOpenHealthCoach = onOpenHealthCoach,
            )
        }
    }
}

@Composable
private fun ReminderCard(
    reminder: CachedReminder,
    highlighted: Boolean,
    onOpen: () -> Unit,
    onResolve: () -> Unit,
    onSnooze: () -> Unit,
    onDismiss: () -> Unit,
    onReplyAgentTicket: (Int, String) -> Unit,
    onOpenHealthCoach: () -> Unit,
) {
    val ticketId = remember(reminder.id, reminder.payloadJson) { extractTicketId(reminder.payloadJson) }
    val isAgentTicket = reminder.type.startsWith("tick.ticket.") && ticketId != null
    val isDailyReport = reminder.type == "tick.daily_report"
    var replyDraft by remember(reminder.id) { mutableStateOf("") }

    Card(
        onClick = onOpen,
        modifier = Modifier
            .fillMaxWidth()
            .padding(horizontal = 16.dp, vertical = 4.dp),
    ) {
        Column(modifier = Modifier.padding(12.dp)) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Text(
                    text = reminder.title,
                    style = MaterialTheme.typography.titleMedium,
                    modifier = Modifier.weight(1f),
                )
                PriorityChip(priority = reminder.priority)
            }
            if (reminder.body.isNotBlank()) {
                Spacer(modifier = Modifier.height(4.dp))
                Text(text = reminder.body, style = MaterialTheme.typography.bodyMedium)
            }
            Spacer(modifier = Modifier.height(4.dp))
            Text(
                text = "${reminder.type} · ${reminder.triggerTime}" +
                    (if (reminder.snoozeCount > 0) " · 已延后 ${reminder.snoozeCount} 次" else ""),
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
            if (isAgentTicket && ticketId != null) {
                Spacer(modifier = Modifier.height(8.dp))
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.spacedBy(8.dp),
                    verticalAlignment = Alignment.CenterVertically,
                ) {
                    OutlinedTextField(
                        value = replyDraft,
                        onValueChange = { replyDraft = it },
                        placeholder = { Text("回复 SailTick 教练…") },
                        singleLine = true,
                        modifier = Modifier.weight(1f),
                    )
                    Button(
                        enabled = replyDraft.isNotBlank(),
                        onClick = {
                            onReplyAgentTicket(ticketId, replyDraft)
                            replyDraft = ""
                        },
                    ) {
                        Text("回复")
                    }
                }
            }
            Spacer(modifier = Modifier.height(8.dp))
            Row(horizontalArrangement = Arrangement.End, modifier = Modifier.fillMaxWidth()) {
                if (isDailyReport) {
                    TextButton(onClick = {
                        onResolve()
                        onOpenHealthCoach()
                    }) {
                        Text("查看完整日报")
                    }
                }
                TextButton(onClick = onResolve) {
                    Text(stringResource(R.string.action_done))
                }
                TextButton(onClick = onSnooze) {
                    Text(stringResource(R.string.action_snooze))
                }
                TextButton(onClick = onDismiss) {
                    Text(stringResource(R.string.action_dismiss))
                }
            }
        }
    }
}

@Composable
private fun PriorityChip(priority: String) {
    val color = when (priority) {
        "urgent" -> MaterialTheme.colorScheme.error
        "high" -> MaterialTheme.colorScheme.tertiary
        "low" -> MaterialTheme.colorScheme.outline
        else -> MaterialTheme.colorScheme.primary
    }
    AssistChip(
        onClick = {},
        label = { Text(priority, color = color) },
    )
}

@Composable
private fun HistoryList(history: List<ReminderDto>) {
    if (history.isEmpty()) {
        EmptyText(stringResource(R.string.inbox_empty_history))
        return
    }
    LazyColumn(modifier = Modifier.fillMaxSize()) {
        items(history, key = { it.id }) { reminder ->
            Card(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(horizontal = 16.dp, vertical = 4.dp),
            ) {
                Row(
                    modifier = Modifier.padding(12.dp),
                    verticalAlignment = Alignment.CenterVertically,
                ) {
                    Column(modifier = Modifier.weight(1f)) {
                        Text(text = reminder.title, style = MaterialTheme.typography.titleSmall)
                        Text(
                            text = "${reminder.type} · ${reminder.triggerTime}",
                            style = MaterialTheme.typography.bodySmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                        )
                    }
                    AssistChip(onClick = {}, label = { Text(reminder.state) })
                }
            }
        }
    }
}

@Composable
private fun EmptyText(text: String) {
    Column(
        modifier = Modifier
            .fillMaxSize()
            .padding(32.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.Center,
    ) {
        Text(text = text, style = MaterialTheme.typography.bodyMedium)
    }
}

@Composable
private fun SnoozeOptionDialog(
    onSelect: (String) -> Unit,
    onDismiss: () -> Unit,
) {
    val options = listOf(
        stringResource(R.string.snooze_15m) to "15m",
        stringResource(R.string.snooze_1h) to "1h",
        stringResource(R.string.snooze_tonight) to "tonight",
        stringResource(R.string.snooze_tomorrow) to "tomorrow",
    )
    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text(stringResource(R.string.snooze_dialog_title)) },
        text = {
            Column {
                options.forEach { (label, option) ->
                    TextButton(
                        onClick = { onSelect(option) },
                        modifier = Modifier.fillMaxWidth(),
                    ) {
                        Text(label, modifier = Modifier.fillMaxWidth())
                    }
                }
            }
        },
        confirmButton = {},
        dismissButton = {
            TextButton(onClick = onDismiss) {
                Text(stringResource(android.R.string.cancel))
            }
        },
    )
}
