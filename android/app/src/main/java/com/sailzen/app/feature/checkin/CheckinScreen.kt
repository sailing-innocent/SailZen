package com.sailzen.app.feature.checkin

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
import androidx.compose.material.icons.filled.Check
import androidx.compose.material.icons.filled.Close
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.FilledTonalButton
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.lifecycle.viewmodel.compose.viewModel
import com.sailzen.app.core.network.dto.CheckinTodayItemDto

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun CheckinScreen(viewModel: CheckinViewModel = viewModel()) {
    val state by viewModel.uiState.collectAsState()

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("打卡 ${state.checkins?.date ?: ""}") },
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
            verticalArrangement = Arrangement.spacedBy(8.dp),
        ) {
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
            if (state.refreshing && state.checkins == null) {
                item {
                    Box(modifier = Modifier.fillMaxWidth().padding(32.dp),
                        contentAlignment = Alignment.Center) {
                        CircularProgressIndicator()
                    }
                }
            }

            // ---------------- 戒律 ----------------
            item {
                Text(
                    "戒律",
                    style = MaterialTheme.typography.titleSmall,
                    fontWeight = FontWeight.Bold,
                    modifier = Modifier.padding(top = 8.dp),
                )
            }
            val precepts = state.checkins?.precepts ?: emptyList()
            if (precepts.isEmpty()) {
                item { Text("今日无戒律项", color = Color.Gray, style = MaterialTheme.typography.bodySmall) }
            }
            items(precepts, key = { "p-${it.affair.id}" }) { item ->
                PreceptCard(
                    item = item,
                    onKept = { viewModel.preceptKept(item) },
                    onViolated = { viewModel.preceptViolated(item) },
                )
            }

            // ---------------- 习惯 ----------------
            item {
                Text(
                    "习惯",
                    style = MaterialTheme.typography.titleSmall,
                    fontWeight = FontWeight.Bold,
                    modifier = Modifier.padding(top = 12.dp),
                )
            }
            val habits = state.checkins?.habits ?: emptyList()
            if (habits.isEmpty()) {
                item { Text("今日无习惯项", color = Color.Gray, style = MaterialTheme.typography.bodySmall) }
            }
            items(habits, key = { "h-${it.affair.id}" }) { item ->
                HabitCard(
                    item = item,
                    onDone = { viewModel.habitDone(item) },
                    onMissed = { viewModel.habitMissed(item) },
                )
            }
            item { Spacer(Modifier.height(80.dp)) }
        }
    }

    // 破戒备注弹窗
    state.noteTarget?.let { target ->
        var note by remember { mutableStateOf("") }
        AlertDialog(
            onDismissRequest = { viewModel.dismissNote() },
            title = { Text("破戒备注") },
            text = {
                Column {
                    Text(target.affair.title, fontWeight = FontWeight.Bold)
                    Spacer(Modifier.height(8.dp))
                    OutlinedTextField(
                        value = note,
                        onValueChange = { note = it },
                        label = { Text("原因（供 AI 复盘归因）") },
                        modifier = Modifier.fillMaxWidth(),
                    )
                }
            },
            confirmButton = {
                TextButton(onClick = { viewModel.confirmViolate(note) }) { Text("记录破戒") }
            },
            dismissButton = {
                TextButton(onClick = { viewModel.dismissNote() }) { Text("取消") }
            },
        )
    }
}

@Composable
private fun PreceptCard(item: CheckinTodayItemDto, onKept: () -> Unit, onViolated: () -> Unit) {
    val ruleText = item.affair.kindMeta["rule_text"]?.toString()?.trim('"')
        ?: item.affair.title
    Card(
        colors = CardDefaults.cardColors(
            containerColor = if (item.doneToday) Color(0xFFF3E5F5) else MaterialTheme.colorScheme.surface,
        ),
        modifier = Modifier.fillMaxWidth(),
    ) {
        Row(
            verticalAlignment = Alignment.CenterVertically,
            modifier = Modifier.padding(12.dp),
        ) {
            Column(modifier = Modifier.weight(1f)) {
                Text(ruleText, fontWeight = FontWeight.Medium)
                Text(
                    when (item.lastResult) {
                        "kept" -> "已守住 ✓"
                        "violated" -> "已破戒 ✗"
                        "exempt" -> "已豁免"
                        else -> "待打卡"
                    },
                    style = MaterialTheme.typography.bodySmall,
                    color = when (item.lastResult) {
                        "kept" -> Color(0xFF4CAF50)
                        "violated" -> Color(0xFFE53935)
                        else -> Color.Gray
                    },
                )
            }
            if (!item.doneToday) {
                IconButton(onClick = onKept) {
                    Icon(Icons.Default.Check, contentDescription = "守住", tint = Color(0xFF4CAF50))
                }
                IconButton(onClick = onViolated) {
                    Icon(Icons.Default.Close, contentDescription = "破戒", tint = Color(0xFFE53935))
                }
            }
        }
    }
}

@Composable
private fun HabitCard(item: CheckinTodayItemDto, onDone: () -> Unit, onMissed: () -> Unit) {
    val streak = item.affair.kindMeta["streak"]?.toString()?.toIntOrNull() ?: 0
    Card(
        colors = CardDefaults.cardColors(
            containerColor = if (item.doneToday) Color(0xFFE8F5E9) else MaterialTheme.colorScheme.surface,
        ),
        modifier = Modifier.fillMaxWidth(),
    ) {
        Row(
            verticalAlignment = Alignment.CenterVertically,
            modifier = Modifier.padding(12.dp),
        ) {
            Column(modifier = Modifier.weight(1f)) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Text(item.affair.title, fontWeight = FontWeight.Medium)
                    if (streak >= 3) {
                        Spacer(Modifier.size(6.dp))
                        Text("🔥$streak", style = MaterialTheme.typography.bodySmall)
                    }
                }
                Text(
                    "本周 ${item.weekDoneCount}/${item.weekTarget}" +
                        (if (item.doneToday) " · 今日已达成 ✓" else ""),
                    style = MaterialTheme.typography.bodySmall,
                    color = if (item.doneToday) Color(0xFF4CAF50) else Color.Gray,
                )
            }
            if (!item.doneToday) {
                FilledTonalButton(onClick = onDone) { Text("达成") }
                TextButton(onClick = onMissed) { Text("缺卡", color = Color.Gray) }
            }
        }
    }
}
