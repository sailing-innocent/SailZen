package com.sailzen.app.core.network

import com.sailzen.app.core.network.dto.DietCreateRequest
import com.sailzen.app.core.network.dto.DietDto
import com.sailzen.app.core.network.dto.DietSummaryDto
import com.sailzen.app.core.network.dto.ExerciseCreateRequest
import com.sailzen.app.core.network.dto.ExerciseDto
import com.sailzen.app.core.network.dto.HealthDashboardDto
import com.sailzen.app.core.network.dto.MedicationCreateRequest
import com.sailzen.app.core.network.dto.MedicationDto
import com.sailzen.app.core.network.dto.MedicationStatsDto
import com.sailzen.app.core.network.dto.MedicationTodayDto
import com.sailzen.app.core.network.dto.MedicationUpdateRequest
import com.sailzen.app.core.network.dto.NutritionGoalCreateRequest
import com.sailzen.app.core.network.dto.NutritionGoalDto
import com.sailzen.app.core.network.dto.SleepCreateRequest
import com.sailzen.app.core.network.dto.SleepDto
import com.sailzen.app.core.network.dto.SleepScheduleGoalCreateRequest
import com.sailzen.app.core.network.dto.SleepScheduleGoalDto
import com.sailzen.app.core.network.dto.WeightCreateRequest
import com.sailzen.app.core.network.dto.WeightDto
import com.sailzen.app.core.network.dto.WeightPlanCheckinStatusDto
import com.sailzen.app.core.network.dto.WeightPlanCreateRequest
import com.sailzen.app.core.network.dto.WeightPlanDto
import com.sailzen.app.core.network.dto.WeightPlanProgressDto
import com.sailzen.app.core.network.dto.WeightExpectedRangeDto
import com.sailzen.app.core.network.dto.WeightWithStatusDto
import retrofit2.http.Body
import retrofit2.http.GET
import retrofit2.http.POST
import retrofit2.http.PUT
import retrofit2.http.Path
import retrofit2.http.Query

/**
 * 健康 REST API（前缀 /api/v1/health）。
 */
interface HealthApi {

    // ---------------- Weight ----------------

    @GET("api/v1/health/weight")
    suspend fun weights(
        @Query("skip") skip: Int = 0,
        @Query("limit") limit: Int = -1,
        @Query("start") start: Double? = null,
        @Query("end") end: Double? = null,
    ): List<WeightDto>

    @POST("api/v1/health/weight")
    suspend fun createWeight(@Body body: WeightCreateRequest): WeightDto

    @GET("api/v1/health/weight/target")
    suspend fun targetWeight(@Query("date") date: String): WeightDto?

    @GET("api/v1/health/weight/avg")
    suspend fun weightAvg(
        @Query("start") start: Double? = null,
        @Query("end") end: Double? = null,
    ): Map<String, Double?>

    @GET("api/v1/health/weight/analysis")
    suspend fun weightAnalysis(
        @Query("start") start: Double? = null,
        @Query("end") end: Double? = null,
        @Query("model_type") modelType: String = "linear",
    ): Map<String, Any>

    // ---------------- Weight Plan ----------------

    @GET("api/v1/health/weight/plan")
    suspend fun activeWeightPlan(): WeightPlanDto?

    @POST("api/v1/health/weight/plan")
    suspend fun createWeightPlan(@Body body: WeightPlanCreateRequest): WeightPlanDto

    @GET("api/v1/health/weight/plan/progress")
    suspend fun weightPlanProgress(
        @Query("plan_id") planId: Int? = null,
    ): WeightPlanProgressDto?

    @GET("api/v1/health/weight/plan/checkin-status")
    suspend fun weightPlanCheckinStatus(
        @Query("plan_id") planId: Int? = null,
    ): WeightPlanCheckinStatusDto?

    @GET("api/v1/health/weight/plan/weights-with-status")
    suspend fun weightsWithStatus(
        @Query("start") start: Double? = null,
        @Query("end") end: Double? = null,
        @Query("plan_id") planId: Int? = null,
    ): List<WeightWithStatusDto>

    @GET("api/v1/health/weight/plan/expected")
    suspend fun weightPlanExpected(
        @Query("start") start: Double,
        @Query("end") end: Double,
        @Query("plan_id") planId: Int? = null,
    ): WeightExpectedRangeDto?

    // ---------------- Exercise ----------------

    @GET("api/v1/health/exercise")
    suspend fun exercises(
        @Query("skip") skip: Int = 0,
        @Query("limit") limit: Int = -1,
        @Query("start") start: Double? = null,
        @Query("end") end: Double? = null,
    ): List<ExerciseDto>

    @POST("api/v1/health/exercise")
    suspend fun createExercise(@Body body: ExerciseCreateRequest): ExerciseDto

    // ---------------- Sleep ----------------

    @GET("api/v1/health/sleep")
    suspend fun sleeps(
        @Query("skip") skip: Int = 0,
        @Query("limit") limit: Int = -1,
        @Query("start") start: Double? = null,
        @Query("end") end: Double? = null,
    ): List<SleepDto>

    @POST("api/v1/health/sleep")
    suspend fun createSleep(@Body body: SleepCreateRequest): SleepDto

    // ---------------- Sleep Schedule ----------------

    @GET("api/v1/health/sleep-schedule")
    suspend fun sleepScheduleGoal(@Query("date") date: String? = null): SleepScheduleGoalDto?

    @POST("api/v1/health/sleep-schedule")
    suspend fun createOrUpdateSleepScheduleGoal(@Body body: SleepScheduleGoalCreateRequest): SleepScheduleGoalDto

    // ---------------- Medication ----------------

    @GET("api/v1/health/medication")
    suspend fun medications(
        @Query("date") date: String? = null,
        @Query("taken") taken: Boolean? = null,
        @Query("skip") skip: Int = 0,
        @Query("limit") limit: Int = -1,
    ): List<MedicationDto>

    @POST("api/v1/health/medication")
    suspend fun createMedication(@Body body: MedicationCreateRequest): MedicationDto

    @PUT("api/v1/health/medication/{id}")
    suspend fun updateMedication(
        @Path("id") id: Int,
        @Body body: MedicationUpdateRequest,
    ): MedicationDto

    @GET("api/v1/health/medication/today")
    suspend fun medicationToday(@Query("date") date: String? = null): MedicationTodayDto

    @GET("api/v1/health/medication/stats")
    suspend fun medicationStats(
        @Query("days") days: Int = 7,
        @Query("end_date") endDate: String? = null,
    ): MedicationStatsDto

    // ---------------- Diet ----------------

    @GET("api/v1/health/diet")
    suspend fun diets(
        @Query("date") date: String? = null,
        @Query("meal_type") mealType: String? = null,
        @Query("skip") skip: Int = 0,
        @Query("limit") limit: Int = -1,
    ): List<DietDto>

    @POST("api/v1/health/diet")
    suspend fun createDiet(@Body body: DietCreateRequest): DietDto

    @GET("api/v1/health/diet/summary")
    suspend fun dietSummary(@Query("date") date: String? = null): DietSummaryDto

    @GET("api/v1/health/diet/goal")
    suspend fun nutritionGoal(@Query("date") date: String? = null): NutritionGoalDto?

    @POST("api/v1/health/diet/goal")
    suspend fun createOrUpdateNutritionGoal(@Body body: NutritionGoalCreateRequest): NutritionGoalDto

    // ---------------- Dashboard ----------------

    @GET("api/v1/health/dashboard")
    suspend fun dashboard(@Query("date") date: String? = null): HealthDashboardDto
}
