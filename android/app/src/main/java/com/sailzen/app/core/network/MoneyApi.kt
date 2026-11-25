package com.sailzen.app.core.network

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
import retrofit2.http.Body
import retrofit2.http.DELETE
import retrofit2.http.GET
import retrofit2.http.POST
import retrofit2.http.PUT
import retrofit2.http.Path
import retrofit2.http.Query

/**
 * 财务 REST API（前缀 /api/v1/finance，契约见 sail_server/router/finance.py
 * 与官方文档 doc/api/finance.md）。
 */
interface MoneyApi {

    /** 账户列表（AccountResponse[]） */
    @GET("api/v1/finance/account/")
    suspend fun listAccounts(): List<AccountDto>

    /** 交易列表（TransactionResponse[]），limit=-1 为全部，默认取最近 200 条 */
    @GET("api/v1/finance/transaction/")
    suspend fun listTransactions(@Query("limit") limit: Int = 200): List<TransactionDto>

    /** 分页交易列表，支持按 ctime（入账时间）或 htime（交易日期）排序 */
    @GET("api/v1/finance/transaction/paginated/")
    suspend fun listTransactionsPaginated(
        @Query("page") page: Int = 1,
        @Query("page_size") pageSize: Int = 50,
        @Query("sort_by") sortBy: String = "ctime",
        @Query("sort_order") sortOrder: String = "desc",
    ): PaginatedTransactionsDto

    /** 交易汇总统计（支持按时间段统计收入/支出/结余） */
    @GET("api/v1/finance/transaction/stats/")
    suspend fun getTransactionStats(
        @Query("from_time") fromTime: Double? = null,
        @Query("to_time") toTime: Double? = null,
        @Query("return_list") returnList: Boolean = false,
    ): TransactionStatsDto

    /** 创建交易，body 为 TransactionCreateRequest */
    @POST("api/v1/finance/transaction/")
    suspend fun createTransaction(@Body body: TransactionUpsertRequest): TransactionDto

    /** 更新交易（全量字段），body 为 TransactionUpdateRequest */
    @PUT("api/v1/finance/transaction/{id}")
    suspend fun updateTransaction(
        @Path("id") id: Int,
        @Body body: TransactionUpsertRequest,
    ): TransactionDto

    /** 删除交易，返回 {id, status, message} */
    @DELETE("api/v1/finance/transaction/{id}")
    suspend fun deleteTransaction(@Path("id") id: Int): TransactionDeleteResponse

    // ------------------------------------------------------------------
    // Finance 2.0 (SailTick 开销秘书)
    // ------------------------------------------------------------------

    /** 财务秘书聚合总览（本月真实收支、真实零食、标签覆盖率、清理队列、沉默账户） */
    @GET("api/v1/finance/overview")
    suspend fun getFinanceOverview(@Query("month") month: String? = null): FinanceOverviewDto

    /** 智能余额核对（小额无感平账，大额进入待排查队列） */
    @POST("api/v1/finance/account/reconcile")
    suspend fun reconcileAccount(@Body body: AccountReconcileRequestDto): AccountReconcileResponseDto

    /** 触发账单健康体检与分级自治扫描 */
    @POST("api/v1/finance/hygiene/scan")
    suspend fun runHygieneScan(@Body body: HygieneScanRequestDto = HygieneScanRequestDto()): HygieneScanResultDto

    /** 查询账单清理建议与 AI 自动托管审计列表 */
    @GET("api/v1/finance/hygiene/proposals")
    suspend fun listHygieneProposals(
        @Query("status") status: String? = null,
        @Query("autonomy_level") autonomyLevel: String? = null,
        @Query("limit") limit: Int = 30,
    ): List<HygieneProposalDto>

    /** 批准待审清理建议 */
    @POST("api/v1/finance/hygiene/proposals/{id}/approve")
    suspend fun approveHygieneProposal(@Path("id") id: Int): HygieneProposalDto

    /** 忽略待审清理建议 */
    @POST("api/v1/finance/hygiene/proposals/{id}/dismiss")
    suspend fun dismissHygieneProposal(@Path("id") id: Int): HygieneProposalDto

    /** 一键撤销已执行的清理或平账操作 */
    @POST("api/v1/finance/hygiene/proposals/{id}/revert")
    suspend fun revertHygieneProposal(@Path("id") id: Int): HygieneProposalDto
}
