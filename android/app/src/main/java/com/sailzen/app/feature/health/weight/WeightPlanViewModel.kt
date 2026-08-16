package com.sailzen.app.feature.health.weight

import android.app.Application
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import com.sailzen.app.core.health.HealthRepository
import com.sailzen.app.core.network.dto.WeightPlanCheckinStatusDto
import com.sailzen.app.core.network.dto.WeightPlanCreateRequest
import com.sailzen.app.core.network.dto.WeightPlanCurveType
import com.sailzen.app.core.network.dto.WeightPlanDto
import com.sailzen.app.core.network.dto.WeightPlanProgressDto
import java.time.LocalDate
import java.time.LocalDateTime
import java.time.ZoneOffset
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch

class WeightPlanViewModel(application: Application) : AndroidViewModel(application) {

    data class FormState(
        val targetWeight: String = "",
        val initialWeight: String = "",
        val curveType: WeightPlanCurveType = WeightPlanCurveType.linear,
        val targetDate: LocalDate = LocalDate.now().plusMonths(3),
        val notifyEnabled: Boolean = false,
        val feedbackEnabled: Boolean = false,
    )

    data class UiState(
        val plan: WeightPlanDto? = null,
        val progress: WeightPlanProgressDto? = null,
        val checkin: WeightPlanCheckinStatusDto? = null,
        val form: FormState = FormState(),
        val loading: Boolean = false,
        val showForm: Boolean = false,
        val message: String? = null,
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
            val plan = repository.activeWeightPlan()
            val progress = repository.weightPlanProgress()
            val checkin = repository.weightPlanCheckinStatus()
            _uiState.update {
                it.copy(
                    loading = false,
                    plan = plan,
                    progress = progress,
                    checkin = checkin,
                    showForm = plan == null,
                )
            }
        }
    }

    fun setForm(form: FormState) = _uiState.update { it.copy(form = form) }
    fun toggleForm() = _uiState.update { it.copy(showForm = !it.showForm) }
    fun dismissMessage() = _uiState.update { it.copy(message = null) }

    fun createPlan() {
        val form = _uiState.value.form
        viewModelScope.launch {
            _uiState.update { it.copy(loading = true) }
            val request = WeightPlanCreateRequest(
                targetWeight = form.targetWeight,
                initialWeight = form.initialWeight.takeIf { it.isNotBlank() },
                curveType = form.curveType,
                startTime = LocalDateTime.now().toString(),
                targetTime = form.targetDate.atStartOfDay().toInstant(ZoneOffset.UTC).toString(),
                notifyEnabled = form.notifyEnabled,
                feedbackEnabled = form.feedbackEnabled,
            )
            val plan = repository.createWeightPlan(request)
            _uiState.update {
                it.copy(
                    loading = false,
                    plan = plan,
                    showForm = plan == null,
                    message = if (plan != null) "计划创建成功" else "创建失败",
                )
            }
            if (plan != null) load()
        }
    }
}
