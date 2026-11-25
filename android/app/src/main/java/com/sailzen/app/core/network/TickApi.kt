package com.sailzen.app.core.network

import com.sailzen.app.core.network.dto.DailyReportDto
import com.sailzen.app.core.network.dto.HealthCoachSummaryDto
import com.sailzen.app.core.network.dto.ImageIntakeCommitRequest
import com.sailzen.app.core.network.dto.ImageIntakeCommitResponse
import com.sailzen.app.core.network.dto.ImageIntakeDraftDto
import com.sailzen.app.core.network.dto.QuickChatRequest
import com.sailzen.app.core.network.dto.QuickChatResponse
import com.sailzen.app.core.network.dto.TickMessageCreateRequest
import com.sailzen.app.core.network.dto.TickMessageDto
import com.sailzen.app.core.network.dto.TickTicketDto
import com.sailzen.app.core.network.dto.TicketReplyRequest
import com.sailzen.app.core.network.dto.TicketResolveRequest
import com.sailzen.app.core.network.dto.TicketSnoozeRequest
import okhttp3.MultipartBody
import okhttp3.RequestBody
import retrofit2.http.Body
import retrofit2.http.GET
import retrofit2.http.Multipart
import retrofit2.http.POST
import retrofit2.http.Part
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

    @Multipart
    @POST("api/v1/tick/intake/analyze")
    suspend fun analyzeImageIntake(
        @Part file: MultipartBody.Part,
        @Part("note") note: RequestBody,
        @Part("source_channel") sourceChannel: RequestBody,
        @Part("use_ocr_assist") useOcrAssist: RequestBody,
        @Part("ticket_id") ticketId: RequestBody? = null,
    ): ImageIntakeDraftDto

    @GET("api/v1/tick/intake/drafts")
    suspend fun listIntakeDrafts(
        @Query("status") status: String? = null,
        @Query("limit") limit: Int = 10,
    ): List<ImageIntakeDraftDto>

    @POST("api/v1/tick/intake/{id}/commit")
    suspend fun commitIntakeDraft(
        @Path("id") id: Int,
        @Body body: ImageIntakeCommitRequest,
    ): ImageIntakeCommitResponse

    @POST("api/v1/tick/intake/{id}/discard")
    suspend fun discardIntakeDraft(
        @Path("id") id: Int,
    ): ImageIntakeDraftDto

    @POST("api/v1/tick/quick-chat")
    suspend fun quickChat(
        @Body body: QuickChatRequest,
    ): QuickChatResponse
}
