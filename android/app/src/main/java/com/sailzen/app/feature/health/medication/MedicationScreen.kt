package com.sailzen.app.feature.health.medication

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
import androidx.compose.material.icons.filled.Add
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.Checkbox
import androidx.compose.material3.CircularProgressIndicator
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
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.unit.dp
import androidx.lifecycle.viewmodel.compose.viewModel
import com.sailzen.app.R
import com.sailzen.app.core.network.dto.MedicationCreateRequest

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun MedicationScreen(
    onBack: () -> Unit,
    viewModel: MedicationViewModel = viewModel(),
) {
    val state by viewModel.uiState.collectAsState()

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("用药节律") },
                navigationIcon = {
                    IconButton(onClick = onBack) {
                        Icon(Icons.AutoMirrored.Filled.ArrowBack, contentDescription = "返回")
                    }
                },
            )
        },
        floatingActionButton = {
            FloatingActionButton(onClick = { viewModel.showEdit() }) {
                Icon(Icons.Default.Add, contentDescription = stringResource(R.string.health_add_medication))
            }
        },
    ) { padding ->
        LazyColumn(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding)
                .padding(horizontal = 16.dp),
            verticalArrangement = Arrangement.spacedBy(8.dp),
            contentPadding = PaddingValues(vertical = 12.dp),
        ) {
            state.today?.let { today ->
                item {
                    Text("今日完成 ${today.taken}/${today.total}，依从性 ${(today.compliance * 100).toInt()}%", style = MaterialTheme.typography.bodyMedium)
                }
            }

            items(state.medications, key = { it.id }) { med ->
                MedicationItem(med, onTake = { viewModel.take(med.id) })
            }

            if (state.loading) {
                item { CircularProgressIndicator(modifier = Modifier.padding(16.dp)) }
            }
            item { Spacer(Modifier.height(80.dp)) }
        }
    }

    if (state.showEdit) {
        MedicationEditDialog(
            form = state.editForm,
            onFormChange = { viewModel.setEditForm(it) },
            onSave = { viewModel.save() },
            onDismiss = { viewModel.dismissEdit() },
        )
    }
}

@Composable
private fun MedicationItem(med: com.sailzen.app.core.network.dto.MedicationDto, onTake: () -> Unit) {
    Card(modifier = Modifier.fillMaxWidth()) {
        Row(
            verticalAlignment = Alignment.CenterVertically,
            modifier = Modifier.padding(12.dp),
        ) {
            Checkbox(checked = med.taken, onCheckedChange = { if (!med.taken) onTake() })
            Column(modifier = Modifier.weight(1f).padding(start = 8.dp)) {
                Text(med.name, style = MaterialTheme.typography.bodyLarge)
                Text("${med.dosage} · ${med.frequency}", style = MaterialTheme.typography.bodySmall, color = Color.Gray)
            }
            if (!med.taken) {
                Button(onClick = onTake) { Text(stringResource(R.string.health_take)) }
            } else {
                Text(stringResource(R.string.health_taken), color = Color(0xFF4CAF50))
            }
        }
    }
}

@Composable
private fun MedicationEditDialog(
    form: MedicationCreateRequest,
    onFormChange: (MedicationCreateRequest) -> Unit,
    onSave: () -> Unit,
    onDismiss: () -> Unit,
) {
    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text("添加用药") },
        text = {
            Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                OutlinedTextField(
                    value = form.name,
                    onValueChange = { onFormChange(form.copy(name = it)) },
                    label = { Text("名称") },
                    modifier = Modifier.fillMaxWidth(),
                )
                OutlinedTextField(
                    value = form.dosage,
                    onValueChange = { onFormChange(form.copy(dosage = it)) },
                    label = { Text("剂量") },
                    modifier = Modifier.fillMaxWidth(),
                )
                OutlinedTextField(
                    value = form.frequency,
                    onValueChange = { onFormChange(form.copy(frequency = it)) },
                    label = { Text("频次 (daily/weekly/as_needed)") },
                    modifier = Modifier.fillMaxWidth(),
                )
            }
        },
        confirmButton = { TextButton(onClick = onSave) { Text("保存") } },
        dismissButton = { TextButton(onClick = onDismiss) { Text("取消") } },
    )
}
