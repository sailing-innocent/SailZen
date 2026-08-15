package com.sailzen.app.feature.health

import android.app.Application
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import com.sailzen.app.core.network.dto.HealthCheckinResponse
import com.sailzen.app.core.network.dto.InfoCollectionType
import com.sailzen.app.core.rhythm.RhythmRepository
import java.time.LocalDate
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch

class HealthCheckinViewModel(application: Application) : AndroidViewModel(application) {

    data class UiState(
        val selectedType: InfoCollectionType = InfoCollectionType.weight,
        val note: String = "",
        val value: String = "",
        val activity: String = "",
        val duration: String = "",
        val submitting: Boolean = false,
        val submitted: HealthCheckinResponse? = null,
        val error: String? = null,
    )

    private val repository = RhythmRepository.get(application)

    private val _uiState = MutableStateFlow(UiState())
    val uiState: StateFlow<UiState> = _uiState.asStateFlow()

    fun selectType(type: InfoCollectionType) = _uiState.update { it.copy(selectedType = type) }
    fun setNote(v: String) = _uiState.update { it.copy(note = v) }
    fun setValue(v: String) = _uiState.update { it.copy(value = v) }
    fun setActivity(v: String) = _uiState.update { it.copy(activity = v) }
    fun setDuration(v: String) = _uiState.update { it.copy(duration = v) }
    fun dismissSubmitted() = _uiState.update { it.copy(submitted = null) }
    fun dismissError() = _uiState.update { it.copy(error = null) }

    fun submit(date: LocalDate = LocalDate.now()) {
        val state = _uiState.value
        val payload = when (state.selectedType) {
            InfoCollectionType.weight -> mapOf("value_kg" to state.value.toDoubleOrNull().orZero())
            InfoCollectionType.exercise -> mapOf(
                "activity" to state.activity,
                "duration_minutes" to state.duration.toIntOrNull().orZero(),
            )
            InfoCollectionType.meal -> mapOf("meal_type" to "snack")
            InfoCollectionType.medication -> mapOf("name" to state.activity)
            InfoCollectionType.sleep -> mapOf("hours" to state.value.toIntOrNull().orZero())
            InfoCollectionType.mood -> mapOf("score" to state.value.toIntOrNull().orZero())
        }

        viewModelScope.launch {
            _uiState.update { it.copy(submitting = true, error = null) }
            val result = repository.healthCheckin(
                collectionType = state.selectedType,
                payload = payload,
                note = state.note,
                date = date,
            )
            _uiState.update {
                if (result != null) {
                    it.copy(submitting = false, submitted = result, value = "", activity = "", duration = "")
                } else {
                    it.copy(submitting = false, error = "提交失败，请检查网络或服务器配置")
                }
            }
        }
    }

    private fun Double?.orZero() = this ?: 0.0
    private fun Int?.orZero() = this ?: 0
}
