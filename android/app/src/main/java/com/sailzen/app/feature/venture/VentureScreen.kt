package com.sailzen.app.feature.venture

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
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.lifecycle.viewmodel.compose.viewModel
import com.sailzen.app.core.network.dto.VentureProgressDto

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun VentureScreen(viewModel: VentureViewModel = viewModel()) {
    val state by viewModel.uiState.collectAsState()

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("长期事业") },
                actions = {
                    IconButton(onClick = { viewModel.refresh() }) {
                        Icon(Icons.Default.Refresh, contentDescription = "刷新")
                    }
                },
            )
        },
    ) { padding ->
        LazyColumn(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding)
                .padding(horizontal = 12.dp),
            verticalArrangement = Arrangement.spacedBy(10.dp),
        ) {
            if (state.refreshing && state.ventures.isEmpty()) {
                item {
                    Box(
                        modifier = Modifier.fillMaxWidth().padding(32.dp),
                        contentAlignment = Alignment.Center,
                    ) { CircularProgressIndicator() }
                }
            }
            if (!state.refreshing && state.ventures.isEmpty()) {
                item {
                    Card {
                        Text(
                            "暂无 ACTIVE 长期事业。\n可通过 CLI: sailzen rhythm capture \"独立游戏上线\" " +
                                "--kind venture --meta '{\"target_date\":\"2027-04-01\",\"weekly_budget_hours\":8}' 创建。",
                            modifier = Modifier.padding(16.dp),
                            color = Color.Gray,
                        )
                    }
                }
            }
            items(state.ventures, key = { it.affairId }) { progress ->
                VentureCard(progress = progress, onMilestoneDone = { viewModel.milestoneDone(it) })
            }
            item { Spacer(Modifier.height(80.dp)) }
        }
    }
}

@Composable
private fun VentureCard(progress: VentureProgressDto, onMilestoneDone: (Int) -> Unit) {
    val pressure = progress.countdownPressure
    val (lampColor, lampText) = when {
        pressure == null -> Color.Gray to "—"
        pressure > 1.0 -> Color(0xFFE53935) to "倒排超压 %.2f".format(pressure)
        pressure > 0.8 -> Color(0xFFFFB300) to "倒排偏紧 %.2f".format(pressure)
        else -> Color(0xFF4CAF50) to "倒排健康 %.2f".format(pressure)
    }
    Card(
        colors = CardDefaults.cardColors(containerColor = Color(0xFFFFF8E1)),
        modifier = Modifier.fillMaxWidth(),
    ) {
        Column(modifier = Modifier.padding(14.dp)) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Column(modifier = Modifier.weight(1f)) {
                    Text(progress.title, fontWeight = FontWeight.Bold,
                        style = MaterialTheme.typography.titleMedium)
                    Text(
                        "目标日 ${progress.targetDate ?: "未定"}" +
                            (progress.weeksLeft?.let { " · 剩余 %.1f 周".format(it) } ?: ""),
                        style = MaterialTheme.typography.bodySmall,
                        color = Color.Gray,
                    )
                }
                Text(lampText, color = lampColor, style = MaterialTheme.typography.bodySmall,
                    fontWeight = FontWeight.Bold)
            }

            Spacer(Modifier.height(10.dp))
            // 本周预算进度条
            val weekRatio = if (progress.weeklyBudgetHours > 0)
                (progress.weekConsumedHours / progress.weeklyBudgetHours).coerceAtMost(1.2) else 0.0
            Text(
                "本周预算 %.1fh / %.1fh".format(progress.weekConsumedHours, progress.weeklyBudgetHours),
                style = MaterialTheme.typography.bodySmall,
            )
            LinearProgressIndicator(
                progress = { weekRatio.toFloat().coerceAtMost(1f) },
                modifier = Modifier.fillMaxWidth().padding(top = 4.dp),
                color = Color(0xFFFF9800),
            )
            Text(
                "累计 %.1fh / 预估 %.0fh".format(progress.totalDoneHours, progress.totalEstHours),
                style = MaterialTheme.typography.bodySmall,
                color = Color.Gray,
                modifier = Modifier.padding(top = 4.dp),
            )

            // 里程碑
            if (progress.milestones.isNotEmpty()) {
                Spacer(Modifier.height(10.dp))
                Text(
                    "里程碑（完成 %.0f%%）".format(progress.completionRatio * 100),
                    style = MaterialTheme.typography.bodySmall,
                    fontWeight = FontWeight.Bold,
                )
                progress.milestones.forEach { m ->
                    Row(
                        verticalAlignment = Alignment.CenterVertically,
                        modifier = Modifier.padding(top = 4.dp),
                    ) {
                        if (m.state == "DONE") {
                            Icon(
                                Icons.Default.CheckCircle,
                                contentDescription = "done",
                                tint = Color(0xFF4CAF50),
                                modifier = Modifier.size(18.dp),
                            )
                        } else {
                            IconButton(
                                onClick = { onMilestoneDone(m.id) },
                                modifier = Modifier.size(24.dp),
                            ) {
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
                            m.title,
                            style = MaterialTheme.typography.bodySmall,
                            color = if (m.state == "DONE") Color.Gray else Color.Unspecified,
                        )
                    }
                }
            }
        }
    }
}
