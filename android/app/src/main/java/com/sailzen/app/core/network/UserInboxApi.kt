package com.sailzen.app.core.network

import com.sailzen.app.core.network.dto.InboxDismissRequest
import com.sailzen.app.core.network.dto.InboxItemDto
import com.sailzen.app.core.network.dto.InboxReplyRequest
import com.sailzen.app.core.network.dto.InboxResolveRequest
import com.sailzen.app.core.network.dto.InboxSnoozeRequest
import com.sailzen.app.core.network.dto.InboxSummaryDto
import com.sailzen.app.core.network.dto.InboxSyncResponseDto
import com.sailzen.app.core.network.dto.UserBootstrapDto
import com.sailzen.app.core.network.dto.UserDeviceDto
import com.sailzen.app.core.network.dto.UserDeviceRegisterRequest
import com.sailzen.app.core.network.dto.UserProfileDto
import com.sailzen.app.core.network.dto.UserProfileUpdateRequest
import retrofit2.http.Body
import retrofit2.http.GET
import retrofit2.http.PATCH
import retrofit2.http.POST
import retrofit2.http.Path
import retrofit2.http.Query

interface UserInboxApi {

    @GET("api/v1/user/bootstrap")
    suspend fun bootstrap(): UserBootstrapDto

    @GET("api/v1/user/profile")
    suspend fun getProfile(): UserProfileDto

    @PATCH("api/v1/user/profile")
    suspend fun updateProfile(@Body body: UserProfileUpdateRequest): UserProfileDto

    @POST("api/v1/user/devices/register")
    suspend fun registerDevice(@Body body: UserDeviceRegisterRequest): UserDeviceDto

    @GET("api/v1/user/devices")
    suspend fun listDevices(): List<UserDeviceDto>

    @GET("api/v1/inbox/sync")
    suspend fun syncInbox(
        @Query("since_seq") sinceSeq: Long = 0L,
        @Query("limit") limit: Int = 200,
    ): InboxSyncResponseDto

    @GET("api/v1/inbox/summary")
    suspend fun summary(): InboxSummaryDto

    @POST("api/v1/inbox/{id}/reply")
    suspend fun reply(
        @Path("id") id: Int,
        @Body body: InboxReplyRequest,
    ): InboxItemDto

    @POST("api/v1/inbox/{id}/resolve")
    suspend fun resolve(
        @Path("id") id: Int,
        @Body body: InboxResolveRequest = InboxResolveRequest(),
    ): InboxItemDto

    @POST("api/v1/inbox/{id}/snooze")
    suspend fun snooze(
        @Path("id") id: Int,
        @Body body: InboxSnoozeRequest,
    ): InboxItemDto

    @POST("api/v1/inbox/{id}/dismiss")
    suspend fun dismiss(
        @Path("id") id: Int,
        @Body body: InboxDismissRequest = InboxDismissRequest(),
    ): InboxItemDto

    @POST("api/v1/inbox/{id}/read")
    suspend fun markRead(@Path("id") id: Int): InboxItemDto
}
