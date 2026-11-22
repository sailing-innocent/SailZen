package com.sailzen.app.feature.health.coach

import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.rememberScrollState
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material3.AssistChip
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.FilterChip
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.SnackbarHost
import androidx.compose.material3.SnackbarHostState
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.lifecycle.viewmodel.compose.viewModel
import com.sailzen.app.core.network.dto.DailyReportDto
import com.sailzen.app.core.network.dto.TickTicketDto

private data class QuickCategoryChip(
    val label: String,
    val category: String,
    val mealType: String? = null,
)

private val SILENT_CHIPS = listOf(
    QuickCategoryChip("早餐", "diet", "breakfast"),
    QuickCategoryChip("午餐", "diet", "lunch"),
    QuickCategoryChip("晚餐", "diet", "dinner"),
    QuickCategoryChip("加餐", "diet", "snack"),
    QuickCategoryChip("日常状态", "daily_info", null),
)

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun HealthCoachScreen(
    onBack: () -> Unit,
    onQuickLogWeight: () -> Unit,
    viewModel: HealthCoachViewModel = viewModel(),
) {
    val state by viewModel.uiState.collectAsState()
    val snackbarHostState = remember { SnackbarHostState() }

    var selectedChipIndex by remember { mutableIntStateOf(1) }
    var silentInput by remember { mutableStateOf("") }
    var reportExpanded by remember { mutableStateOf(false) }

    LaunchedEffect(state.feedbackMessage) {
        val msg = state.feedbackMessage ?: return@LaunchedEffect
        snackbarHostState.showSnackbar(msg)
        viewModel.clearFeedback()
    }

    val activeReport = state.reports.firstOrNull { it.reportDate == state.selectedReportDate }
        ?: state.summary?.latestReport

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("SailTick AI 健康教练") },
                navigationIcon = {
                    IconButton(onClick = onBack) {
                        Icon(Icons.AutoMirrored.Filled.ArrowBack, contentDescription = "返回")
                    }
                },
                actions = {
                    TextButton(onClick = onQuickLogWeight) { Text("记体重") }
                    IconButton(onClick = { viewModel.refresh() }) {
                        Icon(Icons.Default.Refresh, contentDescription = "刷新")
                    }
                },
            )
        },
        snackbarHost = { SnackbarHost(snackbarHostState) },
    ) { padding ->
        LazyColumn(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding)
                .padding(horizontal = 16.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp),
            contentPadding = PaddingValues(vertical = 12.dp),
        ) {
            if (state.loading) {
                item { LinearProgressIndicator(modifier = Modifier.fillMaxWidth()) }
            }

            // 1. 待回复的 AI 渐进式提问
            val pendingTickets = state.summary?.pendingTickets.orEmpty()
            if (pendingTickets.isNotEmpty()) {
                item {
                    Text(
                        "教练提问（${state.summary?.pendingTicketCount ?: pendingTickets.size}）",
                        style = MaterialTheme.typography.titleMedium,
                    )
                }
                items(pendingTickets, key = { it.id }) { ticket ->
                    CoachQuestionCard(
                        ticket = ticket,
                        sending = state.sending,
                        onReply = { reply -> viewModel.replyTicket(ticket.id, reply) },
                        onSnooze = { viewModel.snoozeTicket(ticket.id) },
                    )
                }
            }

            // 2. 随手记餐饮 / 发给教练（静默收集，无需等待即时回复）
            item {
                Card(modifier = Modifier.fillMaxWidth()) {
                    Column(
                        modifier = Modifier.padding(14.dp),
                        verticalArrangement = Arrangement.spacedBy(8.dp),
                    ) {
                        Text(
                            "随手记餐饮 / 发消息",
                            style = MaterialTheme.typography.titleMedium,
                            fontWeight = FontWeight.SemiBold,
                        )
                        Text(
                            "直接发一句吃过什么或今天的状态即可，AI 无需立即回复，会在每天睡前日报中统一整合。",
                            style = MaterialTheme.typography.bodySmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                        )
                        Row(
                            modifier = Modifier
                                .fillMaxWidth()
                                .horizontalScroll(rememberScrollState()),
                            horizontalArrangement = Arrangement.spacedBy(8.dp),
                        ) {
                            SILENT_CHIPS.forEachIndexed { index, chip ->
                                FilterChip(
                                    selected = selectedChipIndex == index,
                                    onClick = { selectedChipIndex = index },
                                    label = { Text(chip.label) },
                                )
                            }
                        }
                        OutlinedTextField(
                            value = silentInput,
                            onValueChange = { silentInput = it },
                            modifier = Modifier.fillMaxWidth(),
                            placeholder = { Text("如：午饭食堂鸡胸肉+半碗米饭+西兰花") },
                            minLines = 2,
                        )
                        Row(
                            modifier = Modifier.fillMaxWidth(),
                            horizontalArrangement = Arrangement.End,
                        ) {
                            Button(
                                enabled = silentInput.isNotBlank() && !state.sending,
                                onClick = {
                                    val chip = SILENT_CHIPS[selectedChipIndex]
                                    viewModel.sendSilentMessage(
                                        content = silentInput,
                                        category = chip.category,
                                        mealType = chip.mealType,
                                    )
                                    silentInput = ""
                                },
                            ) {
                                Text("静默记录")
                            }
                        }
                        val todayMsgs = state.summary?.todayMessages.orEmpty()
                        if (todayMsgs.isNotEmpty()) {
                            Text(
                                "今日已收集（${todayMsgs.size}）：",
                                style = MaterialTheme.typography.labelMedium,
                                color = MaterialTheme.colorScheme.onSurfaceVariant,
                            )
                            todayMsgs.take(5).forEach { m ->
                                val tag = if (m.status == "ingested") "已整合" else "待日报整合"
                                Text(
                                    "• ${m.content}  [$tag]",
                                    style = MaterialTheme.typography.bodySmall,
                                )
                            }
                        }
                    }
                }
            }

            // 3. 每日睡前体重与健康日报
            item {
                Text("每日睡前体重与健康日报", style = MaterialTheme.typography.titleMedium)
            }
            if (state.reports.size > 1) {
                item {
                    Row(
                        modifier = Modifier
                            .fillMaxWidth()
                            .horizontalScroll(rememberScrollState()),
                        horizontalArrangement = Arrangement.spacedBy(8.dp),
                    ) {
                        state.reports.take(7).forEach { r ->
                            FilterChip(
                                selected = activeReport?.reportDate == r.reportDate,
                                onClick = { viewModel.selectReport(r.reportDate) },
                                label = { Text(r.reportDate.takeLast(5)) },
                            )
                        }
                    }
                }
            }
            item {
                DailyReportCard(
                    report = activeReport,
                    expanded = reportExpanded,
                    onToggleExpand = { reportExpanded = !reportExpanded },
                )
            }
            item { Spacer(Modifier.height(48.dp)) }
        }
    }
}

@Composable
private fun CoachQuestionCard(
    ticket: TickTicketDto,
    sending: Boolean,
    onReply: (String) -> Unit,
    onSnooze: () -> Unit,
) {
    var draft by remember(ticket.id) { mutableStateOf("") }
    val quickReplies = remember(ticket.id, ticket.meta) { ticket.quickReplies() }

    Card(
        modifier = Modifier.fillMaxWidth(),
        colors = CardDefaults.cardColors(
            containerColor = MaterialTheme.colorScheme.secondaryContainer.copy(alpha = 0.55f),
        ),
    ) {
        Column(
            modifier = Modifier.padding(14.dp),
            verticalArrangement = Arrangement.spacedBy(8.dp),
        ) {
            Text(
                ticket.title,
                style = MaterialTheme.typography.titleSmall,
                fontWeight = FontWeight.SemiBold,
            )
            if (ticket.body.isNotBlank()) {
                Text(ticket.body, style = MaterialTheme.typography.bodySmall)
            }
            if (quickReplies.isNotEmpty()) {
                Row(
                    modifier = Modifier
                        .fillMaxWidth()
                        .horizontalScroll(rememberScrollState()),
                    horizontalArrangement = Arrangement.spacedBy(8.dp),
                ) {
                    quickReplies.forEach { qr ->
                        AssistChip(
                            onClick = { onReply(qr) },
                            label = { Text(qr) },
                        )
                    }
                }
            }
            OutlinedTextField(
                value = draft,
                onValueChange = { draft = it },
                modifier = Modifier.fillMaxWidth(),
                placeholder = { Text("简短回复一句即可…") },
                singleLine = true,
            )
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.spacedBy(8.dp, Alignment.End),
            ) {
                OutlinedButton(onClick = onSnooze, enabled = !sending) {
                    Text("暂缓24h")
                }
                Button(
                    enabled = draft.isNotBlank() && !sending,
                    onClick = {
                        onReply(draft)
                        draft = ""
                    },
                ) {
                    Text("回复")
                }
            }
        }
    }
}

@Composable
private fun DailyReportCard(
    report: DailyReportDto?,
    expanded: Boolean,
    onToggleExpand: () -> Unit,
) {
    Card(modifier = Modifier.fillMaxWidth()) {
        Column(
            modifier = Modifier.padding(14.dp),
            verticalArrangement = Arrangement.spacedBy(8.dp),
        ) {
            if (report == null) {
                Text(
                    "暂无睡前日报。SailTick 会在每晚睡前整合当天体重、餐饮记录与 AI 动态计划进展并推送到这里。",
                    style = MaterialTheme.typography.bodyMedium,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
                return@Column
            }
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Text(
                    report.title,
                    style = MaterialTheme.typography.titleSmall,
                    fontWeight = FontWeight.SemiBold,
                    modifier = Modifier.weight(1f),
                )
                Text(
                    report.reportDate,
                    style = MaterialTheme.typography.labelSmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
            if (report.summary.isNotBlank()) {
                Text(report.summary, style = MaterialTheme.typography.bodyMedium)
            }
            if (report.tomorrowFocus.isNotEmpty()) {
                Text(
                    "明日轻量建议：",
                    style = MaterialTheme.typography.labelMedium,
                    color = MaterialTheme.colorScheme.primary,
                )
                report.tomorrowFocus.forEach { tip ->
                    Text("• $tip", style = MaterialTheme.typography.bodySmall)
                }
            }
            if (report.bodyMarkdown.isNotBlank()) {
                TextButton(onClick = onToggleExpand) {
                    Text(if (expanded) "收起完整日报" else "展开完整日报")
                }
                if (expanded) {
                    Text(
                        report.bodyMarkdown,
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                }
            }
        }
    }
}
