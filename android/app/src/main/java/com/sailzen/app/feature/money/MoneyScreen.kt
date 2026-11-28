package com.sailzen.app.feature.money

import android.app.Application
import android.net.Uri
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.PickVisualMediaRequest
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ExperimentalLayoutApi
import androidx.compose.foundation.layout.FlowRow
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.WindowInsets
import androidx.compose.foundation.layout.fillMaxHeight
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.KeyboardArrowLeft
import androidx.compose.material.icons.automirrored.filled.KeyboardArrowRight
import androidx.compose.material.icons.filled.CalendarToday
import androidx.compose.material.icons.filled.Close
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material.icons.filled.Schedule
import androidx.compose.material.icons.filled.Settings
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.DatePicker
import androidx.compose.material3.DatePickerDialog
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.FilterChip
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.SegmentedButton
import androidx.compose.material3.SegmentedButtonDefaults
import androidx.compose.material3.SingleChoiceSegmentedButtonRow
import androidx.compose.material3.SnackbarHost
import androidx.compose.material3.SnackbarHostState
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TopAppBar
import androidx.compose.material3.rememberDatePickerState
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
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.core.content.FileProvider
import androidx.lifecycle.viewmodel.compose.viewModel
import com.sailzen.app.core.network.dto.AccountDto
import com.sailzen.app.core.network.dto.TransactionDto
import com.sailzen.app.core.network.dto.TransactionStatsDto
import com.sailzen.app.feature.health.coach.ImageIntakeConfirmSheet
import java.io.File
import java.math.BigDecimal
import java.time.DayOfWeek
import java.time.LocalDate
import java.time.YearMonth
import java.time.format.DateTimeFormatter

private val ExpenseColor = Color(0xFFD32F2F)
private val IncomeColor = Color(0xFF2E7D32)
private val TransferColor = Color(0xFF1565C0)
private val DateFormatter = DateTimeFormatter.ofPattern("yyyy-MM-dd")

/**
 * 记账页：
 * 1. 月度收支统计卡（支持切换月份、查看支出/收入/结余与笔数）；
 * 2. 快速记账卡（类型切换、物理账户选择、金额/描述快捷清空、修复时区偏移的日期选择器与 ±1 天步进）；
 * 3. 最近交易列表（支持按「入账时间」或「交易日期」排序、高亮刚录入记录、分页加载、点击编辑与二次确认删除）。
 */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun MoneyScreen(
    onOpenSettings: () -> Unit,
) {
    val context = LocalContext.current
    val application = context.applicationContext as Application
    val viewModel: MoneyViewModel = viewModel(factory = MoneyViewModelFactory(application))
    val state by viewModel.uiState.collectAsState()
    val snackbarHostState = remember { SnackbarHostState() }
    var pendingCameraUri by remember { mutableStateOf<Uri?>(null) }

    val photoPickerLauncher = rememberLauncherForActivityResult(
        contract = ActivityResultContracts.PickVisualMedia(),
    ) { uri: Uri? ->
        if (uri != null) {
            viewModel.analyzeReceiptUri(uri)
        }
    }

    val takePictureLauncher = rememberLauncherForActivityResult(
        contract = ActivityResultContracts.TakePicture(),
    ) { success: Boolean ->
        val uri = pendingCameraUri
        pendingCameraUri = null
        if (success && uri != null) {
            viewModel.analyzeReceiptUri(uri)
        }
    }

    fun launchGallery() {
        photoPickerLauncher.launch(
            PickVisualMediaRequest(ActivityResultContracts.PickVisualMedia.ImageOnly),
        )
    }

    fun launchCamera() {
        val dir = File(context.cacheDir, "captures").apply { mkdirs() }
        dir.listFiles()?.sortedByDescending { it.lastModified() }?.drop(8)?.forEach { it.delete() }
        val file = File(dir, "receipt_${System.currentTimeMillis()}.jpg")
        val uri = FileProvider.getUriForFile(context, "${context.packageName}.fileprovider", file)
        pendingCameraUri = uri
        takePictureLauncher.launch(uri)
    }

    LaunchedEffect(state.message) {
        val msg = state.message ?: return@LaunchedEffect
        snackbarHostState.showSnackbar(msg)
        viewModel.dismissMessage()
    }

    Scaffold(
        contentWindowInsets = WindowInsets(0, 0, 0, 0),
        topBar = {
            TopAppBar(
                title = { Text("记账", fontWeight = FontWeight.Bold) },
                actions = {
                    IconButton(onClick = { viewModel.refresh() }, enabled = !state.loading) {
                        Icon(Icons.Filled.Refresh, contentDescription = "刷新")
                    }
                    IconButton(onClick = onOpenSettings) {
                        Icon(Icons.Filled.Settings, contentDescription = "设置")
                    }
                },
            )
        },
        snackbarHost = { SnackbarHost(snackbarHostState) },
    ) { padding ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding),
        ) {
            if (state.loading || state.statsLoading) {
                LinearProgressIndicator(
                    modifier = Modifier
                        .fillMaxWidth()
                        .height(2.dp),
                )
            }

            LazyColumn(
                modifier = Modifier.fillMaxSize(),
                contentPadding = PaddingValues(horizontal = 16.dp, vertical = 12.dp),
                verticalArrangement = Arrangement.spacedBy(12.dp),
            ) {
                if (!state.serverConfigured) {
                    item(key = "unconfigured") { UnconfiguredBanner(onOpenSettings) }
                }

                state.error?.let { errMsg ->
                    item(key = "error_banner") {
                        MoneyErrorBanner(
                            message = errMsg,
                            onRetry = { viewModel.refresh() },
                            onOpenSettings = onOpenSettings,
                            onDismiss = { viewModel.dismissError() },
                        )
                    }
                }

                // 0. SailTick 开销秘书卡片（真实零食/覆盖率、分域待回票据、一句话快记、拍小票、智能对账、清理队列）
                item(key = "sailtick_secretary") {
                    SailTickSecretaryCard(
                        overview = state.overview,
                        pendingProposals = state.pendingProposals,
                        autoProposals = state.autoProposals,
                        domainSummary = state.domainSummary,
                        ticketBusyId = state.ticketBusyId,
                        hygieneExpanded = state.hygieneExpanded,
                        hygieneTab = state.hygieneTab,
                        hygieneBusyId = state.hygieneBusyId,
                        scanningHygiene = state.scanningHygiene,
                        chatInput = state.chatInput,
                        chatBusy = state.chatBusy,
                        chatReply = state.chatReply,
                        chatHistory = state.chatHistory,
                        analyzingImage = state.analyzingImage,
                        onChatInputChange = viewModel::setChatInput,
                        onSendChat = { viewModel.sendFinanceQuickChat() },
                        onClearChatReply = viewModel::clearChatReply,
                        onReplyTicket = viewModel::replyFinanceTicket,
                        onSnoozeTicket = viewModel::snoozeFinanceTicket,
                        onPickGallery = { launchGallery() },
                        onTakePhoto = { launchCamera() },
                        onOpenReconcile = { viewModel.openReconcileDialog() },
                        onToggleHygiene = viewModel::toggleHygieneExpanded,
                        onSelectHygieneTab = viewModel::setHygieneTab,
                        onRunHygieneScan = { viewModel.runHygieneScan() },
                        onApproveProposal = viewModel::approveProposal,
                        onDismissProposal = viewModel::dismissProposal,
                        onRevertProposal = viewModel::revertProposal,
                    )
                }

                // 1. 月度收支统计卡
                item(key = "monthly_stats") {
                    MonthlyStatsCard(
                        month = state.statsMonth,
                        stats = state.monthlyStats,
                        loading = state.statsLoading,
                        error = state.statsError,
                        onPrevMonth = { viewModel.stepStatsMonth(-1) },
                        onNextMonth = { viewModel.stepStatsMonth(1) },
                        onCurrentMonth = { viewModel.selectCurrentStatsMonth() },
                        onRetry = { viewModel.selectStatsMonth(state.statsMonth) },
                    )
                }

                // 2. 快速记账卡
                item(key = "quick_entry") {
                    QuickEntryCard(
                        form = state.form,
                        accounts = MoneyViewModel.physicalAccounts(state.accounts),
                        submitting = state.submitting,
                        onFormChange = viewModel::setForm,
                        onClearInputs = viewModel::clearFormInputs,
                        onSubmit = viewModel::submit,
                    )
                }

                // 3. 最近交易标题 + 排序切换
                item(key = "recent_header") {
                    RecentTransactionsHeader(
                        totalCount = state.totalTransactions,
                        shownCount = state.transactions.size,
                        sortMode = state.sortMode,
                        onSortModeChange = viewModel::setSortMode,
                    )
                }

                if (state.transactions.isEmpty() && !state.loading) {
                    item(key = "empty_txns") {
                        Card(
                            modifier = Modifier.fillMaxWidth(),
                            colors = CardDefaults.cardColors(
                                containerColor = MaterialTheme.colorScheme.surfaceContainerLow,
                            ),
                        ) {
                            Text(
                                text = "暂无交易记录",
                                modifier = Modifier.padding(16.dp),
                                style = MaterialTheme.typography.bodyMedium,
                                color = MaterialTheme.colorScheme.onSurfaceVariant,
                            )
                        }
                    }
                }

                items(state.transactions, key = { it.id }) { txn ->
                    TxnRow(
                        txn = txn,
                        accounts = state.accounts,
                        isJustCreated = txn.id == state.lastCreatedTxnId,
                        onClick = { viewModel.openEdit(txn) },
                    )
                }

                if (state.hasMore) {
                    item(key = "load_more") {
                        OutlinedButton(
                            onClick = { viewModel.loadMore() },
                            enabled = !state.loadingMore,
                            modifier = Modifier.fillMaxWidth(),
                        ) {
                            if (state.loadingMore) {
                                CircularProgressIndicator(
                                    modifier = Modifier.size(16.dp),
                                    strokeWidth = 2.dp,
                                )
                                Spacer(Modifier.width(8.dp))
                                Text("加载中…")
                            } else {
                                Text("加载更多（已显示 ${state.transactions.size}/${state.totalTransactions}）")
                            }
                        }
                    }
                }
            }
        }
    }

    // ---------------- 编辑对话框 ----------------
    state.editForm?.let { editForm ->
        TxnEditDialog(
            editing = state.editing,
            form = editForm,
            accounts = MoneyViewModel.physicalAccounts(state.accounts),
            submitting = state.submitting,
            onFormChange = viewModel::updateEditForm,
            onSubmit = viewModel::submitEdit,
            onRequestDelete = { state.editing?.let(viewModel::requestDelete) },
            onDismiss = viewModel::closeEdit,
        )
    }

    // ---------------- 删除二次确认 ----------------
    state.confirmDelete?.let { target ->
        AlertDialog(
            onDismissRequest = viewModel::dismissDelete,
            title = { Text("删除交易") },
            text = {
                val summary = buildString {
                    append("确定删除这条")
                    append(typeLabel(MoneyViewModel.typeOf(target)))
                    append("记录（")
                    append(MoneyViewModel.formatMoney(target.value))
                    if (target.description.isNotBlank()) {
                        append(" · ")
                        append(target.description)
                    }
                    append("）吗？该操作不可撤销。")
                }
                Text(summary)
            },
            confirmButton = {
                TextButton(onClick = viewModel::confirmDelete, enabled = !state.submitting) {
                    Text("删除", color = MaterialTheme.colorScheme.error)
                }
            },
            dismissButton = {
                TextButton(onClick = viewModel::dismissDelete) { Text("取消") }
            },
        )
    }

    // ---------------- 智能余额核对对话框 ----------------
    if (state.reconcileOpen) {
        ReconcileAccountDialog(
            accounts = MoneyViewModel.physicalAccounts(state.accounts),
            selectedAccId = state.reconcileAccId,
            actualBalance = state.reconcileActualBalance,
            note = state.reconcileNote,
            forceAdjust = state.reconcileForceAdjust,
            busy = state.reconcileBusy,
            onSelectAccount = viewModel::setReconcileAccId,
            onActualBalanceChange = viewModel::setReconcileActualBalance,
            onNoteChange = viewModel::setReconcileNote,
            onForceAdjustChange = viewModel::setReconcileForceAdjust,
            onSubmit = viewModel::submitReconcile,
            onDismiss = viewModel::closeReconcileDialog,
        )
    }

    // ---------------- 小票 / 账单截图 OCR 识图确认卡 ----------------
    state.activeDraft?.let { activeDraft ->
        ImageIntakeConfirmSheet(
            draft = activeDraft,
            entries = state.draftEntries,
            summary = state.draftSummary,
            replyText = state.draftReplyText,
            previewBytes = state.previewImageBytes,
            committing = state.committingDraft,
            onDismiss = viewModel::closeDraftSheet,
            onSummaryChange = viewModel::updateDraftSummary,
            onReplyTextChange = viewModel::updateDraftReplyText,
            onToggleEntry = viewModel::toggleEntrySelected,
            onEntryKindChange = viewModel::updateEntryKind,
            onEntryTitleChange = viewModel::updateEntryTitle,
            onEntryFieldChange = viewModel::updateEntryDataField,
            onCommit = viewModel::commitActiveDraft,
            onDiscard = viewModel::discardActiveDraft,
        )
    }
}

// ------------------------------------------------------------------
// 顶部状态提示条
// ------------------------------------------------------------------

@Composable
private fun UnconfiguredBanner(onOpenSettings: () -> Unit) {
    Card(
        modifier = Modifier.fillMaxWidth(),
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.tertiaryContainer),
    ) {
        Row(
            modifier = Modifier.padding(horizontal = 14.dp, vertical = 10.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Text(
                "未配置服务器，无法记账",
                modifier = Modifier.weight(1f),
                color = MaterialTheme.colorScheme.onTertiaryContainer,
                style = MaterialTheme.typography.bodyMedium,
            )
            TextButton(onClick = onOpenSettings) { Text("去设置") }
        }
    }
}

@Composable
private fun MoneyErrorBanner(
    message: String,
    onRetry: () -> Unit,
    onOpenSettings: () -> Unit,
    onDismiss: () -> Unit,
) {
    Card(
        modifier = Modifier.fillMaxWidth(),
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.errorContainer),
    ) {
        Column(modifier = Modifier.padding(horizontal = 14.dp, vertical = 10.dp)) {
            Text(
                text = "加载异常：$message",
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onErrorContainer,
                maxLines = 2,
                overflow = TextOverflow.Ellipsis,
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

// ------------------------------------------------------------------
// 月度收支统计卡
// ------------------------------------------------------------------

@Composable
private fun MonthlyStatsCard(
    month: YearMonth,
    stats: TransactionStatsDto?,
    loading: Boolean,
    error: String?,
    onPrevMonth: () -> Unit,
    onNextMonth: () -> Unit,
    onCurrentMonth: () -> Unit,
    onRetry: () -> Unit,
) {
    val isCurrentMonth = month == YearMonth.now()
    Card(
        modifier = Modifier.fillMaxWidth(),
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surfaceContainerLow),
    ) {
        Column(
            modifier = Modifier.padding(horizontal = 14.dp, vertical = 12.dp),
            verticalArrangement = Arrangement.spacedBy(10.dp),
        ) {
            // 月份导航行
            Row(
                modifier = Modifier.fillMaxWidth(),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                IconButton(onClick = onPrevMonth, modifier = Modifier.size(32.dp)) {
                    Icon(
                        Icons.AutoMirrored.Filled.KeyboardArrowLeft,
                        contentDescription = "上个月",
                    )
                }
                Text(
                    text = "${month.year}年${month.monthValue}月",
                    style = MaterialTheme.typography.titleSmall,
                    fontWeight = FontWeight.SemiBold,
                    modifier = Modifier.padding(horizontal = 4.dp),
                )
                IconButton(onClick = onNextMonth, modifier = Modifier.size(32.dp)) {
                    Icon(
                        Icons.AutoMirrored.Filled.KeyboardArrowRight,
                        contentDescription = "下个月",
                    )
                }
                if (!isCurrentMonth) {
                    Spacer(Modifier.width(4.dp))
                    Surface(
                        shape = RoundedCornerShape(10.dp),
                        color = MaterialTheme.colorScheme.secondaryContainer,
                        modifier = Modifier
                            .clip(RoundedCornerShape(10.dp))
                            .clickable(onClick = onCurrentMonth),
                    ) {
                        Text(
                            text = "本月",
                            style = MaterialTheme.typography.labelSmall,
                            color = MaterialTheme.colorScheme.onSecondaryContainer,
                            modifier = Modifier.padding(horizontal = 8.dp, vertical = 3.dp),
                        )
                    }
                }
                Spacer(Modifier.weight(1f))
                Text(
                    text = when {
                        stats != null -> "共 ${stats.totalCount} 笔"
                        loading -> "统计中…"
                        else -> "月度概览"
                    },
                    style = MaterialTheme.typography.labelMedium,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }

            if (stats != null) {
                val expenseAmount = remember(stats.expenseTotal) {
                    MoneyViewModel.parseMoneyAmount(stats.expenseTotal).max(BigDecimal.ZERO)
                }
                val incomeAmount = remember(stats.incomeTotal) {
                    MoneyViewModel.parseMoneyAmount(stats.incomeTotal).max(BigDecimal.ZERO)
                }
                val netAmount = remember(stats.netTotal) {
                    MoneyViewModel.parseMoneyAmount(stats.netTotal)
                }
                val netColor = when {
                    netAmount > BigDecimal.ZERO -> IncomeColor
                    netAmount < BigDecimal.ZERO -> ExpenseColor
                    else -> MaterialTheme.colorScheme.onSurface
                }

                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.spacedBy(8.dp),
                ) {
                    MonthlyMetricColumn(
                        label = "月支出",
                        value = MoneyViewModel.formatMoney(stats.expenseTotal),
                        subLabel = "${stats.expenseCount} 笔",
                        valueColor = ExpenseColor,
                        modifier = Modifier.weight(1f),
                    )
                    MonthlyMetricColumn(
                        label = "月收入",
                        value = MoneyViewModel.formatMoney(stats.incomeTotal),
                        subLabel = "${stats.incomeCount} 笔",
                        valueColor = IncomeColor,
                        modifier = Modifier.weight(1f),
                    )
                    MonthlyMetricColumn(
                        label = "月结余",
                        value = MoneyViewModel.formatMoney(stats.netTotal, showPlusSign = true),
                        subLabel = if (netAmount >= BigDecimal.ZERO) "净盈余" else "净超支",
                        valueColor = netColor,
                        modifier = Modifier.weight(1f),
                    )
                }

                val sum = expenseAmount + incomeAmount
                if (sum > BigDecimal.ZERO) {
                    val expenseFraction = (expenseAmount.toFloat() / sum.toFloat()).coerceIn(0f, 1f)
                    val incomeFraction = (1f - expenseFraction).coerceIn(0f, 1f)
                    Row(
                        modifier = Modifier
                            .fillMaxWidth()
                            .height(5.dp)
                            .clip(RoundedCornerShape(3.dp))
                            .background(MaterialTheme.colorScheme.surfaceContainerHighest),
                    ) {
                        if (expenseFraction > 0f) {
                            Box(
                                modifier = Modifier
                                    .fillMaxHeight()
                                    .weight(expenseFraction)
                                    .background(ExpenseColor.copy(alpha = 0.78f)),
                            )
                        }
                        if (incomeFraction > 0f) {
                            Box(
                                modifier = Modifier
                                    .fillMaxHeight()
                                    .weight(incomeFraction)
                                    .background(IncomeColor.copy(alpha = 0.78f)),
                            )
                        }
                    }
                }
            } else if (error != null) {
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    verticalAlignment = Alignment.CenterVertically,
                ) {
                    Text(
                        text = "月统计加载失败：$error",
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.error,
                        modifier = Modifier.weight(1f),
                        maxLines = 1,
                        overflow = TextOverflow.Ellipsis,
                    )
                    TextButton(onClick = onRetry) { Text("重试") }
                }
            }
        }
    }
}

@Composable
private fun MonthlyMetricColumn(
    label: String,
    value: String,
    subLabel: String,
    valueColor: Color,
    modifier: Modifier = Modifier,
) {
    Column(
        modifier = modifier,
        verticalArrangement = Arrangement.spacedBy(2.dp),
    ) {
        Text(
            text = label,
            style = MaterialTheme.typography.labelSmall,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )
        Text(
            text = value,
            style = MaterialTheme.typography.titleSmall,
            fontWeight = FontWeight.Bold,
            color = valueColor,
            maxLines = 1,
            overflow = TextOverflow.Ellipsis,
        )
        Text(
            text = subLabel,
            style = MaterialTheme.typography.labelSmall,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )
    }
}

// ------------------------------------------------------------------
// 快速记账卡 & 表单（录入卡与编辑对话框共用）
// ------------------------------------------------------------------

@Composable
private fun QuickEntryCard(
    form: MoneyViewModel.TxnForm,
    accounts: List<AccountDto>,
    submitting: Boolean,
    onFormChange: (MoneyViewModel.TxnForm) -> Unit,
    onClearInputs: () -> Unit,
    onSubmit: () -> Unit,
) {
    Card(
        modifier = Modifier.fillMaxWidth(),
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surfaceContainerLow),
    ) {
        Column(
            modifier = Modifier.padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Text(
                    "快速记账",
                    style = MaterialTheme.typography.titleMedium,
                    fontWeight = FontWeight.SemiBold,
                    modifier = Modifier.weight(1f),
                )
                if (form.value.isNotBlank() || form.description.isNotBlank()) {
                    TextButton(
                        onClick = onClearInputs,
                        contentPadding = PaddingValues(horizontal = 8.dp, vertical = 2.dp),
                    ) {
                        Text("清空输入", style = MaterialTheme.typography.labelMedium)
                    }
                }
            }
            TxnFormFields(
                form = form,
                accounts = accounts,
                onFormChange = onFormChange,
            )
            Button(
                onClick = onSubmit,
                enabled = !submitting,
                modifier = Modifier.fillMaxWidth(),
            ) {
                if (submitting) {
                    CircularProgressIndicator(
                        modifier = Modifier.size(16.dp),
                        strokeWidth = 2.dp,
                        color = MaterialTheme.colorScheme.onPrimary,
                    )
                    Spacer(Modifier.width(8.dp))
                    Text("提交中…")
                } else {
                    Text("记一笔")
                }
            }
        }
    }
}

@Composable
private fun TxnFormFields(
    form: MoneyViewModel.TxnForm,
    accounts: List<AccountDto>,
    onFormChange: (MoneyViewModel.TxnForm) -> Unit,
) {
    Column(verticalArrangement = Arrangement.spacedBy(10.dp)) {
        TypeSegmentedRow(current = form.type) { newType ->
            onFormChange(MoneyViewModel.switchType(form, newType))
        }

        when (form.type) {
            MoneyViewModel.TxnType.EXPENSE -> AccountChips(
                label = "支出账户",
                accounts = accounts,
                selectedId = form.fromAccId,
                onSelect = { onFormChange(form.copy(fromAccId = it)) },
            )
            MoneyViewModel.TxnType.INCOME -> AccountChips(
                label = "收款账户",
                accounts = accounts,
                selectedId = form.toAccId,
                onSelect = { onFormChange(form.copy(toAccId = it)) },
            )
            MoneyViewModel.TxnType.TRANSFER -> {
                AccountChips(
                    label = "转出账户",
                    accounts = accounts,
                    selectedId = form.fromAccId,
                    onSelect = { onFormChange(form.copy(fromAccId = it)) },
                )
                AccountChips(
                    label = "转入账户",
                    accounts = accounts,
                    selectedId = form.toAccId,
                    onSelect = { onFormChange(form.copy(toAccId = it)) },
                )
            }
        }

        OutlinedTextField(
            value = form.value,
            onValueChange = { v -> onFormChange(form.copy(value = v)) },
            label = { Text("金额") },
            prefix = { Text("¥") },
            singleLine = true,
            keyboardOptions = KeyboardOptions(
                keyboardType = KeyboardType.Decimal,
                imeAction = ImeAction.Next,
            ),
            trailingIcon = if (form.value.isNotEmpty()) {
                {
                    IconButton(onClick = { onFormChange(form.copy(value = "")) }) {
                        Icon(Icons.Filled.Close, contentDescription = "清空金额", modifier = Modifier.size(18.dp))
                    }
                }
            } else {
                null
            },
            modifier = Modifier.fillMaxWidth(),
        )
        OutlinedTextField(
            value = form.description,
            onValueChange = { v -> onFormChange(form.copy(description = v)) },
            label = { Text("描述（可选）") },
            singleLine = true,
            keyboardOptions = KeyboardOptions(imeAction = ImeAction.Done),
            trailingIcon = if (form.description.isNotEmpty()) {
                {
                    IconButton(onClick = { onFormChange(form.copy(description = "")) }) {
                        Icon(Icons.Filled.Close, contentDescription = "清空描述", modifier = Modifier.size(18.dp))
                    }
                }
            } else {
                null
            },
            modifier = Modifier.fillMaxWidth(),
        )
        DateField(htimeSec = form.htimeSec) { sec ->
            onFormChange(form.copy(htimeSec = sec))
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun TypeSegmentedRow(
    current: MoneyViewModel.TxnType,
    onChange: (MoneyViewModel.TxnType) -> Unit,
) {
    val types = MoneyViewModel.TxnType.entries
    SingleChoiceSegmentedButtonRow(modifier = Modifier.fillMaxWidth()) {
        types.forEachIndexed { index, type ->
            SegmentedButton(
                selected = current == type,
                onClick = { onChange(type) },
                shape = SegmentedButtonDefaults.itemShape(index = index, count = types.size),
            ) {
                Text(typeLabel(type))
            }
        }
    }
}

@OptIn(ExperimentalLayoutApi::class)
@Composable
private fun AccountChips(
    label: String,
    accounts: List<AccountDto>,
    selectedId: Int,
    onSelect: (Int) -> Unit,
) {
    Column(verticalArrangement = Arrangement.spacedBy(4.dp)) {
        Text(label, style = MaterialTheme.typography.labelMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
        if (accounts.isEmpty()) {
            Text(
                "暂无账户，请先在网页端创建",
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        } else {
            FlowRow(
                horizontalArrangement = Arrangement.spacedBy(8.dp),
                verticalArrangement = Arrangement.spacedBy(2.dp),
            ) {
                accounts.forEach { acc ->
                    FilterChip(
                        selected = acc.id == selectedId,
                        onClick = { onSelect(acc.id) },
                        label = { Text(acc.name) },
                    )
                }
            }
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun DateField(htimeSec: Long, onDate: (Long) -> Unit) {
    var showPicker by remember { mutableStateOf(false) }
    val localDate = remember(htimeSec) { MoneyViewModel.localEpochSecToDate(htimeSec) }
    val isToday = localDate == LocalDate.now()
    val dateLabel = remember(localDate) {
        "${localDate.format(DateFormatter)} · ${weekdayShort(localDate.dayOfWeek)}"
    }

    Row(
        modifier = Modifier.fillMaxWidth(),
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.spacedBy(4.dp),
    ) {
        IconButton(
            onClick = { onDate(MoneyViewModel.stepDateByDays(htimeSec, -1)) },
            modifier = Modifier.size(36.dp),
        ) {
            Icon(Icons.AutoMirrored.Filled.KeyboardArrowLeft, contentDescription = "前一天")
        }
        OutlinedButton(
            onClick = { showPicker = true },
            modifier = Modifier.weight(1f),
            contentPadding = PaddingValues(horizontal = 12.dp, vertical = 8.dp),
        ) {
            Icon(
                Icons.Filled.CalendarToday,
                contentDescription = null,
                modifier = Modifier.size(16.dp),
            )
            Spacer(Modifier.width(8.dp))
            Text(dateLabel, maxLines = 1, overflow = TextOverflow.Ellipsis)
        }
        IconButton(
            onClick = { onDate(MoneyViewModel.stepDateByDays(htimeSec, 1)) },
            modifier = Modifier.size(36.dp),
        ) {
            Icon(Icons.AutoMirrored.Filled.KeyboardArrowRight, contentDescription = "后一天")
        }
        if (!isToday) {
            TextButton(
                onClick = { onDate(MoneyViewModel.todayStartSec()) },
                contentPadding = PaddingValues(horizontal = 6.dp, vertical = 4.dp),
            ) {
                Text("今天", style = MaterialTheme.typography.labelMedium)
            }
        }
    }

    if (showPicker) {
        // 显式转为 UTC 零点毫秒传入 Material3 DatePicker，消除再次打开日期偏移一天的时区问题
        val initialUtcMillis = remember(htimeSec) {
            MoneyViewModel.localEpochSecToPickerUtcMillis(htimeSec)
        }
        val pickerState = rememberDatePickerState(
            initialSelectedDateMillis = initialUtcMillis,
            initialDisplayedMonthMillis = initialUtcMillis,
        )
        DatePickerDialog(
            onDismissRequest = { showPicker = false },
            confirmButton = {
                TextButton(onClick = {
                    pickerState.selectedDateMillis?.let { utcMillis ->
                        onDate(MoneyViewModel.pickerUtcMillisToLocalMidnightSec(utcMillis))
                    }
                    showPicker = false
                }) { Text("确定") }
            },
            dismissButton = {
                TextButton(onClick = { showPicker = false }) { Text("取消") }
            },
        ) {
            DatePicker(state = pickerState)
        }
    }
}

// ------------------------------------------------------------------
// 最近交易标题与排序切换
// ------------------------------------------------------------------

@Composable
private fun RecentTransactionsHeader(
    totalCount: Int,
    shownCount: Int,
    sortMode: MoneyViewModel.TransactionSortMode,
    onSortModeChange: (MoneyViewModel.TransactionSortMode) -> Unit,
) {
    Column(verticalArrangement = Arrangement.spacedBy(6.dp)) {
        Row(
            modifier = Modifier.fillMaxWidth(),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Text(
                "最近交易",
                style = MaterialTheme.typography.titleMedium,
                fontWeight = FontWeight.SemiBold,
                modifier = Modifier.weight(1f),
            )
            if (totalCount > 0) {
                Text(
                    "显示 $shownCount / 共 $totalCount 笔",
                    style = MaterialTheme.typography.labelMedium,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
        }
        Row(
            modifier = Modifier.fillMaxWidth(),
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.spacedBy(8.dp),
        ) {
            MoneyViewModel.TransactionSortMode.entries.forEach { mode ->
                val selected = sortMode == mode
                FilterChip(
                    selected = selected,
                    onClick = { onSortModeChange(mode) },
                    label = { Text(mode.label, style = MaterialTheme.typography.labelMedium) },
                    leadingIcon = {
                        Icon(
                            imageVector = when (mode) {
                                MoneyViewModel.TransactionSortMode.ENTRY_TIME -> Icons.Filled.Schedule
                                MoneyViewModel.TransactionSortMode.TXN_DATE -> Icons.Filled.CalendarToday
                            },
                            contentDescription = null,
                            modifier = Modifier.size(16.dp),
                        )
                    },
                )
            }
        }
    }
}

// ------------------------------------------------------------------
// 交易列表行
// ------------------------------------------------------------------

@Composable
private fun TxnRow(
    txn: TransactionDto,
    accounts: List<AccountDto>,
    isJustCreated: Boolean,
    onClick: () -> Unit,
) {
    val accountMap = remember(accounts) { accounts.associateBy { it.id } }
    val type = MoneyViewModel.typeOf(txn)
    val txnDateText = remember(txn.htime) {
        MoneyViewModel.localEpochSecToDate(txn.htime.toLong()).format(DateFormatter)
    }
    val entryTimeText = remember(txn.ctime) {
        MoneyViewModel.formatEntryTime(txn.ctime)
    }
    val fromName = if (txn.fromAccId == -1) "外部" else accountMap[txn.fromAccId]?.name ?: "#${txn.fromAccId}"
    val toName = if (txn.toAccId == -1) "外部" else accountMap[txn.toAccId]?.name ?: "#${txn.toAccId}"
    val accountFlowText = when (type) {
        MoneyViewModel.TxnType.EXPENSE -> fromName
        MoneyViewModel.TxnType.INCOME -> toName
        MoneyViewModel.TxnType.TRANSFER -> "$fromName → $toName"
    }
    val signedAmount = remember(txn.value, type) {
        val formatted = MoneyViewModel.formatMoney(txn.value)
        when (type) {
            MoneyViewModel.TxnType.EXPENSE -> "-$formatted"
            MoneyViewModel.TxnType.INCOME -> "+$formatted"
            MoneyViewModel.TxnType.TRANSFER -> formatted
        }
    }

    val containerColor = if (isJustCreated) {
        MaterialTheme.colorScheme.primaryContainer.copy(alpha = 0.45f)
    } else {
        MaterialTheme.colorScheme.surfaceContainerLow
    }
    val border = if (isJustCreated) {
        BorderStroke(1.dp, MaterialTheme.colorScheme.primary.copy(alpha = 0.6f))
    } else {
        null
    }

    Card(
        onClick = onClick,
        modifier = Modifier.fillMaxWidth(),
        colors = CardDefaults.cardColors(containerColor = containerColor),
        border = border,
    ) {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(horizontal = 14.dp, vertical = 12.dp),
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            Column(
                modifier = Modifier.weight(1f),
                verticalArrangement = Arrangement.spacedBy(4.dp),
            ) {
                Row(
                    verticalAlignment = Alignment.CenterVertically,
                    horizontalArrangement = Arrangement.spacedBy(6.dp),
                ) {
                    Surface(
                        shape = RoundedCornerShape(6.dp),
                        color = typeColor(type).copy(alpha = 0.14f),
                    ) {
                        Text(
                            text = typeLabel(type),
                            style = MaterialTheme.typography.labelSmall,
                            fontWeight = FontWeight.Medium,
                            color = typeColor(type),
                            modifier = Modifier.padding(horizontal = 6.dp, vertical = 2.dp),
                        )
                    }
                    Text(
                        text = txn.description.ifBlank { accountFlowText },
                        style = MaterialTheme.typography.bodyMedium,
                        fontWeight = FontWeight.Medium,
                        maxLines = 1,
                        overflow = TextOverflow.Ellipsis,
                        modifier = Modifier.weight(1f, fill = false),
                    )
                    if (isJustCreated) {
                        Surface(
                            shape = RoundedCornerShape(6.dp),
                            color = MaterialTheme.colorScheme.primary,
                        ) {
                            Text(
                                text = "刚录入",
                                style = MaterialTheme.typography.labelSmall,
                                color = MaterialTheme.colorScheme.onPrimary,
                                modifier = Modifier.padding(horizontal = 6.dp, vertical = 2.dp),
                            )
                        }
                    }
                }

                val subParts = buildList {
                    if (txn.description.isNotBlank()) add(accountFlowText)
                    entryTimeText?.let { add("录入 $it") }
                }
                if (subParts.isNotEmpty()) {
                    Text(
                        text = subParts.joinToString(" · "),
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                        maxLines = 1,
                        overflow = TextOverflow.Ellipsis,
                    )
                }
            }

            Column(
                horizontalAlignment = Alignment.End,
                verticalArrangement = Arrangement.spacedBy(3.dp),
            ) {
                Text(
                    text = signedAmount,
                    style = MaterialTheme.typography.titleMedium,
                    fontWeight = FontWeight.Bold,
                    color = typeColor(type),
                )
                Text(
                    text = txnDateText,
                    style = MaterialTheme.typography.labelSmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
        }
    }
}

// ------------------------------------------------------------------
// 编辑对话框
// ------------------------------------------------------------------

@Composable
private fun TxnEditDialog(
    editing: TransactionDto?,
    form: MoneyViewModel.TxnForm,
    accounts: List<AccountDto>,
    submitting: Boolean,
    onFormChange: (MoneyViewModel.TxnForm) -> Unit,
    onSubmit: () -> Unit,
    onRequestDelete: () -> Unit,
    onDismiss: () -> Unit,
) {
    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text("编辑交易 #${editing?.id ?: ""}") },
        text = {
            Column(
                modifier = Modifier.verticalScroll(rememberScrollState()),
                verticalArrangement = Arrangement.spacedBy(8.dp),
            ) {
                editing?.ctime?.let { MoneyViewModel.formatEntryTime(it) }?.let { entryText ->
                    Text(
                        text = "入账时间：$entryText",
                        style = MaterialTheme.typography.labelSmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                    HorizontalDivider()
                }
                TxnFormFields(form = form, accounts = accounts, onFormChange = onFormChange)
            }
        },
        confirmButton = {
            TextButton(onClick = onSubmit, enabled = !submitting) { Text("更新") }
        },
        dismissButton = {
            Row {
                TextButton(onClick = onRequestDelete) {
                    Text("删除", color = MaterialTheme.colorScheme.error)
                }
                TextButton(onClick = onDismiss) { Text("取消") }
            }
        },
    )
}

// ------------------------------------------------------------------
// 展示辅助
// ------------------------------------------------------------------

private fun typeLabel(type: MoneyViewModel.TxnType): String = when (type) {
    MoneyViewModel.TxnType.EXPENSE -> "支出"
    MoneyViewModel.TxnType.INCOME -> "收入"
    MoneyViewModel.TxnType.TRANSFER -> "转账"
}

private fun typeColor(type: MoneyViewModel.TxnType): Color = when (type) {
    MoneyViewModel.TxnType.EXPENSE -> ExpenseColor
    MoneyViewModel.TxnType.INCOME -> IncomeColor
    MoneyViewModel.TxnType.TRANSFER -> TransferColor
}

private fun weekdayShort(day: DayOfWeek): String = when (day) {
    DayOfWeek.MONDAY -> "周一"
    DayOfWeek.TUESDAY -> "周二"
    DayOfWeek.WEDNESDAY -> "周三"
    DayOfWeek.THURSDAY -> "周四"
    DayOfWeek.FRIDAY -> "周五"
    DayOfWeek.SATURDAY -> "周六"
    DayOfWeek.SUNDAY -> "周日"
}
