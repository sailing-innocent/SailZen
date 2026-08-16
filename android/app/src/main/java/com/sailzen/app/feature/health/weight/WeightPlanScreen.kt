package com.sailzen.app.feature.health.weight

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.selection.selectable
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.RadioButton
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.unit.dp
import androidx.lifecycle.viewmodel.compose.viewModel
import com.sailzen.app.core.network.dto.WeightPlanCurveType
import java.time.LocalDate
import java.time.format.DateTimeFormatter

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun WeightPlanScreen(
    onBack: () -> Unit,
    viewModel: WeightPlanViewModel = viewModel(),
) {
    val state by viewModel.uiState.collectAsState()

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("体重计划") },
                navigationIcon = {
                    IconButton(onClick = onBack) {
                        Icon(Icons.AutoMirrored.Filled.ArrowBack, contentDescription = "返回")
                    }
                },
            )
        },
    ) { padding ->
        LazyColumn(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding)
                .padding(horizontal = 16.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp),
            contentPadding = PaddingValues(vertical = 12.dp),
        ) {
            if (state.plan == null && !state.showForm) {
                item {
                    Text("暂无活跃体重计划", style = MaterialTheme.typography.bodyLarge, color = Color.Gray)
                    Button(onClick = { viewModel.toggleForm() }) { Text("创建计划") }
                }
            }

            state.plan?.let { plan ->
                item {
                    PlanSummaryCard(plan, state.progress, state.checkin)
                }
                item {
                    Button(onClick = { viewModel.toggleForm() }, modifier = Modifier.fillMaxWidth()) {
                        Text("编辑/重新创建")
                    }
                }
            }

            if (state.showForm) {
                item { PlanForm(state, viewModel) }
            }

            if (state.loading) {
                item { CircularProgressIndicator(modifier = Modifier.padding(16.dp)) }
            }
        }
    }

    state.message?.let { message ->
        AlertDialog(
            onDismissRequest = { viewModel.dismissMessage() },
            title = { Text("提示") },
            text = { Text(message) },
            confirmButton = { TextButton(onClick = { viewModel.dismissMessage() }) { Text("确定") } },
        )
    }
}

@Composable
private fun PlanSummaryCard(plan: com.sailzen.app.core.network.dto.WeightPlanDto, progress: com.sailzen.app.core.network.dto.WeightPlanProgressDto?, checkin: com.sailzen.app.core.network.dto.WeightPlanCheckinStatusDto?) {
    Column(modifier = Modifier.fillMaxWidth().padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
        Text("目标体重 ${plan.targetWeight} kg", style = MaterialTheme.typography.titleMedium)
        Text("起始 ${plan.initialWeight ?: "--"} kg", style = MaterialTheme.typography.bodyMedium)
        Text("曲线类型 ${plan.curveType}", style = MaterialTheme.typography.bodyMedium)
        progress?.let {
            Text("控制率 ${(it.controlRate * 100).toInt()}%", style = MaterialTheme.typography.bodyMedium)
            LinearProgressIndicator(progress = { it.controlRate.toFloat() }, modifier = Modifier.fillMaxWidth())
        }
        checkin?.let {
            Text("今日打卡 ${if (it.todayDone) "✓" else "未打卡"}  连续 ${it.streak} 天", style = MaterialTheme.typography.bodyMedium)
        }
    }
}

@Composable
private fun PlanForm(state: WeightPlanViewModel.UiState, viewModel: WeightPlanViewModel) {
    Column(modifier = Modifier.fillMaxWidth(), verticalArrangement = Arrangement.spacedBy(8.dp)) {
        OutlinedTextField(
            value = state.form.targetWeight,
            onValueChange = { viewModel.setForm(state.form.copy(targetWeight = it)) },
            label = { Text("目标体重 (kg)") },
            modifier = Modifier.fillMaxWidth(),
        )
        OutlinedTextField(
            value = state.form.initialWeight,
            onValueChange = { viewModel.setForm(state.form.copy(initialWeight = it)) },
            label = { Text("起始体重 (kg，留空自动取最近记录)") },
            modifier = Modifier.fillMaxWidth(),
        )
        Text("曲线类型", style = MaterialTheme.typography.titleSmall)
        WeightPlanCurveType.values().forEach { type ->
            Row(
                verticalAlignment = Alignment.CenterVertically,
                modifier = Modifier.fillMaxWidth().selectable(selected = state.form.curveType == type, onClick = { viewModel.setForm(state.form.copy(curveType = type)) }),
            ) {
                RadioButton(selected = state.form.curveType == type, onClick = { viewModel.setForm(state.form.copy(curveType = type)) })
                Text(type.name)
            }
        }
        OutlinedTextField(
            value = state.form.targetDate.toString(),
            onValueChange = { },
            label = { Text("目标日期") },
            modifier = Modifier.fillMaxWidth(),
            readOnly = true,
        )
        Button(onClick = { viewModel.createPlan() }, modifier = Modifier.fillMaxWidth()) { Text("保存计划") }
        Spacer(Modifier.height(8.dp))
    }
}
