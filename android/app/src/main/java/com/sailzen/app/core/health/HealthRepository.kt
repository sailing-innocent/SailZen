package com.sailzen.app.core.health

import android.content.Context
import android.util.Log
import com.sailzen.app.core.data.SettingsManager
import com.sailzen.app.core.network.ApiClient
import com.sailzen.app.core.network.HealthApi
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
import com.sailzen.app.core.network.dto.WeightExpectedRangeDto
import com.sailzen.app.core.network.dto.WeightDto
import com.sailzen.app.core.network.dto.WeightPlanCheckinStatusDto
import com.sailzen.app.core.network.dto.WeightPlanCreateRequest
import com.sailzen.app.core.network.dto.WeightPlanDto
import com.sailzen.app.core.network.dto.WeightPlanProgressDto
import com.sailzen.app.core.network.dto.WeightWithStatusDto
import java.time.LocalDate
import java.time.ZoneId
import java.time.format.DateTimeFormatter
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow

/**
 * 健康模块数据仓库（M1）：封装 HealthApi，提供在线直读/直写能力。
 * 离线队列在后续迭代中由 RhythmRepository / SyncWorker 统一补传。
 */
class HealthRepository private constructor(private val context: Context) {

    companion object {
        private const val TAG = "HealthRepository"

        @Volatile
        private var instance: HealthRepository? = null

        fun get(context: Context): HealthRepository =
            instance ?: synchronized(this) {
                instance ?: HealthRepository(context.applicationContext).also { instance = it }
            }
    }

    private val settings = SettingsManager.get(context)

    private val _dashboard = MutableStateFlow<HealthDashboardDto?>(null)
    val dashboard: StateFlow<HealthDashboardDto?> = _dashboard.asStateFlow()

    private suspend fun apiOrNull(): HealthApi? {
        val url = settings.serverUrl()
        if (url.isBlank()) return null
        return try {
            ApiClient.healthApi(url, settings.apiToken())
        } catch (e: Exception) {
            Log.w(TAG, "api build failed: ${e.message}")
            null
        }
    }

    fun isoDate(date: LocalDate): String = date.format(DateTimeFormatter.ISO_LOCAL_DATE)

    fun epochSeconds(date: LocalDate): Double =
        date.atStartOfDay(ZoneId.systemDefault()).toEpochSecond().toDouble()

    fun epochSecondsEnd(date: LocalDate): Double =
        date.plusDays(1).atStartOfDay(ZoneId.systemDefault()).toEpochSecond().toDouble() - 1

    // ------------------------------------------------------------------
    // Dashboard
    // ------------------------------------------------------------------

    suspend fun loadDashboard(date: LocalDate = LocalDate.now()): HealthDashboardDto? = try {
        apiOrNull()?.dashboard(isoDate(date)).also { _dashboard.value = it }
    } catch (e: Exception) {
        Log.w(TAG, "loadDashboard failed: ${e.message}")
        null
    }

    fun observeDashboard(): Flow<HealthDashboardDto?> = dashboard

    // ------------------------------------------------------------------
    // Weight
    // ------------------------------------------------------------------

    suspend fun weights(
        start: LocalDate? = null,
        end: LocalDate? = null,
        limit: Int = -1,
    ): List<WeightDto> = try {
        apiOrNull()?.weights(
            limit = limit,
            start = start?.let { epochSeconds(it) },
            end = end?.let { epochSecondsEnd(it) },
        ) ?: emptyList()
    } catch (e: Exception) {
        Log.w(TAG, "weights failed: ${e.message}")
        emptyList()
    }

    suspend fun createWeight(value: Double, htime: Double? = null, note: String = ""): WeightDto? = try {
        apiOrNull()?.createWeight(
            WeightCreateRequest(value = value, htime = htime, description = note),
        )
    } catch (e: Exception) {
        Log.w(TAG, "createWeight failed: ${e.message}")
        null
    }

    suspend fun activeWeightPlan(): WeightPlanDto? = try {
        apiOrNull()?.activeWeightPlan()
    } catch (e: Exception) {
        Log.w(TAG, "activeWeightPlan failed: ${e.message}")
        null
    }

    suspend fun createWeightPlan(body: WeightPlanCreateRequest): WeightPlanDto? = try {
        apiOrNull()?.createWeightPlan(body)
    } catch (e: Exception) {
        Log.w(TAG, "createWeightPlan failed: ${e.message}")
        null
    }

    suspend fun weightPlanProgress(): WeightPlanProgressDto? = try {
        apiOrNull()?.weightPlanProgress()
    } catch (e: Exception) {
        Log.w(TAG, "weightPlanProgress failed: ${e.message}")
        null
    }

    suspend fun weightPlanCheckinStatus(): WeightPlanCheckinStatusDto? = try {
        apiOrNull()?.weightPlanCheckinStatus()
    } catch (e: Exception) {
        Log.w(TAG, "weightPlanCheckinStatus failed: ${e.message}")
        null
    }

    suspend fun weightsWithStatus(
        start: LocalDate? = null,
        end: LocalDate? = null,
    ): List<WeightWithStatusDto> = try {
        apiOrNull()?.weightsWithStatus(
            start = start?.let { epochSeconds(it) },
            end = end?.let { epochSecondsEnd(it) },
        ) ?: emptyList()
    } catch (e: Exception) {
        Log.w(TAG, "weightsWithStatus failed: ${e.message}")
        emptyList()
    }

    suspend fun weightPlanExpected(
        start: LocalDate,
        end: LocalDate,
    ): WeightExpectedRangeDto? = try {
        apiOrNull()?.weightPlanExpected(
            start = epochSeconds(start),
            end = epochSecondsEnd(end),
        )
    } catch (e: Exception) {
        Log.w(TAG, "weightPlanExpected failed: ${e.message}")
        null
    }


    suspend fun exercises(
        start: LocalDate? = null,
        end: LocalDate? = null,
    ): List<ExerciseDto> = try {
        apiOrNull()?.exercises(
            start = start?.let { epochSeconds(it) },
            end = end?.let { epochSecondsEnd(it) },
        ) ?: emptyList()
    } catch (e: Exception) {
        Log.w(TAG, "exercises failed: ${e.message}")
        emptyList()
    }

    suspend fun createExercise(body: ExerciseCreateRequest): ExerciseDto? = try {
        apiOrNull()?.createExercise(body)
    } catch (e: Exception) {
        Log.w(TAG, "createExercise failed: ${e.message}")
        null
    }

    // ------------------------------------------------------------------
    // Sleep
    // ------------------------------------------------------------------

    suspend fun sleeps(
        start: LocalDate? = null,
        end: LocalDate? = null,
    ): List<SleepDto> = try {
        apiOrNull()?.sleeps(
            start = start?.let { epochSeconds(it) },
            end = end?.let { epochSecondsEnd(it) },
        ) ?: emptyList()
    } catch (e: Exception) {
        Log.w(TAG, "sleeps failed: ${e.message}")
        emptyList()
    }

    suspend fun createSleep(body: SleepCreateRequest): SleepDto? = try {
        apiOrNull()?.createSleep(body)
    } catch (e: Exception) {
        Log.w(TAG, "createSleep failed: ${e.message}")
        null
    }

    suspend fun sleepScheduleGoal(date: LocalDate): SleepScheduleGoalDto? = try {
        apiOrNull()?.sleepScheduleGoal(isoDate(date))
    } catch (e: Exception) {
        Log.w(TAG, "sleepScheduleGoal failed: ${e.message}")
        null
    }

    suspend fun createOrUpdateSleepScheduleGoal(body: SleepScheduleGoalCreateRequest): SleepScheduleGoalDto? = try {
        apiOrNull()?.createOrUpdateSleepScheduleGoal(body)
    } catch (e: Exception) {
        Log.w(TAG, "createOrUpdateSleepScheduleGoal failed: ${e.message}")
        null
    }

    // ------------------------------------------------------------------
    // Medication
    // ------------------------------------------------------------------

    suspend fun medications(date: LocalDate): List<MedicationDto> = try {
        apiOrNull()?.medications(date = isoDate(date)) ?: emptyList()
    } catch (e: Exception) {
        Log.w(TAG, "medications failed: ${e.message}")
        emptyList()
    }

    suspend fun medicationToday(date: LocalDate): MedicationTodayDto? = try {
        apiOrNull()?.medicationToday(isoDate(date))
    } catch (e: Exception) {
        Log.w(TAG, "medicationToday failed: ${e.message}")
        null
    }

    suspend fun medicationStats(days: Int = 7): MedicationStatsDto? = try {
        apiOrNull()?.medicationStats(days = days)
    } catch (e: Exception) {
        Log.w(TAG, "medicationStats failed: ${e.message}")
        null
    }

    suspend fun createMedication(body: MedicationCreateRequest): MedicationDto? = try {
        apiOrNull()?.createMedication(body)
    } catch (e: Exception) {
        Log.w(TAG, "createMedication failed: ${e.message}")
        null
    }

    suspend fun takeMedication(id: Int): MedicationDto? = try {
        apiOrNull()?.updateMedication(
            id,
            MedicationUpdateRequest(taken = true, takenAt = System.currentTimeMillis() / 1000.0),
        )
    } catch (e: Exception) {
        Log.w(TAG, "takeMedication failed: ${e.message}")
        null
    }

    // ------------------------------------------------------------------
    // Diet
    // ------------------------------------------------------------------

    suspend fun diets(date: LocalDate): List<DietDto> = try {
        apiOrNull()?.diets(date = isoDate(date)) ?: emptyList()
    } catch (e: Exception) {
        Log.w(TAG, "diets failed: ${e.message}")
        emptyList()
    }

    suspend fun createDiet(body: DietCreateRequest): DietDto? = try {
        apiOrNull()?.createDiet(body)
    } catch (e: Exception) {
        Log.w(TAG, "createDiet failed: ${e.message}")
        null
    }

    suspend fun dietSummary(date: LocalDate): DietSummaryDto? = try {
        apiOrNull()?.dietSummary(isoDate(date))
    } catch (e: Exception) {
        Log.w(TAG, "dietSummary failed: ${e.message}")
        null
    }

    suspend fun nutritionGoal(date: LocalDate): NutritionGoalDto? = try {
        apiOrNull()?.nutritionGoal(isoDate(date))
    } catch (e: Exception) {
        Log.w(TAG, "nutritionGoal failed: ${e.message}")
        null
    }

    suspend fun createOrUpdateNutritionGoal(body: NutritionGoalCreateRequest): NutritionGoalDto? = try {
        apiOrNull()?.createOrUpdateNutritionGoal(body)
    } catch (e: Exception) {
        Log.w(TAG, "createOrUpdateNutritionGoal failed: ${e.message}")
        null
    }
}
