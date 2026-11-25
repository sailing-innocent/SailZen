package com.sailzen.app.core.money

import android.content.Context
import android.util.Log
import com.sailzen.app.core.data.DataChangeBus
import com.sailzen.app.core.data.DataChangeEvent
import com.sailzen.app.core.data.OperationResult
import com.sailzen.app.core.data.SettingsManager
import com.sailzen.app.core.data.runOperation
import com.sailzen.app.core.network.ApiClient
import com.sailzen.app.core.network.MoneyApi
import com.sailzen.app.core.network.dto.AccountDto
import com.sailzen.app.core.network.dto.AccountReconcileRequestDto
import com.sailzen.app.core.network.dto.AccountReconcileResponseDto
import com.sailzen.app.core.network.dto.FinanceOverviewDto
import com.sailzen.app.core.network.dto.HygieneProposalDto
import com.sailzen.app.core.network.dto.HygieneScanRequestDto
import com.sailzen.app.core.network.dto.HygieneScanResultDto
import com.sailzen.app.core.network.dto.PaginatedTransactionsDto
import com.sailzen.app.core.network.dto.TransactionDeleteResponse
import com.sailzen.app.core.network.dto.TransactionDto
import com.sailzen.app.core.network.dto.TransactionStatsDto
import com.sailzen.app.core.network.dto.TransactionUpsertRequest

/**
 * 财务（Money）数据层：
 * - 需求定位"简单快速记账"：在线直发，失败即返回 Failure 由 UI 提示，不做离线队列；
 * - 服务端为唯一事实源，写操作成功后广播 [DataChangeEvent.TransactionChanged]，
 *   便于将来其它页面（预算/统计）联动刷新；
 * - 方法声明为 open 以便 JVM 单测用 fake 子类替换（沿用 BodyDataRecord 测试模式）。
 */
open class MoneyRepository protected constructor(private val context: Context) {

    companion object {
        private const val TAG = "MoneyRepository"

        @Volatile
        private var instance: MoneyRepository? = null

        fun get(context: Context): MoneyRepository =
            instance ?: synchronized(this) {
                instance ?: MoneyRepository(context.applicationContext).also { instance = it }
            }
    }

    private val settings = SettingsManager.get(context)
    private val bus = DataChangeBus.get()

    // ------------------------------------------------------------------
    // 基础
    // ------------------------------------------------------------------

    open suspend fun serverConfigured(): Boolean = settings.serverUrl().isNotBlank()

    private suspend fun apiOrNull(): MoneyApi? {
        val url = settings.serverUrl()
        if (url.isBlank()) return null
        return try {
            ApiClient.moneyApi(url, settings.apiToken())
        } catch (e: Exception) {
            Log.w(TAG, "money api build failed: ${e.message}")
            null
        }
    }

    private fun notConfigured(): IllegalStateException = IllegalStateException("未配置服务器")

    // ------------------------------------------------------------------
    // 查询
    // ------------------------------------------------------------------

    /** 账户列表（含预算口袋；调用方按 state 过滤，快速记账仅展示物理账户）。 */
    open suspend fun listAccounts(): OperationResult<List<AccountDto>> =
        runOperation(bus, block = { apiOrNull()?.listAccounts() ?: throw notConfigured() })

    /** 交易列表，服务端按 htime desc 返回（最新在前）。limit=-1 为全部。 */
    open suspend fun listTransactions(limit: Int = 200): OperationResult<List<TransactionDto>> =
        runOperation(bus, block = { apiOrNull()?.listTransactions(limit) ?: throw notConfigured() })

    /** 分页交易列表，支持按 ctime（入账时间）或 htime（交易日期）排序。 */
    open suspend fun listTransactionsPaginated(
        page: Int = 1,
        pageSize: Int = 50,
        sortBy: String = "ctime",
        sortOrder: String = "desc",
    ): OperationResult<PaginatedTransactionsDto> =
        runOperation(
            bus,
            block = {
                apiOrNull()?.listTransactionsPaginated(
                    page = page,
                    pageSize = pageSize,
                    sortBy = sortBy,
                    sortOrder = sortOrder,
                ) ?: throw notConfigured()
            },
        )

    /** 指定时间范围的收支汇总统计（return_list=false）。 */
    open suspend fun getTransactionStats(
        fromTime: Double,
        toTime: Double,
    ): OperationResult<TransactionStatsDto> =
        runOperation(
            bus,
            block = {
                apiOrNull()?.getTransactionStats(
                    fromTime = fromTime,
                    toTime = toTime,
                    returnList = false,
                ) ?: throw notConfigured()
            },
        )

    // ------------------------------------------------------------------
    // 写入（成功广播 TransactionChanged）
    // ------------------------------------------------------------------

    open suspend fun create(req: TransactionUpsertRequest): OperationResult<TransactionDto> =
        runOperation(
            bus,
            block = { apiOrNull()?.createTransaction(req) ?: throw notConfigured() },
            onSuccess = { DataChangeEvent.TransactionChanged(transactionId = it.id, action = "create") },
        )

    open suspend fun update(id: Int, req: TransactionUpsertRequest): OperationResult<TransactionDto> =
        runOperation(
            bus,
            block = { apiOrNull()?.updateTransaction(id, req) ?: throw notConfigured() },
            onSuccess = { DataChangeEvent.TransactionChanged(transactionId = it.id, action = "update") },
        )

    open suspend fun delete(id: Int): OperationResult<TransactionDeleteResponse> =
        runOperation(
            bus,
            block = { apiOrNull()?.deleteTransaction(id) ?: throw notConfigured() },
            onSuccess = { DataChangeEvent.TransactionChanged(transactionId = id, action = "delete") },
        )

    // ------------------------------------------------------------------
    // Finance 2.0 (SailTick 开销秘书)
    // ------------------------------------------------------------------

    open suspend fun getFinanceOverview(month: String? = null): OperationResult<FinanceOverviewDto> =
        runOperation(
            bus,
            block = { apiOrNull()?.getFinanceOverview(month) ?: throw notConfigured() },
        )

    open suspend fun reconcileAccount(
        req: AccountReconcileRequestDto,
    ): OperationResult<AccountReconcileResponseDto> =
        runOperation(
            bus,
            block = { apiOrNull()?.reconcileAccount(req) ?: throw notConfigured() },
            onSuccess = { DataChangeEvent.TransactionChanged(action = "reconcile") },
        )

    open suspend fun runHygieneScan(
        req: HygieneScanRequestDto = HygieneScanRequestDto(),
    ): OperationResult<HygieneScanResultDto> =
        runOperation(
            bus,
            block = { apiOrNull()?.runHygieneScan(req) ?: throw notConfigured() },
            onSuccess = { DataChangeEvent.TransactionChanged(action = "hygiene_scan") },
        )

    open suspend fun listHygieneProposals(
        status: String? = null,
        autonomyLevel: String? = null,
        limit: Int = 30,
    ): OperationResult<List<HygieneProposalDto>> =
        runOperation(
            bus,
            block = {
                apiOrNull()?.listHygieneProposals(
                    status = status,
                    autonomyLevel = autonomyLevel,
                    limit = limit,
                ) ?: throw notConfigured()
            },
        )

    open suspend fun approveHygieneProposal(id: Int): OperationResult<HygieneProposalDto> =
        runOperation(
            bus,
            block = { apiOrNull()?.approveHygieneProposal(id) ?: throw notConfigured() },
            onSuccess = { DataChangeEvent.TransactionChanged(action = "hygiene_approve") },
        )

    open suspend fun dismissHygieneProposal(id: Int): OperationResult<HygieneProposalDto> =
        runOperation(
            bus,
            block = { apiOrNull()?.dismissHygieneProposal(id) ?: throw notConfigured() },
        )

    open suspend fun revertHygieneProposal(id: Int): OperationResult<HygieneProposalDto> =
        runOperation(
            bus,
            block = { apiOrNull()?.revertHygieneProposal(id) ?: throw notConfigured() },
            onSuccess = { DataChangeEvent.TransactionChanged(action = "hygiene_revert") },
        )
}
