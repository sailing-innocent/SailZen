package com.sailzen.app.feature.diet

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
import androidx.compose.material.icons.filled.Add
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.Card
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
import com.sailzen.app.core.network.dto.DietCreateRequest
import com.sailzen.app.core.network.dto.NutrientActualVsGoalDto
import com.sailzen.app.core.network.dto.NutritionGoalCreateRequest
import com.sailzen.app.ui.components.ProgressRing

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun DietScreen(
    onBack: () -> Unit,
    viewModel: DietViewModel = viewModel(),
) {
    val state by viewModel.uiState.collectAsState()

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("饮食三餐") },
                navigationIcon = {
                    IconButton(onClick = onBack) {
                        Icon(Icons.AutoMirrored.Filled.ArrowBack, contentDescription = "返回")
                    }
                },
            )
        },
        floatingActionButton = {
            FloatingActionButton(onClick = { viewModel.showEdit() }) {
                Icon(Icons.Default.Add, contentDescription = stringResource(R.string.health_add_meal))
            }
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
            item { Text("营养目标 vs 实际", style = MaterialTheme.typography.titleSmall) }
            state.summary?.let { summary ->
                item { NutrientRow("热量", summary.calories, Color(0xFFFF9800)) }
                item { NutrientRow("碳水", summary.carbs, Color(0xFF2196F3)) }
                item { NutrientRow("糖分", summary.sugar, Color(0xFFE91E63)) }
                item { NutrientRow("蛋白质", summary.protein, Color(0xFF4CAF50)) }
                item { NutrientRow("脂肪", summary.fat, Color(0xFF795548)) }
                item { NutrientRow("纤维", summary.fiber, Color(0xFF9C27B0)) }
                item { NutrientRow("钠", summary.sodium, Color(0xFF607D8B)) }
            }

            item {
                Text("记录", style = MaterialTheme.typography.titleSmall)
                Row {
                    listOf("早餐", "午餐", "晚餐", "零食").forEachIndexed { index, label ->
                        val type = listOf("breakfast", "lunch", "dinner", "snack")[index]
                        Button(
                            onClick = { viewModel.setEditForm(DietCreateRequest(mealType = type, description = label)) },
                            modifier = Modifier.padding(end = 4.dp),
                        ) { Text(label) }
                    }
                }
            }

            items(state.diets, key = { it.id }) { diet ->
                Card(modifier = Modifier.fillMaxWidth()) {
                    Column(modifier = Modifier.padding(12.dp)) {
                        Text("${diet.mealType} · ${diet.description}", style = MaterialTheme.typography.bodyLarge)
                        Text("${diet.calories?.toInt() ?: 0} kcal", style = MaterialTheme.typography.bodySmall, color = Color.Gray)
                    }
                }
            }

            if (state.loading) {
                item { CircularProgressIndicator(modifier = Modifier.padding(16.dp)) }
            }
            item { Spacer(Modifier.height(80.dp)) }
        }
    }

    if (state.showEdit) {
        DietEditDialog(
            form = state.editForm,
            onFormChange = { viewModel.setEditForm(it) },
            onSave = { viewModel.saveDiet() },
            onDismiss = { viewModel.dismissEdit() },
        )
    }
}

@Composable
private fun NutrientRow(label: String, nutrient: NutrientActualVsGoalDto, color: Color) {
    val progress = if (nutrient.goal != null && nutrient.goal > 0) (nutrient.actual ?: 0.0) / nutrient.goal else 0.0
    Row(modifier = Modifier.fillMaxWidth().padding(vertical = 4.dp), verticalAlignment = androidx.compose.ui.Alignment.CenterVertically) {
        Text(label, modifier = Modifier.weight(1f))
        Text("${nutrient.actual?.toInt() ?: 0} / ${nutrient.goal?.toInt() ?: 0} ${nutrient.unit}", color = Color.Gray)
        ProgressRing(progress = progress.toFloat().coerceIn(0f, 1f), modifier = Modifier.padding(start = 8.dp).size(40.dp), color = color)
    }
}

@Composable
private fun DietEditDialog(
    form: DietCreateRequest,
    onFormChange: (DietCreateRequest) -> Unit,
    onSave: () -> Unit,
    onDismiss: () -> Unit,
) {
    var calories by remember { mutableStateOf(form.calories?.toString() ?: "") }
    var description by remember { mutableStateOf(form.description) }

    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text("添加饮食记录") },
        text = {
            Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                OutlinedTextField(
                    value = form.mealType,
                    onValueChange = { onFormChange(form.copy(mealType = it)) },
                    label = { Text("餐次 (breakfast/lunch/dinner/snack)") },
                    modifier = Modifier.fillMaxWidth(),
                )
                OutlinedTextField(
                    value = description,
                    onValueChange = { description = it },
                    label = { Text("描述") },
                    modifier = Modifier.fillMaxWidth(),
                )
                OutlinedTextField(
                    value = calories,
                    onValueChange = { calories = it },
                    label = { Text("热量 (kcal)") },
                    modifier = Modifier.fillMaxWidth(),
                )
            }
        },
        confirmButton = {
            TextButton(onClick = {
                onFormChange(form.copy(description = description, calories = calories.toDoubleOrNull()))
                onSave()
            }) { Text("保存") }
        },
        dismissButton = { TextButton(onClick = onDismiss) { Text("取消") } },
    )
}
