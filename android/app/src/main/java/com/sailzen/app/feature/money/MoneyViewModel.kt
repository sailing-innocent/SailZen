package com.sailzen.app.feature.money

import android.app.Application
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import com.sailzen.app.core.data.OperationResult
import com.sailzen.app.core.money.MoneyRepository
import com.sailzen.app.core.network.dto.AccountDto
import com.sailzen.app.core.network.dto.TransactionDto
import com.sailzen.app.core.network.dto.TransactionStatsDto
import com.sailzen.app.core.network.dto.TransactionUpsertRequest
import java.math.BigDecimal
import java.text.DecimalFormat
import java.text.DecimalFormatSymbols
import java.time.Instant
import java.time.LocalDate
import java.time.LocalDateTime
import java.time.OffsetDateTime
import java.time.YearMonth
import java.time.ZoneId
import java.time.ZoneOffset
import java.time.format.DateTimeFormatter
import java.util.Locale
import kotlinx.coroutines.Job
import kotlinx.coroutines.async
import kotlinx.coroutines.coroutineScope
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch

/**
 * 记账页 ViewModel：
 * - 月度收支统计（支持切换月份，记账/编辑/删除后自动刷新）
 * - 快速记账表单（修复 DatePicker UTC/本地时区偏移，支持 ±1 天快速步进与保留上下文连续记账）
 * - 最近交易列表（支持按「入账时间 ctime」或「交易日期 htime」排序与分页加载，高亮刚录入的记录）
 * - 编辑与二次确认删除（编辑时保留原有标签与预算关联）
 */
class MoneyViewModel(
    application: Application,
    private val repository: MoneyRepository = MoneyRepository.get(application),
) : AndroidViewModel(application) {

    enum class TxnType { EXPENSE, INCOME, TRANSFER }

    enum class TransactionSortMode(val sortBy: String, val label: String) {
        ENTRY_TIME("ctime", "按入账时间"),
        TXN_DATE("htime", "按交易日期"),
    }

    data class TxnForm(
        val type: TxnType = TxnType.EXPENSE,
        val fromAccId: Int = -1,
        val toAccId: Int = -1,
        val value: String = "",
        val description: String = "",
        val htimeSec: Long = todayStartSec(),
        val tags: String = "",
        val budgetId: Int? = null,
    )

    data class UiState(
        val loading: Boolean = false,
        val loadingMore: Boolean = false,
        val statsLoading: Boolean = false,
        val submitting: Boolean = false,
        val accounts: List<AccountDto> = emptyList(),
        val transactions: List<TransactionDto> = emptyList(),
        val totalTransactions: Int = 0,
        val currentPage: Int = 1,
        val hasMore: Boolean = false,
        val sortMode: TransactionSortMode = TransactionSortMode.ENTRY_TIME,
        val statsMonth: YearMonth = YearMonth.now(),
        val monthlyStats: TransactionStatsDto? = null,
        val statsError: String? = null,
        val lastCreatedTxnId: Int? = null,
        val form: TxnForm = TxnForm(),
        val editing: TransactionDto? = null,
        val editForm: TxnForm? = null,
        val confirmDelete: TransactionDto? = null,
        val error: String? = null,
        val message: String? = null,
        val serverConfigured: Boolean = true,
    )

    private val _uiState = MutableStateFlow(UiState())
    val uiState: StateFlow<UiState> = _uiState.asStateFlow()

    private var refreshJob: Job? = null
    private var listJob: Job? = null
    private var statsJob: Job? = null

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
        const val PAGE_SIZE = 50

        private val NUMBER_PATTERN = Regex("""[+-]?\d+(?:\.\d+)?""")
        private val TIME_HM_FORMATTER = DateTimeFormatter.ofPattern("HH:mm")
        private val MONTH_DAY_HM_FORMATTER = DateTimeFormatter.ofPattern("MM-dd HH:mm")
        private val FULL_DATE_HM_FORMATTER = DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm")

        /** 快速记账渠道：仅物理账户（ORM 语义 state==0；预算口袋不在本页展示）。 */
        fun physicalAccounts(accounts: List<AccountDto>): List<AccountDto> =
            accounts.filter { it.state == 0 }

        /** 将 epoch 秒转换为指定时区的 LocalDate。 */
        fun localEpochSecToDate(
            epochSec: Long,
            zone: ZoneId = ZoneId.systemDefault(),
        ): LocalDate = Instant.ofEpochSecond(epochSec).atZone(zone).toLocalDate()

        /** 将 LocalDate 转换为指定时区零点 epoch 秒。 */
        fun localDateToMidnightSec(
            date: LocalDate,
            zone: ZoneId = ZoneId.systemDefault(),
        ): Long = date.atStartOfDay(zone).toEpochSecond()

        /** millis 所在日期在本地时区的零点 epoch 秒。 */
        fun localMidnightSec(
            millis: Long,
            zone: ZoneId = ZoneId.systemDefault(),
        ): Long = localDateToMidnightSec(
            Instant.ofEpochMilli(millis).atZone(zone).toLocalDate(),
            zone,
        )

        fun todayStartSec(zone: ZoneId = ZoneId.systemDefault()): Long =
            localDateToMidnightSec(LocalDate.now(zone), zone)

        /**
         * 本地日期 epoch 秒 → Material3 DatePicker 所需的 UTC 零点毫秒。
         *
         * Material3 DatePicker 以 UTC 日历日解读 initialSelectedDateMillis / selectedDateMillis；
         * 直接传本地零点（如 UTC+8 的 2026-10-05 00:00 = 2026-10-04T16:00Z）会导致再次打开时
         * 日期回退一天。必须先取本地 LocalDate 再映射为该日的 UTC 00:00:00Z。
         */
        fun localEpochSecToPickerUtcMillis(
            epochSec: Long,
            zone: ZoneId = ZoneId.systemDefault(),
        ): Long = localEpochSecToDate(epochSec, zone)
            .atStartOfDay(ZoneOffset.UTC)
            .toInstant()
            .toEpochMilli()

        /**
         * Material3 DatePicker 返回的 UTC 零点毫秒 → 本地零点 epoch 秒。
         *
         * 无论设备处于正时区（如 UTC+8）还是负时区（如 UTC-5），均先按 UTC 提取用户点选的
         * 年月日，再转为本地时区当天 00:00:00 的 epoch 秒，彻底消除跨时区偏移。
         */
        fun pickerUtcMillisToLocalMidnightSec(
            utcMillis: Long,
            zone: ZoneId = ZoneId.systemDefault(),
        ): Long {
            val pickedDate = Instant.ofEpochMilli(utcMillis).atZone(ZoneOffset.UTC).toLocalDate()
            return localDateToMidnightSec(pickedDate, zone)
        }

        /** 按自然日步进日期（DST 安全），返回目标日期本地零点 epoch 秒。 */
        fun stepDateByDays(
            epochSec: Long,
            deltaDays: Long,
            zone: ZoneId = ZoneId.systemDefault(),
        ): Long = localDateToMidnightSec(
            localEpochSecToDate(epochSec, zone).plusDays(deltaDays),
            zone,
        )

        /** 计算指定自然月在本地时区的 [月初 00:00:00, 月末 23:59:59] epoch 秒范围。 */
        fun monthRangeEpochSec(
            month: YearMonth,
            zone: ZoneId = ZoneId.systemDefault(),
        ): Pair<Double, Double> {
            val start = month.atDay(1).atStartOfDay(zone).toEpochSecond().toDouble()
            val end = month.atEndOfMonth().atTime(23, 59, 59).atZone(zone).toEpochSecond().toDouble()
            return start to end
        }

        /** 解析后端返回的金额字符串（兼容 "15053.37 CNY"、"-12.5"、"0.0" 等格式）。 */
        fun parseMoneyAmount(raw: String): BigDecimal {
            val match = NUMBER_PATTERN.find(raw.trim()) ?: return BigDecimal.ZERO
            return match.value.toBigDecimalOrNull() ?: BigDecimal.ZERO
        }

        /** 格式化金额为人类可读的人民币展示文本（如 ¥15,053.37、+¥4,653.63、-¥120.00）。 */
        fun formatMoney(raw: String, showPlusSign: Boolean = false): String {
            val amount = parseMoneyAmount(raw)
            val formatter = DecimalFormat("#,##0.00", DecimalFormatSymbols(Locale.US))
            val absStr = formatter.format(amount.abs())
            return when {
                amount < BigDecimal.ZERO -> "-¥$absStr"
                amount > BigDecimal.ZERO && showPlusSign -> "+¥$absStr"
                else -> "¥$absStr"
            }
        }

        /** 将服务端返回的 ISO ctime 字符串格式化为易读入账时间（今天/昨天/月日 时分）。 */
        fun formatEntryTime(
            ctime: String?,
            now: LocalDateTime = LocalDateTime.now(),
        ): String? {
            val raw = ctime?.trim()?.takeIf { it.isNotEmpty() } ?: return null
            val parsed = runCatching { LocalDateTime.parse(raw) }.getOrNull()
                ?: runCatching { OffsetDateTime.parse(raw).toLocalDateTime() }.getOrNull()
                ?: return null
            val today = now.toLocalDate()
            val date = parsed.toLocalDate()
            return when {
                date == today -> "今天 ${parsed.format(TIME_HM_FORMATTER)}"
                date == today.minusDays(1) -> "昨天 ${parsed.format(TIME_HM_FORMATTER)}"
                date.year == today.year -> parsed.format(MONTH_DAY_HM_FORMATTER)
                else -> parsed.format(FULL_DATE_HM_FORMATTER)
            }
        }

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
            val numeric = form.value.trim().toDoubleOrNull()
            if (form.value.isBlank() || numeric == null || !numeric.isFinite() || numeric <= 0.0) {
                return "请输入有效金额"
            }
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
         * 新建默认 tags=""、budgetId=null；编辑时保留原有 tags 与 budgetId。
         */
        fun toRequest(form: TxnForm): TransactionUpsertRequest = TransactionUpsertRequest(
            fromAccId = if (form.type == TxnType.INCOME) -1 else form.fromAccId,
            toAccId = if (form.type == TxnType.EXPENSE) -1 else form.toAccId,
            value = form.value.trim(),
            description = form.description.trim(),
            tags = form.tags,
            budgetId = form.budgetId,
            htime = form.htimeSec.toDouble(),
        )

        /** 编辑回显：由交易记录反推表单（保留原有 tags 与 budgetId）。 */
        fun deriveEditForm(txn: TransactionDto): TxnForm = TxnForm(
            type = typeOf(txn),
            fromAccId = txn.fromAccId,
            toAccId = txn.toAccId,
            value = txn.value,
            description = txn.description,
            htimeSec = txn.htime.toLong(),
            tags = txn.tags,
            budgetId = txn.budgetId,
        )
    }

    // ------------------------------------------------------------------
    // 数据加载
    // ------------------------------------------------------------------

    /** 并发拉取账户 + 最近交易（按当前排序）+ 当前统计月汇总；失败保留旧数据并给出非阻塞提示。 */
    fun refresh() {
        refreshJob?.cancel()
        listJob?.cancel()
        statsJob?.cancel()
        val sortMode = _uiState.value.sortMode
        val statsMonth = _uiState.value.statsMonth
        val (fromTime, toTime) = monthRangeEpochSec(statsMonth)
        refreshJob = viewModelScope.launch {
            _uiState.update { it.copy(loading = true, statsLoading = true) }
            val configured = repository.serverConfigured()
            val (accountsResult, pageResult, statsResult) = coroutineScope {
                val accDeferred = async { repository.listAccounts() }
                val txnDeferred = async {
                    repository.listTransactionsPaginated(
                        page = 1,
                        pageSize = PAGE_SIZE,
                        sortBy = sortMode.sortBy,
                        sortOrder = "desc",
                    )
                }
                val statsDeferred = async { repository.getTransactionStats(fromTime, toTime) }
                Triple(accDeferred.await(), txnDeferred.await(), statsDeferred.await())
            }
            val failureMsg = listOfNotNull(
                (accountsResult as? OperationResult.Failure)?.message,
                (pageResult as? OperationResult.Failure)?.message,
            ).firstOrNull()
            val statsFailureMsg = (statsResult as? OperationResult.Failure)?.message
            val pageData = pageResult.getOrNull()
            _uiState.update {
                it.copy(
                    serverConfigured = configured,
                    loading = false,
                    loadingMore = false,
                    statsLoading = false,
                    accounts = accountsResult.getOrNull() ?: it.accounts,
                    transactions = pageData?.data ?: it.transactions,
                    totalTransactions = pageData?.total ?: it.totalTransactions,
                    currentPage = pageData?.page ?: it.currentPage,
                    hasMore = pageData?.hasNext ?: it.hasMore,
                    monthlyStats = statsResult.getOrNull() ?: it.monthlyStats,
                    statsError = statsFailureMsg,
                    error = failureMsg,
                    message = it.message ?: failureMsg?.let { msg -> "加载失败：$msg" },
                )
            }
        }
    }

    /** 切换交易排序方式（按入账时间 / 按交易日期）并立即重新加载第一页。 */
    fun setSortMode(mode: TransactionSortMode) {
        if (_uiState.value.sortMode == mode && !_uiState.value.loading) return
        _uiState.update { it.copy(sortMode = mode) }
        reloadTransactionsPage1(mode)
    }

    private fun reloadTransactionsPage1(mode: TransactionSortMode) {
        listJob?.cancel()
        listJob = viewModelScope.launch {
            _uiState.update { it.copy(loading = true) }
            when (
                val result = repository.listTransactionsPaginated(
                    page = 1,
                    pageSize = PAGE_SIZE,
                    sortBy = mode.sortBy,
                    sortOrder = "desc",
                )
            ) {
                is OperationResult.Success -> {
                    val page = result.data
                    _uiState.update {
                        it.copy(
                            loading = false,
                            loadingMore = false,
                            transactions = page.data,
                            totalTransactions = page.total,
                            currentPage = page.page,
                            hasMore = page.hasNext,
                            error = null,
                        )
                    }
                }
                is OperationResult.Failure -> {
                    _uiState.update {
                        it.copy(
                            loading = false,
                            error = result.message,
                            message = "加载失败：${result.message}",
                        )
                    }
                }
            }
        }
    }

    /** 加载下一页交易记录并去重追加。 */
    fun loadMore() {
        val cur = _uiState.value
        if (cur.loading || cur.loadingMore || !cur.hasMore) return
        val nextPage = cur.currentPage + 1
        val mode = cur.sortMode
        listJob = viewModelScope.launch {
            _uiState.update { it.copy(loadingMore = true) }
            when (
                val result = repository.listTransactionsPaginated(
                    page = nextPage,
                    pageSize = PAGE_SIZE,
                    sortBy = mode.sortBy,
                    sortOrder = "desc",
                )
            ) {
                is OperationResult.Success -> {
                    val page = result.data
                    _uiState.update { state ->
                        val existingIds = state.transactions.mapTo(HashSet()) { it.id }
                        val merged = state.transactions + page.data.filter { it.id !in existingIds }
                        state.copy(
                            loadingMore = false,
                            transactions = merged,
                            totalTransactions = page.total,
                            currentPage = page.page,
                            hasMore = page.hasNext,
                        )
                    }
                }
                is OperationResult.Failure -> {
                    _uiState.update {
                        it.copy(
                            loadingMore = false,
                            message = "加载更多失败：${result.message}",
                        )
                    }
                }
            }
        }
    }

    /** 切换统计月份（deltaMonths 可正可负）并拉取对应月份的收支统计。 */
    fun stepStatsMonth(deltaMonths: Long) {
        val target = _uiState.value.statsMonth.plusMonths(deltaMonths)
        selectStatsMonth(target)
    }

    /** 一键回到当前自然月的统计。 */
    fun selectCurrentStatsMonth() {
        selectStatsMonth(YearMonth.now())
    }

    fun selectStatsMonth(month: YearMonth) {
        _uiState.update { it.copy(statsMonth = month) }
        loadMonthlyStats(month)
    }

    private fun loadMonthlyStats(month: YearMonth) {
        statsJob?.cancel()
        val (fromTime, toTime) = monthRangeEpochSec(month)
        statsJob = viewModelScope.launch {
            _uiState.update { it.copy(statsLoading = true, statsError = null) }
            when (val result = repository.getTransactionStats(fromTime, toTime)) {
                is OperationResult.Success -> _uiState.update {
                    it.copy(
                        statsLoading = false,
                        monthlyStats = result.data,
                        statsError = null,
                    )
                }
                is OperationResult.Failure -> _uiState.update {
                    it.copy(
                        statsLoading = false,
                        statsError = result.message,
                    )
                }
            }
        }
    }

    fun dismissError() = _uiState.update { it.copy(error = null) }

    fun dismissMessage() = _uiState.update { it.copy(message = null) }

    // ------------------------------------------------------------------
    // 录入表单
    // ------------------------------------------------------------------

    /** 切换类型时重算 from/to 语义，重置新类型下未使用的一侧为 -1。 */
    fun setType(type: TxnType) = _uiState.update { it.copy(form = switchType(it.form, type)) }

    /** 表单整体回写（录入卡 TxnFormFields 聚合入口）。 */
    fun setForm(form: TxnForm) = _uiState.update { it.copy(form = form) }

    /** 仅清空金额与描述，保留交易类型、账户和日期，方便连续批量记账。 */
    fun clearFormInputs() = _uiState.update {
        it.copy(form = it.form.copy(value = "", description = ""))
    }

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

    /** 提交创建：校验 → create → 成功后记录刚录入 ID、保留表单（便于连续记账）并刷新列表与月统计。 */
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
                    _uiState.update {
                        it.copy(
                            submitting = false,
                            lastCreatedTxnId = result.data.id,
                            message = "已记一笔",
                        )
                    }
                    refresh()
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
                    _uiState.update {
                        it.copy(submitting = false, editing = null, editForm = null, message = "已更新")
                    }
                    refresh()
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
                    _uiState.update {
                        it.copy(
                            submitting = false,
                            confirmDelete = null,
                            editing = if (wasEditing) null else it.editing,
                            editForm = if (wasEditing) null else it.editForm,
                            lastCreatedTxnId = if (it.lastCreatedTxnId == txn.id) null else it.lastCreatedTxnId,
                            message = "已删除",
                        )
                    }
                    refresh()
                }
                is OperationResult.Failure ->
                    _uiState.update {
                        it.copy(submitting = false, confirmDelete = null, message = "删除失败：${result.message}")
                    }
            }
        }
    }
}
