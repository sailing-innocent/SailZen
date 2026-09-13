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
import com.sailzen.app.core.network.dto.TransactionDeleteResponse
import com.sailzen.app.core.network.dto.TransactionDto
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
}
