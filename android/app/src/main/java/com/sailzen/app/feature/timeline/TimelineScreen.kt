package com.sailzen.app.feature.timeline

import androidx.compose.foundation.ExperimentalFoundationApi
import androidx.compose.foundation.background
import androidx.compose.foundation.combinedClickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Add
import androidx.compose.material.icons.filled.Check
import androidx.compose.material.icons.filled.Close
import androidx.compose.material.icons.filled.Lock
import androidx.compose.material.icons.filled.PlayArrow
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material.icons.filled.Settings
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.ExposedDropdownMenuBox
import androidx.compose.material3.ExposedDropdownMenuDefaults
import androidx.compose.material3.FloatingActionButton
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.SwipeToDismissBox
import androidx.compose.material3.SwipeToDismissBoxValue
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TopAppBar
import androidx.compose.material3.rememberSwipeToDismissBoxState
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.lifecycle.viewmodel.compose.viewModel
import com.sailzen.app.core.network.dto.AffairDto
import com.sailzen.app.core.network.dto.CAPTURE_KINDS
import com.sailzen.app.core.network.dto.HealthSignalItemDto
import com.sailzen.app.core.network.dto.ReviewDto
import com.sailzen.app.core.network.dto.TimeBlockDto
import com.sailzen.app.R
import com.sailzen.app.core.network.dto.kindLabel

/** 块类型配色（设计文档 §8：骨架淡色铺底、fixed 深蓝锁定、precept 紫、habit 绿、career 橙、buffer 灰） */
fun blockColor(blockType: String): Color = when (blockType) {
    "sleep" -> Color(0xFF3F51B5)
    "commute" -> Color(0xFF90A4AE)
    "work_window" -> Color(0xFFCFD8DC)
    "micro_rest" -> Color(0xFFE0E0E0)
    "meal" -> Color(0xFFFFCC80)
    "precept" -> Color(0xFF9C27B0)
    "habit" -> Color(0xFF4CAF50)
    "fixed" -> Color(0xFF1565C0)
    "focus" -> Color(0xFF42A5F5)
    "light" -> Color(0xFF81D4FA)
    "career" -> Color(0xFFFF9800)
    "buffer" -> Color(0xFFBDBDBD)
    else -> Color(0xFF9E9E9E)
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

private fun hhmm(iso: String): String =
    if (iso.length >= 16) iso.substring(11, 16) else iso

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun TimelineScreen(
    onOpenSettings: () -> Unit,
    openCapture: Boolean = false,
    viewModel: TimelineViewModel = viewModel(),
) {
    val state by viewModel.uiState.collectAsState()

    // 外部（磁贴/通知）请求打开快速捕获
    androidx.compose.runtime.LaunchedEffect(openCapture) {
        if (openCapture) viewModel.openCapture()
    }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("时间线 ${state.date}") },
                actions = {
                    IconButton(onClick = { viewModel.plan() }, enabled = !state.planning) {
                        if (state.planning) {
                            CircularProgressIndicator(modifier = Modifier.size(20.dp), strokeWidth = 2.dp)
                        } else {
                            Icon(Icons.Default.PlayArrow, contentDescription = "生成日计划")
                        }
                    }
                    IconButton(onClick = { viewModel.refresh() }) {
                        Icon(Icons.Default.Refresh, contentDescription = "刷新")
                    }
                    IconButton(onClick = onOpenSettings) {
                        Icon(Icons.Default.Settings, contentDescription = "设置")
                    }
                },
            )
        },
        floatingActionButton = {
            FloatingActionButton(onClick = { viewModel.openCapture() }) {
                Icon(Icons.Default.Add, contentDescription = "快速捕获")
            }
        },
    ) { padding ->
        LazyColumn(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding)
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

            // ---------------- 周节奏卡片（rhythm_score + 三指标） ----------------
            state.weekReview?.let { review ->
                item {
                    WeekRhythmCard(review = review, onClick = { viewModel.openWeekReview() })
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

            // ---------------- AI 分拣建议卡（INBOX 待确认） ----------------
            val hinted = state.inbox.filter { it.aiHint.isNotEmpty() }
            if (hinted.isNotEmpty()) {
                item {
                    Text(
                        "待分拣（AI 建议）",
                        style = MaterialTheme.typography.titleSmall,
                        fontWeight = FontWeight.Bold,
                        modifier = Modifier.padding(top = 8.dp),
                    )
                }
                items(hinted, key = { "hint-${it.id}" }) { affair ->
                    HintCard(
                        affair = affair,
                        onAccept = { viewModel.acceptHint(affair.id) },
                        onReject = { viewModel.rejectHint(affair.id) },
                    )
                }
            }

            // ---------------- 当日时间线 ----------------
            item {
                Row(
                    verticalAlignment = Alignment.CenterVertically,
                    modifier = Modifier.padding(top = 8.dp),
                ) {
                    Text(
                        "当日编排 (v${state.timeline?.planVersion ?: 0})",
                        style = MaterialTheme.typography.titleSmall,
                        fontWeight = FontWeight.Bold,
                    )
                    Spacer(Modifier.weight(1f))
                    state.timeline?.let { tl ->
                        Text(
                            "生活 ${tl.domainMinutes.life}m / 工作 ${tl.domainMinutes.work}m / " +
                                "事业 ${tl.domainMinutes.career}m",
                            style = MaterialTheme.typography.bodySmall,
                            color = Color.Gray,
                        )
                    }
                }
            }

            val blocks = state.timeline?.blocks
                ?.filter { it.status != "MOVED" }
                ?.sortedBy { it.startTime }
                ?: emptyList()
            if (blocks.isEmpty()) {
                item {
                    Card {
                        Text(
                            "当日尚无编排。点右上角 ▶ 生成日计划，或点 + 快速捕获。",
                            modifier = Modifier.padding(16.dp),
                            color = Color.Gray,
                        )
                    }
                }
            }
            items(blocks, key = { "block-${it.id}" }) { block ->
                TimelineBlockItem(
                    block = block,
                    onDone = { viewModel.doneBlock(block.id) },
                    onDefer = { viewModel.deferBlock(block) },
                    onLongPress = { viewModel.showPlanB(block) },
                )
            }

            // ---------------- 缓冲余量 ----------------
            state.timeline?.let { tl ->
                if (tl.bufferTotalMinutes > 0) {
                    item {
                        Column(modifier = Modifier.padding(vertical = 8.dp)) {
                            Text(
                                "缓冲余量 ${tl.bufferFreeMinutes}/${tl.bufferTotalMinutes}min · " +
                                    "精力 ${tl.energyConsumed}/${tl.energyBudget}",
                                style = MaterialTheme.typography.bodySmall,
                                color = Color.Gray,
                            )
                            LinearProgressIndicator(
                                progress = {
                                    if (tl.bufferTotalMinutes > 0)
                                        tl.bufferFreeMinutes.toFloat() / tl.bufferTotalMinutes else 0f
                                },
                                modifier = Modifier
                                    .fillMaxWidth()
                                    .padding(top = 4.dp),
                            )
                        }
                    }
                }
            }
            item { Spacer(Modifier.height(80.dp)) }
        }
    }

    // ---------------- Plan B 弹窗 ----------------
    state.planBBlock?.let { block ->
        AlertDialog(
            onDismissRequest = { viewModel.dismissPlanB() },
            title = { Text("备用方案 (Plan B)") },
            text = {
                Column {
                    Text(block.affairTitle ?: block.blockType, fontWeight = FontWeight.Bold)
                    Spacer(Modifier.height(8.dp))
                    Text(state.planBText ?: "加载中…")
                }
            },
            confirmButton = {
                TextButton(onClick = { viewModel.dismissPlanB() }) { Text("知道了") }
            },
        )
    }

    // ---------------- 快速捕获弹窗 ----------------
    if (state.captureOpen) {
        CaptureDialog(
            onDismiss = { viewModel.closeCapture() },
            onConfirm = { title, kind -> viewModel.capture(title, kind) },
        )
    }

    // ---------------- 周报详情弹窗 ----------------
    if (state.weekReviewOpen) {
        state.weekReview?.let { review ->
            AlertDialog(
                onDismissRequest = { viewModel.closeWeekReview() },
                title = { Text("节奏周报 ${review.periodKey}") },
                text = {
                    Column {
                        Text("节奏分 %.1f / 100".format(review.rhythmScore),
                            fontWeight = FontWeight.Bold)
                        Spacer(Modifier.height(8.dp))
                        Text("戒律合规率 %.0f%%".format(review.preceptComplianceRate * 100))
                        Text("习惯达标率 %.0f%%".format(review.habitConsistency * 100))
                        Text("睡眠窗守约 %.0f%%".format(review.sleepWindowKeeping * 100))
                        Text("事业预算达成 %.0f%%".format(review.ventureBudgetFulfillment * 100))
                        Text("缓冲消耗 %.0f%%".format(review.bufferConsumed * 100))
                        Text("侵占事件 ${review.encroachments.size} 起")
                        if (review.aiSummary.isNotBlank()) {
                            Spacer(Modifier.height(8.dp))
                            Text("AI 周评", fontWeight = FontWeight.Bold)
                            Text(review.aiSummary, style = MaterialTheme.typography.bodySmall)
                        }
                    }
                },
                confirmButton = {
                    TextButton(onClick = { viewModel.closeWeekReview() }) { Text("关闭") }
                },
            )
        }
    }
}

/** 周节奏卡片：rhythm_score 环形图 + 戒律/习惯/事业三指标（点击看周报） */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun WeekRhythmCard(review: ReviewDto, onClick: () -> Unit) {
    Card(
        onClick = onClick,
        colors = CardDefaults.cardColors(containerColor = Color(0xFFE8F5E9)),
        modifier = Modifier.fillMaxWidth(),
    ) {
        Row(
            verticalAlignment = Alignment.CenterVertically,
            modifier = Modifier.padding(12.dp),
        ) {
            Box(contentAlignment = Alignment.Center, modifier = Modifier.size(56.dp)) {
                CircularProgressIndicator(
                    progress = { (review.rhythmScore / 100.0).toFloat().coerceIn(0f, 1f) },
                    modifier = Modifier.fillMaxSize(),
                    color = when {
                        review.rhythmScore >= 80 -> Color(0xFF4CAF50)
                        review.rhythmScore >= 60 -> Color(0xFFFFB300)
                        else -> Color(0xFFE53935)
                    },
                    strokeWidth = 5.dp,
                )
                Text(
                    "%.0f".format(review.rhythmScore),
                    fontWeight = FontWeight.Bold,
                    style = MaterialTheme.typography.titleMedium,
                )
            }
            Spacer(Modifier.width(14.dp))
            Column {
                Text("本周节奏 ${review.periodKey}", fontWeight = FontWeight.Bold,
                    style = MaterialTheme.typography.titleSmall)
                Spacer(Modifier.height(4.dp))
                Text(
                    "戒律 %.0f%% · 习惯 %.0f%% · 事业 %.0f%%".format(
                        review.preceptComplianceRate * 100,
                        review.habitConsistency * 100,
                        review.ventureBudgetFulfillment * 100,
                    ),
                    style = MaterialTheme.typography.bodySmall,
                    color = Color(0xFF2E7D32),
                )
                Text(
                    "点击查看周报",
                    style = MaterialTheme.typography.labelSmall,
                    color = Color.Gray,
                )
            }
        }
    }
}

@Composable
private fun HintCard(affair: AffairDto, onAccept: () -> Unit, onReject: () -> Unit) {
    val hintKind = affair.aiHint["kind"]?.toString()?.trim('"') ?: affair.kind
    val reason = affair.aiHint["reason"]?.toString()?.trim('"') ?: ""
    Card(
        colors = CardDefaults.cardColors(containerColor = Color(0xFFF3E5F5)),
        modifier = Modifier.fillMaxWidth(),
    ) {
        Column(modifier = Modifier.padding(12.dp)) {
            Text(affair.title, fontWeight = FontWeight.Bold)
            Text(
                "建议判为「${kindLabel(hintKind)}」" + (if (reason.isNotBlank()) "：$reason" else ""),
                style = MaterialTheme.typography.bodySmall,
                color = Color(0xFF6A1B9A),
            )
            Row(
                horizontalArrangement = Arrangement.End,
                modifier = Modifier.fillMaxWidth(),
            ) {
                TextButton(onClick = onReject) { Text("驳回") }
                TextButton(onClick = onAccept) { Text("采纳并确认") }
            }
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class, ExperimentalFoundationApi::class)
@Composable
private fun TimelineBlockItem(
    block: TimeBlockDto,
    onDone: () -> Unit,
    onDefer: () -> Unit,
    onLongPress: () -> Unit,
) {
    val deferrable = block.affairId != null && !block.pinned && block.blockType != "fixed"
    val done = block.status == "DONE"
    val skipped = block.status == "SKIPPED"

    val dismissState = rememberSwipeToDismissBoxState(
        confirmValueChange = { value ->
            when (value) {
                SwipeToDismissBoxValue.StartToEnd -> { onDone(); false }
                SwipeToDismissBoxValue.EndToStart -> { if (deferrable) onDefer(); false }
                SwipeToDismissBoxValue.Settled -> true
            }
        },
        positionalThreshold = { it * 0.4f },
    )

    SwipeToDismissBox(
        state = dismissState,
        backgroundContent = {
            val isDone = dismissState.dismissDirection == SwipeToDismissBoxValue.StartToEnd
            Box(
                modifier = Modifier
                    .fillMaxSize()
                    .clip(RoundedCornerShape(12.dp))
                    .background(if (isDone) Color(0xFF4CAF50) else Color(0xFFFFB74D))
                    .padding(horizontal = 20.dp),
                contentAlignment = if (isDone) Alignment.CenterStart else Alignment.CenterEnd,
            ) {
                Icon(
                    if (isDone) Icons.Default.Check else Icons.Default.Close,
                    contentDescription = null,
                    tint = Color.White,
                )
            }
        },
        modifier = Modifier.fillMaxWidth(),
    ) {
        Card(
            colors = CardDefaults.cardColors(
                containerColor = when {
                    done -> Color(0xFFE8F5E9)
                    skipped -> Color(0xFFF5F5F5)
                    else -> MaterialTheme.colorScheme.surface
                },
            ),
            modifier = Modifier
                .fillMaxWidth()
                .combinedClickable(onClick = {}, onLongClick = onLongPress),
        ) {
            Row(
                verticalAlignment = Alignment.CenterVertically,
                modifier = Modifier.padding(10.dp),
            ) {
                Box(
                    modifier = Modifier
                        .width(6.dp)
                        .height(40.dp)
                        .clip(RoundedCornerShape(3.dp))
                        .background(blockColor(block.blockType)),
                )
                Spacer(Modifier.width(10.dp))
                Column(modifier = Modifier.weight(1f)) {
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Text(
                            "${hhmm(block.startTime)} - ${hhmm(block.endTime)}",
                            style = MaterialTheme.typography.bodySmall,
                            color = Color.Gray,
                        )
                        if (block.pinned) {
                            Spacer(Modifier.width(4.dp))
                            Icon(
                                Icons.Default.Lock,
                                contentDescription = "pinned",
                                modifier = Modifier.size(12.dp),
                                tint = Color.Gray,
                            )
                        }
                        if (block.energyCost > 0) {
                            Spacer(Modifier.width(6.dp))
                            Text(
                                "⚡${block.energyCost}",
                                style = MaterialTheme.typography.bodySmall,
                                color = Color(0xFFFF6F00),
                            )
                        }
                    }
                    Text(
                        block.affairTitle ?: (block.ref["label"]?.toString()?.trim('"') ?: block.blockType),
                        fontWeight = if (done) FontWeight.Normal else FontWeight.Medium,
                        color = if (done || skipped) Color.Gray else Color.Unspecified,
                    )
                    block.affairKind?.let {
                        Text(
                            kindLabel(it),
                            style = MaterialTheme.typography.labelSmall,
                            color = blockColor(block.blockType),
                        )
                    }
                }
                Text(
                    when (block.status) {
                        "DONE" -> "✓"
                        "SKIPPED" -> "—"
                        "DOING" -> "…"
                        else -> ""
                    },
                    color = if (block.status == "DONE") Color(0xFF4CAF50) else Color.Gray,
                )
            }
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun CaptureDialog(onDismiss: () -> Unit, onConfirm: (String, String) -> Unit) {
    var title by remember { mutableStateOf("") }
    var kind by remember { mutableStateOf("generic") }
    var expanded by remember { mutableStateOf(false) }

    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text("快速捕获") },
        text = {
            Column {
                OutlinedTextField(
                    value = title,
                    onValueChange = { title = it },
                    label = { Text("一句话事务") },
                    singleLine = true,
                    modifier = Modifier.fillMaxWidth(),
                )
                Spacer(Modifier.height(12.dp))
                ExposedDropdownMenuBox(expanded = expanded, onExpandedChange = { expanded = it }) {
                    OutlinedTextField(
                        value = kindLabel(kind),
                        onValueChange = {},
                        readOnly = true,
                        label = { Text("种类（默认未分类，交给 AI 分拣）") },
                        trailingIcon = { ExposedDropdownMenuDefaults.TrailingIcon(expanded = expanded) },
                        modifier = Modifier
                            .fillMaxWidth()
                            .menuAnchor(),
                    )
                    ExposedDropdownMenu(expanded = expanded, onDismissRequest = { expanded = false }) {
                        CAPTURE_KINDS.forEach { k ->
                            DropdownMenuItem(
                                text = { Text(kindLabel(k)) },
                                onClick = { kind = k; expanded = false },
                            )
                        }
                    }
                }
            }
        },
        confirmButton = {
            TextButton(onClick = { onConfirm(title, kind) }, enabled = title.isNotBlank()) {
                Text("捕获")
            }
        },
        dismissButton = { TextButton(onClick = onDismiss) { Text("取消") } },
    )
}
