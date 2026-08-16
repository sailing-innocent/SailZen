package com.sailzen.app.feature.exercise

import android.app.Application
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import com.sailzen.app.core.health.HealthRepository
import com.sailzen.app.core.network.dto.ExerciseCreateRequest
import com.sailzen.app.core.network.dto.ExerciseDto
import java.time.LocalDate
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch

class ExerciseViewModel(application: Application) : AndroidViewModel(application) {

    data class UiState(
        val selectedDate: LocalDate = LocalDate.now(),
        val exercises: List<ExerciseDto> = emptyList(),
        val goalMinutes: Int = 30,
        val loading: Boolean = false,
    )

    private val repository = HealthRepository.get(application)

    private val _uiState = MutableStateFlow(UiState())
    val uiState: StateFlow<UiState> = _uiState.asStateFlow()

    init {
        load()
    }

    fun load() {
        viewModelScope.launch {
            _uiState.update { it.copy(loading = true) }
            val exercises = repository.exercises(_uiState.value.selectedDate, _uiState.value.selectedDate)
            _uiState.update { it.copy(loading = false, exercises = exercises) }
        }
    }

    fun setGoal(minutes: Int) = _uiState.update { it.copy(goalMinutes = minutes) }

    fun recordExercise(type: String, minutes: Int, calories: Int) {
        viewModelScope.launch {
            repository.createExercise(
                ExerciseCreateRequest(
                    exerciseType = type,
                    durationMinutes = minutes,
                    calories = calories,
                    htime = System.currentTimeMillis() / 1000.0,
                ),
            )
            load()
        }
    }
}
