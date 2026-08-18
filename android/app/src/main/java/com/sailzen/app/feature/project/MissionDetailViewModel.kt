package com.sailzen.app.feature.project

import android.app.Application
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import com.sailzen.app.core.network.dto.MissionDto
import com.sailzen.app.core.network.dto.MissionUpdateRequest
import com.sailzen.app.core.project.ProjectRepository
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch

class MissionDetailViewModel(
    application: Application,
    private val missionId: Int,
) : AndroidViewModel(application) {

    data class UiState(
        val mission: MissionDto? = null,
        val loading: Boolean = false,
    )

    private val repository = ProjectRepository.get(application)

    private val _uiState = MutableStateFlow(UiState())
    val uiState: StateFlow<UiState> = _uiState.asStateFlow()

    fun load() {
        viewModelScope.launch {
            _uiState.update { it.copy(loading = true) }
            val mission = repository.getMission(missionId)
            _uiState.update { it.copy(mission = mission, loading = false) }
        }
    }

    fun updateMission(name: String, description: String, ddl: String) {
        viewModelScope.launch {
            repository.updateMission(
                missionId,
                MissionUpdateRequest(
                    name = name.takeIf { it.isNotBlank() },
                    description = description,
                    ddl = ddl.toDoubleOrNull(),
                ),
            )
            load()
        }
    }

    fun start() = transition { repository.doingMission(missionId) }
    fun complete() = transition { repository.doneMission(missionId) }
    fun cancel() = transition { repository.cancelMission(missionId) }
    fun reopen() = transition { repository.pendingMission(missionId) }
    fun postpone(days: Int = 7) = transition { repository.postponeMission(missionId, days) }

    private fun transition(block: suspend () -> MissionDto?) {
        viewModelScope.launch {
            block()
            load()
        }
    }
}
