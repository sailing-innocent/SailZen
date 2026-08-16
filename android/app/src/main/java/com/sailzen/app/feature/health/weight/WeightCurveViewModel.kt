package com.sailzen.app.feature.health.weight

import android.app.Application
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import com.sailzen.app.core.health.HealthRepository
import com.sailzen.app.core.network.dto.WeightDto
import com.sailzen.app.core.network.dto.WeightExpectedRangeDto
import com.sailzen.app.core.network.dto.WeightWithStatusDto
import java.time.LocalDate
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch

class WeightCurveViewModel(application: Application) : AndroidViewModel(application) {

    data class UiState(
        val rangeLabel: String = "近 7 天",
        val weights: List<WeightDto> = emptyList(),
        val expected: WeightExpectedRangeDto? = null,
        val weightsWithStatus: List<WeightWithStatusDto> = emptyList(),
        val loading: Boolean = false,
    )

    private val repository = HealthRepository.get(application)

    private val _uiState = MutableStateFlow(UiState())
    val uiState: StateFlow<UiState> = _uiState.asStateFlow()

    private val rangeOptions = mapOf(
        "近 7 天" to 7L,
        "近 30 天" to 30L,
        "近 90 天" to 90L,
    )

    init {
        load()
    }

    fun selectRange(label: String) {
        _uiState.update { it.copy(rangeLabel = label) }
        load()
    }

    fun load() {
        viewModelScope.launch {
            _uiState.update { it.copy(loading = true) }
            val days = rangeOptions[_uiState.value.rangeLabel] ?: 7L
            val end = LocalDate.now()
            val start = end.minusDays(days - 1)
            val weights = repository.weights(start, end)
            val expected = repository.weightPlanExpected(start, end)
            val weightsWithStatus = repository.weightsWithStatus(start, end)
            _uiState.update {
                it.copy(
                    loading = false,
                    weights = weights,
                    expected = expected,
                    weightsWithStatus = weightsWithStatus,
                )
            }
        }
    }
}
