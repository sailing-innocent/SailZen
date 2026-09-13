package com.sailzen.app.core.network

import com.sailzen.app.core.network.dto.AccountDto
import com.sailzen.app.core.network.dto.TransactionDeleteResponse
import com.sailzen.app.core.network.dto.TransactionDto
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
 *
 * 列表接口返回纯 JSON 数组；服务端按 Transaction.htime desc 返回，最新在前。
 */
interface MoneyApi {

    /** 账户列表（AccountResponse[]） */
    @GET("api/v1/finance/account/")
    suspend fun listAccounts(): List<AccountDto>

    /** 交易列表（TransactionResponse[]），limit=-1 为全部，默认取最近 200 条 */
    @GET("api/v1/finance/transaction/")
    suspend fun listTransactions(@Query("limit") limit: Int = 200): List<TransactionDto>

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
