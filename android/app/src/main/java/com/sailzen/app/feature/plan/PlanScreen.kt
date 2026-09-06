package com.sailzen.app.feature.plan

import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.automirrored.filled.ArrowForward
import androidx.compose.material.icons.filled.Add
import androidx.compose.material.icons.filled.PlayArrow
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material.icons.filled.Settings
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Badge
import androidx.compose.material3.BadgedBox
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.FloatingActionButton
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.PrimaryTabRow
import androidx.compose.material3.Scaffold
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
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.lifecycle.viewmodel.compose.viewModel
import com.sailzen.app.core.network.dto.AffairActions
import com.sailzen.app.feature.plan.components.AffairsTab
import com.sailzen.app.feature.plan.components.CreateTaskDialog
import com.sailzen.app.feature.plan.components.CreateVentureDialog
import com.sailzen.app.feature.plan.components.CaptureDialog
import com.sailzen.app.feature.plan.components.TodayTab
import com.sailzen.app.feature.plan.components.VenturesTab
import com.sailzen.app.feature.plan.PlanViewModel.PlanTab

/**
 * 规划页（合并原 时间线 / 打卡 / 事业）：
 * 捕获 → 分拣 → 排程 → 打卡 → 复盘在同一页面内闭环。
 * 页内 PrimaryTabRow：今日 / 事务 / 事业，徽标仅作存在性提示。
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

    // 外部（磁贴/通知）请求打开快速捕获
    LaunchedEffect(openCapture) {
        if (openCapture) viewModel.openCapture()
    }

    // 每次进入页面时刷新（订阅管道在 ViewModel init 中建立）
    LaunchedEffect(Unit) {
        viewModel.refresh()
    }

    Scaffold(
        topBar = {
            TopAppBar(
                title = {
                    Column {
                        Row(verticalAlignment = Alignment.CenterVertically) {
                            IconButton(onClick = { viewModel.selectDate(prev = true) }) {
                                Icon(Icons.AutoMirrored.Filled.ArrowBack, contentDescription = "前一天")
                            }
                            Text("规划 ${state.date}", fontWeight = FontWeight.Bold)
                            IconButton(onClick = { viewModel.selectDate(prev = false) }) {
                                Icon(Icons.AutoMirrored.Filled.ArrowForward, contentDescription = "后一天")
                            }
                        }
                        Text(
                            text = when {
                                state.serverUrl.isBlank() -> "未配置服务器地址"
                                state.connected -> "${state.serverUrl} ● 已连接"
                                else -> "${state.serverUrl} ● 未连接"
                            },
                            style = MaterialTheme.typography.bodySmall,
                            color = if (state.connected) {
                                MaterialTheme.colorScheme.primary
                            } else {
                                MaterialTheme.colorScheme.error
                            },
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
            // 今日 Tab 的捕获入口为顶部常驻 CaptureBar；事务/事业 Tab 保留 FAB 新建
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
        Column(modifier = Modifier.padding(padding)) {
            PrimaryTabRow(selectedTabIndex = state.selectedTab.ordinal) {
                Tab(
                    selected = state.selectedTab == PlanTab.TODAY,
                    onClick = { viewModel.selectTab(PlanTab.TODAY) },
                    text = {
                        BadgedBox(badge = { if (state.inbox.isNotEmpty()) Badge { Text("${state.inbox.size}") } }) {
                            Text("今日")
                        }
                    },
                )
                Tab(
                    selected = state.selectedTab == PlanTab.AFFAIR,
                    onClick = { viewModel.selectTab(PlanTab.AFFAIR) },
                    text = {
                        BadgedBox(badge = { if (state.tasks.isNotEmpty()) Badge { Text("${state.tasks.size}") } }) {
                            Text("事务")
                        }
                    },
                )
                Tab(
                    selected = state.selectedTab == PlanTab.VENTURE,
                    onClick = { viewModel.selectTab(PlanTab.VENTURE) },
                    text = {
                        BadgedBox(badge = { if (state.ventures.isNotEmpty()) Badge { Text("${state.ventures.size}") } }) {
                            Text("事业")
                        }
                    },
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

    // ---------------- 操作失败提示 ----------------
    state.message?.let { message ->
        AlertDialog(
            onDismissRequest = { viewModel.dismissMessage() },
            title = { Text("提示") },
            text = { Text(message) },
            confirmButton = {
                TextButton(onClick = { viewModel.dismissMessage() }) { Text("确定") }
            },
        )
    }
}
