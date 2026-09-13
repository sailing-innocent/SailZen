package com.sailzen.app.feature.money

import android.app.Application
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import com.sailzen.app.core.data.OperationResult
import com.sailzen.app.core.money.MoneyRepository
import com.sailzen.app.core.network.dto.AccountDto
import com.sailzen.app.core.network.dto.TransactionDto
import com.sailzen.app.core.network.dto.TransactionUpsertRequest
import java.util.Calendar
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch

/**
 * 快速记账页 ViewModel：账户/交易加载、录入表单、编辑与删除。
 *
 * 表单校验与请求映射抽取为 companion 纯函数，便于 JVM 单测直接覆盖；
 * [repository] 可注入 fake 子类，验证成功/失败后的 UI 状态流转。
 */
class MoneyViewModel(
    application: Application,
    private val repository: MoneyRepository = MoneyRepository.get(application),
) : AndroidViewModel(application) {

    enum class TxnType { EXPENSE, INCOME, TRANSFER }

    data class TxnForm(
        val type: TxnType = TxnType.EXPENSE,
        val fromAccId: Int = -1,
        val toAccId: Int = -1,
        val value: String = "",
        val description: String = "",
        val htimeSec: Long = todayStartSec(),
    )

    data class UiState(
        val loading: Boolean = false,
        val submitting: Boolean = false,
        val accounts: List<AccountDto> = emptyList(),
        val transactions: List<TransactionDto> = emptyList(),
        val form: TxnForm = TxnForm(),
        val editing: TransactionDto? = null,
        val editForm: TxnForm? = null,
        val confirmDelete: TransactionDto? = null,
        val message: String? = null,
        val serverConfigured: Boolean = true,
    )

    private val _uiState = MutableStateFlow(UiState())
    val uiState: StateFlow<UiState> = _uiState.asStateFlow()

    init {
        viewModelScope.launch {
            _uiState.update { it.copy(serverConfigured = repository.serverConfigured()) }
        }
        refresh()
    }

    // ------------------------------------------------------------------
    // 纯函数（单测直接覆盖）
    // ------------------------------------------------------------------

    companion object {
        const val TRANSACTION_LIMIT = 200

        /** 快速记账渠道：仅物理账户（ORM 语义 state==0；预算口袋不在本页展示）。 */
        fun physicalAccounts(accounts: List<AccountDto>): List<AccountDto> =
            accounts.filter { it.state == 0 }

        /** millis 所在日期在本地时区的零点 epoch 秒（DatePicker 只精确到日，对齐前端行为）。 */
        fun localMidnightSec(millis: Long): Long {
            val cal = Calendar.getInstance()
            cal.timeInMillis = millis
            cal.set(Calendar.HOUR_OF_DAY, 0)
            cal.set(Calendar.MINUTE, 0)
            cal.set(Calendar.SECOND, 0)
            cal.set(Calendar.MILLISECOND, 0)
            return cal.timeInMillis / 1000
        }

        fun todayStartSec(): Long = localMidnightSec(System.currentTimeMillis())

        /**
         * 交易类型推断（对齐前端 transactions_data_table.tsx 过滤逻辑）：
         * to_acc_id == -1 为支出（流向外部），from_acc_id == -1 为收入（外部流入），
         * 两侧均为有效账户为转账。
         */
        fun typeOf(txn: TransactionDto): TxnType = when {
            txn.toAccId == -1 -> TxnType.EXPENSE
            txn.fromAccId == -1 -> TxnType.INCOME
            else -> TxnType.TRANSFER
        }

        /** 切换类型并重算 from/to 语义：新类型下未使用的一侧重置为 -1。 */
        fun switchType(form: TxnForm, type: TxnType): TxnForm = when (type) {
            TxnType.EXPENSE -> form.copy(type = type, toAccId = -1)
            TxnType.INCOME -> form.copy(type = type, fromAccId = -1)
            TxnType.TRANSFER -> form.copy(type = type)
        }

        /** 表单校验：返回错误文案，null 表示通过（对齐前端 transaction_add_card.tsx）。 */
        fun validateForm(form: TxnForm): String? {
            if (form.value.isBlank() || form.value.toDoubleOrNull() == null) return "请输入有效金额"
            if (form.htimeSec <= 0) return "请选择日期"
            return when (form.type) {
                TxnType.EXPENSE ->
                    if (form.fromAccId <= 0) "请选择账户" else null
                TxnType.INCOME ->
                    if (form.toAccId <= 0) "请选择账户" else null
                TxnType.TRANSFER -> when {
                    form.fromAccId <= 0 || form.toAccId <= 0 -> "请选择转出和转入账户"
                    form.fromAccId == form.toAccId -> "转出与转入账户不能相同"
                    else -> null
                }
            }
        }

        /**
         * 表单 → 创建/更新请求体：
         * EXPENSE 收款方为外部(-1)，INCOME 付款方为外部(-1)，TRANSFER 两侧均为有效账户；
         * tags 恒为空串，budget_id 不传。
         */
        fun toRequest(form: TxnForm): TransactionUpsertRequest = TransactionUpsertRequest(
            fromAccId = if (form.type == TxnType.INCOME) -1 else form.fromAccId,
            toAccId = if (form.type == TxnType.EXPENSE) -1 else form.toAccId,
            value = form.value.trim(),
            description = form.description.trim(),
            tags = "",
            budgetId = null,
            htime = form.htimeSec.toDouble(),
        )

        /** 编辑回显：由交易记录反推表单。 */
        fun deriveEditForm(txn: TransactionDto): TxnForm = TxnForm(
            type = typeOf(txn),
            fromAccId = txn.fromAccId,
            toAccId = txn.toAccId,
            value = txn.value,
            description = txn.description,
            htimeSec = txn.htime.toLong(),
        )
    }

    // ------------------------------------------------------------------
    // 数据加载
    // ------------------------------------------------------------------

    /** 并发拉取账户 + 最近交易；任一失败保留旧数据并提示。 */
    fun refresh() {
        viewModelScope.launch {
            _uiState.update { it.copy(loading = true) }
            val accountsResult = repository.listAccounts()
            val transactionsResult = repository.listTransactions(TRANSACTION_LIMIT)
            val failureMsg = listOfNotNull(
                (accountsResult as? OperationResult.Failure)?.message,
                (transactionsResult as? OperationResult.Failure)?.message,
            ).firstOrNull()
            _uiState.update {
                it.copy(
                    loading = false,
                    accounts = accountsResult.getOrNull() ?: it.accounts,
                    transactions = transactionsResult.getOrNull() ?: it.transactions,
                    message = it.message ?: failureMsg?.let { msg -> "加载失败：$msg" },
                )
            }
        }
    }

    fun dismissMessage() = _uiState.update { it.copy(message = null) }

    // ------------------------------------------------------------------
    // 录入表单
    // ------------------------------------------------------------------

    /** 切换类型时重算 from/to 语义，重置新类型下未使用的一侧为 -1。 */
    fun setType(type: TxnType) = _uiState.update { it.copy(form = switchType(it.form, type)) }

    /** 表单整体回写（录入卡 TxnFormFields 聚合入口）。 */
    fun setForm(form: TxnForm) = _uiState.update { it.copy(form = form) }

    /** 单账户选择：支出=转出账户，收入=转入账户（转账模式请用 setFromAcc/setToAcc）。 */
    fun selectAccount(accountId: Int) = _uiState.update {
        when (it.form.type) {
            TxnType.EXPENSE -> it.copy(form = it.form.copy(fromAccId = accountId))
            TxnType.INCOME -> it.copy(form = it.form.copy(toAccId = accountId))
            TxnType.TRANSFER -> it
        }
    }

    fun setFromAcc(accountId: Int) = _uiState.update { it.copy(form = it.form.copy(fromAccId = accountId)) }
    fun setToAcc(accountId: Int) = _uiState.update { it.copy(form = it.form.copy(toAccId = accountId)) }
    fun setValue(value: String) = _uiState.update { it.copy(form = it.form.copy(value = value)) }
    fun setDescription(description: String) = _uiState.update { it.copy(form = it.form.copy(description = description)) }
    fun setDate(htimeSec: Long) = _uiState.update { it.copy(form = it.form.copy(htimeSec = htimeSec)) }

    /** 提交创建：校验 → create → 成功后保留表单（对齐前端"继续添加"）并刷新列表。 */
    fun submit() {
        val form = _uiState.value.form
        validateForm(form)?.let { msg ->
            _uiState.update { it.copy(message = msg) }
            return
        }
        if (_uiState.value.submitting) return
        viewModelScope.launch {
            _uiState.update { it.copy(submitting = true) }
            when (val result = repository.create(toRequest(form))) {
                is OperationResult.Success -> {
                    refresh()
                    _uiState.update { it.copy(submitting = false, message = "已记一笔") }
                }
                is OperationResult.Failure ->
                    _uiState.update { it.copy(submitting = false, message = "记账失败：${result.message}") }
            }
        }
    }

    // ------------------------------------------------------------------
    // 编辑 / 删除
    // ------------------------------------------------------------------

    fun openEdit(txn: TransactionDto) = _uiState.update {
        it.copy(editing = txn, editForm = deriveEditForm(txn))
    }

    fun updateEditForm(form: TxnForm) = _uiState.update { it.copy(editForm = form) }

    fun closeEdit() = _uiState.update { it.copy(editing = null, editForm = null) }

    fun submitEdit() {
        val editForm = _uiState.value.editForm ?: return
        val editing = _uiState.value.editing ?: return
        validateForm(editForm)?.let { msg ->
            _uiState.update { it.copy(message = msg) }
            return
        }
        if (_uiState.value.submitting) return
        viewModelScope.launch {
            _uiState.update { it.copy(submitting = true) }
            when (val result = repository.update(editing.id, toRequest(editForm))) {
                is OperationResult.Success -> {
                    refresh()
                    _uiState.update {
                        it.copy(submitting = false, editing = null, editForm = null, message = "已更新")
                    }
                }
                is OperationResult.Failure ->
                    _uiState.update { it.copy(submitting = false, message = "更新失败：${result.message}") }
            }
        }
    }

    fun requestDelete(txn: TransactionDto) = _uiState.update { it.copy(confirmDelete = txn) }

    fun dismissDelete() = _uiState.update { it.copy(confirmDelete = null) }

    /** 二次确认后执行删除；若被删的是当前编辑对象，同步关闭编辑对话框。 */
    fun confirmDelete() {
        val txn = _uiState.value.confirmDelete ?: return
        if (_uiState.value.submitting) return
        viewModelScope.launch {
            _uiState.update { it.copy(submitting = true) }
            when (val result = repository.delete(txn.id)) {
                is OperationResult.Success -> {
                    val wasEditing = _uiState.value.editing?.id == txn.id
                    refresh()
                    _uiState.update {
                        it.copy(
                            submitting = false,
                            confirmDelete = null,
                            editing = if (wasEditing) null else it.editing,
                            editForm = if (wasEditing) null else it.editForm,
                            message = "已删除",
                        )
                    }
                }
                is OperationResult.Failure ->
                    _uiState.update {
                        it.copy(submitting = false, confirmDelete = null, message = "删除失败：${result.message}")
                    }
            }
        }
    }
}
