package com.sailzen.app.core.network

import com.sailzen.app.core.network.dto.DailyReportDto
import com.sailzen.app.core.network.dto.HealthCoachSummaryDto
import com.sailzen.app.core.network.dto.TickMessageCreateRequest
import com.sailzen.app.core.network.dto.TickMessageDto
import com.sailzen.app.core.network.dto.TickTicketDto
import com.sailzen.app.core.network.dto.TicketReplyRequest
import com.sailzen.app.core.network.dto.TicketResolveRequest
import com.sailzen.app.core.network.dto.TicketSnoozeRequest
import retrofit2.http.Body
import retrofit2.http.GET
import retrofit2.http.POST
import retrofit2.http.Path
import retrofit2.http.Query

/**
 * SailTick 教练 REST API（对应服务端 /api/v1/tick 路由组）。
 */
interface TickApi {

    @GET("api/v1/tick/tickets")
    suspend fun listTickets(
        @Query("status") status: String? = null,
        @Query("limit") limit: Int = 50,
    ): List<TickTicketDto>

    @POST("api/v1/tick/tickets/{id}/reply")
    suspend fun replyTicket(
        @Path("id") id: Int,
        @Body body: TicketReplyRequest,
    ): TickTicketDto

    @POST("api/v1/tick/tickets/{id}/snooze")
    suspend fun snoozeTicket(
        @Path("id") id: Int,
        @Body body: TicketSnoozeRequest = TicketSnoozeRequest(24),
    ): TickTicketDto

    @POST("api/v1/tick/tickets/{id}/resolve")
    suspend fun resolveTicket(
        @Path("id") id: Int,
        @Body body: TicketResolveRequest = TicketResolveRequest(""),
    ): TickTicketDto

    @POST("api/v1/tick/messages")
    suspend fun sendMessage(
        @Body body: TickMessageCreateRequest,
    ): TickMessageDto

    @GET("api/v1/tick/messages")
    suspend fun listMessages(
        @Query("status") status: String? = null,
        @Query("category") category: String? = null,
        @Query("limit") limit: Int = 50,
    ): List<TickMessageDto>

    @GET("api/v1/tick/reports")
    suspend fun listDailyReports(
        @Query("limit") limit: Int = 14,
    ): List<DailyReportDto>

    @GET("api/v1/tick/reports/latest")
    suspend fun latestDailyReport(): DailyReportDto?

    @GET("api/v1/tick/health-summary")
    suspend fun healthCoachSummary(): HealthCoachSummaryDto
}
