package com.sailzen.app.feature.plan.components

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.CheckCircle
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.FilledTonalButton
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import com.sailzen.app.core.network.dto.AffairDto
import com.sailzen.app.core.network.dto.VentureProgressDto
import com.sailzen.app.core.network.dto.kindLabel
import com.sailzen.app.feature.plan.PlanViewModel

/** 事业 Tab：待分拣事业（启动）+ 进行中事业卡（倒排灯 / 周预算 / 里程碑） */
@Composable
fun VenturesTab(
    state: PlanViewModel.UiState,
    onOpenDetail: (Int) -> Unit,
    onMilestoneDone: (Int) -> Unit,
    onConfirmVenture: (Int) -> Unit,
) {
    LazyColumn(
        modifier = Modifier.fillMaxSize().padding(horizontal = 12.dp),
        verticalArrangement = Arrangement.spacedBy(10.dp),
    ) {
        if (state.refreshing && state.ventures.isEmpty() && state.inboxVentures.isEmpty()) {
            item {
                Box(
                    modifier = Modifier.fillMaxWidth().padding(32.dp),
                    contentAlignment = Alignment.Center,
                ) { CircularProgressIndicator() }
            }
        }
        if (!state.refreshing && state.ventures.isEmpty() && state.inboxVentures.isEmpty()) {
            item {
                Card {
                    Text(
                        "暂无长期事业。点右下角 + 新建，或在今日 Tab 待分拣中确认已有的事业。",
                        modifier = Modifier.padding(16.dp),
                        color = Color.Gray,
                    )
                }
            }
        }
        if (state.inboxVentures.isNotEmpty()) {
            item {
                Text(
                    "待分拣事业",
                    style = MaterialTheme.typography.titleSmall,
                    modifier = Modifier.padding(top = 12.dp, bottom = 4.dp),
                )
            }
            items(state.inboxVentures, key = { it.id }) { venture ->
                InboxVentureCard(
                    venture = venture,
                    onOpenDetail = { onOpenDetail(venture.id) },
                    onConfirm = { onConfirmVenture(venture.id) },
                )
            }
        }
        if (state.ventures.isNotEmpty()) {
            item {
                Text(
                    "进行中",
                    style = MaterialTheme.typography.titleSmall,
                    modifier = Modifier.padding(top = 12.dp, bottom = 4.dp),
                )
            }
        }
        items(state.ventures, key = { it.affairId }) { progress ->
            VentureCard(
                progress = progress,
                onClick = { onOpenDetail(progress.affairId) },
                onMilestoneDone = onMilestoneDone,
            )
        }
        item { Spacer(Modifier.height(80.dp)) }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun VentureCard(
    progress: VentureProgressDto,
    onClick: () -> Unit,
    onMilestoneDone: (Int) -> Unit,
) {
    val pressure = progress.countdownPressure
    val (lampColor, lampText) = when {
        pressure == null -> Color.Gray to "—"
        pressure > 1.0 -> Color(0xFFE53935) to "倒排超压 %.2f".format(pressure)
        pressure > 0.8 -> Color(0xFFFFB300) to "倒排偏紧 %.2f".format(pressure)
        else -> Color(0xFF4CAF50) to "倒排健康 %.2f".format(pressure)
    }
    Card(
        onClick = onClick,
        colors = CardDefaults.cardColors(containerColor = Color(0xFFFFF8E1)),
        modifier = Modifier.fillMaxWidth(),
    ) {
        Column(modifier = Modifier.padding(14.dp)) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Column(modifier = Modifier.weight(1f)) {
                    Text(
                        progress.title,
                        fontWeight = FontWeight.Bold,
                        style = MaterialTheme.typography.titleMedium,
                    )
                    Text(
                        "目标日 ${progress.targetDate ?: "未定"}" +
                            (progress.weeksLeft?.let { " · 剩余 %.1f 周".format(it) } ?: ""),
                        style = MaterialTheme.typography.bodySmall,
                        color = Color.Gray,
                    )
                }
                Text(
                    lampText,
                    color = lampColor,
                    style = MaterialTheme.typography.bodySmall,
                    fontWeight = FontWeight.Bold,
                )
            }

            Spacer(Modifier.height(10.dp))
            val weekRatio = if (progress.weeklyBudgetHours > 0) {
                (progress.weekConsumedHours / progress.weeklyBudgetHours).coerceAtMost(1.0)
            } else {
                0.0
            }
            Text(
                "本周预算 %.1fh / %.1fh".format(progress.weekConsumedHours, progress.weeklyBudgetHours),
                style = MaterialTheme.typography.bodySmall,
            )
            LinearProgressIndicator(
                progress = { weekRatio.toFloat() },
                modifier = Modifier.fillMaxWidth().padding(top = 4.dp),
                color = Color(0xFFFF9800),
            )
            Text(
                "累计 %.1fh / 预估 %.0fh".format(progress.totalDoneHours, progress.totalEstHours),
                style = MaterialTheme.typography.bodySmall,
                color = Color.Gray,
                modifier = Modifier.padding(top = 4.dp),
            )

            if (progress.milestones.isNotEmpty()) {
                Spacer(Modifier.height(10.dp))
                Text(
                    "里程碑（完成 %.0f%%）".format(progress.completionRatio * 100),
                    style = MaterialTheme.typography.bodySmall,
                    fontWeight = FontWeight.Bold,
                )
                progress.milestones.take(3).forEach { milestone ->
                    MilestoneRow(milestone = milestone, onDone = { onMilestoneDone(milestone.id) })
                }
                if (progress.milestones.size > 3) {
                    Text(
                        "共 ${progress.milestones.size} 个里程碑，点击查看全部",
                        style = MaterialTheme.typography.bodySmall,
                        color = Color.Gray,
                        modifier = Modifier.padding(top = 4.dp),
                    )
                }
            }
        }
    }
}

@Composable
private fun InboxVentureCard(
    venture: AffairDto,
    onOpenDetail: () -> Unit,
    onConfirm: () -> Unit,
) {
    Card(
        onClick = onOpenDetail,
        colors = CardDefaults.cardColors(containerColor = Color(0xFFE3F2FD)),
        modifier = Modifier.fillMaxWidth(),
    ) {
        Column(modifier = Modifier.padding(14.dp)) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Column(modifier = Modifier.weight(1f)) {
                    Text(
                        venture.title,
                        fontWeight = FontWeight.Bold,
                        style = MaterialTheme.typography.titleMedium,
                    )
                    Text(
                        "待分拣 · ${kindLabel(venture.kind)}",
                        style = MaterialTheme.typography.bodySmall,
                        color = Color.Gray,
                    )
                }
                TextButton(onClick = onConfirm) { Text("启动") }
            }
        }
    }
}

@Composable
fun MilestoneRow(milestone: AffairDto, onDone: () -> Unit) {
    Row(
        verticalAlignment = Alignment.CenterVertically,
        modifier = Modifier.padding(top = 4.dp),
    ) {
        val done = milestone.state == "DONE"
        if (done) {
            Icon(
                Icons.Default.CheckCircle,
                contentDescription = "已完成",
                tint = Color(0xFF4CAF50),
                modifier = Modifier.size(18.dp),
            )
        } else {
            IconButton(onClick = onDone, modifier = Modifier.size(24.dp)) {
                Icon(
                    Icons.Default.CheckCircle,
                    contentDescription = "勾选完成",
                    tint = Color.Gray,
                    modifier = Modifier.size(18.dp),
                )
            }
        }
        Spacer(Modifier.size(6.dp))
        Text(
            milestone.title,
            style = MaterialTheme.typography.bodySmall,
            color = if (done) Color.Gray else Color.Unspecified,
        )
    }
}

@Composable
fun CreateVentureDialog(
    onDismiss: () -> Unit,
    onConfirm: (String, String?, Double) -> Unit,
) {
    var title by remember { mutableStateOf("") }
    var targetDate by remember { mutableStateOf("") }
    var weeklyHours by remember { mutableStateOf("8") }

    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text("新建长期事业") },
        text = {
            Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                OutlinedTextField(
                    value = title,
                    onValueChange = { title = it },
                    label = { Text("事业名称") },
                    modifier = Modifier.fillMaxWidth(),
                )
                OutlinedTextField(
                    value = targetDate,
                    onValueChange = { targetDate = it },
                    label = { Text("目标日 YYYY-MM-DD（可留空）") },
                    modifier = Modifier.fillMaxWidth(),
                )
                OutlinedTextField(
                    value = weeklyHours,
                    onValueChange = { weeklyHours = it },
                    label = { Text("每周投入预算（小时）") },
                    modifier = Modifier.fillMaxWidth(),
                )
            }
        },
        confirmButton = {
            FilledTonalButton(
                onClick = {
                    onConfirm(
                        title.trim(),
                        targetDate.trim().ifBlank { null },
                        weeklyHours.toDoubleOrNull() ?: 8.0,
                    )
                },
                enabled = title.isNotBlank(),
            ) { Text("创建") }
        },
        dismissButton = { TextButton(onClick = onDismiss) { Text("取消") } },
    )
}
