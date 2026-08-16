package com.sailzen.app.feature.health.sleep

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
import androidx.compose.foundation.lazy.items
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material3.Button
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ExperimentalMaterial3Api
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
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.unit.dp
import androidx.lifecycle.viewmodel.compose.viewModel
import com.sailzen.app.R
import com.sailzen.app.ui.components.BarChart

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun SleepScheduleScreen(
    onBack: () -> Unit,
    viewModel: SleepScheduleViewModel = viewModel(),
) {
    val state by viewModel.uiState.collectAsState()
    var hoursInput by remember { mutableStateOf("") }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("作息节律") },
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
            item {
                Text("目标", style = MaterialTheme.typography.titleSmall)
                val goal = state.goal
                if (goal != null) {
                    Text(stringResource(R.string.health_bed_time, goal.bedTime))
                    Text(stringResource(R.string.health_wake_time, goal.wakeTime))
                    Text("目标时长 ${goal.targetHours} 小时")
                } else {
                    Text("未设置作息目标", color = Color.Gray)
                }
                TextButton(onClick = { viewModel.saveGoal("23:00", "07:00", 8.0) }) {
                    Text("恢复默认目标")
                }
            }

            item {
                Text("记录睡眠", style = MaterialTheme.typography.titleSmall)
                Row(verticalAlignment = Alignment.CenterVertically) {
                    OutlinedTextField(
                        value = hoursInput,
                        onValueChange = { hoursInput = it },
                        label = { Text("时长 (小时)") },
                        modifier = Modifier.weight(1f),
                    )
                    Button(
                        onClick = {
                            hoursInput.toDoubleOrNull()?.let { viewModel.recordSleep(it, 3) }
                            hoursInput = ""
                        },
                        modifier = Modifier.padding(start = 8.dp),
                    ) { Text("保存") }
                }
            }

            item {
                Text("近 7 天睡眠", style = MaterialTheme.typography.titleSmall)
                val bars = state.sleeps.map { "${it.id}" to it.hours }.takeLast(7)
                if (bars.isNotEmpty()) {
                    BarChart(bars = bars, modifier = Modifier.fillMaxWidth().height(160.dp))
                } else if (!state.loading) {
                    Text("暂无记录", color = Color.Gray)
                }
            }

            items(state.sleeps, key = { it.id }) { sleep ->
                Text("${sleep.htime?.toLong()?.let { java.time.Instant.ofEpochSecond(it).toString() } ?: "--"} · ${sleep.hours} 小时 · 质量 ${sleep.quality}")
            }

            if (state.loading) {
                item { CircularProgressIndicator(modifier = Modifier.padding(16.dp)) }
            }
            item { Spacer(Modifier.height(80.dp)) }
        }
    }
}
