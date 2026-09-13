package com.sailzen.app.feature.money

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ExperimentalLayoutApi
import androidx.compose.foundation.layout.FlowRow
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.DatePicker
import androidx.compose.material3.DatePickerDialog
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.FilterChip
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.SegmentedButton
import androidx.compose.material3.SegmentedButtonDefaults
import androidx.compose.material3.SingleChoiceSegmentedButtonRow
import androidx.compose.material3.SnackbarHost
import androidx.compose.material3.SnackbarHostState
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
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.unit.dp
import androidx.lifecycle.viewmodel.compose.viewModel
import com.sailzen.app.core.network.dto.AccountDto
import com.sailzen.app.core.network.dto.TransactionDto
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

/**
 * 快速记账页：
 * 顶部类型切换 + 渠道（物理账户）选择 + 金额/描述/日期 + 「记一笔」；
 * 下方为最近交易列表（服务端按 htime desc 返回），点击行弹编辑对话框，删除需二次确认。
 */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun MoneyScreen(
    onOpenSettings: () -> Unit,
    viewModel: MoneyViewModel = viewModel(),
) {
    val state by viewModel.uiState.collectAsState()
    val snackbarHostState = remember { SnackbarHostState() }

    LaunchedEffect(state.message) {
        val msg = state.message ?: return@LaunchedEffect
        snackbarHostState.showSnackbar(msg)
        viewModel.dismissMessage()
    }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("记账") },
                actions = {
                    IconButton(onClick = { viewModel.refresh() }) {
                        Icon(Icons.Filled.Refresh, contentDescription = "刷新")
                    }
                },
            )
        },
        snackbarHost = { SnackbarHost(snackbarHostState) },
    ) { padding ->
        LazyColumn(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding),
            contentPadding = PaddingValues(16.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            if (!state.serverConfigured) {
                item { UnconfiguredBanner(onOpenSettings) }
            }

            item {
                Card(modifier = Modifier.fillMaxWidth()) {
                    Column(
                        modifier = Modifier.padding(16.dp),
                        verticalArrangement = Arrangement.spacedBy(12.dp),
                    ) {
                        Text("快速记账", style = MaterialTheme.typography.titleMedium)
                        TxnFormFields(
                            form = state.form,
                            accounts = MoneyViewModel.physicalAccounts(state.accounts),
                            onFormChange = viewModel::setForm,
                        )
                        Button(
                            onClick = { viewModel.submit() },
                            enabled = !state.submitting,
                            modifier = Modifier.fillMaxWidth(),
                        ) {
                            Text(if (state.submitting) "提交中…" else "记一笔")
                        }
                    }
                }
            }

            item {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Text("最近交易", style = MaterialTheme.typography.titleMedium, modifier = Modifier.weight(1f))
                    if (state.transactions.size >= MoneyViewModel.TRANSACTION_LIMIT) {
                        Text(
                            "仅显示最近 ${MoneyViewModel.TRANSACTION_LIMIT} 条",
                            style = MaterialTheme.typography.bodySmall,
                            color = Color.Gray,
                        )
                    }
                }
            }

            if (state.transactions.isEmpty() && !state.loading) {
                item {
                    Text("暂无记录", style = MaterialTheme.typography.bodyMedium, color = Color.Gray)
                }
            }

            items(state.transactions, key = { it.id }) { txn ->
                TxnRow(
                    txn = txn,
                    accounts = state.accounts,
                    onClick = { viewModel.openEdit(txn) },
                )
            }

            if (state.loading) {
                item {
                    CircularProgressIndicator(modifier = Modifier.padding(16.dp))
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
    state.confirmDelete?.let {
        AlertDialog(
            onDismissRequest = viewModel::dismissDelete,
            title = { Text("删除交易") },
            text = { Text("确定删除这条交易吗？该操作不可撤销。") },
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
}

@Composable
private fun UnconfiguredBanner(onOpenSettings: () -> Unit) {
    Card(colors = CardDefaults.cardColors(containerColor = Color(0xFFFFF3E0))) {
        Row(
            modifier = Modifier.padding(12.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Text(
                "未配置服务器，无法记账",
                modifier = Modifier.weight(1f),
                color = Color(0xFFE65100),
                style = MaterialTheme.typography.bodyMedium,
            )
            TextButton(onClick = onOpenSettings) { Text("去设置") }
        }
    }
}

// ------------------------------------------------------------------
// 表单（录入卡与编辑对话框共用）
// ------------------------------------------------------------------

@Composable
private fun TxnFormFields(
    form: MoneyViewModel.TxnForm,
    accounts: List<AccountDto>,
    onFormChange: (MoneyViewModel.TxnForm) -> Unit,
) {
    Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
        TypeSegmentedRow(current = form.type) { newType ->
            onFormChange(MoneyViewModel.switchType(form, newType))
        }

        when (form.type) {
            MoneyViewModel.TxnType.EXPENSE -> AccountChips(
                label = "账户",
                accounts = accounts,
                selectedId = form.fromAccId,
                onSelect = { onFormChange(form.copy(fromAccId = it)) },
            )
            MoneyViewModel.TxnType.INCOME -> AccountChips(
                label = "账户",
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
            singleLine = true,
            keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Decimal),
            modifier = Modifier.fillMaxWidth(),
        )
        OutlinedTextField(
            value = form.description,
            onValueChange = { v -> onFormChange(form.copy(description = v)) },
            label = { Text("描述（可选）") },
            singleLine = true,
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
        Text(label, style = MaterialTheme.typography.bodySmall, color = Color.Gray)
        if (accounts.isEmpty()) {
            Text("暂无账户，请先在网页端创建", style = MaterialTheme.typography.bodySmall, color = Color.Gray)
        } else {
            FlowRow(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
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
    val dateText = remember(htimeSec) {
        SimpleDateFormat("yyyy-MM-dd", Locale.getDefault()).format(Date(htimeSec * 1000))
    }
    OutlinedButton(onClick = { showPicker = true }, modifier = Modifier.fillMaxWidth()) {
        Text("日期：$dateText")
    }
    if (showPicker) {
        val pickerState = rememberDatePickerState(initialSelectedDateMillis = htimeSec * 1000)
        DatePickerDialog(
            onDismissRequest = { showPicker = false },
            confirmButton = {
                TextButton(onClick = {
                    pickerState.selectedDateMillis?.let { onDate(MoneyViewModel.localMidnightSec(it)) }
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
// 交易列表
// ------------------------------------------------------------------

@Composable
private fun TxnRow(
    txn: TransactionDto,
    accounts: List<AccountDto>,
    onClick: () -> Unit,
) {
    val accountMap = remember(accounts) { accounts.associateBy { it.id } }
    val type = MoneyViewModel.typeOf(txn)
    val dateText = remember(txn.htime) {
        SimpleDateFormat("yyyy-MM-dd", Locale.getDefault()).format(Date(txn.htime.toLong() * 1000))
    }
    val fromName = if (txn.fromAccId == -1) "外部" else accountMap[txn.fromAccId]?.name ?: "#${txn.fromAccId}"
    val toName = if (txn.toAccId == -1) "外部" else accountMap[txn.toAccId]?.name ?: "#${txn.toAccId}"

    Card(onClick = onClick, modifier = Modifier.fillMaxWidth()) {
        Row(
            modifier = Modifier.padding(12.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Column(modifier = Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(2.dp)) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Text(
                        typeLabel(type),
                        style = MaterialTheme.typography.labelMedium,
                        color = typeColor(type),
                    )
                    Text(
                        " ${txn.value}",
                        style = MaterialTheme.typography.titleMedium,
                        fontWeight = FontWeight.Bold,
                    )
                }
                if (txn.description.isNotBlank()) {
                    Text(txn.description, style = MaterialTheme.typography.bodyMedium)
                }
                Text(
                    "$fromName → $toName",
                    style = MaterialTheme.typography.bodySmall,
                    color = Color.Gray,
                )
            }
            Text(dateText, style = MaterialTheme.typography.bodySmall, color = Color.Gray)
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
            Column(modifier = Modifier.verticalScroll(rememberScrollState())) {
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
    MoneyViewModel.TxnType.EXPENSE -> Color(0xFFE53935)
    MoneyViewModel.TxnType.INCOME -> Color(0xFF43A047)
    MoneyViewModel.TxnType.TRANSFER -> Color(0xFF1E88E5)
}
