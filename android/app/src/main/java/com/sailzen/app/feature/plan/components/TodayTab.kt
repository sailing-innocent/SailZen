package com.sailzen.app.feature.plan.components

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
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.Send
import androidx.compose.material.icons.filled.AutoAwesome
import androidx.compose.material.icons.filled.Close
import androidx.compose.material3.AssistChip
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.FilledTonalIconButton
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import com.sailzen.app.R
import com.sailzen.app.core.network.dto.CheckinTodayItemDto
import com.sailzen.app.core.network.dto.HealthSignalItemDto
import com.sailzen.app.core.network.dto.QuickChatHistoryItemDto
import com.sailzen.app.core.network.dto.TickTicketDto
import com.sailzen.app.core.network.dto.TimeBlockDto
import com.sailzen.app.feature.plan.PlanViewModel

private val QUICK_NEGOTIATION_PROMPTS = listOf(
    "看看今天怎么排" to "/today",
    "下午临时加会重排" to "下午临时加了会，帮我把剩下的安排重新排一下",
    "今天太累减负" to "今天状态有点累，帮我减负，只保留最关键的一两件事",
    "看看重点项目" to "/projects",
)

/**
 * 今日 Tab（Rhythm v2 + SailTick Personal Agent）：
 * 顶部 SailTick 随身协商卡 → AI 排程思路横幅 + 今日日程画布 → 待分拣（按需展示）→ 打卡 → 今日健康信号。
 */
@Composable
fun TodayTab(
    state: PlanViewModel.UiState,
    onQuickChat: (String) -> Unit,
    onDismissChatReply: () -> Unit,
    onReplyDomainTicket: (Int, String) -> Unit = { _, _ -> },
    onSnoozeDomainTicket: (Int) -> Unit = {},
    onAcceptHint: (Int) -> Unit,
    onRejectHint: (Int) -> Unit,
    onConfirmInbox: (Int) -> Unit,
    onCancelInbox: (Int) -> Unit,
    onPreceptKept: (CheckinTodayItemDto) -> Unit,
    onPreceptViolated: (CheckinTodayItemDto) -> Unit,
    onHabitDone: (CheckinTodayItemDto) -> Unit,
    onHabitMissed: (CheckinTodayItemDto) -> Unit,
    onDoneBlock: (Int) -> Unit,
    onDeferBlock: (TimeBlockDto) -> Unit,
    onDeleteBlock: (TimeBlockDto) -> Unit,
    onPlanB: (TimeBlockDto) -> Unit,
) {
    LazyColumn(
        modifier = Modifier
            .fillMaxSize()
            .padding(horizontal = 12.dp),
        contentPadding = PaddingValues(top = 8.dp, bottom = 24.dp),
        verticalArrangement = Arrangement.spacedBy(10.dp),
    ) {
        if (state.queuedCount > 0) {
            item {
                Card(
                    colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.primaryContainer),
                    modifier = Modifier.fillMaxWidth(),
                ) {
                    Text(
                        "离线队列 ${state.queuedCount} 条待补传",
                        modifier = Modifier.padding(12.dp),
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onPrimaryContainer,
                    )
                }
            }
        }

        // ---------------- 节奏规划师待确认票据（仅本域） ----------------
        val rhythmTickets = state.domainSummary?.pendingTickets.orEmpty()
        if (rhythmTickets.isNotEmpty()) {
            items(rhythmTickets.take(2), key = { "rticket-${it.id}" }) { ticket ->
                RhythmDomainTicketCard(
                    ticket = ticket,
                    busy = state.ticketBusyId == ticket.id,
                    onReply = { reply -> onReplyDomainTicket(ticket.id, reply) },
                    onSnooze = { onSnoozeDomainTicket(ticket.id) },
                )
            }
        }

        // ---------------- 昨夜睡前日报·日程摘录 ----------------
        val rhythmReportSummary = state.domainSummary?.reportSectionSummary().orEmpty()
        if (rhythmReportSummary.isNotBlank()) {
            item(key = "rhythm-report-section") {
                Card(
                    colors = CardDefaults.cardColors(
                        containerColor = MaterialTheme.colorScheme.secondaryContainer.copy(alpha = 0.38f),
                    ),
                    modifier = Modifier.fillMaxWidth(),
                ) {
                    Column(
                        modifier = Modifier.padding(12.dp),
                        verticalArrangement = Arrangement.spacedBy(4.dp),
                    ) {
                        Text(
                            text = "节奏规划师 · 日报摘录（${state.domainSummary?.latestReportDate.orEmpty()}）",
                            style = MaterialTheme.typography.labelMedium,
                            fontWeight = FontWeight.SemiBold,
                            color = MaterialTheme.colorScheme.primary,
                        )
                        Text(
                            text = rhythmReportSummary,
                            style = MaterialTheme.typography.bodySmall,
                        )
                    }
                }
            }
        }

        // ---------------- SailTick 随身协商卡（移动端核心入口，多端共享 owner:rhythm） ----------------
        item {
            SailTickNegotiationCard(
                busy = state.chatBusy,
                reply = state.chatReply,
                history = state.chatHistory,
                isAsyncFallback = state.chatIsAsyncFallback,
                onSend = onQuickChat,
                onDismissReply = onDismissChatReply,
            )
        }

        // ---------------- 当日日程画布 ----------------
        item { TimelineSectionHeader(state.timeline) }

        val rationale = state.timeline?.aiRationale.orEmpty()
        if (rationale.isNotBlank()) {
            item { AiRationaleBanner(rationale = rationale) }
        }

        val blocks = state.timeline?.blocks
            ?.filter { it.status != "MOVED" }
            ?.sortedBy { it.startTime }
            ?: emptyList()
        if (blocks.isEmpty()) {
            item {
                Card(
                    colors = CardDefaults.cardColors(
                        containerColor = MaterialTheme.colorScheme.surfaceContainerLow,
                    ),
                    modifier = Modifier.fillMaxWidth(),
                ) {
                    Text(
                        "今日尚无时间块。在上方跟 SailTick 说一句今天的状态或想推进的事，马上帮你排妥。",
                        modifier = Modifier.padding(16.dp),
                        style = MaterialTheme.typography.bodyMedium,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                }
            }
        }
        items(blocks, key = { "block-${it.id}" }) { block ->
            TimelineBlockItem(
                block = block,
                onDone = { onDoneBlock(block.id) },
                onDefer = { onDeferBlock(block) },
                onDelete = { onDeleteBlock(block) },
                onLongPress = { onPlanB(block) },
            )
        }

        // ---------------- 待分拣（仅当存在未分拣事项时出现） ----------------
        if (state.inbox.isNotEmpty()) {
            item {
                InboxSection(
                    inbox = state.inbox,
                    onAcceptHint = { onAcceptHint(it.id) },
                    onRejectHint = { onRejectHint(it.id) },
                    onConfirm = { onConfirmInbox(it.id) },
                    onCancel = { onCancelInbox(it.id) },
                )
            }
        }

        // ---------------- 打卡速览 ----------------
        item {
            CheckinSection(
                checkins = state.checkins,
                onPreceptKept = onPreceptKept,
                onPreceptViolated = onPreceptViolated,
                onHabitDone = onHabitDone,
                onHabitMissed = onHabitMissed,
            )
        }

        // ---------------- 今日健康信号摘要 ----------------
        if (state.healthSignals.isNotEmpty()) {
            item {
                Text(
                    stringResource(R.string.health_signals_title),
                    style = MaterialTheme.typography.titleSmall,
                    fontWeight = FontWeight.Bold,
                    modifier = Modifier.padding(top = 6.dp),
                )
            }
            items(state.healthSignals, key = { "hs-${it.refId}-${it.signalType}" }) { signal ->
                HealthSignalCard(signal = signal)
            }
        }

        item { Spacer(Modifier.height(64.dp)) }
    }
}

@Composable
private fun RhythmDomainTicketCard(
    ticket: TickTicketDto,
    busy: Boolean,
    onReply: (String) -> Unit,
    onSnooze: () -> Unit,
) {
    var draft by remember(ticket.id) { mutableStateOf("") }
    val quickReplies = remember(ticket.id, ticket.meta) { ticket.quickReplies() }

    Card(
        colors = CardDefaults.cardColors(
            containerColor = MaterialTheme.colorScheme.primaryContainer.copy(alpha = 0.42f),
        ),
        modifier = Modifier.fillMaxWidth(),
    ) {
        Column(
            modifier = Modifier.padding(12.dp),
            verticalArrangement = Arrangement.spacedBy(6.dp),
        ) {
            Text(
                text = "节奏规划师提问 · ${ticket.title}",
                style = MaterialTheme.typography.titleSmall,
                fontWeight = FontWeight.SemiBold,
            )
            if (ticket.body.isNotBlank()) {
                Text(text = ticket.body, style = MaterialTheme.typography.bodySmall)
            }
            if (quickReplies.isNotEmpty()) {
                Row(
                    modifier = Modifier
                        .fillMaxWidth()
                        .horizontalScroll(rememberScrollState()),
                    horizontalArrangement = Arrangement.spacedBy(6.dp),
                ) {
                    quickReplies.forEach { qr ->
                        AssistChip(
                            onClick = { if (!busy) onReply(qr) },
                            enabled = !busy,
                            label = { Text(qr) },
                        )
                    }
                }
            }
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.spacedBy(6.dp),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                OutlinedTextField(
                    value = draft,
                    onValueChange = { draft = it },
                    placeholder = { Text("简短回复一句…", style = MaterialTheme.typography.bodySmall) },
                    singleLine = true,
                    enabled = !busy,
                    modifier = Modifier.weight(1f),
                )
                Button(
                    enabled = !busy && draft.isNotBlank(),
                    onClick = {
                        onReply(draft)
                        draft = ""
                    },
                ) {
                    Text("回复")
                }
                OutlinedButton(enabled = !busy, onClick = onSnooze) {
                    Text("延后")
                }
            }
        }
    }
}

@Composable
private fun SailTickNegotiationCard(
    busy: Boolean,
    reply: String?,
    history: List<QuickChatHistoryItemDto> = emptyList(),
    isAsyncFallback: Boolean,
    onSend: (String) -> Unit,
    onDismissReply: () -> Unit,
) {
    var input by remember { mutableStateOf("") }

    Card(
        colors = CardDefaults.cardColors(
            containerColor = MaterialTheme.colorScheme.surfaceContainerLow,
        ),
        modifier = Modifier.fillMaxWidth(),
    ) {
        Column(
            modifier = Modifier.padding(12.dp),
            verticalArrangement = Arrangement.spacedBy(8.dp),
        ) {
            Row(
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.spacedBy(6.dp),
            ) {
                Icon(
                    Icons.Default.AutoAwesome,
                    contentDescription = null,
                    tint = MaterialTheme.colorScheme.primary,
                    modifier = Modifier.size(18.dp),
                )
                Text(
                    "与节奏规划师协商（多端共享会话）",
                    style = MaterialTheme.typography.titleSmall,
                    fontWeight = FontWeight.SemiBold,
                )
            }

            if (history.isNotEmpty()) {
                Column(verticalArrangement = Arrangement.spacedBy(4.dp)) {
                    history.takeLast(4).forEach { msg ->
                        val isUser = msg.role == "user"
                        Surface(
                            shape = RoundedCornerShape(8.dp),
                            color = if (isUser) {
                                MaterialTheme.colorScheme.secondaryContainer.copy(alpha = 0.7f)
                            } else {
                                MaterialTheme.colorScheme.primaryContainer.copy(alpha = 0.45f)
                            },
                            modifier = Modifier.fillMaxWidth(),
                        ) {
                            Text(
                                text = (if (isUser) "我：" else "规划师：") + msg.content,
                                style = MaterialTheme.typography.bodySmall,
                                modifier = Modifier.padding(horizontal = 8.dp, vertical = 5.dp),
                            )
                        }
                    }
                }
            }

            Row(
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.spacedBy(8.dp),
                modifier = Modifier.fillMaxWidth(),
            ) {
                OutlinedTextField(
                    value = input,
                    onValueChange = { input = it },
                    placeholder = {
                        Text(
                            "临时加会、想推进哪件事、累了想减负…",
                            style = MaterialTheme.typography.bodySmall,
                        )
                    },
                    singleLine = true,
                    enabled = !busy,
                    modifier = Modifier.weight(1f),
                )
                FilledTonalIconButton(
                    onClick = {
                        val text = input.trim()
                        if (text.isNotEmpty()) {
                            onSend(text)
                            input = ""
                        }
                    },
                    enabled = !busy && input.isNotBlank(),
                ) {
                    if (busy) {
                        CircularProgressIndicator(
                            modifier = Modifier.size(18.dp),
                            strokeWidth = 2.dp,
                        )
                    } else {
                        Icon(Icons.AutoMirrored.Filled.Send, contentDescription = "发送给 SailTick")
                    }
                }
            }

            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .horizontalScroll(rememberScrollState()),
                horizontalArrangement = Arrangement.spacedBy(6.dp),
            ) {
                QUICK_NEGOTIATION_PROMPTS.forEach { (label, prompt) ->
                    AssistChip(
                        onClick = { if (!busy) onSend(prompt) },
                        enabled = !busy,
                        label = { Text(label, style = MaterialTheme.typography.labelMedium) },
                    )
                }
            }

            if (!reply.isNullOrBlank()) {
                Surface(
                    shape = RoundedCornerShape(10.dp),
                    color = if (isAsyncFallback) {
                        MaterialTheme.colorScheme.tertiaryContainer.copy(alpha = 0.6f)
                    } else {
                        MaterialTheme.colorScheme.primaryContainer.copy(alpha = 0.55f)
                    },
                    modifier = Modifier.fillMaxWidth(),
                ) {
                    Column(
                        modifier = Modifier.padding(10.dp),
                        verticalArrangement = Arrangement.spacedBy(4.dp),
                    ) {
                        Row(
                            verticalAlignment = Alignment.CenterVertically,
                            horizontalArrangement = Arrangement.SpaceBetween,
                            modifier = Modifier.fillMaxWidth(),
                        ) {
                            Text(
                                text = if (isAsyncFallback) "已转入异步消息箱" else "SailTick 回复",
                                style = MaterialTheme.typography.labelMedium,
                                fontWeight = FontWeight.SemiBold,
                                color = MaterialTheme.colorScheme.onPrimaryContainer,
                            )
                            IconButton(
                                onClick = onDismissReply,
                                modifier = Modifier.size(22.dp),
                            ) {
                                Icon(
                                    Icons.Default.Close,
                                    contentDescription = "收起回复",
                                    modifier = Modifier.size(15.dp),
                                )
                            }
                        }
                        Text(
                            text = reply,
                            style = MaterialTheme.typography.bodySmall,
                            color = MaterialTheme.colorScheme.onSurface,
                        )
                    }
                }
            }
        }
    }
}

@Composable
private fun HealthSignalCard(signal: HealthSignalItemDto) {
    val label = when (signal.signalType) {
        "weight" -> "体重"
        "meal" -> "饮食"
        "exercise" -> "运动"
        "medication" -> "用药"
        "sleep" -> "睡眠"
        "mood" -> "心情"
        else -> signal.signalType
    }
    val summary = formatHealthSignalSummary(signal)
    Card(modifier = Modifier.fillMaxWidth()) {
        Row(
            verticalAlignment = Alignment.CenterVertically,
            modifier = Modifier.padding(12.dp),
        ) {
            Column(modifier = Modifier.weight(1f)) {
                Text(label, fontWeight = FontWeight.Medium)
                if (summary.isNotBlank()) {
                    Text(
                        summary,
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                }
            }
            signal.htime?.takeIf { it.length >= 16 }?.let {
                Text(
                    it.substring(11, 16),
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
        }
    }
}

private fun formatHealthSignalSummary(signal: HealthSignalItemDto): String {
    val obj = signal.valueJson as? kotlinx.serialization.json.JsonObject ?: return ""
    fun str(key: String): String? =
        (obj[key] as? kotlinx.serialization.json.JsonPrimitive)?.content?.takeIf { it.isNotBlank() && it != "null" }

    val parts = mutableListOf<String>()
    str("value_kg")?.let { parts += "$it kg" }
    str("weight")?.let { if (parts.isEmpty()) parts += "$it kg" }
    str("hours")?.let { parts += "$it 小时" }
    str("duration_min")?.let { parts += "$it 分钟" }
    str("minutes")?.let { parts += "$it 分钟" }
    str("calories")?.let { parts += "$it kcal" }
    str("title")?.let { parts += it }
    str("name")?.let { parts += it }
    str("note")?.let { parts += it }

    if (parts.isNotEmpty()) return parts.joinToString(" · ")
    return obj.entries
        .mapNotNull { (k, v) ->
            val text = (v as? kotlinx.serialization.json.JsonPrimitive)?.content?.takeIf { it.isNotBlank() && it != "null" }
            text?.let { "$k: $it" }
        }
        .joinToString(" · ")
}
