package com.sailzen.app.feature.plan

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.WindowInsets
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.KeyboardArrowLeft
import androidx.compose.material.icons.automirrored.filled.KeyboardArrowRight
import androidx.compose.material.icons.filled.Add
import androidx.compose.material.icons.filled.PlayArrow
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material.icons.filled.Settings
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Badge
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.FloatingActionButton
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.PrimaryTabRow
import androidx.compose.material3.Scaffold
import androidx.compose.material3.SnackbarHost
import androidx.compose.material3.SnackbarHostState
import androidx.compose.material3.Surface
import androidx.compose.material3.Tab
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
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.lifecycle.viewmodel.compose.viewModel
import com.sailzen.app.core.network.ReminderWebSocket.ConnectionState
import com.sailzen.app.core.network.dto.AffairActions
import com.sailzen.app.feature.plan.PlanViewModel.PlanTab
import com.sailzen.app.feature.plan.components.AffairsTab
import com.sailzen.app.feature.plan.components.CaptureDialog
import com.sailzen.app.feature.plan.components.CreateTaskDialog
import com.sailzen.app.feature.plan.components.CreateVentureDialog
import com.sailzen.app.feature.plan.components.TodayTab
import com.sailzen.app.feature.plan.components.VenturesTab
import java.time.DayOfWeek
import java.time.LocalDate

/**
 * 规划页（合并原 时间线 / 打卡 / 事业）：
 * - 顶部单行 TopAppBar（标题 + 连接状态胶囊 + 快捷操作），彻底避免内容溢出挤压下方 Tab；
 * - 独立日期切换条（◀ 日期 · 星期 ▶ + 回今天）与非侵入式断连提示条；
 * - 页内 PrimaryTabRow：今日 / 事务 / 事业。
 */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun PlanScreen(
    onOpenSettings: () -> Unit,
    onOpenDetail: (Int) -> Unit,
    openCapture: Boolean = false,
    viewModel: PlanViewModel = viewModel(),
) {
    val state by viewModel.uiState.collectAsState()
    var showCreateTask by remember { mutableStateOf(false) }
    var showCreateVenture by remember { mutableStateOf(false) }
    val snackbarHostState = remember { SnackbarHostState() }

    LaunchedEffect(openCapture) {
        if (openCapture) viewModel.openCapture()
    }

    LaunchedEffect(Unit) {
        viewModel.refresh()
    }

    LaunchedEffect(state.message) {
        val msg = state.message ?: return@LaunchedEffect
        snackbarHostState.showSnackbar(msg)
        viewModel.dismissMessage()
    }

    Scaffold(
        contentWindowInsets = WindowInsets(0, 0, 0, 0),
        snackbarHost = { SnackbarHost(snackbarHostState) },
        topBar = {
            TopAppBar(
                title = {
                    Row(
                        verticalAlignment = Alignment.CenterVertically,
                        horizontalArrangement = Arrangement.spacedBy(8.dp),
                    ) {
                        Text("规划", fontWeight = FontWeight.Bold)
                        ConnectionStatusPill(
                            configured = state.configured,
                            connected = state.connected,
                            connectionState = state.connectionState,
                            onClick = onOpenSettings,
                        )
                    }
                },
                actions = {
                    IconButton(onClick = { viewModel.plan() }, enabled = !state.planning) {
                        if (state.planning) {
                            CircularProgressIndicator(modifier = Modifier.size(20.dp), strokeWidth = 2.dp)
                        } else {
                            Icon(Icons.Default.PlayArrow, contentDescription = "生成日计划")
                        }
                    }
                    IconButton(onClick = { viewModel.refresh() }) {
                        Icon(Icons.Default.Refresh, contentDescription = "刷新")
                    }
                    IconButton(onClick = onOpenSettings) {
                        Icon(Icons.Default.Settings, contentDescription = "设置")
                    }
                },
            )
        },
        floatingActionButton = {
            when (state.selectedTab) {
                PlanTab.AFFAIR -> FloatingActionButton(onClick = { showCreateTask = true }) {
                    Icon(Icons.Default.Add, contentDescription = "新建任务")
                }
                PlanTab.VENTURE -> FloatingActionButton(onClick = { showCreateVenture = true }) {
                    Icon(Icons.Default.Add, contentDescription = "新建事业")
                }
                PlanTab.TODAY -> {}
            }
        },
    ) { padding ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding),
        ) {
            if (state.refreshing) {
                LinearProgressIndicator(modifier = Modifier.fillMaxWidth().height(2.dp))
            }

            // 独立日期切换栏，布局清爽不与 TopAppBar 或 Tab 互相挤压
            DateNavigatorBar(
                date = state.date,
                onPrev = { viewModel.selectDate(prev = true) },
                onNext = { viewModel.selectDate(prev = false) },
                onToday = { viewModel.selectToday() },
            )

            // 仅在异常/未配置时以独立细条展示，不挤压标题或 Tab
            if (!state.configured || (!state.connected && state.connectionState == ConnectionState.ERROR)) {
                ConnectionWarningStrip(
                    configured = state.configured,
                    serverUrl = state.serverUrl,
                    detail = state.connectionDetail,
                    onRetry = { viewModel.reconnect() },
                    onOpenSettings = onOpenSettings,
                )
            }

            PrimaryTabRow(selectedTabIndex = state.selectedTab.ordinal) {
                PlanTabItem(
                    label = "今日",
                    count = state.inbox.size,
                    selected = state.selectedTab == PlanTab.TODAY,
                    onClick = { viewModel.selectTab(PlanTab.TODAY) },
                )
                PlanTabItem(
                    label = "事务",
                    count = state.tasks.size,
                    selected = state.selectedTab == PlanTab.AFFAIR,
                    onClick = { viewModel.selectTab(PlanTab.AFFAIR) },
                )
                PlanTabItem(
                    label = "事业",
                    count = state.ventures.size,
                    selected = state.selectedTab == PlanTab.VENTURE,
                    onClick = { viewModel.selectTab(PlanTab.VENTURE) },
                )
            }

            when (state.selectedTab) {
                PlanTab.TODAY -> TodayTab(
                    state = state,
                    onCapture = { title, kind -> viewModel.capture(title, kind) },
                    onAcceptHint = { viewModel.acceptHint(it) },
                    onRejectHint = { viewModel.rejectHint(it) },
                    onConfirmInbox = { viewModel.transit(it, AffairActions.CONFIRM) },
                    onCancelInbox = { viewModel.transit(it, AffairActions.CANCEL) },
                    onOpenWeekReview = { viewModel.openWeekReview() },
                    onPreceptKept = { viewModel.preceptKept(it) },
                    onPreceptViolated = { viewModel.preceptViolated(it) },
                    onHabitDone = { viewModel.habitDone(it) },
                    onHabitMissed = { viewModel.habitMissed(it) },
                    onDoneBlock = { viewModel.doneBlock(it) },
                    onDeferBlock = { viewModel.deferBlock(it) },
                    onPlanB = { viewModel.showPlanB(it) },
                )

                PlanTab.AFFAIR -> AffairsTab(
                    state = state,
                    onSelectFilter = { viewModel.selectStateFilter(it) },
                    onOpenDetail = onOpenDetail,
                    onAction = { id, action -> viewModel.transit(id, action) },
                )

                PlanTab.VENTURE -> VenturesTab(
                    state = state,
                    onOpenDetail = onOpenDetail,
                    onMilestoneDone = { viewModel.milestoneDone(it) },
                    onConfirmVenture = { viewModel.transit(it, AffairActions.CONFIRM) },
                )
            }
        }
    }

    // ---------------- Plan B 弹窗 ----------------
    state.planBBlock?.let { block ->
        AlertDialog(
            onDismissRequest = { viewModel.dismissPlanB() },
            title = { Text("备用方案 (Plan B)") },
            text = {
                Column {
                    Text(block.affairTitle ?: block.blockType, fontWeight = FontWeight.Bold)
                    Spacer(Modifier.height(8.dp))
                    Text(state.planBText ?: "加载中…")
                }
            },
            confirmButton = {
                TextButton(onClick = { viewModel.dismissPlanB() }) { Text("知道了") }
            },
        )
    }

    // ---------------- 快速捕获弹窗（磁贴深链） ----------------
    if (state.captureOpen) {
        CaptureDialog(
            onDismiss = { viewModel.closeCapture() },
            onConfirm = { title, kind -> viewModel.capture(title, kind) },
        )
    }

    // ---------------- 破戒备注弹窗 ----------------
    state.noteTarget?.let { target ->
        var note by remember { mutableStateOf("") }
        AlertDialog(
            onDismissRequest = { viewModel.dismissNote() },
            title = { Text("破戒备注") },
            text = {
                Column {
                    Text(target.affair.title, fontWeight = FontWeight.Bold)
                    Spacer(Modifier.height(8.dp))
                    OutlinedTextField(
                        value = note,
                        onValueChange = { note = it },
                        label = { Text("原因（供 AI 复盘归因）") },
                        modifier = Modifier.fillMaxWidth(),
                    )
                }
            },
            confirmButton = {
                TextButton(onClick = { viewModel.confirmViolate(note) }) { Text("记录破戒") }
            },
            dismissButton = {
                TextButton(onClick = { viewModel.dismissNote() }) { Text("取消") }
            },
        )
    }

    // ---------------- 周报详情弹窗 ----------------
    if (state.weekReviewOpen) {
        state.weekReview?.let { review ->
            AlertDialog(
                onDismissRequest = { viewModel.closeWeekReview() },
                title = { Text("节奏周报 ${review.periodKey}") },
                text = {
                    Column {
                        Text("节奏分 %.1f / 100".format(review.rhythmScore), fontWeight = FontWeight.Bold)
                        Spacer(Modifier.height(8.dp))
                        Text("戒律合规率 %.0f%%".format(review.preceptComplianceRate * 100))
                        Text("习惯达标率 %.0f%%".format(review.habitConsistency * 100))
                        Text("睡眠窗守约 %.0f%%".format(review.sleepWindowKeeping * 100))
                        Text("事业预算达成 %.0f%%".format(review.ventureBudgetFulfillment * 100))
                        Text("缓冲消耗 %.0f%%".format(review.bufferConsumed * 100))
                        Text("侵占事件 ${review.encroachments.size} 起")
                        if (review.aiSummary.isNotBlank()) {
                            Spacer(Modifier.height(8.dp))
                            Text("AI 周评", fontWeight = FontWeight.Bold)
                            Text(review.aiSummary, style = MaterialTheme.typography.bodySmall)
                        }
                    }
                },
                confirmButton = {
                    TextButton(onClick = { viewModel.closeWeekReview() }) { Text("关闭") }
                },
            )
        }
    }

    // ---------------- 新建任务 / 事业弹窗 ----------------
    if (showCreateTask) {
        CreateTaskDialog(
            onDismiss = { showCreateTask = false },
            onConfirm = { title, kind, domain, minutes, ddl ->
                viewModel.createTask(title, kind, domain, minutes, ddl)
                showCreateTask = false
            },
        )
    }
    if (showCreateVenture) {
        CreateVentureDialog(
            onDismiss = { showCreateVenture = false },
            onConfirm = { title, targetDate, hours ->
                viewModel.createVenture(title, targetDate, hours)
                showCreateVenture = false
            },
        )
    }
}

@Composable
private fun ConnectionStatusPill(
    configured: Boolean,
    connected: Boolean,
    connectionState: ConnectionState,
    onClick: () -> Unit,
) {
    val (dotColor, containerColor, textColor, label) = when {
        !configured -> Quad(
            MaterialTheme.colorScheme.error,
            MaterialTheme.colorScheme.errorContainer,
            MaterialTheme.colorScheme.onErrorContainer,
            "未配置",
        )
        connected -> Quad(
            Color(0xFF2E7D32),
            Color(0xFFE8F5E9),
            Color(0xFF1B5E20),
            "已连接",
        )
        connectionState == ConnectionState.CONNECTING -> Quad(
            Color(0xFFEF6C00),
            Color(0xFFFFF3E0),
            Color(0xFFE65100),
            "连接中",
        )
        else -> Quad(
            MaterialTheme.colorScheme.error,
            MaterialTheme.colorScheme.errorContainer,
            MaterialTheme.colorScheme.onErrorContainer,
            "未连接",
        )
    }
    Surface(
        shape = RoundedCornerShape(999.dp),
        color = containerColor,
        modifier = Modifier.clickable(onClick = onClick),
    ) {
        Row(
            modifier = Modifier.padding(horizontal = 8.dp, vertical = 3.dp),
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.spacedBy(5.dp),
        ) {
            Box(
                modifier = Modifier
                    .size(7.dp)
                    .clip(CircleShape)
                    .background(dotColor),
            )
            Text(
                text = label,
                style = MaterialTheme.typography.labelSmall,
                color = textColor,
                maxLines = 1,
            )
        }
    }
}

private data class Quad<A, B, C, D>(val first: A, val second: B, val third: C, val fourth: D)

@Composable
private fun DateNavigatorBar(
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
                    if (isToday) {
                        Spacer(Modifier.width(6.dp))
                        Text(
                            text = "今天",
                            style = MaterialTheme.typography.labelSmall,
                            color = MaterialTheme.colorScheme.primary,
                        )
                    } else {
                        Spacer(Modifier.width(6.dp))
                        Text(
                            text = "回今天",
                            style = MaterialTheme.typography.labelSmall,
                            color = MaterialTheme.colorScheme.primary,
                        )
                    }
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
private fun ConnectionWarningStrip(
    configured: Boolean,
    serverUrl: String,
    detail: String,
    onRetry: () -> Unit,
    onOpenSettings: () -> Unit,
) {
    Surface(
        color = MaterialTheme.colorScheme.errorContainer,
        modifier = Modifier.fillMaxWidth(),
    ) {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(horizontal = 12.dp, vertical = 6.dp),
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.spacedBy(8.dp),
        ) {
            Text(
                text = if (!configured) {
                    "未配置服务器地址"
                } else {
                    val shortDetail = detail.takeIf { it.isNotBlank() }?.let { " ($it)" }.orEmpty()
                    "连接失败：$serverUrl$shortDetail"
                },
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onErrorContainer,
                maxLines = 2,
                overflow = TextOverflow.Ellipsis,
                modifier = Modifier.weight(1f),
            )
            if (configured) {
                TextButton(onClick = onRetry) { Text("重试") }
            }
            TextButton(onClick = onOpenSettings) { Text("设置") }
        }
    }
}

@Composable
private fun PlanTabItem(
    label: String,
    count: Int,
    selected: Boolean,
    onClick: () -> Unit,
) {
    Tab(
        selected = selected,
        onClick = onClick,
        text = {
            Row(
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.spacedBy(4.dp),
            ) {
                Text(label, maxLines = 1)
                if (count > 0) {
                    Badge { Text(if (count > 99) "99+" else "$count") }
                }
            }
        },
    )
}
