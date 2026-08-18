package com.sailzen.app.feature.affair

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
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.horizontalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Add
import androidx.compose.material.icons.filled.CheckCircle
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.FilledTonalButton
import androidx.compose.material3.FilterChip
import androidx.compose.material3.FloatingActionButton
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Tab
import androidx.compose.material3.TabRow
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
import com.sailzen.app.core.network.dto.AffairDto
import com.sailzen.app.core.network.dto.VentureProgressDto
import com.sailzen.app.core.network.dto.kindLabel
import com.sailzen.app.core.network.dto.stateLabel
import com.sailzen.app.core.rhythm.RhythmTime

/**
 * 统一事务页：长期事业与任务同源于 rhythm affair，只是 kind 不同。
 */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun AffairHomeScreen(
    onOpenDetail: (Int) -> Unit,
    viewModel: AffairHomeViewModel = viewModel(),
) {
    val state by viewModel.uiState.collectAsState()
    var showCreate by remember { mutableStateOf(false) }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("事业") },
                actions = {
                    IconButton(onClick = { viewModel.refresh() }) {
                        Icon(Icons.Default.Refresh, contentDescription = "刷新")
                    }
                },
            )
        },
        floatingActionButton = {
            FloatingActionButton(onClick = { showCreate = true }) {
                Icon(Icons.Default.Add, contentDescription = "新建")
            }
        },
    ) { padding ->
        Column(modifier = Modifier.fillMaxSize().padding(padding)) {
            TabRow(selectedTabIndex = state.tab.ordinal) {
                Tab(
                    selected = state.tab == AffairHomeViewModel.Tab.VENTURE,
                    onClick = { viewModel.selectTab(AffairHomeViewModel.Tab.VENTURE) },
                    text = { Text("事业") },
                )
                Tab(
                    selected = state.tab == AffairHomeViewModel.Tab.TASK,
                    onClick = { viewModel.selectTab(AffairHomeViewModel.Tab.TASK) },
                    text = { Text("任务") },
                )
            }

            if (!state.configured) {
                Card(
                    colors = CardDefaults.cardColors(containerColor = Color(0xFFFFF3E0)),
                    modifier = Modifier.fillMaxWidth().padding(12.dp),
                ) {
                    Text("未配置服务器地址，请到设置页填写", modifier = Modifier.padding(12.dp))
                }
            }

            when (state.tab) {
                AffairHomeViewModel.Tab.VENTURE -> VentureList(
                    ventures = state.ventures,
                    loading = state.loading,
                    onOpenDetail = onOpenDetail,
                    onMilestoneDone = { viewModel.milestoneDone(it) },
                )

                AffairHomeViewModel.Tab.TASK -> TaskList(
                    tasks = state.tasks,
                    loading = state.loading,
                    stateFilter = state.stateFilter,
                    onSelectFilter = { viewModel.selectStateFilter(it) },
                    onOpenDetail = onOpenDetail,
                    onAction = { id, action -> viewModel.transit(id, action) },
                )
            }
        }
    }

    if (showCreate) {
        when (state.tab) {
            AffairHomeViewModel.Tab.VENTURE -> CreateVentureDialog(
                onDismiss = { showCreate = false },
                onConfirm = { title, targetDate, hours ->
                    viewModel.createVenture(title, targetDate, hours)
                    showCreate = false
                },
            )

            AffairHomeViewModel.Tab.TASK -> CreateTaskDialog(
                onDismiss = { showCreate = false },
                onConfirm = { title, kind, domain, minutes, ddl ->
                    viewModel.createTask(title, kind, domain, minutes, ddl)
                    showCreate = false
                },
            )
        }
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
private fun VentureList(
    ventures: List<VentureProgressDto>,
    loading: Boolean,
    onOpenDetail: (Int) -> Unit,
    onMilestoneDone: (Int) -> Unit,
) {
    LazyColumn(
        modifier = Modifier.fillMaxSize().padding(horizontal = 12.dp),
        verticalArrangement = Arrangement.spacedBy(10.dp),
    ) {
        if (loading && ventures.isEmpty()) {
            item { LoadingRow() }
        }
        if (!loading && ventures.isEmpty()) {
            item {
                Card {
                    Text(
                        "暂无进行中的长期事业。点右下角 + 新建，设定目标日与每周投入预算即可开始倒排。",
                        modifier = Modifier.padding(16.dp),
                        color = Color.Gray,
                    )
                }
            }
        }
        items(ventures, key = { it.affairId }) { progress ->
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
private fun TaskList(
    tasks: List<AffairDto>,
    loading: Boolean,
    stateFilter: String?,
    onSelectFilter: (String?) -> Unit,
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
            AffairHomeViewModel.TASK_STATE_FILTERS.forEach { filter ->
                FilterChip(
                    selected = stateFilter == filter,
                    onClick = { onSelectFilter(filter) },
                    label = { Text(filter?.let { stateLabel(it) } ?: "全部") },
                )
            }
        }

        LazyColumn(
            modifier = Modifier.fillMaxSize().padding(horizontal = 12.dp),
            verticalArrangement = Arrangement.spacedBy(8.dp),
        ) {
            if (loading && tasks.isEmpty()) {
                item { LoadingRow() }
            }
            if (!loading && tasks.isEmpty()) {
                item {
                    Card {
                        Text(
                            "暂无任务。点右下角 + 新建，或在收件箱确认捕获的事务。",
                            modifier = Modifier.padding(16.dp),
                            color = Color.Gray,
                        )
                    }
                }
            }
            items(tasks, key = { it.id }) { task ->
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
    val overdue = AffairHomeViewModel.isOverdue(task.urgencyDdl, task.state)
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
            val actions = AffairHomeViewModel.availableActions(task.kind, task.state)
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
private fun LoadingRow() {
    Box(
        modifier = Modifier.fillMaxWidth().padding(32.dp),
        contentAlignment = Alignment.Center,
    ) { CircularProgressIndicator() }
}

@Composable
private fun CreateVentureDialog(
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

@Composable
private fun CreateTaskDialog(
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
                            label = { Text(com.sailzen.app.core.network.dto.domainLabel(option)) },
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
