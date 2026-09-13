package com.sailzen.app.feature.money

import android.app.Application
import android.content.Context
import androidx.lifecycle.viewModelScope
import com.sailzen.app.core.data.OperationResult
import com.sailzen.app.core.money.MoneyRepository
import com.sailzen.app.core.network.dto.AccountDto
import com.sailzen.app.core.network.dto.TransactionDeleteResponse
import com.sailzen.app.core.network.dto.TransactionDto
import com.sailzen.app.core.network.dto.TransactionUpsertRequest
import java.io.File
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
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test

/**
 * 快速记账 ViewModel 语义测试（JVM，FakeApplication + FakeMoneyRepository）：
 * - 表单校验（金额/账户/转账两侧）与 from/to 请求映射；
 * - 类型推断与物理账户过滤；
 * - create 成功后列表 refresh、表单保留（对齐前端"继续添加"）；
 * - update/delete 成功后编辑/确认状态清空；
 * - repository Failure 时错误 message 正确回传。
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

    private class FakeMoneyRepository(context: Context) : MoneyRepository(context) {
        var accountsResult: OperationResult<List<AccountDto>> = OperationResult.Success(emptyList())
        var transactionsResult: OperationResult<List<TransactionDto>> = OperationResult.Success(emptyList())
        var createResult: OperationResult<TransactionDto> = OperationResult.Failure("未配置服务器")
        var updateResult: OperationResult<TransactionDto> = OperationResult.Failure("未配置服务器")
        var deleteResult: OperationResult<TransactionDeleteResponse> =
            OperationResult.Failure("未配置服务器")

        val createdRequests = mutableListOf<TransactionUpsertRequest>()
        val updatedRequests = mutableListOf<Pair<Int, TransactionUpsertRequest>>()
        val deletedIds = mutableListOf<Int>()
        var configured = true

        // override 绕过 DataStore 读：避免 VM init 协程在 DataStore 后台线程上恢复并并发
        // 触碰 Dispatchers.Main，导致跨测试的 setMain/resetMain 竞态
        override suspend fun serverConfigured() = configured

        override suspend fun listAccounts() = accountsResult
        override suspend fun listTransactions(limit: Int) = transactionsResult
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
    }

    private fun newVm(repository: FakeMoneyRepository): MoneyViewModel =
        MoneyViewModel(FakeApplication(), repository).also(vms::add)

    private fun account(id: Int, state: Int = 0) = AccountDto(id = id, name = "账户$id", state = state)

    private fun txn(
        id: Int,
        fromAccId: Int = 1,
        toAccId: Int = -1,
        value: String = "12.5",
        description: String = "午餐",
        htime: Double = 1_700_000_000.0,
    ) = TransactionDto(
        id = id,
        fromAccId = fromAccId,
        toAccId = toAccId,
        value = value,
        description = description,
        htime = htime,
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
        // 泵空 TestMainDispatcher，确保取消的协程在 resetMain 前完成
        testDispatcher.scheduler.runCurrent()
        Dispatchers.resetMain()
    }

    // ---------------- 表单校验 ----------------

    @Test
    fun validateForm_rejectsBlankAndNonNumericAmount() {
        val base = MoneyViewModel.TxnForm(type = MoneyViewModel.TxnType.EXPENSE, fromAccId = 1)
        assertEquals("请输入有效金额", MoneyViewModel.validateForm(base.copy(value = "")))
        assertEquals("请输入有效金额", MoneyViewModel.validateForm(base.copy(value = "abc")))
        assertEquals("请输入有效金额", MoneyViewModel.validateForm(base.copy(value = "  ")))
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
    fun toRequest_incomeUsesExternalAsPayer() {
        val req = MoneyViewModel.toRequest(
            MoneyViewModel.TxnForm(
                type = MoneyViewModel.TxnType.INCOME,
                fromAccId = 9, // 收入模式下应被忽略
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

    // ---------------- create 流程 ----------------

    @Test
    fun submit_success_refreshesListAndKeepsForm() = runBlocking {
        val repo = FakeMoneyRepository(FakeApplication())
        val latest = txn(id = 9)
        repo.accountsResult = OperationResult.Success(listOf(account(1)))
        repo.transactionsResult = OperationResult.Success(listOf(latest))
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
        // 列表已 refresh 到服务端最新
        assertEquals(listOf(9), vm.uiState.value.transactions.map { it.id })
        // 表单保留（对齐前端"继续添加"）
        assertEquals(form, vm.uiState.value.form)
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
    fun refresh_failure_keepsDataAndReportsMessage() = runBlocking {
        val repo = FakeMoneyRepository(FakeApplication())
        val existing = txn(id = 1)
        repo.accountsResult = OperationResult.Success(listOf(account(1)))
        repo.transactionsResult = OperationResult.Success(listOf(existing))

        val vm = newVm(repo)
        awaitCondition { vm.uiState.value.transactions.isNotEmpty() }
        assertEquals(listOf(1), vm.uiState.value.transactions.map { it.id })

        repo.transactionsResult = OperationResult.Failure("连接超时")
        vm.refresh()
        awaitCondition { !vm.uiState.value.loading && vm.uiState.value.message != null }

        assertTrue(vm.uiState.value.message!!.contains("连接超时"))
        // 旧数据保留
        assertEquals(listOf(1), vm.uiState.value.transactions.map { it.id })
    }

    // ---------------- Repository：未配置服务器短路 ----------------

    @Test
    fun repository_withoutServer_returnsFailureWithoutNetwork() = runBlocking {
        // debug 构建 BuildConfig.SERVER_URL 为空 → apiOrNull 早退 null →
        // listAccounts 返回 Failure("未配置服务器")，不触网、不抛异常
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
        // 零点对齐：当天任意时刻（含跨日边界 ±1s 容差）与零点差为整天数
        val delta = nowSec - midnight
        assertTrue(delta in 0..86400L)
    }
}
