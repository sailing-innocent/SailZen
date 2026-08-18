package com.sailzen.app.feature.health

import android.app.Application
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import com.sailzen.app.R
import com.sailzen.app.core.health.HealthRepository
import com.sailzen.app.core.network.dto.HealthDashboardDto
import java.time.LocalDate
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch

class HealthHomeViewModel(application: Application) : AndroidViewModel(application) {

    data class UiState(
        val selectedDate: LocalDate = LocalDate.now(),
        val dashboard: HealthDashboardDto? = null,
        val loading: Boolean = false,
        val error: String? = null,
    )

    private val repository = HealthRepository.get(application)

    private val _uiState = MutableStateFlow(UiState())
    val uiState: StateFlow<UiState> = _uiState.asStateFlow()

    init {
        refresh()
    }

    fun selectDate(date: LocalDate) {
        _uiState.update { it.copy(selectedDate = date) }
        refresh()
    }

    fun refresh() {
        viewModelScope.launch {
            _uiState.update { it.copy(loading = true, error = null) }
            val result = repository.loadDashboard(_uiState.value.selectedDate)
            _uiState.update {
                it.copy(
                    loading = false,
                    dashboard = result,
                    error = if (result == null) "加载失败，请检查网络" else null,
                )
            }
        }
    }

    fun weightLabelRes(status: String): Int = Companion.weightLabelRes(status)

    companion object {
        fun weightLabelRes(status: String): Int = when (status) {
            "above" -> R.string.health_weight_status_above
            "below" -> R.string.health_weight_status_below
            else -> R.string.health_weight_status_normal
        }
    }
}
