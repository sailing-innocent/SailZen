package com.sailzen.app.feature.project

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
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.filled.Add
import androidx.compose.material.icons.filled.CheckCircle
import androidx.compose.material.icons.filled.MoreVert
import androidx.compose.material.icons.filled.PlayArrow
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.DropdownMenu
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.FloatingActionButton
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
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
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.unit.dp
import androidx.lifecycle.viewmodel.compose.viewModel
import com.sailzen.app.R
import com.sailzen.app.core.network.dto.MissionDto
import com.sailzen.app.core.network.dto.MissionState
import com.sailzen.app.feature.project.ProjectMissionViewModel.Companion.hoursUntilDeadline
import com.sailzen.app.feature.project.ProjectMissionViewModel.Companion.isMissionActive
import com.sailzen.app.feature.project.ProjectMissionViewModel.Companion.isOverdue
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale
import java.util.concurrent.TimeUnit
import kotlin.math.abs

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun ProjectMissionScreen(
    projectId: Int,
    highlightMissionId: Int = -1,
    onBack: () -> Unit,
    onOpenMissionDetail: (Int) -> Unit,
    viewModel: ProjectMissionViewModel = viewModel(
        factory = ProjectMissionViewModelFactory(
            application = androidx.compose.ui.platform.LocalContext.current.applicationContext as android.app.Application,
            projectId = projectId,
        ),
    ),
) {
    val state by viewModel.uiState.collectAsState()

    LaunchedEffect(highlightMissionId) {
        if (highlightMissionId > 0) {
            viewModel.setHighlightMissionId(highlightMissionId)
        }
    }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text(stringResource(R.string.project_mission_board)) },
                navigationIcon = {
                    IconButton(onClick = onBack) {
                        Icon(Icons.AutoMirrored.Filled.ArrowBack, contentDescription = "返回")
                    }
                },
                actions = {
                    IconButton(onClick = { viewModel.refresh() }) {
                        Icon(Icons.Default.Refresh, contentDescription = "刷新")
                    }
                },
            )
        },
        floatingActionButton = {
            FloatingActionButton(onClick = { viewModel.showCreateDialog() }) {
                Icon(Icons.Default.Add, contentDescription = "创建任务")
            }
        },
    ) { padding ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding)
                .padding(horizontal = 12.dp),
        ) {
            FilterTabs(
                selected = state.filter,
                onSelect = { viewModel.setFilter(it) },
            )
            LazyColumn(
                modifier = Modifier.fillMaxSize(),
                verticalArrangement = Arrangement.spacedBy(10.dp),
            ) {
                if (state.loading && state.missions.isEmpty()) {
                    item {
                        Column(
                            modifier = Modifier.fillMaxWidth().padding(32.dp),
                            horizontalAlignment = Alignment.CenterHorizontally,
                        ) { CircularProgressIndicator() }
                    }
                }
                val filtered = state.missions.filter { mission ->
                    when (state.filter) {
                        ProjectMissionViewModel.Filter.ALL -> true
                        ProjectMissionViewModel.Filter.URGENT ->
                            isOverdue(mission.ddl, mission.state) || hoursUntilDeadline(mission.ddl) <= 24
                        ProjectMissionViewModel.Filter.DOING -> mission.state == MissionState.DOING
                    }
                }.sortedWith(
                    compareByDescending<MissionDto> { isOverdue(it.ddl, it.state) }
                        .thenBy { hoursUntilDeadline(it.ddl) },
                )

                items(filtered, key = { it.id }) { mission ->
                    MissionCard(
                        mission = mission,
                        isHighlighted = mission.id == state.highlightMissionId,
                        onStart = { viewModel.startMission(mission.id) },
                        onComplete = { viewModel.completeMission(mission.id) },
                        onCancel = { viewModel.cancelMission(mission.id) },
                        onReopen = { viewModel.reopenMission(mission.id) },
                        onPostpone = { viewModel.postponeMission(mission.id, 7) },
                        onDetail = { onOpenMissionDetail(mission.id) },
                    )
                }
                item { Spacer(Modifier.height(80.dp)) }
            }
        }
    }

    if (state.showCreateDialog) {
        CreateMissionDialog(
            onDismiss = { viewModel.dismissCreateDialog() },
            onConfirm = { name, desc, ddl, minutes ->
                viewModel.createMission(name, desc, ddl, minutes)
            },
        )
    }
}

@Composable
private fun FilterTabs(
    selected: ProjectMissionViewModel.Filter,
    onSelect: (ProjectMissionViewModel.Filter) -> Unit,
) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .padding(vertical = 8.dp),
        horizontalArrangement = Arrangement.SpaceEvenly,
    ) {
        FilterTab(
            label = stringResource(R.string.mission_filter_all),
            selected = selected == ProjectMissionViewModel.Filter.ALL,
            onClick = { onSelect(ProjectMissionViewModel.Filter.ALL) },
        )
        FilterTab(
            label = stringResource(R.string.mission_filter_urgent),
            selected = selected == ProjectMissionViewModel.Filter.URGENT,
            onClick = { onSelect(ProjectMissionViewModel.Filter.URGENT) },
        )
        FilterTab(
            label = stringResource(R.string.mission_filter_doing),
            selected = selected == ProjectMissionViewModel.Filter.DOING,
            onClick = { onSelect(ProjectMissionViewModel.Filter.DOING) },
        )
    }
}

@Composable
private fun FilterTab(label: String, selected: Boolean, onClick: () -> Unit) {
    TextButton(onClick = onClick) {
        Text(
            label,
            color = if (selected) MaterialTheme.colorScheme.primary else Color.Gray,
            fontWeight = if (selected) FontWeight.Bold else FontWeight.Normal,
        )
    }
}

@Composable
private fun MissionCard(
    mission: MissionDto,
    isHighlighted: Boolean,
    onStart: () -> Unit,
    onComplete: () -> Unit,
    onCancel: () -> Unit,
    onReopen: () -> Unit,
    onPostpone: () -> Unit,
    onDetail: () -> Unit,
) {
    val active = isMissionActive(mission.state)
    val overdue = isOverdue(mission.ddl, mission.state)
    val hours = hoursUntilDeadline(mission.ddl)
    val priorityColor = when {
        !active -> Color.Gray
        overdue -> Color(0xFFE53935)
        hours <= 2 -> Color(0xFFE53935)
        hours <= 24 -> Color(0xFFFFB300)
        else -> Color.Unspecified
    }
    var menuExpanded by remember { mutableStateOf(false) }

    Card(
        modifier = Modifier.fillMaxWidth(),
        colors = CardDefaults.cardColors(
            containerColor = if (isHighlighted) Color(0xFFFFF9C4) else MaterialTheme.colorScheme.surface,
        ),
    ) {
        Column(modifier = Modifier.padding(14.dp)) {
            Row(
                verticalAlignment = Alignment.CenterVertically,
                modifier = Modifier.fillMaxWidth(),
            ) {
                Text(
                    mission.name,
                    modifier = Modifier.weight(1f),
                    fontWeight = FontWeight.Bold,
                    style = MaterialTheme.typography.titleSmall,
                    color = if (active) Color.Unspecified else Color.Gray,
                )
                if (overdue) {
                    Text(
                        stringResource(R.string.mission_overdue),
                        color = Color(0xFFE53935),
                        style = MaterialTheme.typography.labelSmall,
                        fontWeight = FontWeight.Bold,
                    )
                }
                IconButton(onClick = { menuExpanded = true }) {
                    Icon(Icons.Default.MoreVert, contentDescription = "更多")
                }
                DropdownMenu(
                    expanded = menuExpanded,
                    onDismissRequest = { menuExpanded = false },
                ) {
                    if (active) {
                        DropdownMenuItem(
                            text = { Text(stringResource(R.string.action_postpone)) },
                            onClick = { menuExpanded = false; onPostpone() },
                        )
                    }
                    DropdownMenuItem(
                        text = { Text(stringResource(R.string.action_view_detail)) },
                        onClick = { menuExpanded = false; onDetail() },
                    )
                    if (active) {
                        DropdownMenuItem(
                            text = { Text(stringResource(R.string.action_cancel)) },
                            onClick = { menuExpanded = false; onCancel() },
                        )
                    } else {
                        DropdownMenuItem(
                            text = { Text(stringResource(R.string.action_reopen)) },
                            onClick = { menuExpanded = false; onReopen() },
                        )
                    }
                }
            }

            if (mission.description.isNotBlank()) {
                Text(
                    mission.description,
                    style = MaterialTheme.typography.bodySmall,
                    color = Color.Gray,
                    modifier = Modifier.padding(top = 4.dp),
                )
            }

            Text(
                formatDeadline(mission.ddl),
                style = MaterialTheme.typography.bodySmall,
                color = priorityColor,
                modifier = Modifier.padding(top = 4.dp),
            )

            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(top = 8.dp),
                horizontalArrangement = Arrangement.End,
            ) {
                if (active && mission.state != MissionState.DOING) {
                    IconButton(onClick = onStart) {
                        Icon(Icons.Default.PlayArrow, contentDescription = stringResource(R.string.action_start))
                    }
                }
                if (active) {
                    IconButton(onClick = onComplete) {
                        Icon(Icons.Default.CheckCircle, contentDescription = stringResource(R.string.action_complete))
                    }
                }
            }
        }
    }
}

@Composable
private fun formatDeadline(ddl: Double?): String {
    if (ddl == null) return stringResource(R.string.mission_no_deadline)
    val nowMillis = System.currentTimeMillis()
    val ddlMillis = TimeUnit.SECONDS.toMillis(ddl.toLong())
    val diffHours = (ddlMillis - nowMillis) / (1000.0 * 60 * 60)
    return when {
        diffHours < 0 -> {
            val days = (abs(diffHours) / 24).toInt()
            if (days > 0) "已逾期 ${days} 天" else "已逾期 ${abs(diffHours).toInt()} 小时"
        }
        diffHours < 1 -> "${(diffHours * 60).toInt()} 分钟后"
        diffHours < 24 -> "${diffHours.toInt()} 小时后"
        diffHours < 72 -> "${(diffHours / 24).toInt()} 天后"
        else -> SimpleDateFormat("MM-dd", Locale.getDefault()).format(Date(ddlMillis))
    }
}

@Composable
private fun CreateMissionDialog(
    onDismiss: () -> Unit,
    onConfirm: (String, String, String, String) -> Unit,
) {
    var name by remember { mutableStateOf("") }
    var description by remember { mutableStateOf("") }
    var ddl by remember { mutableStateOf("") }
    var minutes by remember { mutableStateOf("") }

    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text(stringResource(R.string.mission_create_title)) },
        text = {
            Column {
                OutlinedTextField(
                    value = name,
                    onValueChange = { name = it },
                    label = { Text(stringResource(R.string.mission_name_hint)) },
                    singleLine = true,
                )
                OutlinedTextField(
                    value = description,
                    onValueChange = { description = it },
                    label = { Text(stringResource(R.string.mission_description_hint)) },
                )
                OutlinedTextField(
                    value = ddl,
                    onValueChange = { ddl = it },
                    label = { Text(stringResource(R.string.mission_deadline_hint)) },
                    keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Number),
                    singleLine = true,
                )
                OutlinedTextField(
                    value = minutes,
                    onValueChange = { minutes = it },
                    label = { Text(stringResource(R.string.mission_planned_minutes_hint)) },
                    keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Number),
                    singleLine = true,
                )
            }
        },
        confirmButton = {
            TextButton(
                onClick = { onConfirm(name, description, ddl, minutes) },
                enabled = name.isNotBlank(),
            ) { Text(stringResource(R.string.dialog_confirm)) }
        },
        dismissButton = {
            TextButton(onClick = onDismiss) { Text(stringResource(R.string.dialog_cancel)) }
        },
    )
}
