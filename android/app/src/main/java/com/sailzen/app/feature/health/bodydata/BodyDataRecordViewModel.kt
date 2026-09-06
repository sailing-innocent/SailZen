package com.sailzen.app.feature.health.bodydata

import android.app.Application
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import com.sailzen.app.core.data.OperationResult
import com.sailzen.app.core.data.onFailure
import com.sailzen.app.core.data.onSuccess
import com.sailzen.app.core.health.HealthDateUtils
import com.sailzen.app.core.health.HealthRepository
import com.sailzen.app.core.network.dto.BUILTIN_BODY_METRICS
import com.sailzen.app.core.network.dto.BodyDataCreateRequest
import com.sailzen.app.core.network.dto.BodyMetricDefDto
import java.time.LocalDate
import java.time.LocalDateTime
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch

/**
 * 身体数据记录页 ViewModel：多指标一次录入。
 *
 * 未测量语义：[UiState.values] 中缺失或为空串的指标一律不进 data；
 * 自定义指标走 x_ 前缀键，与内置指标同等校验。
 */
class BodyDataRecordViewModel(application: Application) : AndroidViewModel(application) {

    data class UiState(
        val metrics: List<BodyMetricDefDto> = BUILTIN_BODY_METRICS,
        val date: LocalDate = LocalDate.now(),
        val time: String = LocalDateTime.now().let { "%02d:%02d".format(it.hour, it.minute) },
        val note: String = "",
        /** metricKey -> 输入文本；空文本 = 本次未测量 */
        val values: Map<String, String> = emptyMap(),
        val customKey: String = "",
        val customValue: String = "",
        val submitting: Boolean = false,
        val submitted: Boolean = false,
        val error: String? = null,
    )

    private val repository = HealthRepository.get(application)
    private val _uiState = MutableStateFlow(UiState())
    val uiState: StateFlow<UiState> = _uiState.asStateFlow()

    init {
        // 动态指标注册表下发后覆盖内置镜像（首屏 fallback 保证离线可用）
        viewModelScope.launch {
            val metrics = repository.bodyDataMetrics()
            if (metrics.isNotEmpty()) {
                _uiState.update { it.copy(metrics = metrics) }
            }
        }
    }

    fun setDate(date: LocalDate) = _uiState.update { it.copy(date = date) }
    fun setTime(time: String) = _uiState.update { it.copy(time = time) }
    fun setNote(v: String) = _uiState.update { it.copy(note = v) }
    fun setValue(key: String, text: String) = _uiState.update { it.copy(values = it.values + (key to text)) }
    fun setCustomKey(v: String) = _uiState.update { it.copy(customKey = v) }
    fun setCustomValue(v: String) = _uiState.update { it.copy(customValue = v) }
    fun dismissSubmitted() = _uiState.update { it.copy(submitted = false) }
    fun dismissError() = _uiState.update { it.copy(error = null) }

    /** 组装待提交的 data（含自定义行）；供 UI 预览已测数量。 */
    internal fun buildMeasuredData(state: UiState): Map<String, Double> {
        val measured = BodyDataInputParser.extractMeasured(state.values).toMutableMap()
        val customValue = state.customValue.trim()
        val customKey = state.customKey.trim()
        if (customValue.isNotEmpty() && customKey.isNotEmpty() &&
            BodyDataInputParser.isValidCustomKey(customKey)
        ) {
            customValue.toDoubleOrNull()?.let { measured[customKey] = it }
        }
        return measured
    }

    private fun timestampSeconds(state: UiState): Double {
        val (hour, minute) = HealthDateUtils.parseTime(state.time)
        return HealthDateUtils.timestampFor(state.date, hour, minute)
    }

    fun submit() {
        val state = _uiState.value
        val measured = buildMeasuredData(state)
        if (measured.isEmpty()) {
            _uiState.update { it.copy(error = "请至少填写一项指标") }
            return
        }
        val customValue = state.customValue.trim()
        if (customValue.isNotEmpty() && !BodyDataInputParser.isValidCustomKey(state.customKey.trim())) {
            _uiState.update { it.copy(error = "自定义指标键需以 x_ 开头，仅含小写字母/数字/下划线") }
            return
        }
        val violations = BodyDataInputParser.validateOutOfRange(state.metrics, measured)
        if (violations.isNotEmpty()) {
            _uiState.update { it.copy(error = violations.joinToString("；")) }
            return
        }
        viewModelScope.launch {
            _uiState.update { it.copy(submitting = true, error = null) }
            val result: OperationResult<Boolean> = run {
                val created = repository.createBodyData(
                    BodyDataCreateRequest(
                        htime = timestampSeconds(state),
                        data = measured,
                        description = state.note,
                    )
                )
                when (created) {
                    is OperationResult.Success -> OperationResult.Success(true)
                    is OperationResult.Failure -> OperationResult.Failure(created.message, created.cause)
                }
            }
            result
                .onSuccess {
                    _uiState.update {
                        it.copy(
                            submitting = false,
                            submitted = true,
                            values = emptyMap(),
                            customKey = "",
                            customValue = "",
                            note = "",
                        )
                    }
                }
                .onFailure { failure ->
                    _uiState.update { it.copy(submitting = false, error = failure.message) }
                }
        }
    }
}
