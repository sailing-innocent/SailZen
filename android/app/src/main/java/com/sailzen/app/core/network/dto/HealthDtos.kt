package com.sailzen.app.core.network.dto

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable
import kotlinx.serialization.json.JsonObject

/**
 * 与服务端 sail_server.application.dto.health 对齐的网络 DTO。
 * 时间字段使用 float 时间戳（秒）或 ISO 日期字符串，按字段约定。
 */

@Serializable
enum class WeightPlanCurveType {
    linear, polynomial, exponential
}

@Serializable
data class WeightDto(
    val id: Int,
    val value: Double,
    val htime: Double? = null,
    val tag: String = "raw",
    val description: String = "",
)

@Serializable
data class WeightCreateRequest(
    val value: Double,
    val htime: Double? = null,
    val tag: String = "raw",
    val description: String = "",
)

@Serializable
data class WeightPlanDto(
    val id: Int,
    val targetWeight: String,
    val initialWeight: String? = null,
    val curveType: WeightPlanCurveType = WeightPlanCurveType.linear,
    val startTime: Double? = null,
    val targetTime: Double? = null,
    val description: String = "",
    val notifyEnabled: Boolean = false,
    val notifyTime: String = "08:30",
    val feedbackEnabled: Boolean = false,
    val rhythmAffairId: Int? = null,
)

@Serializable
data class WeightPlanCreateRequest(
    val targetWeight: String,
    val initialWeight: String? = null,
    val curveType: WeightPlanCurveType = WeightPlanCurveType.linear,
    val startTime: String? = null,
    val targetTime: String? = null,
    val description: String = "",
    val notifyEnabled: Boolean = false,
    val notifyTime: String = "08:30",
    val feedbackEnabled: Boolean = false,
)

@Serializable
data class WeightPlanProgressDto(
    val plan: JsonObject? = null,
    val controlRate: Double = 0.0,
    val currentWeight: Double = 0.0,
    val expectedCurrentWeight: Double = 0.0,
    val dailyPredictions: List<JsonObject> = emptyList(),
    val isOnTrack: Boolean = false,
)

@Serializable
data class WeightPlanCheckinStatusDto(
    val planId: Int,
    val affairId: Int,
    val todayDone: Boolean = false,
    val streak: Int = 0,
)

@Serializable
data class WeightExpectedPointDto(
    val htime: Double,
    val expectedWeight: Double,
)

@Serializable
data class WeightExpectedRangeDto(
    val plan: WeightPlanDto? = null,
    val points: List<WeightExpectedPointDto> = emptyList(),
)

@Serializable
data class WeightWithStatusDto(
    val id: Int,
    val value: Double,
    val htime: Double? = null,
    val expectedValue: Double = 0.0,
    val status: String = "normal", // above | below | normal
    val diff: Double = 0.0,
)

@Serializable
data class ExerciseDto(
    val id: Int,
    val htime: Double? = null,
    val description: String = "",
    val exerciseType: String = "",
    val durationMinutes: Int = 0,
    val calories: Int = 0,
    val completed: Boolean = true,
    val source: String = "health",
)

@Serializable
data class ExerciseCreateRequest(
    val htime: Double? = null,
    val description: String = "",
    val exerciseType: String = "",
    val durationMinutes: Int = 0,
    val calories: Int = 0,
    val completed: Boolean = true,
    val source: String = "health",
)

@Serializable
data class SleepDto(
    val id: Int,
    val dayId: Int? = null,
    val hours: Double = 0.0,
    val quality: Int = 3,
    val description: String = "",
    val htime: Double? = null,
)

@Serializable
data class SleepCreateRequest(
    val dayId: Int? = null,
    val hours: Double = 0.0,
    val quality: Int = 3,
    val description: String = "",
    val htime: Double? = null,
)

@Serializable
data class SleepScheduleGoalDto(
    val id: Int,
    val date: String,
    val bedTime: String = "23:00",
    val wakeTime: String = "07:00",
    val targetHours: Double = 8.0,
)

@Serializable
data class SleepScheduleGoalCreateRequest(
    val date: String,
    val bedTime: String = "23:00",
    val wakeTime: String = "07:00",
    val targetHours: Double = 8.0,
)

@Serializable
data class MedicationDto(
    val id: Int,
    val name: String,
    val dosage: String = "",
    val frequency: String = "daily",
    val scheduleTimes: List<String> = emptyList(),
    val plannedDate: String? = null,
    val taken: Boolean = false,
    val note: String = "",
    val isSupplement: Boolean = false,
    val htime: Double? = null,
    val takenAt: Double? = null,
)

@Serializable
data class MedicationCreateRequest(
    val name: String,
    val dosage: String = "",
    val frequency: String = "daily",
    val scheduleTimes: List<String> = emptyList(),
    val plannedDate: String? = null,
    val taken: Boolean = false,
    val note: String = "",
    val isSupplement: Boolean = false,
    val htime: Double? = null,
    val takenAt: Double? = null,
)

@Serializable
data class MedicationUpdateRequest(
    val taken: Boolean = true,
    val takenAt: Double? = null,
    val note: String? = null,
)

@Serializable
data class MedicationTodayDto(
    val date: String,
    val medications: List<MedicationDto> = emptyList(),
    val total: Int = 0,
    val taken: Int = 0,
    val compliance: Double = 0.0,
)

@Serializable
data class MedicationStatsDto(
    val days: Int = 7,
    val total: Int = 0,
    val taken: Int = 0,
    val compliance: Double = 0.0,
)

@Serializable
data class MealType(val value: String)

@Serializable
data class DietDto(
    val id: Int,
    val mealType: String = "snack",
    val description: String = "",
    val photoPath: String? = null,
    val calories: Double? = null,
    val carbs: Double? = null,
    val sugar: Double? = null,
    val protein: Double? = null,
    val fat: Double? = null,
    val fiber: Double? = null,
    val sodium: Double? = null,
    val micronutrients: Map<String, Double> = emptyMap(),
    val htime: Double? = null,
)

@Serializable
data class DietCreateRequest(
    val mealType: String = "snack",
    val description: String = "",
    val photoPath: String? = null,
    val calories: Double? = null,
    val carbs: Double? = null,
    val sugar: Double? = null,
    val protein: Double? = null,
    val fat: Double? = null,
    val fiber: Double? = null,
    val sodium: Double? = null,
    val micronutrients: Map<String, Double> = emptyMap(),
    val htime: Double? = null,
)

@Serializable
data class NutrientActualVsGoalDto(
    val actual: Double? = null,
    val goal: Double? = null,
    val unit: String = "g",
)

@Serializable
data class DietSummaryDto(
    val date: String,
    val calories: NutrientActualVsGoalDto = NutrientActualVsGoalDto(),
    val carbs: NutrientActualVsGoalDto = NutrientActualVsGoalDto(),
    val sugar: NutrientActualVsGoalDto = NutrientActualVsGoalDto(),
    val protein: NutrientActualVsGoalDto = NutrientActualVsGoalDto(),
    val fat: NutrientActualVsGoalDto = NutrientActualVsGoalDto(),
    val fiber: NutrientActualVsGoalDto = NutrientActualVsGoalDto(),
    val sodium: NutrientActualVsGoalDto = NutrientActualVsGoalDto(),
    val micronutrients: Map<String, Double> = emptyMap(),
)

@Serializable
data class NutritionGoalDto(
    val id: Int,
    val date: String,
    val calories: Double? = null,
    val carbs: Double? = null,
    val sugar: Double? = null,
    val protein: Double? = null,
    val fat: Double? = null,
    val fiber: Double? = null,
    val sodium: Double? = null,
    val micronutrients: Map<String, Double> = emptyMap(),
)

@Serializable
data class NutritionGoalCreateRequest(
    val date: String,
    val calories: Double? = null,
    val carbs: Double? = null,
    val sugar: Double? = null,
    val protein: Double? = null,
    val fat: Double? = null,
    val fiber: Double? = null,
    val sodium: Double? = null,
    val micronutrients: Map<String, Double> = emptyMap(),
)

@Serializable
data class DashboardWeightItemDto(
    val latest: Double? = null,
    val planTarget: Double? = null,
    val status: String = "normal",
)

@Serializable
data class DashboardSleepItemDto(
    val lastNightHours: Double? = null,
    val goal: Double? = null,
    val status: String = "normal",
)

@Serializable
data class DashboardExerciseItemDto(
    val todayMinutes: Int = 0,
    val goalMinutes: Int = 0,
    val completed: Boolean = false,
)

@Serializable
data class DashboardMedicationItemDto(
    val total: Int = 0,
    val taken: Int = 0,
    val compliance: Double = 0.0,
)

@Serializable
data class DashboardDietItemDto(
    val caloriesActual: Double? = null,
    val caloriesGoal: Double? = null,
    val sugarActual: Double? = null,
    val sugarGoal: Double? = null,
)

@Serializable
data class DashboardMoodItemDto(
    val score: Int? = null,
)

@Serializable
data class HealthDashboardDto(
    val date: String,
    val weight: DashboardWeightItemDto = DashboardWeightItemDto(),
    val sleep: DashboardSleepItemDto = DashboardSleepItemDto(),
    val exercise: DashboardExerciseItemDto = DashboardExerciseItemDto(),
    val medication: DashboardMedicationItemDto = DashboardMedicationItemDto(),
    val diet: DashboardDietItemDto = DashboardDietItemDto(),
    val mood: DashboardMoodItemDto = DashboardMoodItemDto(),
    val warnings: List<String> = emptyList(),
)
