package com.sailzen.app.feature.health

import android.app.Application
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import com.sailzen.app.core.network.dto.HealthCheckinResponse
import com.sailzen.app.core.network.dto.InfoCollectionType
import com.sailzen.app.core.rhythm.RhythmRepository
import java.time.LocalDate
import java.time.LocalDateTime
import java.time.ZoneId
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch

class HealthCheckinViewModel(application: Application) : AndroidViewModel(application) {

    data class UiState(
        val selectedType: InfoCollectionType = InfoCollectionType.weight,
        val date: LocalDate = LocalDate.now(),
        val time: String = LocalDateTime.now().let { "%02d:%02d".format(it.hour, it.minute) },
        val note: String = "",
        // weight
        val weight: String = "",
        // exercise
        val exerciseType: String = "",
        val exerciseMinutes: String = "",
        val exerciseCalories: String = "",
        // meal
        val mealType: String = "snack",
        val mealDescription: String = "",
        val mealCalories: String = "",
        // medication
        val medicationName: String = "",
        val medicationDosage: String = "",
        val medicationTaken: Boolean = false,
        // sleep
        val sleepHours: String = "",
        val sleepQuality: String = "3",
        // mood
        val moodScore: String = "",
        val submitting: Boolean = false,
        val submitted: HealthCheckinResponse? = null,
        val error: String? = null,
    )

    private val repository = RhythmRepository.get(application)

    private val _uiState = MutableStateFlow(UiState())
    val uiState: StateFlow<UiState> = _uiState.asStateFlow()

    fun selectType(type: InfoCollectionType) = _uiState.update { it.copy(selectedType = type) }
    fun setDate(date: LocalDate) = _uiState.update { it.copy(date = date) }
    fun setTime(time: String) = _uiState.update { it.copy(time = time) }
    fun setNote(v: String) = _uiState.update { it.copy(note = v) }
    fun setWeight(v: String) = _uiState.update { it.copy(weight = v) }
    fun setExerciseType(v: String) = _uiState.update { it.copy(exerciseType = v) }
    fun setExerciseMinutes(v: String) = _uiState.update { it.copy(exerciseMinutes = v) }
    fun setExerciseCalories(v: String) = _uiState.update { it.copy(exerciseCalories = v) }
    fun setMealType(v: String) = _uiState.update { it.copy(mealType = v) }
    fun setMealDescription(v: String) = _uiState.update { it.copy(mealDescription = v) }
    fun setMealCalories(v: String) = _uiState.update { it.copy(mealCalories = v) }
    fun setMedicationName(v: String) = _uiState.update { it.copy(medicationName = v) }
    fun setMedicationDosage(v: String) = _uiState.update { it.copy(medicationDosage = v) }
    fun setMedicationTaken(v: Boolean) = _uiState.update { it.copy(medicationTaken = v) }
    fun setSleepHours(v: String) = _uiState.update { it.copy(sleepHours = v) }
    fun setSleepQuality(v: String) = _uiState.update { it.copy(sleepQuality = v) }
    fun setMoodScore(v: String) = _uiState.update { it.copy(moodScore = v) }
    fun dismissSubmitted() = _uiState.update { it.copy(submitted = null) }
    fun dismissError() = _uiState.update { it.copy(error = null) }

    private fun timestampSeconds(): Double {
        val state = _uiState.value
        val timeParts = state.time.split(":")
        val hour = timeParts.getOrNull(0)?.toIntOrNull() ?: 0
        val minute = timeParts.getOrNull(1)?.toIntOrNull() ?: 0
        return state.date.atTime(hour, minute).atZone(ZoneId.systemDefault()).toEpochSecond().toDouble()
    }

    fun submit() {
        val state = _uiState.value
        val htime = timestampSeconds()
        val payload = when (state.selectedType) {
            InfoCollectionType.weight -> mapOf(
                "value_kg" to state.weight.toDoubleOrNull().orZero(),
                "measured_at" to htime,
            )
            InfoCollectionType.exercise -> mapOf(
                "exercise_type" to state.exerciseType,
                "duration_minutes" to state.exerciseMinutes.toIntOrNull().orZero(),
                "calories" to state.exerciseCalories.toIntOrNull().orZero(),
                "htime" to htime,
            )
            InfoCollectionType.meal -> mapOf(
                "meal_type" to state.mealType,
                "description" to state.mealDescription,
                "calories" to state.mealCalories.toDoubleOrNull().orZero(),
                "htime" to htime,
            )
            InfoCollectionType.medication -> mapOf(
                "name" to state.medicationName,
                "dosage" to state.medicationDosage,
                "taken" to state.medicationTaken,
                "planned_date" to state.date.toString(),
                "taken_at" to if (state.medicationTaken) htime else null,
                "htime" to htime,
            )
            InfoCollectionType.sleep -> mapOf(
                "hours" to state.sleepHours.toDoubleOrNull().orZero(),
                "quality" to state.sleepQuality.toIntOrNull().orZero(),
                "htime" to htime,
            )
            InfoCollectionType.mood -> mapOf(
                "score" to state.moodScore.toIntOrNull().orZero(),
                "htime" to htime,
            )
        }

        viewModelScope.launch {
            _uiState.update { it.copy(submitting = true, error = null) }
            val result = repository.healthCheckin(
                collectionType = state.selectedType,
                payload = payload,
                note = state.note,
                date = state.date,
            )
            _uiState.update {
                if (result != null) {
                    it.copy(submitting = false, submitted = result)
                } else {
                    it.copy(submitting = false, error = "提交失败，请检查网络或服务器配置")
                }
            }
        }
    }

    private fun Double?.orZero() = this ?: 0.0
    private fun Int?.orZero() = this ?: 0
}
