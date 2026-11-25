package com.sailzen.app.feature.plan

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.horizontalScroll
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
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.KeyboardArrowLeft
import androidx.compose.material.icons.automirrored.filled.KeyboardArrowRight
import androidx.compose.material.icons.filled.Add
import androidx.compose.material.icons.filled.EventBusy
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material.icons.filled.Settings
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Badge
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.FilledTonalButton
import androidx.compose.material3.FilterChip
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
import androidx.compose.material3.Switch
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
 * 规划页（Rhythm v2 + SailTick Personal Agent）：
 * - 顶部单行 TopAppBar（标题 + 连接状态胶囊 + 钉占用 / 刷新 / 设置）
 * - 独立日期切换条（◀ 日期 · 星期 ▶ + 回今天）与非阻塞断连提示条
 * - 页内 PrimaryTabRow：今日 / 待办 / 项目
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
                    IconButton(onClick = { viewModel.openOccupancyDialog() }) {
                        Icon(Icons.Default.EventBusy, contentDescription = "钉住临时占用")
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
                    Icon(Icons.Default.Add, contentDescription = "新建待办")
                }
                PlanTab.VENTURE -> FloatingActionButton(onClick = { showCreateVenture = true }) {
                    Icon(Icons.Default.Add, contentDescription = "新建项目")
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

            DateNavigatorBar(
                date = state.date,
                onPrev = { viewModel.selectDate(prev = true) },
                onNext = { viewModel.selectDate(prev = false) },
                onToday = { viewModel.selectToday() },
            )

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
                    label = "待办",
                    count = state.tasks.size,
                    selected = state.selectedTab == PlanTab.AFFAIR,
                    onClick = { viewModel.selectTab(PlanTab.AFFAIR) },
                )
                PlanTabItem(
                    label = "项目",
                    count = state.ventures.size,
                    selected = state.selectedTab == PlanTab.VENTURE,
                    onClick = { viewModel.selectTab(PlanTab.VENTURE) },
                )
            }

            when (state.selectedTab) {
                PlanTab.TODAY -> TodayTab(
                    state = state,
                    onQuickChat = { viewModel.sendQuickChat(it) },
                    onDismissChatReply = { viewModel.clearChatReply() },
                    onAcceptHint = { viewModel.acceptHint(it) },
                    onRejectHint = { viewModel.rejectHint(it) },
                    onConfirmInbox = { viewModel.transit(it, AffairActions.CONFIRM) },
                    onCancelInbox = { viewModel.transit(it, AffairActions.CANCEL) },
                    onPreceptKept = { viewModel.preceptKept(it) },
                    onPreceptViolated = { viewModel.preceptViolated(it) },
                    onHabitDone = { viewModel.habitDone(it) },
                    onHabitMissed = { viewModel.habitMissed(it) },
                    onDoneBlock = { viewModel.doneBlock(it) },
                    onDeferBlock = { viewModel.deferBlock(it) },
                    onDeleteBlock = { block ->
                        if (block.blockType == "occupied") {
                            viewModel.deleteOccupancy(block.id)
                        } else {
                            viewModel.deleteBlock(block.id)
                        }
                    },
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

    // ---------------- 钉住临时占用弹窗 ----------------
    if (state.occupancyDialogOpen) {
        CreateOccupancyDialog(
            date = state.date,
            onDismiss = { viewModel.closeOccupancyDialog() },
            onConfirm = { type, start, end, wholeDay, label ->
                viewModel.createOccupancy(
                    occupancyType = type,
                    start = start,
                    end = end,
                    wholeDay = wholeDay,
                    label = label,
                )
            },
        )
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
                        label = { Text("原因（供 SailTick 复盘归因）") },
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

    // ---------------- 新建待办 / 项目弹窗 ----------------
    if (showCreateTask) {
        CreateTaskDialog(
            onDismiss = { showCreateTask = false },
            onConfirm = { title, ddl, minutes, domain ->
                viewModel.createTask(title = title, ddlIso = ddl, estMinutes = minutes, domain = domain)
                showCreateTask = false
            },
        )
    }
    if (showCreateVenture) {
        CreateVentureDialog(
            onDismiss = { showCreateVenture = false },
            onConfirm = { title, targetDate, description ->
                viewModel.createVenture(title = title, targetDate = targetDate, description = description)
                showCreateVenture = false
            },
        )
    }
}

@Composable
private fun CreateOccupancyDialog(
    date: LocalDate,
    onDismiss: () -> Unit,
    onConfirm: (type: String, start: String?, end: String?, wholeDay: Boolean, label: String) -> Unit,
) {
    val types = listOf(
        "meeting" to "会议",
        "leave" to "请假",
        "travel" to "出行",
        "appointment" to "预约",
    )
    var selectedType by remember { mutableStateOf("meeting") }
    var wholeDay by remember { mutableStateOf(false) }
    var start by remember { mutableStateOf("14:00") }
    var end by remember { mutableStateOf("15:00") }
    var label by remember { mutableStateOf("") }

    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text("钉住临时占用 · $date") },
        text = {
            Column(verticalArrangement = Arrangement.spacedBy(10.dp)) {
                Row(
                    modifier = Modifier
                        .fillMaxWidth()
                        .horizontalScroll(rememberScrollState()),
                    horizontalArrangement = Arrangement.spacedBy(6.dp),
                ) {
                    types.forEach { (key, title) ->
                        FilterChip(
                            selected = selectedType == key,
                            onClick = { selectedType = key },
                            label = { Text(title) },
                        )
                    }
                }
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    verticalAlignment = Alignment.CenterVertically,
                    horizontalArrangement = Arrangement.SpaceBetween,
                ) {
                    Text("全天占用", style = MaterialTheme.typography.bodyMedium)
                    Switch(checked = wholeDay, onCheckedChange = { wholeDay = it })
                }
                if (!wholeDay) {
                    Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                        OutlinedTextField(
                            value = start,
                            onValueChange = { start = it },
                            label = { Text("开始 HH:MM") },
                            singleLine = true,
                            modifier = Modifier.weight(1f),
                        )
                        OutlinedTextField(
                            value = end,
                            onValueChange = { end = it },
                            label = { Text("结束 HH:MM") },
                            singleLine = true,
                            modifier = Modifier.weight(1f),
                        )
                    }
                }
                OutlinedTextField(
                    value = label,
                    onValueChange = { label = it },
                    label = { Text("说明（如：产品评审、看牙）") },
                    singleLine = true,
                    modifier = Modifier.fillMaxWidth(),
                )
            }
        },
        confirmButton = {
            FilledTonalButton(
                onClick = {
                    val defaultLabel = types.firstOrNull { it.first == selectedType }?.second ?: "占用"
                    onConfirm(
                        selectedType,
                        if (wholeDay) null else start.trim(),
                        if (wholeDay) null else end.trim(),
                        wholeDay,
                        label.trim().ifBlank { defaultLabel },
                    )
                },
                enabled = wholeDay || (start.isNotBlank() && end.isNotBlank()),
            ) { Text("钉住") }
        },
        dismissButton = { TextButton(onClick = onDismiss) { Text("取消") } },
    )
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
