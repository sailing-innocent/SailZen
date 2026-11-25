package com.sailzen.app.feature.money

import android.app.Application
import android.content.Context
import androidx.lifecycle.viewModelScope
import com.sailzen.app.core.data.OperationResult
import com.sailzen.app.core.money.MoneyRepository
import com.sailzen.app.core.network.dto.AccountDto
import com.sailzen.app.core.network.dto.AccountReconcileRequestDto
import com.sailzen.app.core.network.dto.AccountReconcileResponseDto
import com.sailzen.app.core.network.dto.BalanceCheckpointDto
import com.sailzen.app.core.network.dto.FinanceOverviewDto
import com.sailzen.app.core.network.dto.HygieneProposalDto
import com.sailzen.app.core.network.dto.HygieneScanRequestDto
import com.sailzen.app.core.network.dto.HygieneScanResultDto
import com.sailzen.app.core.network.dto.PaginatedTransactionsDto
import com.sailzen.app.core.network.dto.TransactionDeleteResponse
import com.sailzen.app.core.network.dto.TransactionDto
import com.sailzen.app.core.network.dto.TransactionStatsDto
import com.sailzen.app.core.network.dto.TransactionUpsertRequest
import com.sailzen.app.core.tick.QuickChatResult
import com.sailzen.app.core.tick.TickRepository
import java.io.File
import java.math.BigDecimal
import java.time.Instant
import java.time.LocalDate
import java.time.LocalDateTime
import java.time.YearMonth
import java.time.ZoneId
import java.time.ZoneOffset
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.cancel
import kotlinx.coroutines.delay
import kotlinx.coroutines.runBlocking
import kotlinx.coroutines.test.UnconfinedTestDispatcher
import kotlinx.coroutines.test.resetMain
import kotlinx.coroutines.test.setMain
import kotlinx.coroutines.withTimeoutOrNull
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test

/**
 * 记账页 ViewModel 语义测试（JVM，FakeApplication + FakeMoneyRepository）：
 * - DatePicker UTC ↔ 本地时区转换回归（修复再次点开回退一天问题）；
 * - 排序切换（按入账时间 ctime / 按交易日期 htime）与分页加载；
 * - 月度收支统计拉取、切月、金额与入账时间格式化；
 * - 表单校验、请求映射、编辑保留 tags/budgetId、连续记账与清空输入；
 * - create / update / delete / failure 状态流转。
 */
@OptIn(ExperimentalCoroutinesApi::class)
class MoneyViewModelTest {

    private val testDispatcher = UnconfinedTestDispatcher()
    private val vms = mutableListOf<MoneyViewModel>()

    /** 最小 Application fake（沿用 BodyDataRecordViewModelTest 模式）。 */
    private class FakeApplication : Application() {
        override fun getApplicationContext(): Context = this
        override fun getFilesDir(): File =
            File(System.getProperty("java.io.tmpdir") ?: ".", "sailzen-test-files")
    }

    private data class PaginatedCall(
        val page: Int,
        val pageSize: Int,
        val sortBy: String,
        val sortOrder: String,
    )

    private class FakeMoneyRepository(context: Context) : MoneyRepository(context) {
        var accountsResult: OperationResult<List<AccountDto>> = OperationResult.Success(emptyList())
        var paginatedHandler: (PaginatedCall) -> OperationResult<PaginatedTransactionsDto> = {
            OperationResult.Success(PaginatedTransactionsDto())
        }
        var statsHandler: (Double, Double) -> OperationResult<TransactionStatsDto> = { _, _ ->
            OperationResult.Success(TransactionStatsDto())
        }
        var createResult: OperationResult<TransactionDto> = OperationResult.Failure("未配置服务器")
        var updateResult: OperationResult<TransactionDto> = OperationResult.Failure("未配置服务器")
        var deleteResult: OperationResult<TransactionDeleteResponse> =
            OperationResult.Failure("未配置服务器")
        var overviewResult: OperationResult<FinanceOverviewDto> =
            OperationResult.Success(FinanceOverviewDto())
        var pendingProposalsResult: OperationResult<List<HygieneProposalDto>> =
            OperationResult.Success(emptyList())
        var autoProposalsResult: OperationResult<List<HygieneProposalDto>> =
            OperationResult.Success(emptyList())
        var reconcileHandler: (AccountReconcileRequestDto) -> OperationResult<AccountReconcileResponseDto> = {
            OperationResult.Failure("未配置服务器")
        }
        var hygieneScanResult: OperationResult<HygieneScanResultDto> =
            OperationResult.Success(HygieneScanResultDto())
        var approveResult: OperationResult<HygieneProposalDto> =
            OperationResult.Failure("未配置服务器")
        var dismissResult: OperationResult<HygieneProposalDto> =
            OperationResult.Failure("未配置服务器")
        var revertResult: OperationResult<HygieneProposalDto> =
            OperationResult.Failure("未配置服务器")

        val paginatedCalls = mutableListOf<PaginatedCall>()
        val statsCalls = mutableListOf<Pair<Double, Double>>()
        val createdRequests = mutableListOf<TransactionUpsertRequest>()
        val updatedRequests = mutableListOf<Pair<Int, TransactionUpsertRequest>>()
        val deletedIds = mutableListOf<Int>()
        val reconcileRequests = mutableListOf<AccountReconcileRequestDto>()
        val approvedIds = mutableListOf<Int>()
        val dismissedIds = mutableListOf<Int>()
        val revertedIds = mutableListOf<Int>()
        var configured = true

        fun setTransactions(items: List<TransactionDto>, hasNext: Boolean = false, total: Int = items.size) {
            paginatedHandler = { call ->
                OperationResult.Success(
                    PaginatedTransactionsDto(
                        data = items,
                        total = total,
                        page = call.page,
                        pageSize = call.pageSize,
                        totalPages = if (hasNext) call.page + 1 else call.page,
                        hasNext = hasNext,
                        hasPrev = call.page > 1,
                    ),
                )
            }
        }

        // override 绕过 DataStore 读：避免 VM init 协程在 DataStore 后台线程上恢复并并发
        // 触碰 Dispatchers.Main，导致跨测试的 setMain/resetMain 竞态
        override suspend fun serverConfigured() = configured

        override suspend fun listAccounts() = accountsResult

        override suspend fun listTransactionsPaginated(
            page: Int,
            pageSize: Int,
            sortBy: String,
            sortOrder: String,
        ): OperationResult<PaginatedTransactionsDto> {
            val call = PaginatedCall(page, pageSize, sortBy, sortOrder)
            paginatedCalls += call
            return paginatedHandler(call)
        }

        override suspend fun getTransactionStats(
            fromTime: Double,
            toTime: Double,
        ): OperationResult<TransactionStatsDto> {
            statsCalls += fromTime to toTime
            return statsHandler(fromTime, toTime)
        }

        override suspend fun create(req: TransactionUpsertRequest): OperationResult<TransactionDto> {
            createdRequests += req
            return createResult
        }

        override suspend fun update(id: Int, req: TransactionUpsertRequest): OperationResult<TransactionDto> {
            updatedRequests += id to req
            return updateResult
        }

        override suspend fun delete(id: Int): OperationResult<TransactionDeleteResponse> {
            deletedIds += id
            return deleteResult
        }

        override suspend fun getFinanceOverview(month: String?): OperationResult<FinanceOverviewDto> =
            overviewResult

        override suspend fun reconcileAccount(
            req: AccountReconcileRequestDto,
        ): OperationResult<AccountReconcileResponseDto> {
            reconcileRequests += req
            return reconcileHandler(req)
        }

        override suspend fun runHygieneScan(
            req: HygieneScanRequestDto,
        ): OperationResult<HygieneScanResultDto> = hygieneScanResult

        override suspend fun listHygieneProposals(
            status: String?,
            autonomyLevel: String?,
            limit: Int,
        ): OperationResult<List<HygieneProposalDto>> =
            if (autonomyLevel == "auto_applied") autoProposalsResult else pendingProposalsResult

        override suspend fun approveHygieneProposal(id: Int): OperationResult<HygieneProposalDto> {
            approvedIds += id
            return approveResult
        }

        override suspend fun dismissHygieneProposal(id: Int): OperationResult<HygieneProposalDto> {
            dismissedIds += id
            return dismissResult
        }

        override suspend fun revertHygieneProposal(id: Int): OperationResult<HygieneProposalDto> {
            revertedIds += id
            return revertResult
        }
    }

    private class FakeTickRepository(context: Context) : TickRepository(context) {
        var quickChatHandler: (String) -> Result<QuickChatResult> = {
            Result.success(QuickChatResult(reply = "ok", financeUpdated = false))
        }
        val chatInputs = mutableListOf<String>()

        override suspend fun quickChat(
            text: String,
            channel: String,
            sessionId: String,
        ): Result<QuickChatResult> {
            chatInputs += text
            return quickChatHandler(text)
        }
    }

    private fun newVm(
        repository: FakeMoneyRepository,
        tickRepository: FakeTickRepository? = null,
    ): MoneyViewModel =
        MoneyViewModel(FakeApplication(), repository, tickRepository).also(vms::add)

    private fun account(id: Int, state: Int = 0) = AccountDto(id = id, name = "账户$id", state = state)

    private fun txn(
        id: Int,
        fromAccId: Int = 1,
        toAccId: Int = -1,
        value: String = "12.5",
        description: String = "午餐",
        tags: String = "",
        budgetId: Int? = null,
        htime: Double = 1_700_000_000.0,
        ctime: String? = "2026-11-22T23:45:48",
    ) = TransactionDto(
        id = id,
        fromAccId = fromAccId,
        toAccId = toAccId,
        value = value,
        description = description,
        tags = tags,
        budgetId = budgetId,
        htime = htime,
        ctime = ctime,
    )

    private suspend fun awaitCondition(timeoutMs: Long = 3000, cond: () -> Boolean) {
        withTimeoutOrNull(timeoutMs) { while (!cond()) delay(20) }
    }

    @Before
    fun setUp() {
        Dispatchers.setMain(testDispatcher)
    }

    @After
    fun tearDown() {
        vms.forEach { it.viewModelScope.cancel() }
        vms.clear()
        testDispatcher.scheduler.runCurrent()
        Dispatchers.resetMain()
    }

    // ---------------- DatePicker 时区回归测试 ----------------

    @Test
    fun datePickerConversion_preservesExactDateInUtcPlus8_noOffByOneDay() {
        val shanghai = ZoneId.of("Asia/Shanghai")
        val targetDate = LocalDate.of(2026, 10, 5)
        val utcMillisFromPicker = targetDate.atStartOfDay(ZoneOffset.UTC).toInstant().toEpochMilli()

        // 1. 用户在 DatePicker 点选 2026-10-05 → 保存为上海时区 2026-10-05 00:00:00
        val savedSec = MoneyViewModel.pickerUtcMillisToLocalMidnightSec(utcMillisFromPicker, shanghai)
        assertEquals(targetDate, MoneyViewModel.localEpochSecToDate(savedSec, shanghai))

        // 2. 再次打开 DatePicker：转回 UTC 零点毫秒，必须是 2026-10-05T00:00:00Z，而非 2026-10-04！
        val reopenedUtcMillis = MoneyViewModel.localEpochSecToPickerUtcMillis(savedSec, shanghai)
        val reopenedUtcDate = Instant.ofEpochMilli(reopenedUtcMillis).atZone(ZoneOffset.UTC).toLocalDate()
        assertEquals(targetDate, reopenedUtcDate)
        assertEquals(utcMillisFromPicker, reopenedUtcMillis)

        // 3. 连续多次打开确认不漂移
        var sec = savedSec
        repeat(5) {
            val pickerMillis = MoneyViewModel.localEpochSecToPickerUtcMillis(sec, shanghai)
            sec = MoneyViewModel.pickerUtcMillisToLocalMidnightSec(pickerMillis, shanghai)
        }
        assertEquals(savedSec, sec)
        assertEquals(targetDate, MoneyViewModel.localEpochSecToDate(sec, shanghai))
    }

    @Test
    fun datePickerConversion_preservesExactDateInNegativeOffsetAndUtc() {
        val targetDate = LocalDate.of(2026, 10, 5)
        val utcMillis = targetDate.atStartOfDay(ZoneOffset.UTC).toInstant().toEpochMilli()

        for (zone in listOf(ZoneId.of("America/New_York"), ZoneId.of("UTC"), ZoneId.of("Pacific/Kiritimati"))) {
            val savedSec = MoneyViewModel.pickerUtcMillisToLocalMidnightSec(utcMillis, zone)
            assertEquals("zone=$zone", targetDate, MoneyViewModel.localEpochSecToDate(savedSec, zone))
            val reopened = MoneyViewModel.localEpochSecToPickerUtcMillis(savedSec, zone)
            assertEquals("zone=$zone", utcMillis, reopened)
        }
    }

    @Test
    fun stepDateByDays_stepsAcrossMonthBoundaries() {
        val shanghai = ZoneId.of("Asia/Shanghai")
        val oct31 = MoneyViewModel.localDateToMidnightSec(LocalDate.of(2026, 10, 31), shanghai)
        val nov01 = MoneyViewModel.stepDateByDays(oct31, 1, shanghai)
        val oct30 = MoneyViewModel.stepDateByDays(oct31, -1, shanghai)
        assertEquals(LocalDate.of(2026, 11, 1), MoneyViewModel.localEpochSecToDate(nov01, shanghai))
        assertEquals(LocalDate.of(2026, 10, 30), MoneyViewModel.localEpochSecToDate(oct30, shanghai))
    }

    @Test
    fun monthRangeEpochSec_coversFullLocalMonth() {
        val shanghai = ZoneId.of("Asia/Shanghai")
        val (fromSec, toSec) = MoneyViewModel.monthRangeEpochSec(YearMonth.of(2026, 10), shanghai)
        assertEquals(
            LocalDate.of(2026, 10, 1).atStartOfDay(shanghai).toEpochSecond().toDouble(),
            fromSec,
            0.0,
        )
        assertEquals(
            LocalDate.of(2026, 10, 31).atTime(23, 59, 59).atZone(shanghai).toEpochSecond().toDouble(),
            toSec,
            0.0,
        )
    }

    // ---------------- 金额与时间格式化 ----------------

    @Test
    fun formatMoney_handlesCurrencySuffixNegativesAndPlusSign() {
        assertEquals("¥15,053.37", MoneyViewModel.formatMoney("15053.37 CNY"))
        assertEquals("+¥4,653.63", MoneyViewModel.formatMoney("4653.63 CNY", showPlusSign = true))
        assertEquals("-¥120.50", MoneyViewModel.formatMoney("-120.5 CNY", showPlusSign = true))
        assertEquals("¥0.00", MoneyViewModel.formatMoney("0.0 CNY", showPlusSign = true))
        assertEquals(BigDecimal("19707.0"), MoneyViewModel.parseMoneyAmount("19707.0 CNY"))
    }

    @Test
    fun formatEntryTime_formatsRelativeAndAbsoluteDates() {
        val now = LocalDateTime.of(2026, 11, 22, 23, 50, 0)
        assertEquals("今天 23:45", MoneyViewModel.formatEntryTime("2026-11-22T23:45:48.094738", now))
        assertEquals("昨天 08:15", MoneyViewModel.formatEntryTime("2026-11-21T08:15:00", now))
        assertEquals("10-05 14:20", MoneyViewModel.formatEntryTime("2026-10-05T14:20:00", now))
        assertEquals("2025-12-31 23:59", MoneyViewModel.formatEntryTime("2025-12-31T23:59:00", now))
        assertNull(MoneyViewModel.formatEntryTime(null, now))
        assertNull(MoneyViewModel.formatEntryTime("not-a-date", now))
    }

    // ---------------- 表单校验 ----------------

    @Test
    fun validateForm_rejectsBlankZeroNegativeAndNonNumericAmount() {
        val base = MoneyViewModel.TxnForm(type = MoneyViewModel.TxnType.EXPENSE, fromAccId = 1)
        assertEquals("请输入有效金额", MoneyViewModel.validateForm(base.copy(value = "")))
        assertEquals("请输入有效金额", MoneyViewModel.validateForm(base.copy(value = "abc")))
        assertEquals("请输入有效金额", MoneyViewModel.validateForm(base.copy(value = "  ")))
        assertEquals("请输入有效金额", MoneyViewModel.validateForm(base.copy(value = "0")))
        assertEquals("请输入有效金额", MoneyViewModel.validateForm(base.copy(value = "-5")))
    }

    @Test
    fun validateForm_requiresAccountByType() {
        assertEquals(
            "请选择账户",
            MoneyViewModel.validateForm(
                MoneyViewModel.TxnForm(type = MoneyViewModel.TxnType.EXPENSE, value = "1"),
            ),
        )
        assertEquals(
            "请选择账户",
            MoneyViewModel.validateForm(
                MoneyViewModel.TxnForm(type = MoneyViewModel.TxnType.INCOME, value = "1"),
            ),
        )
        assertEquals(
            "请选择转出和转入账户",
            MoneyViewModel.validateForm(
                MoneyViewModel.TxnForm(
                    type = MoneyViewModel.TxnType.TRANSFER,
                    value = "1",
                    fromAccId = 1,
                ),
            ),
        )
        assertEquals(
            "转出与转入账户不能相同",
            MoneyViewModel.validateForm(
                MoneyViewModel.TxnForm(
                    type = MoneyViewModel.TxnType.TRANSFER,
                    value = "1",
                    fromAccId = 1,
                    toAccId = 1,
                ),
            ),
        )
        assertNull(
            MoneyViewModel.validateForm(
                MoneyViewModel.TxnForm(type = MoneyViewModel.TxnType.EXPENSE, value = "1", fromAccId = 2),
            ),
        )
    }

    // ---------------- 表单 → 请求体映射 ----------------

    @Test
    fun toRequest_expenseUsesExternalAsPayee() {
        val req = MoneyViewModel.toRequest(
            MoneyViewModel.TxnForm(
                type = MoneyViewModel.TxnType.EXPENSE,
                fromAccId = 3,
                toAccId = 9, // 支出模式下应被忽略
                value = " 12.50 ",
                description = " 午餐 ",
                htimeSec = 1_700_000_000L,
            ),
        )
        assertEquals(3, req.fromAccId)
        assertEquals(-1, req.toAccId)
        assertEquals("12.50", req.value)
        assertEquals("午餐", req.description)
        assertEquals("", req.tags)
        assertNull(req.budgetId)
        assertEquals(1_700_000_000.0, req.htime!!, 0.0)
    }

    @Test
    fun deriveEditForm_preservesExistingTagsAndBudgetId() {
        val existing = txn(id = 42, tags = "餐饮,零食", budgetId = 7)
        val form = MoneyViewModel.deriveEditForm(existing)
        val req = MoneyViewModel.toRequest(form)
        assertEquals("餐饮,零食", req.tags)
        assertEquals(7, req.budgetId)
    }

    @Test
    fun toRequest_incomeUsesExternalAsPayer() {
        val req = MoneyViewModel.toRequest(
            MoneyViewModel.TxnForm(
                type = MoneyViewModel.TxnType.INCOME,
                fromAccId = 9,
                toAccId = 2,
                value = "3000",
                htimeSec = 1_700_000_000L,
            ),
        )
        assertEquals(-1, req.fromAccId)
        assertEquals(2, req.toAccId)
    }

    @Test
    fun toRequest_transferKeepsBothAccounts() {
        val req = MoneyViewModel.toRequest(
            MoneyViewModel.TxnForm(
                type = MoneyViewModel.TxnType.TRANSFER,
                fromAccId = 1,
                toAccId = 2,
                value = "500",
                htimeSec = 1_700_000_000L,
            ),
        )
        assertEquals(1, req.fromAccId)
        assertEquals(2, req.toAccId)
    }

    // ---------------- 类型推断 / 账户过滤 / 类型切换 ----------------

    @Test
    fun typeOf_infersFromAccountIds() {
        assertEquals(MoneyViewModel.TxnType.EXPENSE, MoneyViewModel.typeOf(txn(id = 1, toAccId = -1)))
        assertEquals(MoneyViewModel.TxnType.INCOME, MoneyViewModel.typeOf(txn(id = 2, fromAccId = -1, toAccId = 1)))
        assertEquals(MoneyViewModel.TxnType.TRANSFER, MoneyViewModel.typeOf(txn(id = 3, fromAccId = 1, toAccId = 2)))
    }

    @Test
    fun physicalAccounts_filtersOutBudgetPockets() {
        val accounts = listOf(account(1, state = 0), account(2, state = 1), account(3, state = 0))
        assertEquals(listOf(1, 3), MoneyViewModel.physicalAccounts(accounts).map { it.id })
    }

    @Test
    fun switchType_resetsUnusedSide() {
        val expense = MoneyViewModel.TxnForm(type = MoneyViewModel.TxnType.EXPENSE, fromAccId = 1, toAccId = 2)
        val income = MoneyViewModel.switchType(expense, MoneyViewModel.TxnType.INCOME)
        assertEquals(-1, income.fromAccId)
        assertEquals(2, income.toAccId)
        val transfer = MoneyViewModel.switchType(income, MoneyViewModel.TxnType.TRANSFER)
        assertEquals(-1, transfer.fromAccId)
        val backToExpense = MoneyViewModel.switchType(transfer, MoneyViewModel.TxnType.EXPENSE)
        assertEquals(-1, backToExpense.toAccId)
    }

    // ---------------- 排序切换与分页加载 ----------------

    @Test
    fun sortMode_defaultsToEntryTimeAndSwitchesToTxnDate() = runBlocking {
        val repo = FakeMoneyRepository(FakeApplication())
        repo.setTransactions(listOf(txn(id = 10)))

        val vm = newVm(repo)
        awaitCondition { repo.paginatedCalls.isNotEmpty() && !vm.uiState.value.loading }

        assertEquals(MoneyViewModel.TransactionSortMode.ENTRY_TIME, vm.uiState.value.sortMode)
        assertEquals("ctime", repo.paginatedCalls.last().sortBy)
        assertEquals("desc", repo.paginatedCalls.last().sortOrder)

        vm.setSortMode(MoneyViewModel.TransactionSortMode.TXN_DATE)
        awaitCondition { repo.paginatedCalls.size >= 2 && !vm.uiState.value.loading }

        assertEquals(MoneyViewModel.TransactionSortMode.TXN_DATE, vm.uiState.value.sortMode)
        assertEquals("htime", repo.paginatedCalls.last().sortBy)
    }

    @Test
    fun loadMore_appendsNextPageAndDeduplicates() = runBlocking {
        val repo = FakeMoneyRepository(FakeApplication())
        repo.paginatedHandler = { call ->
            when (call.page) {
                1 -> OperationResult.Success(
                    PaginatedTransactionsDto(
                        data = listOf(txn(id = 3), txn(id = 2)),
                        total = 3,
                        page = 1,
                        pageSize = 2,
                        totalPages = 2,
                        hasNext = true,
                    ),
                )
                else -> OperationResult.Success(
                    PaginatedTransactionsDto(
                        data = listOf(txn(id = 2), txn(id = 1)), // 包含重复 id=2
                        total = 3,
                        page = 2,
                        pageSize = 2,
                        totalPages = 2,
                        hasNext = false,
                    ),
                )
            }
        }

        val vm = newVm(repo)
        awaitCondition { vm.uiState.value.transactions.size == 2 }
        assertTrue(vm.uiState.value.hasMore)

        vm.loadMore()
        awaitCondition { !vm.uiState.value.loadingMore && vm.uiState.value.transactions.size == 3 }

        assertEquals(listOf(3, 2, 1), vm.uiState.value.transactions.map { it.id })
        assertFalse(vm.uiState.value.hasMore)
    }

    // ---------------- 月度统计切换 ----------------

    @Test
    fun stepStatsMonth_updatesMonthAndFetchesStats() = runBlocking {
        val repo = FakeMoneyRepository(FakeApplication())
        repo.statsHandler = { _, _ ->
            OperationResult.Success(
                TransactionStatsDto(
                    totalCount = 12,
                    incomeCount = 2,
                    expenseCount = 10,
                    incomeTotal = "5000.0 CNY",
                    expenseTotal = "1234.56 CNY",
                    netTotal = "3765.44 CNY",
                ),
            )
        }

        val vm = newVm(repo)
        awaitCondition { vm.uiState.value.monthlyStats != null }
        val initialMonth = vm.uiState.value.statsMonth
        val initialCalls = repo.statsCalls.size

        vm.stepStatsMonth(-1)
        awaitCondition { repo.statsCalls.size > initialCalls && !vm.uiState.value.statsLoading }

        assertEquals(initialMonth.minusMonths(1), vm.uiState.value.statsMonth)
        assertEquals("1234.56 CNY", vm.uiState.value.monthlyStats?.expenseTotal)
    }

    // ---------------- create 流程与清空输入 ----------------

    @Test
    fun submit_success_tracksLastCreatedRefreshesAndKeepsForm() = runBlocking {
        val repo = FakeMoneyRepository(FakeApplication())
        val latest = txn(id = 9)
        repo.accountsResult = OperationResult.Success(listOf(account(1)))
        repo.setTransactions(listOf(latest))
        repo.createResult = OperationResult.Success(latest)

        val vm = newVm(repo)
        val form = MoneyViewModel.TxnForm(
            type = MoneyViewModel.TxnType.EXPENSE,
            fromAccId = 1,
            value = "12.5",
            description = "午餐",
            htimeSec = 1_700_000_000L,
        )
        vm.setForm(form)
        vm.submit()
        awaitCondition { !vm.uiState.value.submitting && vm.uiState.value.message != null }

        assertEquals(1, repo.createdRequests.size)
        assertEquals("已记一笔", vm.uiState.value.message)
        assertEquals(9, vm.uiState.value.lastCreatedTxnId)
        assertEquals(listOf(9), vm.uiState.value.transactions.map { it.id })
        // 表单保留（便于批量同账户/同日期连续录入）
        assertEquals(form, vm.uiState.value.form)

        // 一键清空仅清除金额与描述，保留账户与日期
        vm.clearFormInputs()
        assertEquals("", vm.uiState.value.form.value)
        assertEquals("", vm.uiState.value.form.description)
        assertEquals(1, vm.uiState.value.form.fromAccId)
        assertEquals(1_700_000_000L, vm.uiState.value.form.htimeSec)
    }

    @Test
    fun submit_failure_surfacesMessageAndKeepsForm() = runBlocking {
        val repo = FakeMoneyRepository(FakeApplication())
        repo.createResult = OperationResult.Failure("网络错误")

        val vm = newVm(repo)
        vm.setForm(MoneyViewModel.TxnForm(type = MoneyViewModel.TxnType.EXPENSE, fromAccId = 1, value = "8"))
        vm.submit()
        awaitCondition { !vm.uiState.value.submitting && vm.uiState.value.message != null }

        assertTrue(vm.uiState.value.message!!.contains("网络错误"))
        assertEquals("8", vm.uiState.value.form.value)
    }

    @Test
    fun submit_invalidForm_blockedBeforeRepositoryCall() {
        val repo = FakeMoneyRepository(FakeApplication())
        val vm = newVm(repo)
        vm.setForm(MoneyViewModel.TxnForm(type = MoneyViewModel.TxnType.EXPENSE, value = "abc"))
        vm.submit()
        assertTrue(repo.createdRequests.isEmpty())
        assertEquals("请输入有效金额", vm.uiState.value.message)
    }

    // ---------------- update / delete 流程 ----------------

    @Test
    fun submitEdit_success_clearsEditingState() = runBlocking {
        val repo = FakeMoneyRepository(FakeApplication())
        val updated = txn(id = 5, value = "20")
        repo.updateResult = OperationResult.Success(updated)

        val vm = newVm(repo)
        vm.openEdit(txn(id = 5))
        assertNotNull(vm.uiState.value.editForm)
        vm.updateEditForm(
            MoneyViewModel.TxnForm(
                type = MoneyViewModel.TxnType.EXPENSE,
                fromAccId = 1,
                value = "20",
                htimeSec = 1_700_000_000L,
            ),
        )
        vm.submitEdit()
        awaitCondition { vm.uiState.value.editing == null && vm.uiState.value.message != null }

        assertNull(vm.uiState.value.editing)
        assertNull(vm.uiState.value.editForm)
        assertEquals("已更新", vm.uiState.value.message)
        assertEquals(listOf(5 to "20"), repo.updatedRequests.map { it.first to it.second.value })
    }

    @Test
    fun confirmDelete_success_clearsConfirmAndEditing() = runBlocking {
        val repo = FakeMoneyRepository(FakeApplication())
        repo.deleteResult = OperationResult.Success(TransactionDeleteResponse(id = 7, status = "success"))

        val vm = newVm(repo)
        val target = txn(id = 7)
        vm.openEdit(target)
        vm.requestDelete(target)
        assertEquals(7, vm.uiState.value.confirmDelete?.id)

        vm.confirmDelete()
        awaitCondition { vm.uiState.value.confirmDelete == null && vm.uiState.value.message != null }

        assertEquals(listOf(7), repo.deletedIds)
        assertNull(vm.uiState.value.confirmDelete)
        assertNull(vm.uiState.value.editing)
        assertNull(vm.uiState.value.editForm)
        assertEquals("已删除", vm.uiState.value.message)
    }

    @Test
    fun confirmDelete_failure_surfacesMessage() = runBlocking {
        val repo = FakeMoneyRepository(FakeApplication())
        repo.deleteResult = OperationResult.Failure("服务端错误")

        val vm = newVm(repo)
        vm.requestDelete(txn(id = 3))
        vm.confirmDelete()
        awaitCondition { vm.uiState.value.confirmDelete == null && vm.uiState.value.message != null }

        assertTrue(vm.uiState.value.message!!.contains("服务端错误"))
        assertNull(vm.uiState.value.confirmDelete)
    }

    // ---------------- refresh 失败回传 ----------------

    @Test
    fun refresh_failure_keepsDataAndReportsErrorAndMessage() = runBlocking {
        val repo = FakeMoneyRepository(FakeApplication())
        val existing = txn(id = 1)
        repo.accountsResult = OperationResult.Success(listOf(account(1)))
        repo.setTransactions(listOf(existing))

        val vm = newVm(repo)
        awaitCondition { vm.uiState.value.transactions.isNotEmpty() }
        assertEquals(listOf(1), vm.uiState.value.transactions.map { it.id })

        repo.paginatedHandler = { OperationResult.Failure("连接超时") }
        vm.refresh()
        awaitCondition { !vm.uiState.value.loading && vm.uiState.value.message != null }

        assertTrue(vm.uiState.value.message!!.contains("连接超时"))
        assertEquals("连接超时", vm.uiState.value.error)
        assertEquals(listOf(1), vm.uiState.value.transactions.map { it.id })
    }

    // ---------------- Repository：未配置服务器短路 ----------------

    @Test
    fun repository_withoutServer_returnsFailureWithoutNetwork() = runBlocking {
        val repo = MoneyRepository.get(FakeApplication())
        val result = repo.listAccounts()
        assertTrue(result is OperationResult.Failure)
        assertEquals("未配置服务器", (result as OperationResult.Failure).message)
    }

    // ---------------- 日期工具 ----------------

    @Test
    fun localMidnightSec_alignsToLocalDayStart() {
        val nowSec = System.currentTimeMillis() / 1000
        val midnight = MoneyViewModel.localMidnightSec(System.currentTimeMillis())
        assertTrue(midnight in (nowSec - 86400)..nowSec)
        val delta = nowSec - midnight
        assertTrue(delta in 0..86400L)
    }

    // ---------------- ViewModel 工厂 ----------------

    @Test
    fun factory_createsViewModelWithoutDefaultFactoryCrash() = runBlocking {
        val app = FakeApplication()
        val repo = FakeMoneyRepository(app)
        repo.accountsResult = OperationResult.Success(listOf(account(1)))

        val vm = MoneyViewModelFactory(app, repo).create(MoneyViewModel::class.java)
        vms.add(vm)
        awaitCondition { vm.uiState.value.accounts.isNotEmpty() }

        assertEquals(listOf(1), vm.uiState.value.accounts.map { it.id })
    }

    // ---------------- Finance 2.0：智能对账 / 清理队列 / 快脑对话 ----------------

    @Test
    fun computeReconcileDrift_calculatesSignedDifferenceAndRejectsInvalid() {
        assertEquals(BigDecimal("12.50"), MoneyViewModel.computeReconcileDrift("100.00 CNY", "112.5"))
        assertEquals(BigDecimal("-8.30"), MoneyViewModel.computeReconcileDrift("100.00", "91.7"))
        assertEquals(BigDecimal("0.00"), MoneyViewModel.computeReconcileDrift("500.0", "500"))
        assertNull(MoneyViewModel.computeReconcileDrift("100.00", ""))
        assertNull(MoneyViewModel.computeReconcileDrift("100.00", "abc"))
    }

    @Test
    fun submitReconcile_microDrift_closesDialogAndRefreshes() = runBlocking {
        val repo = FakeMoneyRepository(FakeApplication())
        repo.accountsResult = OperationResult.Success(listOf(AccountDto(id = 2, name = "微信", balance = "100.00")))
        repo.reconcileHandler = { req ->
            OperationResult.Success(
                AccountReconcileResponseDto(
                    account = AccountDto(id = req.accountId, name = "微信", balance = req.actualBalance),
                    checkpoint = BalanceCheckpointDto(
                        id = 1,
                        accountId = req.accountId,
                        reportedBalance = req.actualBalance,
                        bookBalance = "100.00",
                        driftAmount = "-12.00",
                        handling = "micro_adjusted",
                    ),
                    handling = "micro_adjusted",
                    driftAmount = "-12.00",
                    message = "已为「微信」执行小额无感平账（差额 -12.00 元）。",
                ),
            )
        }

        val vm = newVm(repo)
        awaitCondition { vm.uiState.value.accounts.isNotEmpty() }

        vm.openReconcileDialog()
        assertTrue(vm.uiState.value.reconcileOpen)
        assertEquals(2, vm.uiState.value.reconcileAccId)

        vm.setReconcileActualBalance("88.00")
        vm.submitReconcile()
        awaitCondition { !vm.uiState.value.reconcileBusy && !vm.uiState.value.reconcileOpen }

        assertEquals(1, repo.reconcileRequests.size)
        assertEquals("88.00", repo.reconcileRequests.first().actualBalance)
        assertTrue(vm.uiState.value.message!!.contains("小额无感平账"))
    }

    @Test
    fun hygieneProposal_approveAndRevert_triggersRefresh() = runBlocking {
        val repo = FakeMoneyRepository(FakeApplication())
        val pending = HygieneProposalDto(
            id = 11,
            proposalType = "auto_tag",
            autonomyLevel = "needs_review",
            status = "pending",
            title = "建议打标",
        )
        repo.pendingProposalsResult = OperationResult.Success(listOf(pending))
        repo.approveResult = OperationResult.Success(pending.copy(status = "applied"))
        repo.revertResult = OperationResult.Success(pending.copy(status = "reverted"))

        val vm = newVm(repo)
        awaitCondition { vm.uiState.value.pendingProposals.size == 1 }

        vm.approveProposal(11)
        awaitCondition { vm.uiState.value.hygieneBusyId == null && vm.uiState.value.message == "已批准执行" }
        assertEquals(listOf(11), repo.approvedIds)

        vm.revertProposal(11)
        awaitCondition { vm.uiState.value.hygieneBusyId == null && vm.uiState.value.message == "已撤销并恢复原状" }
        assertEquals(listOf(11), repo.revertedIds)
    }

    @Test
    fun sendFinanceQuickChat_withFinanceUpdated_refreshesAndShowsReply() = runBlocking {
        val app = FakeApplication()
        val repo = FakeMoneyRepository(app)
        val tickRepo = FakeTickRepository(app)
        tickRepo.quickChatHandler = {
            Result.success(
                QuickChatResult(
                    reply = "已记入 微信 支出 ¥32.00（午饭）",
                    financeUpdated = true,
                ),
            )
        }

        val vm = newVm(repo, tickRepo)
        awaitCondition { !vm.uiState.value.loading }
        val callsBefore = repo.paginatedCalls.size

        vm.setChatInput("午饭 32 微信")
        vm.sendFinanceQuickChat()
        awaitCondition { !vm.uiState.value.chatBusy && vm.uiState.value.chatReply != null }

        assertEquals(listOf("午饭 32 微信"), tickRepo.chatInputs)
        assertEquals("", vm.uiState.value.chatInput)
        assertTrue(vm.uiState.value.chatReply!!.contains("32.00"))
        assertTrue(repo.paginatedCalls.size > callsBefore)
    }
}
