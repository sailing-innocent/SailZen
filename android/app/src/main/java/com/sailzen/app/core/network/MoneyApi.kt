package com.sailzen.app.core.network

import com.sailzen.app.core.network.dto.AccountDto
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
}
