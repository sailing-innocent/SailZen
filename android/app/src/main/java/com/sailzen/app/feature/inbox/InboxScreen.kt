@file:OptIn(ExperimentalMaterial3Api::class, ExperimentalLayoutApi::class)

package com.sailzen.app.feature.inbox

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ExperimentalLayoutApi
import androidx.compose.foundation.layout.FlowRow
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
import androidx.compose.material3.SuggestionChip
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
import com.sailzen.app.core.data.db.CachedInboxItem
import com.sailzen.app.core.network.ApiClient
import kotlinx.serialization.json.booleanOrNull
import kotlinx.serialization.json.jsonArray
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
    var snoozeTarget by remember { mutableStateOf<CachedInboxItem?>(null) }
    val listState = rememberLazyListState()

    // 通知"处理"跳入：滚动到对应收件箱卡片（兼容 reminderId 或 inboxItemId）
    LaunchedEffect(highlightReminderId, state.pending) {
        if (highlightReminderId > 0) {
            val index = state.pending.indexOfFirst {
                it.reminderId == highlightReminderId || it.id == highlightReminderId
            }
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
                active = state.summary?.active ?: state.pending.size,
                answered = (state.summary?.answered ?: 0) + (state.summary?.resolved ?: 0),
                dismissed = state.summary?.dismissed ?: 0,
                expired = state.summary?.expired ?: 0,
            )
            TabRow(selectedTabIndex = selectedTab) {
                Tab(
                    selected = selectedTab == 0,
                    onClick = { selectedTab = 0 },
                    text = { Text("${stringResource(R.string.inbox_tab_pending)} (${state.pending.size})") },
                )
                Tab(
                    selected = selectedTab == 1,
                    onClick = { selectedTab = 1 },
                    text = { Text(stringResource(R.string.inbox_tab_history)) },
                )
            }
            if (selectedTab == 0) {
                PendingInboxList(
                    pending = state.pending,
                    listState = listState,
                    onReply = { item, text -> viewModel.reply(item.id, text) },
                    onResolve = { viewModel.resolve(it.id) },
                    onSnooze = { snoozeTarget = it },
                    onDismiss = { viewModel.dismiss(it.id) },
                    onOpenHealthCoach = onOpenHealthCoach,
                )
            } else {
                HistoryInboxList(history = state.history)
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
    active: Int,
    answered: Int,
    dismissed: Int,
    expired: Int,
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
                text = "待处理 $active · 已处理 $answered · 已忽略 $dismissed · 已过期 $expired",
                style = MaterialTheme.typography.bodyMedium,
            )
        }
    }
}

private fun extractQuickReplies(actionSchemaJson: String): List<String> = runCatching {
    val obj = ApiClient.json.parseToJsonElement(actionSchemaJson).jsonObject
    obj["quick_replies"]?.jsonArray?.mapNotNull { it.jsonPrimitive.content.takeIf(String::isNotBlank) }
        ?: emptyList()
}.getOrDefault(emptyList())

private fun allowsTextReply(item: CachedInboxItem): Boolean {
    if (item.itemKind == "question") return true
    return runCatching {
        val obj = ApiClient.json.parseToJsonElement(item.actionSchemaJson).jsonObject
        obj["allow_text_reply"]?.jsonPrimitive?.booleanOrNull == true
    }.getOrDefault(false)
}

private fun domainLabel(domain: String): String = when (domain) {
    "sailtick" -> "AI 教练"
    "rhythm" -> "节奏"
    "health" -> "健康"
    "finance" -> "财务"
    else -> "系统"
}

private fun statusLabel(status: String): String = when (status) {
    "answered" -> "已答复"
    "resolved" -> "已完成"
    "dismissed" -> "已忽略"
    "expired" -> "已过期"
    "canceled" -> "已撤销"
    "snoozed" -> "已延后"
    else -> status
}

@Composable
private fun PendingInboxList(
    pending: List<CachedInboxItem>,
    listState: LazyListState,
    onReply: (CachedInboxItem, String) -> Unit,
    onResolve: (CachedInboxItem) -> Unit,
    onSnooze: (CachedInboxItem) -> Unit,
    onDismiss: (CachedInboxItem) -> Unit,
    onOpenHealthCoach: () -> Unit,
) {
    if (pending.isEmpty()) {
        EmptyText(stringResource(R.string.inbox_empty_pending))
        return
    }
    LazyColumn(state = listState, modifier = Modifier.fillMaxSize()) {
        items(pending, key = { it.id }) { item ->
            InboxItemCard(
                item = item,
                onReply = { text -> onReply(item, text) },
                onResolve = { onResolve(item) },
                onSnooze = { onSnooze(item) },
                onDismiss = { onDismiss(item) },
                onOpenHealthCoach = onOpenHealthCoach,
            )
        }
    }
}

@Composable
private fun InboxItemCard(
    item: CachedInboxItem,
    onReply: (String) -> Unit,
    onResolve: () -> Unit,
    onSnooze: () -> Unit,
    onDismiss: () -> Unit,
    onOpenHealthCoach: () -> Unit,
) {
    val quickReplies = remember(item.id, item.actionSchemaJson) {
        extractQuickReplies(item.actionSchemaJson)
    }
    val canReply = remember(item.id, item.itemKind, item.actionSchemaJson) {
        allowsTextReply(item)
    }
    val isDailyReport = item.itemKind == "report" || item.topic == "daily_report"
    var replyDraft by remember(item.id) { mutableStateOf("") }

    Card(
        modifier = Modifier
            .fillMaxWidth()
            .padding(horizontal = 16.dp, vertical = 4.dp),
    ) {
        Column(modifier = Modifier.padding(12.dp)) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Text(
                    text = item.title,
                    style = MaterialTheme.typography.titleMedium,
                    modifier = Modifier.weight(1f),
                )
                PriorityChip(priority = item.priority)
            }
            if (item.body.isNotBlank()) {
                Spacer(modifier = Modifier.height(4.dp))
                Text(text = item.body, style = MaterialTheme.typography.bodyMedium)
            }
            Spacer(modifier = Modifier.height(4.dp))
            Text(
                text = "${domainLabel(item.sourceDomain)} · ${statusLabel(item.status)} · ${item.updatedAt}",
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
            if (quickReplies.isNotEmpty()) {
                Spacer(modifier = Modifier.height(8.dp))
                FlowRow(
                    horizontalArrangement = Arrangement.spacedBy(6.dp),
                    verticalArrangement = Arrangement.spacedBy(4.dp),
                ) {
                    quickReplies.forEach { qr ->
                        SuggestionChip(
                            onClick = { onReply(qr) },
                            label = { Text(qr) },
                        )
                    }
                }
            }
            if (canReply) {
                Spacer(modifier = Modifier.height(8.dp))
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.spacedBy(8.dp),
                    verticalAlignment = Alignment.CenterVertically,
                ) {
                    OutlinedTextField(
                        value = replyDraft,
                        onValueChange = { replyDraft = it },
                        placeholder = { Text("简短回复，多端同步关闭…") },
                        singleLine = true,
                        modifier = Modifier.weight(1f),
                    )
                    Button(
                        enabled = replyDraft.isNotBlank(),
                        onClick = {
                            onReply(replyDraft)
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
private fun HistoryInboxList(history: List<CachedInboxItem>) {
    if (history.isEmpty()) {
        EmptyText(stringResource(R.string.inbox_empty_history))
        return
    }
    LazyColumn(modifier = Modifier.fillMaxSize()) {
        items(history, key = { it.id }) { item ->
            Card(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(horizontal = 16.dp, vertical = 4.dp),
            ) {
                Column(modifier = Modifier.padding(12.dp)) {
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Column(modifier = Modifier.weight(1f)) {
                            Text(text = item.title, style = MaterialTheme.typography.titleSmall)
                            Text(
                                text = "${domainLabel(item.sourceDomain)} · ${item.updatedAt}",
                                style = MaterialTheme.typography.bodySmall,
                                color = MaterialTheme.colorScheme.onSurfaceVariant,
                            )
                        }
                        AssistChip(onClick = {}, label = { Text(statusLabel(item.status)) })
                    }
                    if (item.resolutionSummary.isNotBlank()) {
                        Spacer(modifier = Modifier.height(6.dp))
                        Text(
                            text = item.resolutionSummary,
                            style = MaterialTheme.typography.bodySmall,
                            color = MaterialTheme.colorScheme.primary,
                        )
                    }
                    if (item.resolutionSource.isNotBlank()) {
                        Text(
                            text = "来源：${item.resolutionSource}",
                            style = MaterialTheme.typography.labelSmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                        )
                    }
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
