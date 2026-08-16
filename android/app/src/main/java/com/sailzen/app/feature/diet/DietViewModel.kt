package com.sailzen.app.feature.diet

import android.app.Application
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import com.sailzen.app.core.health.HealthRepository
import com.sailzen.app.core.network.dto.DietCreateRequest
import com.sailzen.app.core.network.dto.DietDto
import com.sailzen.app.core.network.dto.DietSummaryDto
import com.sailzen.app.core.network.dto.NutritionGoalCreateRequest
import com.sailzen.app.core.network.dto.NutritionGoalDto
import java.time.LocalDate
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch

class DietViewModel(application: Application) : AndroidViewModel(application) {

    data class UiState(
        val selectedDate: LocalDate = LocalDate.now(),
        val summary: DietSummaryDto? = null,
        val diets: List<DietDto> = emptyList(),
        val goal: NutritionGoalDto? = null,
        val loading: Boolean = false,
        val showEdit: Boolean = false,
        val editForm: DietCreateRequest = DietCreateRequest(),
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
            val date = _uiState.value.selectedDate
            val summary = repository.dietSummary(date)
            val diets = repository.diets(date)
            val goal = repository.nutritionGoal(date)
            _uiState.update { it.copy(loading = false, summary = summary, diets = diets, goal = goal) }
        }
    }

    fun setEditForm(form: DietCreateRequest) = _uiState.update { it.copy(editForm = form) }
    fun showEdit() = _uiState.update { it.copy(showEdit = true) }
    fun dismissEdit() = _uiState.update { it.copy(showEdit = false, editForm = DietCreateRequest()) }

    fun saveDiet() {
        val form = _uiState.value.editForm
        viewModelScope.launch {
            repository.createDiet(form.copy(htime = System.currentTimeMillis() / 1000.0))
            dismissEdit()
            load()
        }
    }

    fun saveGoal(goal: NutritionGoalCreateRequest) {
        viewModelScope.launch {
            repository.createOrUpdateNutritionGoal(goal)
            load()
        }
    }
}
