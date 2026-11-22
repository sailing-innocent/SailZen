package com.sailzen.app.feature.health

import android.app.Application
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import com.sailzen.app.R
import com.sailzen.app.core.data.DataChangeBus
import com.sailzen.app.core.data.DataChangeEvent
import com.sailzen.app.core.data.SettingsManager
import com.sailzen.app.core.health.HealthRepository
import com.sailzen.app.core.network.dto.HealthCoachSummaryDto
import com.sailzen.app.core.network.dto.HealthDashboardDto
import com.sailzen.app.core.tick.TickRepository
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
        val coachSummary: HealthCoachSummaryDto? = null,
        val loading: Boolean = false,
        val error: String? = null,
        val serverConfigured: Boolean = true,
    )

    private val repository = HealthRepository.get(application)
    private val tickRepository = TickRepository.get(application)
    private val settings = SettingsManager.get(application)
    private val bus = DataChangeBus.get()

    private val _uiState = MutableStateFlow(UiState())
    val uiState: StateFlow<UiState> = _uiState.asStateFlow()

    init {
        viewModelScope.launch {
            settings.serverUrlFlow.collect { url ->
                val configured = url.isNotBlank()
                val wasUnconfigured = !_uiState.value.serverConfigured
                _uiState.update { it.copy(serverConfigured = configured) }
                if (configured && wasUnconfigured) {
                    refresh()
                }
            }
        }
        viewModelScope.launch {
            bus.events.collect { event ->
                when (event) {
                    is DataChangeEvent.WeightChanged,
                    is DataChangeEvent.BodyDataChanged,
                    is DataChangeEvent.HealthSignalChanged,
                    -> refresh()
                    else -> {}
                }
            }
        }
        refresh()
    }

    fun selectDate(date: LocalDate) {
        _uiState.update { it.copy(selectedDate = date) }
        refresh()
    }

    fun stepDate(days: Long) {
        selectDate(_uiState.value.selectedDate.plusDays(days))
    }

    fun selectToday() {
        val today = LocalDate.now()
        if (_uiState.value.selectedDate != today) {
            selectDate(today)
        }
    }

    fun dismissError() {
        _uiState.update { it.copy(error = null) }
    }

    fun refresh() {
        viewModelScope.launch {
            val serverUrl = settings.serverUrl()
            if (serverUrl.isBlank()) {
                _uiState.update {
                    it.copy(
                        loading = false,
                        serverConfigured = false,
                        error = "未配置服务器地址，请先在设置页配置",
                    )
                }
                return@launch
            }
            _uiState.update { it.copy(loading = true, error = null, serverConfigured = true) }
            val result = repository.loadDashboard(_uiState.value.selectedDate)
            val coach = tickRepository.loadCoachSummary()
            _uiState.update { prev ->
                prev.copy(
                    loading = false,
                    // 加载失败时保留上一次已加载的缓存数据，不清空页面
                    dashboard = result ?: prev.dashboard,
                    coachSummary = coach ?: prev.coachSummary,
                    error = if (result == null) "加载健康数据失败，请检查网络连接或服务器地址（$serverUrl）" else null,
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
