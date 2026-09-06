package com.sailzen.app.feature.health.bodydata

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
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
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.unit.dp
import androidx.lifecycle.viewmodel.compose.viewModel
import com.sailzen.app.R

/**
 * 身体数据记录页：一次录入多项指标（留空 = 未测量），支持 x_ 自定义指标。
 */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun BodyDataRecordScreen(
    onBack: () -> Unit,
    viewModel: BodyDataRecordViewModel = viewModel(),
) {
    val state by viewModel.uiState.collectAsState()
    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text(stringResource(R.string.health_body_data_record_title)) },
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
                Row(horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                    OutlinedTextField(
                        value = state.date.toString(),
                        onValueChange = { /* 简化：日期选择器在后续迭代补充 */ },
                        label = { Text("日期") },
                        modifier = Modifier.weight(1f),
                        readOnly = true,
                    )
                    OutlinedTextField(
                        value = state.time,
                        onValueChange = { viewModel.setTime(it) },
                        label = { Text("时间 (HH:mm)") },
                        modifier = Modifier.weight(1f),
                    )
                }
            }
            items(state.metrics, key = { it.key }) { metric ->
                OutlinedTextField(
                    value = state.values[metric.key].orEmpty(),
                    onValueChange = { viewModel.setValue(metric.key, it) },
                    label = {
                        Text(stringResource(R.string.health_body_data_metric_label, metric.labelZh, metric.unit))
                    },
                    modifier = Modifier.fillMaxWidth(),
                    singleLine = true,
                )
            }
            item {
                Text("自定义指标", style = MaterialTheme.typography.titleSmall)
                Row(horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                    OutlinedTextField(
                        value = state.customKey,
                        onValueChange = { viewModel.setCustomKey(it) },
                        label = { Text(stringResource(R.string.health_body_data_custom_key_hint)) },
                        modifier = Modifier.weight(1f),
                        singleLine = true,
                    )
                    OutlinedTextField(
                        value = state.customValue,
                        onValueChange = { viewModel.setCustomValue(it) },
                        label = { Text("数值") },
                        modifier = Modifier.weight(1f),
                        singleLine = true,
                    )
                }
            }
            item {
                OutlinedTextField(
                    value = state.note,
                    onValueChange = { viewModel.setNote(it) },
                    label = { Text("备注") },
                    modifier = Modifier.fillMaxWidth(),
                )
            }
            state.error?.let { error ->
                item { Text(error, color = MaterialTheme.colorScheme.error) }
            }
            item {
                Button(
                    onClick = { viewModel.submit() },
                    enabled = !state.submitting,
                    modifier = Modifier.fillMaxWidth(),
                ) {
                    Text(stringResource(R.string.health_body_data_save))
                }
            }
        }
    }
    if (state.submitted) {
        AlertDialog(
            onDismissRequest = { viewModel.dismissSubmitted() },
            title = { Text(stringResource(R.string.health_body_data_saved)) },
            text = { Text("身体数据已保存") },
            confirmButton = {
                TextButton(onClick = { viewModel.dismissSubmitted() }) { Text("继续记录") }
            },
        )
    }
}
