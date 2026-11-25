package com.sailzen.app.feature.plan.components

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
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
import androidx.compose.foundation.shape.RoundedCornerShape
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
import androidx.compose.material3.Surface
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
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import com.sailzen.app.core.network.dto.AffairDto
import com.sailzen.app.core.network.dto.VentureProgressDto
import com.sailzen.app.core.network.dto.kindLabel
import com.sailzen.app.feature.plan.PlanViewModel

/** 项目 Tab：轻量化长期项目视图（目标日倒计时 + 里程碑进度 + 近 14 天投入，去除重型周预算与倒排压力公式） */
@Composable
fun VenturesTab(
    state: PlanViewModel.UiState,
    onOpenDetail: (Int) -> Unit,
    onMilestoneDone: (Int) -> Unit,
    onConfirmVenture: (Int) -> Unit,
) {
    LazyColumn(
        modifier = Modifier
            .fillMaxSize()
            .padding(horizontal = 12.dp),
        contentPadding = PaddingValues(top = 8.dp, bottom = 84.dp),
        verticalArrangement = Arrangement.spacedBy(10.dp),
    ) {
        if (state.refreshing && state.ventures.isEmpty() && state.inboxVentures.isEmpty()) {
            item {
                Box(
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(32.dp),
                    contentAlignment = Alignment.Center,
                ) { CircularProgressIndicator() }
            }
        }
        if (!state.refreshing && state.ventures.isEmpty() && state.inboxVentures.isEmpty()) {
            item {
                Card(modifier = Modifier.fillMaxWidth()) {
                    Text(
                        "暂无进行中的长期项目。点右下角 + 新建，或在今日页直接告诉 SailTick「我想启动一个新项目」。",
                        modifier = Modifier.padding(16.dp),
                        style = MaterialTheme.typography.bodyMedium,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                }
            }
        }
        if (state.inboxVentures.isNotEmpty()) {
            item {
                Text(
                    "待启动项目",
                    style = MaterialTheme.typography.titleSmall,
                    fontWeight = FontWeight.Bold,
                    modifier = Modifier.padding(top = 4.dp),
                )
            }
            items(state.inboxVentures, key = { "inbox-v-${it.id}" }) { venture ->
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
                    "重点项目（${state.ventures.size}）",
                    style = MaterialTheme.typography.titleSmall,
                    fontWeight = FontWeight.Bold,
                    modifier = Modifier.padding(top = 4.dp),
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
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun VentureCard(
    progress: VentureProgressDto,
    onClick: () -> Unit,
    onMilestoneDone: (Int) -> Unit,
) {
    val (deadlineLabel, isUrgent) = PlanViewModel.projectDeadlineBadge(progress.daysLeft)
    Card(
        onClick = onClick,
        colors = CardDefaults.cardColors(
            containerColor = MaterialTheme.colorScheme.surfaceContainerLow,
        ),
        modifier = Modifier.fillMaxWidth(),
    ) {
        Column(modifier = Modifier.padding(14.dp)) {
            Row(
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.spacedBy(8.dp),
            ) {
                Column(modifier = Modifier.weight(1f)) {
                    Text(
                        progress.title,
                        fontWeight = FontWeight.Bold,
                        style = MaterialTheme.typography.titleMedium,
                        maxLines = 2,
                        overflow = TextOverflow.Ellipsis,
                    )
                    if (progress.description.isNotBlank()) {
                        Text(
                            progress.description,
                            style = MaterialTheme.typography.bodySmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                            maxLines = 2,
                            overflow = TextOverflow.Ellipsis,
                        )
                    }
                }
                Surface(
                    shape = RoundedCornerShape(999.dp),
                    color = if (isUrgent) {
                        MaterialTheme.colorScheme.errorContainer
                    } else {
                        MaterialTheme.colorScheme.secondaryContainer
                    },
                ) {
                    Text(
                        text = deadlineLabel,
                        style = MaterialTheme.typography.labelSmall,
                        fontWeight = FontWeight.Medium,
                        color = if (isUrgent) {
                            MaterialTheme.colorScheme.onErrorContainer
                        } else {
                            MaterialTheme.colorScheme.onSecondaryContainer
                        },
                        modifier = Modifier.padding(horizontal = 8.dp, vertical = 3.dp),
                    )
                }
            }

            Spacer(Modifier.height(8.dp))
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
            ) {
                Text(
                    text = "目标日 ${progress.targetDate ?: "未定"}",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
                Text(
                    text = "近14天投入 %.1fh · 累计 %.1fh".format(progress.recent14dHours, progress.totalDoneHours),
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }

            if (progress.milestones.isNotEmpty()) {
                Spacer(Modifier.height(10.dp))
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.SpaceBetween,
                    verticalAlignment = Alignment.CenterVertically,
                ) {
                    Text(
                        "里程碑进度",
                        style = MaterialTheme.typography.labelMedium,
                        fontWeight = FontWeight.SemiBold,
                    )
                    Text(
                        "%.0f%%".format(progress.completionRatio * 100),
                        style = MaterialTheme.typography.labelMedium,
                        color = MaterialTheme.colorScheme.primary,
                    )
                }
                LinearProgressIndicator(
                    progress = { progress.completionRatio.toFloat().coerceIn(0f, 1f) },
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(top = 4.dp, bottom = 6.dp),
                )
                progress.milestones.take(3).forEach { milestone ->
                    MilestoneRow(milestone = milestone, onDone = { onMilestoneDone(milestone.id) })
                }
                if (progress.milestones.size > 3) {
                    Text(
                        "共 ${progress.milestones.size} 个里程碑，点击查看全部",
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
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
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.primaryContainer.copy(alpha = 0.45f)),
        modifier = Modifier.fillMaxWidth(),
    ) {
        Row(
            verticalAlignment = Alignment.CenterVertically,
            modifier = Modifier.padding(14.dp),
        ) {
            Column(modifier = Modifier.weight(1f)) {
                Text(
                    venture.title,
                    fontWeight = FontWeight.Bold,
                    style = MaterialTheme.typography.titleMedium,
                )
                Text(
                    "待启动 · ${kindLabel(venture.kind)}",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
            TextButton(onClick = onConfirm) { Text("启动") }
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
            color = if (done) Color.Gray else MaterialTheme.colorScheme.onSurface,
        )
    }
}

@Composable
fun CreateVentureDialog(
    onDismiss: () -> Unit,
    onConfirm: (title: String, targetDate: String?, description: String) -> Unit,
) {
    var title by remember { mutableStateOf("") }
    var targetDate by remember { mutableStateOf("") }
    var description by remember { mutableStateOf("") }

    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text("新建项目") },
        text = {
            Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                OutlinedTextField(
                    value = title,
                    onValueChange = { title = it },
                    label = { Text("项目名称") },
                    singleLine = true,
                    modifier = Modifier.fillMaxWidth(),
                )
                OutlinedTextField(
                    value = targetDate,
                    onValueChange = { targetDate = it },
                    label = { Text("目标日 YYYY-MM-DD（可选）") },
                    singleLine = true,
                    modifier = Modifier.fillMaxWidth(),
                )
                OutlinedTextField(
                    value = description,
                    onValueChange = { description = it },
                    label = { Text("一句话背景（可选，便于 SailTick 理解）") },
                    minLines = 2,
                    maxLines = 3,
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
                        description.trim(),
                    )
                },
                enabled = title.isNotBlank(),
            ) { Text("创建") }
        },
        dismissButton = { TextButton(onClick = onDismiss) { Text("取消") } },
    )
}
