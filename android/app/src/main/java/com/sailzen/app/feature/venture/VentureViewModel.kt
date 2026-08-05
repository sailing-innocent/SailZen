package com.sailzen.app.feature.venture

import android.app.Application
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import com.sailzen.app.core.network.dto.VentureProgressDto
import com.sailzen.app.core.rhythm.RhythmRepository
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch

class VentureViewModel(application: Application) : AndroidViewModel(application) {

    data class UiState(
        val ventures: List<VentureProgressDto> = emptyList(),
        val refreshing: Boolean = false,
        val configured: Boolean = true,
    )

    private val repository = RhythmRepository.get(application)

    private val _uiState = MutableStateFlow(UiState())
    val uiState: StateFlow<UiState> = _uiState.asStateFlow()

    init {
        refresh()
    }

    fun refresh() {
        viewModelScope.launch {
            _uiState.update { it.copy(refreshing = true) }
            val ventures = repository.activeVentures().mapNotNull { v ->
                repository.ventureProgress(v.id)
            }
            _uiState.update {
                it.copy(
                    ventures = ventures,
                    refreshing = false,
                    configured = repository.serverConfigured(),
                )
            }
        }
    }

    fun milestoneDone(milestoneId: Int) = viewModelScope.launch {
        repository.milestoneDone(milestoneId)
        refresh()
    }
}
