package com.sailzen.app.core.network

import com.sailzen.app.core.network.dto.AckRequest
import com.sailzen.app.core.network.dto.DeviceDto
import com.sailzen.app.core.network.dto.DeviceRegisterRequest
import com.sailzen.app.core.network.dto.FeedbackRequest
import com.sailzen.app.core.network.dto.OkResponse
import com.sailzen.app.core.network.dto.ReminderDto
import com.sailzen.app.core.network.dto.SummaryDto
import retrofit2.http.Body
import retrofit2.http.DELETE
import retrofit2.http.GET
import retrofit2.http.POST
import retrofit2.http.Path
import retrofit2.http.Query

/**
 * 提醒 REST API（前缀 /api/v1/reminder，契约见服务端 controller/reminder.py）。
 */
interface ReminderApi {

    @POST("api/v1/reminder/device/register")
    suspend fun registerDevice(@Body body: DeviceRegisterRequest): DeviceDto

    @GET("api/v1/reminder/pending")
    suspend fun pending(@Query("since") since: String? = null): List<ReminderDto>

    @GET("api/v1/reminder/history")
    suspend fun history(
        @Query("date") date: String,
        @Query("type") type: String? = null,
    ): List<ReminderDto>

    @GET("api/v1/reminder/summary/today")
    suspend fun summaryToday(): SummaryDto

    @POST("api/v1/reminder/ack")
    suspend fun ack(@Body body: AckRequest): OkResponse

    @POST("api/v1/reminder/{id}/feedback")
    suspend fun feedback(
        @Path("id") id: Int,
        @Body body: FeedbackRequest,
    ): ReminderDto

    @DELETE("api/v1/reminder/{id}")
    suspend fun cancel(@Path("id") id: Int): ReminderDto
}
