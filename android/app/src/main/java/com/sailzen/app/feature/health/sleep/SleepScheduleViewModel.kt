package com.sailzen.app.feature.health.sleep

import android.app.Application
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import com.sailzen.app.core.health.HealthRepository
import com.sailzen.app.core.network.dto.SleepCreateRequest
import com.sailzen.app.core.network.dto.SleepDto
import com.sailzen.app.core.network.dto.SleepScheduleGoalCreateRequest
import com.sailzen.app.core.network.dto.SleepScheduleGoalDto
import java.time.LocalDate
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch

class SleepScheduleViewModel(application: Application) : AndroidViewModel(application) {

    data class UiState(
        val selectedDate: LocalDate = LocalDate.now(),
        val goal: SleepScheduleGoalDto? = null,
        val sleeps: List<SleepDto> = emptyList(),
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
            val goal = repository.sleepScheduleGoal(_uiState.value.selectedDate)
            val sleeps = repository.sleeps(
                _uiState.value.selectedDate.minusDays(7),
                _uiState.value.selectedDate,
            )
            _uiState.update { it.copy(loading = false, goal = goal, sleeps = sleeps) }
        }
    }

    fun saveGoal(bedTime: String, wakeTime: String, targetHours: Double) {
        viewModelScope.launch {
            repository.createOrUpdateSleepScheduleGoal(
                SleepScheduleGoalCreateRequest(
                    date = repository.isoDate(_uiState.value.selectedDate),
                    bedTime = bedTime,
                    wakeTime = wakeTime,
                    targetHours = targetHours,
                ),
            )
            load()
        }
    }

    fun recordSleep(hours: Double, quality: Int) {
        viewModelScope.launch {
            repository.createSleep(
                SleepCreateRequest(
                    hours = hours,
                    quality = quality,
                    description = "",
                    htime = System.currentTimeMillis() / 1000.0,
                ),
            )
            load()
        }
    }
}
