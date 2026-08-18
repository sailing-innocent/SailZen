package com.sailzen.app.feature.affair

import android.app.Application
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
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.filled.Add
import androidx.compose.material.icons.filled.Delete
import androidx.compose.material.icons.filled.Edit
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.FilledTonalButton
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.lifecycle.viewmodel.compose.viewModel
import com.sailzen.app.core.network.dto.AffairDto
import com.sailzen.app.core.network.dto.domainLabel
import com.sailzen.app.core.network.dto.kindLabel
import com.sailzen.app.core.network.dto.stateLabel
import com.sailzen.app.core.rhythm.RhythmTime

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun AffairDetailScreen(
    affairId: Int,
    onBack: () -> Unit,
    onOpenChild: (Int) -> Unit,
) {
    val application = LocalContext.current.applicationContext as Application
    val viewModel: AffairDetailViewModel = viewModel(
        key = "affair_detail_$affairId",
        factory = AffairDetailViewModelFactory(application, affairId),
    )
    val state by viewModel.uiState.collectAsState()
    var showEdit by remember { mutableStateOf(false) }
    var showMilestone by remember { mutableStateOf(false) }
    var showDelete by remember { mutableStateOf(false) }

    LaunchedEffect(state.deleted) {
        if (state.deleted) onBack()
    }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text(state.affair?.title ?: "事务详情") },
                navigationIcon = {
                    IconButton(onClick = onBack) {
                        Icon(Icons.AutoMirrored.Filled.ArrowBack, contentDescription = "返回")
                    }
                },
                actions = {
                    IconButton(onClick = { showEdit = true }) {
                        Icon(Icons.Default.Edit, contentDescription = "编辑")
                    }
                    IconButton(onClick = { showDelete = true }) {
                        Icon(Icons.Default.Delete, contentDescription = "删除")
                    }
                },
            )
        },
    ) { padding ->
        val affair = state.affair
        LazyColumn(
            modifier = Modifier.fillMaxSize().padding(padding).padding(horizontal = 12.dp),
            verticalArrangement = Arrangement.spacedBy(10.dp),
        ) {
            if (affair == null) {
                item {
                    Text(
                        if (state.loading) "加载中…" else "未找到该事务",
                        modifier = Modifier.padding(24.dp),
                        color = Color.Gray,
                    )
                }
                return@LazyColumn
            }

            item { MetaCard(affair) }

            val actions = AffairHomeViewModel.availableActions(affair.kind, affair.state)
            if (actions.isNotEmpty()) {
                item {
                    Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                        actions.forEach { (action, label) ->
                            FilledTonalButton(onClick = { viewModel.transit(action) }) { Text(label) }
                        }
                    }
                }
            }

            state.progress?.let { progress ->
                item {
                    Card(colors = CardDefaults.cardColors(containerColor = Color(0xFFFFF8E1))) {
                        Column(modifier = Modifier.padding(14.dp)) {
                            Text("倒排进度", fontWeight = FontWeight.Bold)
                            Text(
                                "目标日 ${progress.targetDate ?: "未定"}" +
                                    (progress.weeksLeft?.let { " · 剩余 %.1f 周".format(it) } ?: ""),
                                style = MaterialTheme.typography.bodySmall,
                                color = Color.Gray,
                            )
                            Spacer(Modifier.height(8.dp))
                            Text(
                                "本周 %.1fh / %.1fh · 累计 %.1fh / 预估 %.0fh".format(
                                    progress.weekConsumedHours,
                                    progress.weeklyBudgetHours,
                                    progress.totalDoneHours,
                                    progress.totalEstHours,
                                ),
                                style = MaterialTheme.typography.bodySmall,
                            )
                            LinearProgressIndicator(
                                progress = { progress.completionRatio.toFloat() },
                                modifier = Modifier.fillMaxWidth().padding(top = 6.dp),
                            )
                            progress.countdownPressure?.let {
                                Text(
                                    "倒排压力 %.2f".format(it),
                                    style = MaterialTheme.typography.bodySmall,
                                    color = if (it > 1.0) Color(0xFFE53935) else Color.Gray,
                                    modifier = Modifier.padding(top = 4.dp),
                                )
                            }
                        }
                    }
                }

                item {
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Text("里程碑", style = MaterialTheme.typography.titleSmall, fontWeight = FontWeight.Bold)
                        Spacer(Modifier.weight(1f))
                        IconButton(onClick = { showMilestone = true }) {
                            Icon(Icons.Default.Add, contentDescription = "添加里程碑")
                        }
                    }
                }
                items(progress.milestones, key = { "m-${it.id}" }) { milestone ->
                    MilestoneRow(milestone = milestone, onDone = { viewModel.milestoneDone(milestone.id) })
                }
            }

            if (state.children.isNotEmpty()) {
                item {
                    Text(
                        "子事务",
                        style = MaterialTheme.typography.titleSmall,
                        fontWeight = FontWeight.Bold,
                        modifier = Modifier.padding(top = 8.dp),
                    )
                }
                items(state.children, key = { "c-${it.id}" }) { child ->
                    ChildCard(
                        child = child,
                        onClick = { onOpenChild(child.id) },
                        onAction = { action -> viewModel.transitChild(child.id, action) },
                    )
                }
            }

            item { Spacer(Modifier.height(60.dp)) }
        }
    }

    if (showEdit) {
        state.affair?.let { affair ->
            EditAffairDialog(
                affair = affair,
                onDismiss = { showEdit = false },
                onConfirm = { title, description, minutes, importance ->
                    viewModel.updateAffair(title, description, minutes, importance)
                    showEdit = false
                },
            )
        }
    }

    if (showMilestone) {
        AddMilestoneDialog(
            onDismiss = { showMilestone = false },
            onConfirm = { title, minutes ->
                viewModel.addMilestone(title, minutes)
                showMilestone = false
            },
        )
    }

    if (showDelete) {
        AlertDialog(
            onDismissRequest = { showDelete = false },
            title = { Text("删除事务") },
            text = { Text("删除后不可恢复，确认删除「${state.affair?.title.orEmpty()}」？") },
            confirmButton = {
                TextButton(onClick = { showDelete = false; viewModel.delete() }) { Text("删除") }
            },
            dismissButton = { TextButton(onClick = { showDelete = false }) { Text("取消") } },
        )
    }

    state.message?.let { message ->
        AlertDialog(
            onDismissRequest = { viewModel.dismissMessage() },
            title = { Text("提示") },
            text = { Text(message) },
            confirmButton = {
                TextButton(onClick = { viewModel.dismissMessage() }) { Text("确定") }
            },
        )
    }
}

@Composable
private fun MetaCard(affair: AffairDto) {
    Card(modifier = Modifier.fillMaxWidth()) {
        Column(modifier = Modifier.padding(14.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
            Text(affair.title, style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold)
            Text(
                "${kindLabel(affair.kind)} · ${domainLabel(affair.domain)} · ${stateLabel(affair.state)}",
                style = MaterialTheme.typography.bodySmall,
                color = Color.Gray,
            )
            Text(
                "重要性 ${affair.importance} · 预估 ${affair.estMinutes} 分钟 · 精力 ${affair.energyCost}",
                style = MaterialTheme.typography.bodySmall,
            )
            RhythmTime.parse(affair.urgencyDdl)?.let {
                Text("截止 $it", style = MaterialTheme.typography.bodySmall)
            }
            if (affair.description.isNotBlank()) {
                Text(affair.description, style = MaterialTheme.typography.bodySmall)
            }
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun ChildCard(child: AffairDto, onClick: () -> Unit, onAction: (String) -> Unit) {
    Card(onClick = onClick, modifier = Modifier.fillMaxWidth()) {
        Column(modifier = Modifier.padding(12.dp)) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Text(child.title, modifier = Modifier.weight(1f))
                Text(
                    stateLabel(child.state),
                    style = MaterialTheme.typography.bodySmall,
                    color = Color.Gray,
                )
            }
            val actions = AffairHomeViewModel.availableActions(child.kind, child.state)
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
private fun EditAffairDialog(
    affair: AffairDto,
    onDismiss: () -> Unit,
    onConfirm: (String, String, Int, Int) -> Unit,
) {
    var title by remember { mutableStateOf(affair.title) }
    var description by remember { mutableStateOf(affair.description) }
    var minutes by remember { mutableStateOf(affair.estMinutes.toString()) }
    var importance by remember { mutableStateOf(affair.importance.toString()) }

    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text("编辑事务") },
        text = {
            Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                OutlinedTextField(
                    value = title,
                    onValueChange = { title = it },
                    label = { Text("标题") },
                    modifier = Modifier.fillMaxWidth(),
                )
                OutlinedTextField(
                    value = description,
                    onValueChange = { description = it },
                    label = { Text("描述") },
                    modifier = Modifier.fillMaxWidth(),
                )
                OutlinedTextField(
                    value = minutes,
                    onValueChange = { minutes = it },
                    label = { Text("预估时长（分钟）") },
                    modifier = Modifier.fillMaxWidth(),
                )
                OutlinedTextField(
                    value = importance,
                    onValueChange = { importance = it },
                    label = { Text("重要性 1-5") },
                    modifier = Modifier.fillMaxWidth(),
                )
            }
        },
        confirmButton = {
            FilledTonalButton(
                onClick = {
                    onConfirm(
                        title.trim(),
                        description.trim(),
                        minutes.toIntOrNull() ?: affair.estMinutes,
                        importance.toIntOrNull()?.coerceIn(1, 5) ?: affair.importance,
                    )
                },
                enabled = title.isNotBlank(),
            ) { Text("保存") }
        },
        dismissButton = { TextButton(onClick = onDismiss) { Text("取消") } },
    )
}

@Composable
private fun AddMilestoneDialog(
    onDismiss: () -> Unit,
    onConfirm: (String, Int?) -> Unit,
) {
    var title by remember { mutableStateOf("") }
    var minutes by remember { mutableStateOf("") }

    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text("添加里程碑") },
        text = {
            Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                OutlinedTextField(
                    value = title,
                    onValueChange = { title = it },
                    label = { Text("里程碑标题") },
                    modifier = Modifier.fillMaxWidth(),
                )
                OutlinedTextField(
                    value = minutes,
                    onValueChange = { minutes = it },
                    label = { Text("预估时长（分钟，可留空）") },
                    modifier = Modifier.fillMaxWidth(),
                )
            }
        },
        confirmButton = {
            FilledTonalButton(
                onClick = { onConfirm(title.trim(), minutes.toIntOrNull()) },
                enabled = title.isNotBlank(),
            ) { Text("添加") }
        },
        dismissButton = { TextButton(onClick = onDismiss) { Text("取消") } },
    )
}
