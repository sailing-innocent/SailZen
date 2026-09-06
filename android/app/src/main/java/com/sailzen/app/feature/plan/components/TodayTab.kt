package com.sailzen.app.feature.plan.components

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import com.sailzen.app.R
import com.sailzen.app.core.network.dto.HealthSignalItemDto
import com.sailzen.app.core.network.dto.TimeBlockDto
import com.sailzen.app.feature.plan.PlanViewModel

/**
 * 今日 Tab：捕获 → 待分拣 → 周节奏 → 打卡 → 时间线 → 页脚，同帧联动刷新。
 * 未配置服务器 / 离线队列提示置于最顶（沿用旧时间线页行为）。
 */
@Composable
fun TodayTab(
    state: PlanViewModel.UiState,
    onCapture: (String, String) -> Unit,
    onAcceptHint: (Int) -> Unit,
    onRejectHint: (Int) -> Unit,
    onConfirmInbox: (Int) -> Unit,
    onCancelInbox: (Int) -> Unit,
    onOpenWeekReview: () -> Unit,
    onPreceptKept: (com.sailzen.app.core.network.dto.CheckinTodayItemDto) -> Unit,
    onPreceptViolated: (com.sailzen.app.core.network.dto.CheckinTodayItemDto) -> Unit,
    onHabitDone: (com.sailzen.app.core.network.dto.CheckinTodayItemDto) -> Unit,
    onHabitMissed: (com.sailzen.app.core.network.dto.CheckinTodayItemDto) -> Unit,
    onDoneBlock: (Int) -> Unit,
    onDeferBlock: (TimeBlockDto) -> Unit,
    onPlanB: (TimeBlockDto) -> Unit,
) {
    LazyColumn(
        modifier = Modifier
            .fillMaxSize()
            .padding(horizontal = 12.dp),
        verticalArrangement = Arrangement.spacedBy(8.dp),
    ) {
        if (!state.configured) {
            item {
                Card(colors = CardDefaults.cardColors(containerColor = Color(0xFFFFF3E0))) {
                    Text(
                        "未配置服务器地址，请到设置页填写",
                        modifier = Modifier.padding(12.dp),
                        color = Color(0xFFE65100),
                    )
                }
            }
        }
        if (state.queuedCount > 0) {
            item {
                Card(colors = CardDefaults.cardColors(containerColor = Color(0xFFE3F2FD))) {
                    Text(
                        "离线队列 ${state.queuedCount} 条待补传",
                        modifier = Modifier.padding(12.dp),
                        color = Color(0xFF1565C0),
                    )
                }
            }
        }

        // ---------------- 吸顶捕获栏（核心入口） ----------------
        item {
            CaptureBar(onCapture = onCapture)
        }

        // ---------------- 待分拣（INBOX + AI 建议） ----------------
        item {
            InboxSection(
                inbox = state.inbox,
                onAcceptHint = { onAcceptHint(it.id) },
                onRejectHint = { onRejectHint(it.id) },
                onConfirm = { onConfirmInbox(it.id) },
                onCancel = { onCancelInbox(it.id) },
            )
        }

        // ---------------- 周节奏卡 ----------------
        state.weekReview?.let { review ->
            item {
                WeekRhythmCard(review = review, onClick = onOpenWeekReview)
            }
        }

        // ---------------- 今日健康信号摘要 ----------------
        if (state.healthSignals.isNotEmpty()) {
            item {
                Text(
                    stringResource(R.string.health_signals_title),
                    style = MaterialTheme.typography.titleSmall,
                    fontWeight = FontWeight.Bold,
                    modifier = Modifier.padding(top = 8.dp),
                )
            }
            items(state.healthSignals, key = { "hs-${it.refId}-${it.signalType}" }) { signal ->
                HealthSignalCard(signal = signal)
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

        // ---------------- 当日时间线 ----------------
        item { TimelineSectionHeader(state.timeline) }
        val blocks = state.timeline?.blocks
            ?.filter { it.status != "MOVED" }
            ?.sortedBy { it.startTime }
            ?: emptyList()
        if (blocks.isEmpty()) {
            item {
                Card {
                    Text(
                        "当日尚无编排。点右上角 ▶ 生成日计划，或先在顶部捕获事务。",
                        modifier = Modifier.padding(16.dp),
                        color = Color.Gray,
                    )
                }
            }
        }
        items(blocks, key = { "block-${it.id}" }) { block ->
            TimelineBlockItem(
                block = block,
                onDone = { onDoneBlock(block.id) },
                onDefer = { onDeferBlock(block) },
                onLongPress = { onPlanB(block) },
            )
        }

        // ---------------- 缓冲余量页脚 ----------------
        state.timeline?.let { tl ->
            if (tl.bufferTotalMinutes > 0) {
                item { TimelineBufferFooter(tl) }
            }
        }
        item { Spacer(Modifier.height(80.dp)) }
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
    Card(modifier = Modifier.fillMaxWidth()) {
        Row(
            verticalAlignment = Alignment.CenterVertically,
            modifier = Modifier.padding(12.dp),
        ) {
            Column(modifier = Modifier.weight(1f)) {
                Text(label, fontWeight = FontWeight.Medium)
                Text(
                    signal.valueJson.toString(),
                    style = MaterialTheme.typography.bodySmall,
                    color = Color.Gray,
                )
            }
            signal.htime?.let {
                Text(it.substring(11, 16), style = MaterialTheme.typography.bodySmall)
            }
        }
    }
}
