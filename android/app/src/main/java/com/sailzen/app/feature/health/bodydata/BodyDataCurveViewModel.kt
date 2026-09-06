package com.sailzen.app.feature.health.bodydata

import android.app.Application
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import com.sailzen.app.core.data.DataChangeBus
import com.sailzen.app.core.data.DataChangeEvent
import com.sailzen.app.core.health.HealthRepository
import com.sailzen.app.core.network.dto.BUILTIN_BODY_METRICS
import com.sailzen.app.core.network.dto.BodyDataSeriesResponse
import com.sailzen.app.core.network.dto.BodyMetricDefDto
import com.sailzen.app.core.network.dto.WeightExpectedRangeDto
import java.time.LocalDate
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch

/**
 * 身体数据曲线页 ViewModel：单指标时序 + 体重计划叠加（与旧体重曲线对齐）。
 *
 * 通用指标走 body-data series 端点；选中 weight 时额外拉取
 * weights-with-status / plan-expected 以保留计划预期曲线。
 * 订阅 BodyDataChanged 与 WeightChanged（dual-write 兼容旧监听方）。
 */
class BodyDataCurveViewModel(application: Application) : AndroidViewModel(application) {

    data class UiState(
        val rangeLabel: String = "近 7 天",
        val metrics: List<BodyMetricDefDto> = BUILTIN_BODY_METRICS,
        val selectedMetric: String = "weight",
        val series: BodyDataSeriesResponse? = null,
        val expected: WeightExpectedRangeDto? = null,
        val analysis: Map<String, Any>? = null,
        val loading: Boolean = false,
    )

    private val repository = HealthRepository.get(application)
    private val bus = DataChangeBus.get()
    private val _uiState = MutableStateFlow(UiState())
    val uiState: StateFlow<UiState> = _uiState.asStateFlow()

    private val rangeOptions = mapOf(
        "近 7 天" to 7L,
        "近 30 天" to 30L,
        "近 90 天" to 90L,
    )

    init {
        viewModelScope.launch {
            bus.events.collect { event ->
                if (event is DataChangeEvent.BodyDataChanged || event is DataChangeEvent.WeightChanged) load()
            }
        }
        viewModelScope.launch {
            val metrics = repository.bodyDataMetrics()
            if (metrics.isNotEmpty()) {
                _uiState.update { it.copy(metrics = metrics) }
            }
        }
        load()
    }

    fun selectMetric(key: String) {
        _uiState.update { it.copy(selectedMetric = key) }
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
            val metric = _uiState.value.selectedMetric
            val series = repository.bodyDataSeries(metric, start, end)
            val analysis = repository.bodyDataAnalysis(metric, start, end)
            val expected = if (metric == "weight") {
                repository.weightPlanExpected(start, end)
            } else {
                null
            }
            _uiState.update {
                it.copy(
                    loading = false,
                    series = series,
                    analysis = analysis,
                    expected = expected,
                )
            }
        }
    }
}
