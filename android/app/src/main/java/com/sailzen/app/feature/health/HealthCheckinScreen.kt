package com.sailzen.app.feature.health

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.selection.selectable
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.Checkbox
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.RadioButton
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.lifecycle.viewmodel.compose.viewModel
import com.sailzen.app.core.network.dto.InfoCollectionType

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun HealthCheckinScreen(
    onBack: () -> Unit,
    initialType: InfoCollectionType? = null,
    viewModel: HealthCheckinViewModel = viewModel(),
) {
    val state by viewModel.uiState.collectAsState()
    LaunchedEffect(initialType) {
        initialType?.let { viewModel.selectType(it) }
    }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("健康速记") },
                navigationIcon = {
                    IconButton(onClick = onBack) {
                        Icon(Icons.AutoMirrored.Filled.ArrowBack, contentDescription = "返回")
                    }
                },
            )
        },
    ) { padding ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding)
                .padding(16.dp)
                .verticalScroll(rememberScrollState()),
            verticalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            Text("类型", style = MaterialTheme.typography.titleSmall)
            InfoCollectionType.values().forEach { type ->
                Row(
                    verticalAlignment = Alignment.CenterVertically,
                    modifier = Modifier
                        .fillMaxWidth()
                        .selectable(
                            selected = state.selectedType == type,
                            onClick = { viewModel.selectType(type) },
                        )
                        .padding(vertical = 4.dp),
                ) {
                    RadioButton(
                        selected = state.selectedType == type,
                        onClick = { viewModel.selectType(type) },
                    )
                    Text(typeLabel(type), modifier = Modifier.padding(start = 8.dp))
                }
            }

            Row {
                OutlinedTextField(
                    value = state.date.toString(),
                    onValueChange = { },
                    label = { Text("日期") },
                    modifier = Modifier.weight(1f).padding(end = 8.dp),
                    readOnly = true,
                )
                OutlinedTextField(
                    value = state.time,
                    onValueChange = { viewModel.setTime(it) },
                    label = { Text("时间") },
                    modifier = Modifier.weight(1f),
                )
            }

            when (state.selectedType) {
                InfoCollectionType.weight -> {
                    OutlinedTextField(
                        value = state.weight,
                        onValueChange = { viewModel.setWeight(it) },
                        label = { Text("体重 (kg)") },
                        modifier = Modifier.fillMaxWidth(),
                    )
                }
                InfoCollectionType.exercise -> {
                    OutlinedTextField(
                        value = state.exerciseType,
                        onValueChange = { viewModel.setExerciseType(it) },
                        label = { Text("运动类型") },
                        modifier = Modifier.fillMaxWidth(),
                    )
                    OutlinedTextField(
                        value = state.exerciseMinutes,
                        onValueChange = { viewModel.setExerciseMinutes(it) },
                        label = { Text("时长 (分钟)") },
                        modifier = Modifier.fillMaxWidth(),
                    )
                    OutlinedTextField(
                        value = state.exerciseCalories,
                        onValueChange = { viewModel.setExerciseCalories(it) },
                        label = { Text("热量 (千卡)") },
                        modifier = Modifier.fillMaxWidth(),
                    )
                }
                InfoCollectionType.meal -> {
                    OutlinedTextField(
                        value = state.mealType,
                        onValueChange = { viewModel.setMealType(it) },
                        label = { Text("餐次 (breakfast/lunch/dinner/snack)") },
                        modifier = Modifier.fillMaxWidth(),
                    )
                    OutlinedTextField(
                        value = state.mealDescription,
                        onValueChange = { viewModel.setMealDescription(it) },
                        label = { Text("饮食内容") },
                        modifier = Modifier.fillMaxWidth(),
                    )
                    OutlinedTextField(
                        value = state.mealCalories,
                        onValueChange = { viewModel.setMealCalories(it) },
                        label = { Text("热量 (kcal)") },
                        modifier = Modifier.fillMaxWidth(),
                    )
                }
                InfoCollectionType.medication -> {
                    OutlinedTextField(
                        value = state.medicationName,
                        onValueChange = { viewModel.setMedicationName(it) },
                        label = { Text("药品名") },
                        modifier = Modifier.fillMaxWidth(),
                    )
                    OutlinedTextField(
                        value = state.medicationDosage,
                        onValueChange = { viewModel.setMedicationDosage(it) },
                        label = { Text("剂量") },
                        modifier = Modifier.fillMaxWidth(),
                    )
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Checkbox(
                            checked = state.medicationTaken,
                            onCheckedChange = { viewModel.setMedicationTaken(it) },
                        )
                        Text("已服用")
                    }
                }
                InfoCollectionType.sleep -> {
                    OutlinedTextField(
                        value = state.sleepHours,
                        onValueChange = { viewModel.setSleepHours(it) },
                        label = { Text("睡眠时长 (小时)") },
                        modifier = Modifier.fillMaxWidth(),
                    )
                    OutlinedTextField(
                        value = state.sleepQuality,
                        onValueChange = { viewModel.setSleepQuality(it) },
                        label = { Text("睡眠质量 (1-5)") },
                        modifier = Modifier.fillMaxWidth(),
                    )
                }
                InfoCollectionType.mood -> {
                    OutlinedTextField(
                        value = state.moodScore,
                        onValueChange = { viewModel.setMoodScore(it) },
                        label = { Text("心情评分 (1-5)") },
                        modifier = Modifier.fillMaxWidth(),
                    )
                }
            }

            OutlinedTextField(
                value = state.note,
                onValueChange = { viewModel.setNote(it) },
                label = { Text("备注") },
                modifier = Modifier.fillMaxWidth(),
            )

            Spacer(Modifier.height(8.dp))

            Button(
                onClick = { viewModel.submit() },
                modifier = Modifier.fillMaxWidth(),
                enabled = !state.submitting,
            ) {
                if (state.submitting) {
                    CircularProgressIndicator(modifier = Modifier.height(20.dp))
                } else {
                    Text("提交")
                }
            }
        }
    }

    state.submitted?.let {
        AlertDialog(
            onDismissRequest = { viewModel.dismissSubmitted(); onBack() },
            title = { Text("提交成功") },
            text = { Text("已记录 ${typeLabel(InfoCollectionType.valueOf(it.collectionType))}") },
            confirmButton = {
                TextButton(onClick = { viewModel.dismissSubmitted(); onBack() }) {
                    Text("完成")
                }
            },
        )
    }

    state.error?.let {
        AlertDialog(
            onDismissRequest = { viewModel.dismissError() },
            title = { Text("提交失败") },
            text = { Text(it) },
            confirmButton = {
                TextButton(onClick = { viewModel.dismissError() }) { Text("确定") }
            },
        )
    }
}

@Composable
private fun typeLabel(type: InfoCollectionType): String = when (type) {
    InfoCollectionType.weight -> "体重"
    InfoCollectionType.meal -> "饮食"
    InfoCollectionType.exercise -> "运动"
    InfoCollectionType.medication -> "用药"
    InfoCollectionType.sleep -> "睡眠"
    InfoCollectionType.mood -> "心情"
}
