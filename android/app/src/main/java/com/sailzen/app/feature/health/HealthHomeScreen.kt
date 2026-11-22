package com.sailzen.app.feature.health

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.WindowInsets
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.KeyboardArrowLeft
import androidx.compose.material.icons.automirrored.filled.KeyboardArrowRight
import androidx.compose.material.icons.automirrored.filled.ShowChart
import androidx.compose.material.icons.filled.Add
import androidx.compose.material.icons.filled.Bedtime
import androidx.compose.material.icons.filled.FitnessCenter
import androidx.compose.material.icons.filled.Medication
import androidx.compose.material.icons.filled.MonitorWeight
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material.icons.filled.Restaurant
import androidx.compose.material.icons.filled.Settings
import androidx.compose.material.icons.filled.TrackChanges
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.DropdownMenu
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.ExtendedFloatingActionButton
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Surface
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
import androidx.compose.ui.graphics.vector.ImageVector
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
import com.sailzen.app.core.network.dto.HealthCoachSummaryDto
import com.sailzen.app.core.network.dto.HealthDashboardDto
import com.sailzen.app.core.network.dto.InfoCollectionType
import com.sailzen.app.ui.components.SectionCard
import com.sailzen.app.ui.navigation.Routes
import java.time.DayOfWeek
import java.time.LocalDate

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun HealthHomeScreen(
    onNavigate: (String) -> Unit,
    onOpenHealthCheckin: (InfoCollectionType) -> Unit,
    onOpenSettings: () -> Unit = {},
    viewModel: HealthHomeViewModel = viewModel(),
) {
    val state by viewModel.uiState.collectAsState()
    var menuExpanded by remember { mutableStateOf(false) }

    // 首次进入或之前失败且无数据时自动尝试刷新
    LaunchedEffect(Unit) {
        if (state.dashboard == null && !state.loading) {
            viewModel.refresh()
        }
    }

    Scaffold(
        contentWindowInsets = WindowInsets(0, 0, 0, 0),
        topBar = {
            TopAppBar(
                title = { Text(stringResource(R.string.health_home_title), fontWeight = FontWeight.Bold) },
                actions = {
                    IconButton(onClick = { viewModel.refresh() }, enabled = !state.loading) {
                        Icon(Icons.Default.Refresh, contentDescription = "刷新")
                    }
                    IconButton(onClick = onOpenSettings) {
                        Icon(Icons.Default.Settings, contentDescription = "设置")
                    }
                },
            )
        },
        floatingActionButton = {
            Box {
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
                        onClick = { menuExpanded = false; onOpenHealthCheckin(InfoCollectionType.weight) },
                    )
                    DropdownMenuItem(
                        text = { Text(stringResource(R.string.health_body_data_quick_record)) },
                        onClick = { menuExpanded = false; onNavigate(Routes.HEALTH_BODY_DATA_RECORD) },
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
                        onClick = { menuExpanded = false; onOpenHealthCheckin(InfoCollectionType.meal) },
                    )
                }
            }
        },
    ) { padding ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding),
        ) {
            if (state.loading) {
                LinearProgressIndicator(modifier = Modifier.fillMaxWidth().height(2.dp))
            }

            HealthDateBar(
                date = state.selectedDate,
                onPrev = { viewModel.stepDate(-1) },
                onNext = { viewModel.stepDate(1) },
                onToday = { viewModel.selectToday() },
            )

            LazyColumn(
                modifier = Modifier
                    .fillMaxSize()
                    .padding(horizontal = 16.dp),
                verticalArrangement = Arrangement.spacedBy(12.dp),
                contentPadding = PaddingValues(vertical = 12.dp),
            ) {
                // 非阻塞错误提示卡：绝不拦截底栏切换与返回键
                state.error?.let { errorMsg ->
                    item {
                        HealthErrorBanner(
                            message = errorMsg,
                            onRetry = { viewModel.refresh() },
                            onOpenSettings = onOpenSettings,
                            onDismiss = { viewModel.dismissError() },
                        )
                    }
                }

                item {
                    SailTickCoachBanner(
                        coach = state.coachSummary,
                        onOpenCoach = { onNavigate(Routes.HEALTH_COACH) },
                        onQuickWeight = { onOpenHealthCheckin(InfoCollectionType.weight) },
                    )
                }

                item {
                    Text(
                        stringResource(R.string.health_today_overview),
                        style = MaterialTheme.typography.titleMedium,
                        fontWeight = FontWeight.SemiBold,
                    )
                }
                item { OverviewCard(state.dashboard, viewModel) }

                if (!state.dashboard?.warnings.isNullOrEmpty()) {
                    item {
                        Text(
                            stringResource(R.string.health_warnings),
                            style = MaterialTheme.typography.titleMedium,
                            fontWeight = FontWeight.SemiBold,
                        )
                    }
                    items(state.dashboard!!.warnings) { warning ->
                        Card(
                            modifier = Modifier.fillMaxWidth(),
                            colors = CardDefaults.cardColors(containerColor = Color(0xFFFFF3E0)),
                        ) {
                            Text(
                                warning,
                                modifier = Modifier.padding(12.dp),
                                color = Color(0xFFE65100),
                                style = MaterialTheme.typography.bodySmall,
                            )
                        }
                    }
                }

                item {
                    Text(
                        "健康模块",
                        style = MaterialTheme.typography.titleMedium,
                        fontWeight = FontWeight.SemiBold,
                    )
                }

                val dash = state.dashboard
                item {
                    SectionCard(
                        title = stringResource(R.string.health_body_data_curve),
                        subtitle = dash?.weight?.latest?.let { "最近体重 %.1f kg · 查看多指标趋势".format(it) }
                            ?: "查看体重、体脂等身体指标曲线",
                        icon = Icons.AutoMirrored.Filled.ShowChart,
                        iconTint = Color(0xFFE91E63),
                        showChevron = true,
                        onClick = { onNavigate(Routes.HEALTH_BODY_DATA_CURVE) },
                    )
                }
                item {
                    SectionCard(
                        title = stringResource(R.string.health_weight_plan),
                        subtitle = dash?.weight?.planTarget?.let { "目标 %.1f kg".format(it) }
                            ?: "管理减重阶段计划与进度",
                        icon = Icons.Default.TrackChanges,
                        iconTint = Color(0xFF00897B),
                        showChevron = true,
                        onClick = { onNavigate(Routes.HEALTH_WEIGHT_PLAN) },
                    )
                }
                item {
                    SectionCard(
                        title = stringResource(R.string.health_medication),
                        subtitle = dash?.medication?.let { "今日依从性 ${(it.compliance * 100).toInt()}%" }
                            ?: "每日用药计划与打卡",
                        icon = Icons.Default.Medication,
                        iconTint = Color(0xFF1E88E5),
                        showChevron = true,
                        onClick = { onNavigate(Routes.HEALTH_MEDICATION) },
                    )
                }
                item {
                    SectionCard(
                        title = stringResource(R.string.health_sleep_schedule),
                        subtitle = dash?.sleep?.lastNightHours?.let { "昨夜睡眠 %.1f 小时".format(it) }
                            ?: "记录就寝起床与睡眠节律",
                        icon = Icons.Default.Bedtime,
                        iconTint = Color(0xFF8E24AA),
                        showChevron = true,
                        onClick = { onNavigate(Routes.HEALTH_SLEEP) },
                    )
                }
                item {
                    SectionCard(
                        title = stringResource(R.string.health_diet),
                        subtitle = dash?.diet?.let {
                            "今日热量 ${it.caloriesActual?.toInt() ?: 0} / ${it.caloriesGoal?.toInt() ?: 0} kcal"
                        } ?: "记录三餐与热量营养目标",
                        icon = Icons.Default.Restaurant,
                        iconTint = Color(0xFFFB8C00),
                        showChevron = true,
                        onClick = { onNavigate(Routes.HEALTH_DIET) },
                    )
                }
                item {
                    SectionCard(
                        title = stringResource(R.string.health_exercise),
                        subtitle = dash?.exercise?.let {
                            if (it.completed) "今日运动 ${it.todayMinutes} 分钟 · 已达标"
                            else "今日运动 ${it.todayMinutes} 分钟"
                        } ?: "记录每日运动与目标",
                        icon = Icons.Default.FitnessCenter,
                        iconTint = Color(0xFF43A047),
                        showChevron = true,
                        onClick = { onNavigate(Routes.HEALTH_EXERCISE) },
                    )
                }
                item { Spacer(Modifier.height(80.dp)) }
            }
        }
    }
}

@Composable
private fun HealthDateBar(
    date: LocalDate,
    onPrev: () -> Unit,
    onNext: () -> Unit,
    onToday: () -> Unit,
) {
    val isToday = date == LocalDate.now()
    val weekLabel = when (date.dayOfWeek) {
        DayOfWeek.MONDAY -> "周一"
        DayOfWeek.TUESDAY -> "周二"
        DayOfWeek.WEDNESDAY -> "周三"
        DayOfWeek.THURSDAY -> "周四"
        DayOfWeek.FRIDAY -> "周五"
        DayOfWeek.SATURDAY -> "周六"
        DayOfWeek.SUNDAY -> "周日"
    }
    Surface(color = MaterialTheme.colorScheme.surface) {
        Column {
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(horizontal = 8.dp, vertical = 2.dp),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                IconButton(onClick = onPrev, modifier = Modifier.size(36.dp)) {
                    Icon(Icons.AutoMirrored.Filled.KeyboardArrowLeft, contentDescription = "前一天")
                }
                Row(
                    modifier = Modifier
                        .weight(1f)
                        .clickable(enabled = !isToday, onClick = onToday),
                    horizontalArrangement = Arrangement.Center,
                    verticalAlignment = Alignment.CenterVertically,
                ) {
                    Text(
                        text = "$date · $weekLabel",
                        style = MaterialTheme.typography.titleSmall,
                        fontWeight = FontWeight.Medium,
                    )
                    Spacer(Modifier.width(6.dp))
                    Text(
                        text = if (isToday) "今天" else "回今天",
                        style = MaterialTheme.typography.labelSmall,
                        color = MaterialTheme.colorScheme.primary,
                    )
                }
                IconButton(onClick = onNext, modifier = Modifier.size(36.dp)) {
                    Icon(Icons.AutoMirrored.Filled.KeyboardArrowRight, contentDescription = "后一天")
                }
            }
            HorizontalDivider(color = MaterialTheme.colorScheme.outlineVariant.copy(alpha = 0.5f))
        }
    }
}

@Composable
private fun HealthErrorBanner(
    message: String,
    onRetry: () -> Unit,
    onOpenSettings: () -> Unit,
    onDismiss: () -> Unit,
) {
    Card(
        modifier = Modifier.fillMaxWidth(),
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.errorContainer),
    ) {
        Column(modifier = Modifier.padding(12.dp)) {
            Text(
                text = message,
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onErrorContainer,
            )
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.End,
            ) {
                TextButton(onClick = onDismiss) { Text("忽略") }
                TextButton(onClick = onOpenSettings) { Text("设置") }
                TextButton(onClick = onRetry) { Text("重试") }
            }
        }
    }
}

@Composable
private fun SailTickCoachBanner(
    coach: HealthCoachSummaryDto?,
    onOpenCoach: () -> Unit,
    onQuickWeight: () -> Unit,
) {
    val pendingCount = coach?.pendingTicketCount ?: 0
    val latestReport = coach?.latestReport
    val plan = coach?.activePlan
    val isAiPlan = plan?.managedBy == "sailtick" || plan?.curveType?.name == "ai_dynamic"

    Card(
        onClick = onOpenCoach,
        modifier = Modifier.fillMaxWidth(),
        colors = CardDefaults.cardColors(
            containerColor = MaterialTheme.colorScheme.primaryContainer.copy(alpha = 0.55f),
        ),
    ) {
        Column(
            modifier = Modifier.padding(14.dp),
            verticalArrangement = Arrangement.spacedBy(6.dp),
        ) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Text(
                    text = if (pendingCount > 0) "SailTick 教练 · $pendingCount 条待回复" else "SailTick AI 健康教练",
                    style = MaterialTheme.typography.titleSmall,
                    fontWeight = FontWeight.SemiBold,
                    color = MaterialTheme.colorScheme.onPrimaryContainer,
                )
                if (isAiPlan && !plan?.phaseName.isNullOrBlank()) {
                    Text(
                        text = plan!!.phaseName,
                        style = MaterialTheme.typography.labelSmall,
                        color = MaterialTheme.colorScheme.primary,
                    )
                }
            }
            val headline = when {
                pendingCount > 0 -> "新提问：${coach?.pendingTickets?.firstOrNull()?.title.orEmpty()}"
                latestReport != null && latestReport.summary.isNotBlank() ->
                    "最新日报(${latestReport.reportDate.takeLast(5)})：${latestReport.summary}"
                isAiPlan && !plan?.aiSummary.isNullOrBlank() -> plan!!.aiSummary
                else -> "随手发一句饮食或记录体重，每晚睡前自动整合日报并动态调整计划"
            }
            Text(
                text = headline,
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onPrimaryContainer,
            )
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.End,
            ) {
                TextButton(onClick = onQuickWeight) { Text("记体重") }
                TextButton(onClick = onOpenCoach) { Text("随手记一餐 / 看日报") }
            }
        }
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
private fun MetricRow(
    icon: ImageVector,
    tint: Color,
    label: String,
    trailing: String? = null,
    trailingColor: Color = MaterialTheme.colorScheme.onSurfaceVariant,
) {
    Row(
        modifier = Modifier.fillMaxWidth(),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Icon(icon, contentDescription = null, modifier = Modifier.size(20.dp), tint = tint)
        Text(
            text = label,
            style = MaterialTheme.typography.bodyMedium,
            modifier = Modifier.padding(start = 10.dp),
        )
        Spacer(Modifier.weight(1f))
        if (!trailing.isNullOrBlank()) {
            Text(text = trailing, style = MaterialTheme.typography.bodySmall, color = trailingColor)
        }
    }
}

@Composable
private fun WeightRow(item: DashboardWeightItemDto?, viewModel: HealthHomeViewModel) {
    val label = item?.latest?.let { stringResource(R.string.health_weight_latest, it) } ?: "体重 --"
    val statusText = item?.let {
        val status = stringResource(viewModel.weightLabelRes(it.status))
        it.planTarget?.let { target -> "$status · 目标 %.1f kg".format(target) } ?: status
    }
    MetricRow(
        icon = Icons.Default.MonitorWeight,
        tint = Color(0xFFE91E63),
        label = label,
        trailing = statusText,
    )
}

@Composable
private fun SleepRow(item: DashboardSleepItemDto?) {
    MetricRow(
        icon = Icons.Default.Bedtime,
        tint = Color(0xFF8E24AA),
        label = item?.lastNightHours?.let { stringResource(R.string.health_sleep_hours, it) } ?: "睡眠 --",
    )
}

@Composable
private fun ExerciseRow(item: DashboardExerciseItemDto?) {
    MetricRow(
        icon = Icons.Default.FitnessCenter,
        tint = Color(0xFF43A047),
        label = item?.let { stringResource(R.string.health_exercise_minutes, it.todayMinutes) } ?: "运动 --",
        trailing = if (item?.completed == true) "已达标 ✓" else null,
        trailingColor = Color(0xFF2E7D32),
    )
}

@Composable
private fun MedicationRow(item: DashboardMedicationItemDto?) {
    MetricRow(
        icon = Icons.Default.Medication,
        tint = Color(0xFF1E88E5),
        label = item?.let { stringResource(R.string.health_medication_compliance, (it.compliance * 100).toInt()) }
            ?: "用药 --",
    )
}

@Composable
private fun DietRow(item: DashboardDietItemDto?) {
    MetricRow(
        icon = Icons.Default.Restaurant,
        tint = Color(0xFFFB8C00),
        label = item?.let {
            stringResource(
                R.string.health_diet_calories,
                it.caloriesActual?.toInt() ?: 0,
                it.caloriesGoal?.toInt() ?: 0,
            )
        } ?: "饮食 --",
    )
}
