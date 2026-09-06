package com.sailzen.app.feature.plan.components

import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.rememberScrollState
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.FilterChip
import androidx.compose.material3.FilledTonalButton
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
import com.sailzen.app.core.network.dto.domainLabel
import com.sailzen.app.core.network.dto.kindLabel
import com.sailzen.app.core.network.dto.stateLabel
import com.sailzen.app.core.rhythm.AffairRules
import com.sailzen.app.core.rhythm.RhythmTime
import com.sailzen.app.feature.plan.PlanViewModel

/** 事务 Tab：状态筛选 chips + 逾期优先排序任务列表 + 空态（沿用旧事业页任务视图） */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun AffairsTab(
    state: PlanViewModel.UiState,
    onSelectFilter: (String) -> Unit,
    onOpenDetail: (Int) -> Unit,
    onAction: (Int, String) -> Unit,
) {
    Column(modifier = Modifier.fillMaxSize()) {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .horizontalScroll(rememberScrollState())
                .padding(horizontal = 12.dp, vertical = 6.dp),
            horizontalArrangement = Arrangement.spacedBy(8.dp),
        ) {
            AffairRules.TASK_STATE_FILTERS.forEach { filter ->
                FilterChip(
                    selected = state.stateFilter == filter,
                    onClick = { onSelectFilter(filter) },
                    label = { Text(stateLabel(filter)) },
                )
            }
        }

        LazyColumn(
            modifier = Modifier.fillMaxSize().padding(horizontal = 12.dp),
            verticalArrangement = Arrangement.spacedBy(8.dp),
        ) {
            if (state.refreshing && state.tasks.isEmpty()) {
                item {
                    Box(
                        modifier = Modifier.fillMaxWidth().padding(32.dp),
                        contentAlignment = Alignment.Center,
                    ) { CircularProgressIndicator() }
                }
            }
            if (!state.refreshing && state.tasks.isEmpty()) {
                item {
                    Card {
                        Text(
                            "暂无任务。点右下角 + 新建，或在今日 Tab 确认待分拣事务。",
                            modifier = Modifier.padding(16.dp),
                            color = Color.Gray,
                        )
                    }
                }
            }
            items(state.tasks, key = { it.id }) { task ->
                TaskCard(
                    task = task,
                    onClick = { onOpenDetail(task.id) },
                    onAction = { action -> onAction(task.id, action) },
                )
            }
            item { Spacer(Modifier.height(80.dp)) }
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun TaskCard(task: AffairDto, onClick: () -> Unit, onAction: (String) -> Unit) {
    val overdue = AffairRules.isOverdue(task.urgencyDdl, task.state)
    Card(
        onClick = onClick,
        colors = CardDefaults.cardColors(
            containerColor = if (overdue) Color(0xFFFFEBEE) else MaterialTheme.colorScheme.surface,
        ),
        modifier = Modifier.fillMaxWidth(),
    ) {
        Column(modifier = Modifier.padding(12.dp)) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Text(task.title, fontWeight = FontWeight.Medium, modifier = Modifier.weight(1f))
                Text(
                    stateLabel(task.state),
                    style = MaterialTheme.typography.bodySmall,
                    color = Color.Gray,
                )
            }
            Text(
                buildString {
                    append(kindLabel(task.kind))
                    append(" · ${task.estMinutes} 分钟")
                    RhythmTime.parse(task.urgencyDdl)?.let { append(" · 截止 $it") }
                    if (overdue) append(" · 已逾期")
                },
                style = MaterialTheme.typography.bodySmall,
                color = if (overdue) Color(0xFFE53935) else Color.Gray,
            )
            val actions = AffairRules.availableActions(task.kind, task.state)
            if (actions.isNotEmpty()) {
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    actions.forEach { (action, label) ->
                        TextButton(onClick = { onAction(action) }) { Text(label) }
                    }
                }
            }
        }
    }
}

@Composable
fun CreateTaskDialog(
    onDismiss: () -> Unit,
    onConfirm: (String, String, String?, Int, String?) -> Unit,
) {
    var title by remember { mutableStateOf("") }
    var kind by remember { mutableStateOf("task_oneoff") }
    var domain by remember { mutableStateOf("work") }
    var minutes by remember { mutableStateOf("30") }
    var ddl by remember { mutableStateOf("") }

    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text("新建任务") },
        text = {
            Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                OutlinedTextField(
                    value = title,
                    onValueChange = { title = it },
                    label = { Text("任务名称") },
                    modifier = Modifier.fillMaxWidth(),
                )
                Row(
                    modifier = Modifier.fillMaxWidth().horizontalScroll(rememberScrollState()),
                    horizontalArrangement = Arrangement.spacedBy(8.dp),
                ) {
                    listOf("task_oneoff", "task_maintenance", "fixed_plan", "generic").forEach { option ->
                        FilterChip(
                            selected = kind == option,
                            onClick = { kind = option },
                            label = { Text(kindLabel(option)) },
                        )
                    }
                }
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    listOf("life", "work", "career").forEach { option ->
                        FilterChip(
                            selected = domain == option,
                            onClick = { domain = option },
                            label = { Text(domainLabel(option)) },
                        )
                    }
                }
                OutlinedTextField(
                    value = minutes,
                    onValueChange = { minutes = it },
                    label = { Text("预估时长（分钟）") },
                    modifier = Modifier.fillMaxWidth(),
                )
                OutlinedTextField(
                    value = ddl,
                    onValueChange = { ddl = it },
                    label = { Text("截止 YYYY-MM-DDTHH:MM:SS（可留空）") },
                    modifier = Modifier.fillMaxWidth(),
                )
            }
        },
        confirmButton = {
            FilledTonalButton(
                onClick = {
                    onConfirm(
                        title.trim(),
                        kind,
                        domain,
                        minutes.toIntOrNull() ?: 30,
                        ddl.trim().ifBlank { null },
                    )
                },
                enabled = title.isNotBlank(),
            ) { Text("创建") }
        },
        dismissButton = { TextButton(onClick = onDismiss) { Text("取消") } },
    )
}
