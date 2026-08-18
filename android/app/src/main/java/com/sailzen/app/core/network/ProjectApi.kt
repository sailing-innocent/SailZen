package com.sailzen.app.core.network

import com.sailzen.app.core.network.dto.DeleteResponse
import com.sailzen.app.core.network.dto.MissionCreateRequest
import com.sailzen.app.core.network.dto.MissionDto
import com.sailzen.app.core.network.dto.MissionUpdateRequest
import com.sailzen.app.core.network.dto.ProjectCreateRequest
import com.sailzen.app.core.network.dto.ProjectDto
import com.sailzen.app.core.network.dto.ProjectUpdateRequest
import retrofit2.http.Body
import retrofit2.http.DELETE
import retrofit2.http.GET
import retrofit2.http.POST
import retrofit2.http.PUT
import retrofit2.http.Path
import retrofit2.http.Query

/**
 * 项目/任务 REST API（前缀 /api/v1/project）。
 * 端点与 packages/site/src/lib/api/project.ts 完全对齐。
 */
interface ProjectApi {

    // ---------------- Project ----------------

    @GET("api/v1/project/project")
    suspend fun getProjects(
        @Query("skip") skip: Int = 0,
        @Query("limit") limit: Int = -1,
    ): List<ProjectDto>

    @GET("api/v1/project/project/{id}")
    suspend fun getProject(@Path("id") id: Int): ProjectDto

    @POST("api/v1/project/project/")
    suspend fun createProject(@Body body: ProjectCreateRequest): ProjectDto

    @PUT("api/v1/project/project/{id}")
    suspend fun updateProject(
        @Path("id") id: Int,
        @Body body: ProjectUpdateRequest,
    ): ProjectDto

    @DELETE("api/v1/project/project/{id}")
    suspend fun deleteProject(@Path("id") id: Int): DeleteResponse

    // ---------------- Mission ----------------

    @GET("api/v1/project/mission/")
    suspend fun getMissions(
        @Query("skip") skip: Int = 0,
        @Query("limit") limit: Int = -1,
        @Query("project_id") projectId: Int? = null,
        @Query("parent_id") parentId: Int? = null,
    ): List<MissionDto>

    @GET("api/v1/project/mission/{id}")
    suspend fun getMission(@Path("id") id: Int): MissionDto

    @POST("api/v1/project/mission/")
    suspend fun createMission(@Body body: MissionCreateRequest): MissionDto

    @PUT("api/v1/project/mission/{id}")
    suspend fun updateMission(
        @Path("id") id: Int,
        @Body body: MissionUpdateRequest,
    ): MissionDto

    @DELETE("api/v1/project/mission/{id}")
    suspend fun deleteMission(@Path("id") id: Int): DeleteResponse

    // ---------------- Mission State Transition ----------------

    @POST("api/v1/project/mission/{id}/pending")
    suspend fun pendingMission(@Path("id") id: Int): MissionDto

    @POST("api/v1/project/mission/{id}/ready")
    suspend fun readyMission(@Path("id") id: Int): MissionDto

    @POST("api/v1/project/mission/{id}/doing")
    suspend fun doingMission(@Path("id") id: Int): MissionDto

    @POST("api/v1/project/mission/{id}/done")
    suspend fun doneMission(@Path("id") id: Int): MissionDto

    @POST("api/v1/project/mission/{id}/cancel")
    suspend fun cancelMission(@Path("id") id: Int): MissionDto

    @POST("api/v1/project/mission/{id}/postpone")
    suspend fun postponeMission(
        @Path("id") id: Int,
        @Query("days") days: Int = 7,
    ): MissionDto

    // ---------------- Mission Reminder ----------------

    @GET("api/v1/project/mission/upcoming")
    suspend fun getUpcomingMissions(
        @Query("hours") hours: Int = 24,
    ): List<MissionDto>

    @GET("api/v1/project/mission/overdue")
    suspend fun getOverdueMissions(): List<MissionDto>
}
