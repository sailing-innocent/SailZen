package com.sailzen.app.feature.health.medication

import android.app.Application
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import com.sailzen.app.core.data.DataChangeBus
import com.sailzen.app.core.data.DataChangeEvent
import com.sailzen.app.core.data.onFailure
import com.sailzen.app.core.data.onSuccess
import com.sailzen.app.core.health.HealthAlarmScheduler
import com.sailzen.app.core.health.HealthRepository
import com.sailzen.app.core.network.dto.MedicationCreateRequest
import com.sailzen.app.core.network.dto.MedicationDto
import com.sailzen.app.core.network.dto.MedicationTodayDto
import java.time.LocalDate
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch

class MedicationViewModel(application: Application) : AndroidViewModel(application) {

    data class UiState(
        val selectedDate: LocalDate = LocalDate.now(),
        val today: MedicationTodayDto? = null,
        val medications: List<MedicationDto> = emptyList(),
        val loading: Boolean = false,
        val showEdit: Boolean = false,
        val editForm: MedicationCreateRequest = MedicationCreateRequest(name = ""),
    )

    private val repository = HealthRepository.get(application)
    private val bus = DataChangeBus.get()

    private val _uiState = MutableStateFlow(UiState())
    val uiState: StateFlow<UiState> = _uiState.asStateFlow()

    init {
        viewModelScope.launch {
            bus.events.collect { event ->
                if (event is DataChangeEvent.HealthSignalChanged && event.collectionType == "medication") load()
            }
        }
        load()
    }

    fun load() {
        viewModelScope.launch {
            _uiState.update { it.copy(loading = true) }
            val today = repository.medicationToday(_uiState.value.selectedDate)
            val meds = repository.medications(_uiState.value.selectedDate)
            _uiState.update { it.copy(loading = false, today = today, medications = meds) }
            HealthAlarmScheduler.scheduleMedications(getApplication(), meds)
        }
    }

    fun take(medicationId: Int) {
        viewModelScope.launch {
            _uiState.update { it.copy(loading = true) }
            repository.takeMedication(medicationId)
                .onSuccess { load() }
                .onFailure { _uiState.update { it.copy(loading = false) } }
        }
    }

    fun setEditForm(form: MedicationCreateRequest) = _uiState.update { it.copy(editForm = form) }
    fun showEdit() = _uiState.update { it.copy(showEdit = true) }
    fun dismissEdit() = _uiState.update { it.copy(showEdit = false, editForm = MedicationCreateRequest(name = "")) }

    fun save() {
        val form = _uiState.value.editForm
        if (form.name.isBlank()) return
        viewModelScope.launch {
            _uiState.update { it.copy(loading = true) }
            repository.createMedication(form.copy(plannedDate = _uiState.value.selectedDate.toString()))
                .onSuccess { dismissEdit(); load() }
                .onFailure { _uiState.update { it.copy(loading = false) } }
        }
    }
}
