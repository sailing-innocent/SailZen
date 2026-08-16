package com.sailzen.app.feature.health

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
import androidx.compose.material.icons.filled.Favorite
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.DropdownMenu
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.ExtendedFloatingActionButton
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
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
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.lifecycle.viewmodel.compose.viewModel
import com.sailzen.app.R
import com.sailzen.app.core.network.dto.DashboardDietItemDto
import com.sailzen.app.core.network.dto.DashboardExerciseItemDto
import com.sailzen.app.core.network.dto.DashboardMedicationItemDto
import com.sailzen.app.core.network.dto.DashboardSleepItemDto
import com.sailzen.app.core.network.dto.DashboardWeightItemDto
import com.sailzen.app.ui.components.SectionCard
import com.sailzen.app.ui.navigation.Routes
import java.time.LocalDate

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun HealthHomeScreen(
    onNavigate: (String) -> Unit,
    onOpenHealthCheckin: () -> Unit,
    viewModel: HealthHomeViewModel = viewModel(),
) {
    val state by viewModel.uiState.collectAsState()
    var menuExpanded by remember { mutableStateOf(false) }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text(stringResource(R.string.health_home_title)) },
                actions = {
                    TextButton(onClick = { /* date picker simplified */ }) {
                        Text(state.selectedDate.toString())
                    }
                },
            )
        },
        floatingActionButton = {
            ExtendedFloatingActionButton(
                onClick = { menuExpanded = true },
                icon = { Icon(Icons.Default.Add, contentDescription = null) },
                text = { Text(stringResource(R.string.health_quick_record)) },
            )
            DropdownMenu(
                expanded = menuExpanded,
                onDismissRequest = { menuExpanded = false },
            ) {
                DropdownMenuItem(
                    text = { Text(stringResource(R.string.health_checkin_weight)) },
                    onClick = { menuExpanded = false; onOpenHealthCheckin() },
                )
                DropdownMenuItem(
                    text = { Text(stringResource(R.string.health_checkin_medication)) },
                    onClick = { menuExpanded = false; onNavigate(Routes.HEALTH_MEDICATION) },
                )
                DropdownMenuItem(
                    text = { Text(stringResource(R.string.health_checkin_sleep)) },
                    onClick = { menuExpanded = false; onNavigate(Routes.HEALTH_SLEEP) },
                )
                DropdownMenuItem(
                    text = { Text(stringResource(R.string.health_checkin_exercise)) },
                    onClick = { menuExpanded = false; onNavigate(Routes.HEALTH_EXERCISE) },
                )
                DropdownMenuItem(
                    text = { Text(stringResource(R.string.health_checkin_meal)) },
                    onClick = { menuExpanded = false; onNavigate(Routes.HEALTH_DIET) },
                )
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
            item { Text(stringResource(R.string.health_today_overview), style = MaterialTheme.typography.titleMedium) }
            item { OverviewCard(state.dashboard, viewModel) }

            if (!state.dashboard?.warnings.isNullOrEmpty()) {
                item { Text(stringResource(R.string.health_warnings), style = MaterialTheme.typography.titleMedium) }
                items(state.dashboard!!.warnings) { warning ->
                    Card(colors = CardDefaults.cardColors(containerColor = Color(0xFFFFF3E0))) {
                        Text(warning, modifier = Modifier.padding(12.dp), color = Color(0xFFE65100))
                    }
                }
            }

            item { SectionCard(title = stringResource(R.string.health_weight_curve), onClick = { onNavigate(Routes.HEALTH_WEIGHT_CURVE) }) {} }
            item { SectionCard(title = stringResource(R.string.health_weight_plan), onClick = { onNavigate(Routes.HEALTH_WEIGHT_PLAN) }) {} }
            item { SectionCard(title = stringResource(R.string.health_medication), onClick = { onNavigate(Routes.HEALTH_MEDICATION) }) {} }
            item { SectionCard(title = stringResource(R.string.health_sleep_schedule), onClick = { onNavigate(Routes.HEALTH_SLEEP) }) {} }
            item { SectionCard(title = stringResource(R.string.health_diet), onClick = { onNavigate(Routes.HEALTH_DIET) }) {} }
            item { SectionCard(title = stringResource(R.string.health_exercise), onClick = { onNavigate(Routes.HEALTH_EXERCISE) }) {} }
            item { Spacer(Modifier.height(80.dp)) }
        }

        if (state.loading) {
            CircularProgressIndicator(modifier = Modifier.padding(32.dp))
        }
    }

    state.error?.let { error ->
        AlertDialog(
            onDismissRequest = { viewModel.refresh() },
            title = { Text("加载失败") },
            text = { Text(error) },
            confirmButton = {
                TextButton(onClick = { viewModel.refresh() }) { Text("重试") }
            },
        )
    }
}

@Composable
private fun OverviewCard(dashboard: HealthDashboardDto?, viewModel: HealthHomeViewModel) {
    Card(modifier = Modifier.fillMaxWidth()) {
        Column(modifier = Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
            WeightRow(dashboard?.weight, viewModel)
            SleepRow(dashboard?.sleep)
            ExerciseRow(dashboard?.exercise)
            MedicationRow(dashboard?.medication)
            DietRow(dashboard?.diet)
        }
    }
}

@Composable
private fun WeightRow(item: DashboardWeightItemDto?, viewModel: HealthHomeViewModel) {
    Row(verticalAlignment = Alignment.CenterVertically) {
        Icon(Icons.Default.Favorite, contentDescription = null, modifier = Modifier.size(20.dp), tint = Color(0xFFE91E63))
        Text(
            item?.latest?.let { stringResource(R.string.health_weight_latest, it) } ?: "体重 --",
            modifier = Modifier.padding(start = 8.dp),
        )
        Spacer(Modifier.weight(1f))
        item?.let {
            Text(stringResource(viewModel.weightLabelRes(it.status)), color = Color(0xFF757575))
        }
    }
}

@Composable
private fun SleepRow(item: DashboardSleepItemDto?) {
    Row(verticalAlignment = Alignment.CenterVertically) {
        Icon(Icons.Default.Favorite, contentDescription = null, modifier = Modifier.size(20.dp), tint = Color(0xFF9C27B0))
        Text(
            item?.lastNightHours?.let { stringResource(R.string.health_sleep_hours, it) } ?: "睡眠 --",
            modifier = Modifier.padding(start = 8.dp),
        )
    }
}

@Composable
private fun ExerciseRow(item: DashboardExerciseItemDto?) {
    Row(verticalAlignment = Alignment.CenterVertically) {
        Icon(Icons.Default.Favorite, contentDescription = null, modifier = Modifier.size(20.dp), tint = Color(0xFF4CAF50))
        Text(
            item?.let { stringResource(R.string.health_exercise_minutes, it.todayMinutes) } ?: "运动 --",
            modifier = Modifier.padding(start = 8.dp),
        )
        Spacer(Modifier.weight(1f))
        if (item?.completed == true) Text("✓", color = Color(0xFF4CAF50))
    }
}

@Composable
private fun MedicationRow(item: DashboardMedicationItemDto?) {
    Row(verticalAlignment = Alignment.CenterVertically) {
        Icon(Icons.Default.Favorite, contentDescription = null, modifier = Modifier.size(20.dp), tint = Color(0xFF2196F3))
        Text(
            item?.let { stringResource(R.string.health_medication_compliance, (it.compliance * 100).toInt()) } ?: "用药 --",
            modifier = Modifier.padding(start = 8.dp),
        )
    }
}

@Composable
private fun DietRow(item: DashboardDietItemDto?) {
    Row(verticalAlignment = Alignment.CenterVertically) {
        Icon(Icons.Default.Favorite, contentDescription = null, modifier = Modifier.size(20.dp), tint = Color(0xFFFF9800))
        Text(
            item?.let {
                stringResource(
                    R.string.health_diet_calories,
                    it.caloriesActual?.toInt() ?: 0,
                    it.caloriesGoal?.toInt() ?: 0,
                )
            } ?: "饮食 --",
            modifier = Modifier.padding(start = 8.dp),
        )
    }
}
