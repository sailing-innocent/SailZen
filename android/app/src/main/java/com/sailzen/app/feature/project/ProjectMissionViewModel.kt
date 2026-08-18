package com.sailzen.app.feature.project

import android.app.Application
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import com.sailzen.app.core.network.dto.MissionCreateRequest
import com.sailzen.app.core.network.dto.MissionDto
import com.sailzen.app.core.network.dto.MissionUpdateRequest
import com.sailzen.app.core.network.dto.MissionState
import com.sailzen.app.core.project.ProjectRepository
import java.util.concurrent.TimeUnit
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch

class ProjectMissionViewModel(
    application: Application,
    private val projectId: Int,
) : AndroidViewModel(application) {

    enum class Filter { ALL, URGENT, DOING }

    data class UiState(
        val missions: List<MissionDto> = emptyList(),
        val loading: Boolean = false,
        val filter: Filter = Filter.ALL,
        val showCreateDialog: Boolean = false,
        val highlightMissionId: Int = -1,
    )

    private val repository = ProjectRepository.get(application)

    private val _uiState = MutableStateFlow(UiState())
    val uiState: StateFlow<UiState> = _uiState.asStateFlow()

    init {
        refresh()
    }

    fun setHighlightMissionId(id: Int) = _uiState.update { it.copy(highlightMissionId = id) }

    fun setFilter(filter: Filter) = _uiState.update { it.copy(filter = filter) }

    fun refresh() {
        viewModelScope.launch {
            _uiState.update { it.copy(loading = true) }
            val missions = repository.getMissions(projectId = projectId)
            _uiState.update { it.copy(missions = missions, loading = false) }
        }
    }

    fun createMission(name: String, description: String, ddlSeconds: String, plannedMinutes: String) {
        if (name.isBlank()) return
        viewModelScope.launch {
            val body = MissionCreateRequest(
                name = name,
                description = description,
                projectId = if (projectId > 0) projectId else null,
                ddl = ddlSeconds.toDoubleOrNull(),
                plannedMinutes = plannedMinutes.toIntOrNull(),
            )
            repository.createMission(body)
            _uiState.update { it.copy(showCreateDialog = false) }
            refresh()
        }
    }

    fun startMission(id: Int) = transition { repository.doingMission(id) }
    fun completeMission(id: Int) = transition { repository.doneMission(id) }
    fun cancelMission(id: Int) = transition { repository.cancelMission(id) }
    fun reopenMission(id: Int) = transition { repository.pendingMission(id) }
    fun postponeMission(id: Int, days: Int = 7) = transition { repository.postponeMission(id, days) }

    fun updateMissionName(id: Int, name: String) {
        if (name.isBlank()) return
        viewModelScope.launch {
            repository.updateMission(id, MissionUpdateRequest(name = name))
            refresh()
        }
    }

    private fun transition(block: suspend () -> MissionDto?) {
        viewModelScope.launch {
            block()
            refresh()
        }
    }

    fun showCreateDialog() = _uiState.update { it.copy(showCreateDialog = true) }
    fun dismissCreateDialog() = _uiState.update { it.copy(showCreateDialog = false) }

    companion object {
        fun isMissionActive(state: Int?): Boolean = state != MissionState.DONE && state != MissionState.CANCELED

        fun ddlTimestampSeconds(ddl: Double?): Long? = ddl?.toLong()

        fun isOverdue(ddl: Double?, state: Int?): Boolean {
            if (!isMissionActive(state)) return false
            val ts = ddlTimestampSeconds(ddl) ?: return false
            return ts < System.currentTimeMillis() / TimeUnit.SECONDS.toMillis(1)
        }

        fun hoursUntilDeadline(ddl: Double?): Double {
            val ts = ddlTimestampSeconds(ddl) ?: return Double.POSITIVE_INFINITY
            val nowSeconds = System.currentTimeMillis() / TimeUnit.SECONDS.toMillis(1)
            return (ts - nowSeconds) / 3600.0
        }
    }
}
