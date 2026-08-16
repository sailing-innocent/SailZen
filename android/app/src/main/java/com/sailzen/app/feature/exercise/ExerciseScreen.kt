package com.sailzen.app.feature.exercise

import androidx.compose.foundation.layout.Arrangement
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
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material3.Button
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ExperimentalMaterial3Api
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
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.unit.dp
import androidx.lifecycle.viewmodel.compose.viewModel
import com.sailzen.app.R
import com.sailzen.app.ui.components.ProgressRing

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun ExerciseScreen(
    onBack: () -> Unit,
    viewModel: ExerciseViewModel = viewModel(),
) {
    val state by viewModel.uiState.collectAsState()
    var type by remember { mutableStateOf("") }
    var minutes by remember { mutableStateOf("") }
    var calories by remember { mutableStateOf("") }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("必备运动") },
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
            val totalMinutes = state.exercises.sumOf { it.durationMinutes }
            val progress = if (state.goalMinutes > 0) totalMinutes / state.goalMinutes.toFloat() else 0f

            item {
                Text(stringResource(R.string.health_exercise_goal), style = MaterialTheme.typography.titleSmall)
                Row(verticalAlignment = Alignment.CenterVertically) {
                    ProgressRing(progress = progress, modifier = Modifier.size(80.dp))
                    Column(modifier = Modifier.padding(start = 16.dp)) {
                        Text("$totalMinutes / ${state.goalMinutes} 分钟")
                        LinearProgressIndicator(progress = progress.coerceIn(0f, 1f), modifier = Modifier.fillMaxWidth())
                    }
                }
            }

            item {
                Text("快速记录", style = MaterialTheme.typography.titleSmall)
                listOf("散步", "跑步", "力量训练", "骑行").forEach { preset ->
                    TextButton(onClick = { viewModel.recordExercise(preset, 30, 200) }) {
                        Text("$preset 30 分钟")
                    }
                }
            }

            item {
                Text("自定义记录", style = MaterialTheme.typography.titleSmall)
                OutlinedTextField(value = type, onValueChange = { type = it }, label = { Text("类型") }, modifier = Modifier.fillMaxWidth())
                OutlinedTextField(value = minutes, onValueChange = { minutes = it }, label = { Text("时长 (分钟)") }, modifier = Modifier.fillMaxWidth())
                OutlinedTextField(value = calories, onValueChange = { calories = it }, label = { Text("热量 (千卡)") }, modifier = Modifier.fillMaxWidth())
                Button(
                    onClick = {
                        viewModel.recordExercise(
                            type,
                            minutes.toIntOrNull() ?: 0,
                            calories.toIntOrNull() ?: 0,
                        )
                        type = ""; minutes = ""; calories = ""
                    },
                    modifier = Modifier.fillMaxWidth(),
                ) { Text(stringResource(R.string.health_record_exercise)) }
            }

            items(state.exercises, key = { it.id }) { ex ->
                Text("${ex.exerciseType} · ${ex.durationMinutes} 分钟 · ${ex.calories} kcal")
            }

            if (state.loading) {
                item { CircularProgressIndicator(modifier = Modifier.padding(16.dp)) }
            }
            item { Spacer(Modifier.height(80.dp)) }
        }
    }
}
