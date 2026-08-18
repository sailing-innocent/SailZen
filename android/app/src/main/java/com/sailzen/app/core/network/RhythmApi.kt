package com.sailzen.app.core.network

import com.sailzen.app.core.network.dto.AffairCreateRequest
import com.sailzen.app.core.network.dto.AffairDto
import com.sailzen.app.core.network.dto.AffairListResponse
import com.sailzen.app.core.network.dto.AffairStateRequest
import com.sailzen.app.core.network.dto.AffairUpdateRequest
import com.sailzen.app.core.network.dto.BlockMoveRequest
import com.sailzen.app.core.network.dto.BlockStatusRequest
import com.sailzen.app.core.network.dto.CheckinLogDto
import com.sailzen.app.core.network.dto.CheckinRequest
import com.sailzen.app.core.network.dto.CheckinTodayDto
import com.sailzen.app.core.network.dto.ConfirmHintRequest
import com.sailzen.app.core.network.dto.DayTimelineDto
import com.sailzen.app.core.network.dto.DeleteResponse
import com.sailzen.app.core.network.dto.HealthCheckinRequest
import com.sailzen.app.core.network.dto.HealthCheckinResponse
import com.sailzen.app.core.network.dto.PlanDayDto
import com.sailzen.app.core.network.dto.PlanDayRequest
import com.sailzen.app.core.network.dto.ProjectTimelineDto
import com.sailzen.app.core.network.dto.ReviewDto
import com.sailzen.app.core.network.dto.ReviewTimespanDto
import com.sailzen.app.core.network.dto.RhythmDayViewDto
import com.sailzen.app.core.network.dto.TimeBlockDto
import com.sailzen.app.core.network.dto.VentureMilestoneRequest
import com.sailzen.app.core.network.dto.VentureProgressDto
import retrofit2.http.Body
import retrofit2.http.DELETE
import retrofit2.http.GET
import retrofit2.http.POST
import retrofit2.http.PUT
import retrofit2.http.Path
import retrofit2.http.Query

/**
 * 节奏 REST API（前缀 /api/v1/rhythm，契约见服务端 controller/rhythm.py
 * 与设计文档 doc/design/manager/rhythm.md §5）。
 */
interface RhythmApi {

    // ---------------- Affair ----------------

    @POST("api/v1/rhythm/affair/")
    suspend fun capture(@Body body: AffairCreateRequest): AffairDto

    @GET("api/v1/rhythm/affair/")
    suspend fun listAffairs(
        @Query("state") state: String? = null,
        @Query("domain") domain: String? = null,
        @Query("kind") kinds: List<String>? = null,
        @Query("parent_id") parentId: Int? = null,
        @Query("urgency_ddl_before") urgencyDdlBefore: String? = null,
        @Query("urgency_ddl_after") urgencyDdlAfter: String? = null,
        @Query("limit") limit: Int = -1,
    ): AffairListResponse

    @GET("api/v1/rhythm/affair/{id}")
    suspend fun getAffair(@Path("id") id: Int): AffairDto

    @PUT("api/v1/rhythm/affair/{id}")
    suspend fun updateAffair(@Path("id") id: Int, @Body body: AffairUpdateRequest): AffairDto

    @DELETE("api/v1/rhythm/affair/{id}")
    suspend fun deleteAffair(@Path("id") id: Int): DeleteResponse

    @POST("api/v1/rhythm/affair/{id}/state")
    suspend fun transit(@Path("id") id: Int, @Body body: AffairStateRequest): AffairDto

    @POST("api/v1/rhythm/affair/{id}/confirm-hint")
    suspend fun confirmHint(@Path("id") id: Int, @Body body: ConfirmHintRequest): AffairDto

    // ---------------- Timeline / Plan ----------------

    @GET("api/v1/rhythm/timeline/day")
    suspend fun timelineDay(@Query("date") date: String): DayTimelineDto

    @POST("api/v1/rhythm/timeline/block/{id}/status")
    suspend fun blockStatus(@Path("id") id: Int, @Body body: BlockStatusRequest): TimeBlockDto

    @POST("api/v1/rhythm/timeline/block/{id}/move")
    suspend fun blockMove(@Path("id") id: Int, @Body body: BlockMoveRequest): TimeBlockDto

    @POST("api/v1/rhythm/plan/day")
    suspend fun planDay(@Body body: PlanDayRequest): PlanDayDto

    // ---------------- Checkin ----------------

    @POST("api/v1/rhythm/checkin/")
    suspend fun checkin(@Body body: CheckinRequest): CheckinLogDto

    @GET("api/v1/rhythm/checkin/today")
    suspend fun checkinToday(@Query("date") date: String? = null): CheckinTodayDto

    // ---------------- Venture ----------------

    @GET("api/v1/rhythm/venture/{id}/progress")
    suspend fun ventureProgress(@Path("id") id: Int): VentureProgressDto

    @POST("api/v1/rhythm/venture/{id}/milestone")
    suspend fun addMilestone(
        @Path("id") id: Int,
        @Body body: VentureMilestoneRequest,
    ): AffairDto

    @POST("api/v1/rhythm/venture/milestone/{id}/done")
    suspend fun milestoneDone(@Path("id") id: Int): AffairDto

    // ---------------- Review ----------------

    @GET("api/v1/rhythm/review/day")
    suspend fun reviewDay(@Query("date") date: String): ReviewDto

    @GET("api/v1/rhythm/review/week")
    suspend fun reviewWeek(@Query("span") span: String? = null): ReviewDto

    @GET("api/v1/rhythm/review/timespan/{id}")
    suspend fun reviewTimespan(@Path("id") id: Int): ReviewTimespanDto

    @GET("api/v1/rhythm/review/project/{project_id}")
    suspend fun projectTimeline(@Path("project_id") projectId: Int): ProjectTimelineDto

    // ---------------- Day View / Health ----------------

    @GET("api/v1/rhythm/timeline/day-view")
    suspend fun dayView(@Query("date") date: String): RhythmDayViewDto

    @POST("api/v1/rhythm/checkin/health")
    suspend fun healthCheckin(@Body body: HealthCheckinRequest): HealthCheckinResponse
}
