package com.sailzen.app.feature.project

import android.app.Application
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import com.sailzen.app.R
import com.sailzen.app.core.network.dto.ProjectCreateRequest
import com.sailzen.app.core.network.dto.ProjectDto
import com.sailzen.app.core.project.ProjectRepository
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch

class ProjectListViewModel(application: Application) : AndroidViewModel(application) {

    data class UiState(
        val projects: List<ProjectDto> = emptyList(),
        val loading: Boolean = false,
        val error: String? = null,
        val showCreateDialog: Boolean = false,
    )

    private val repository = ProjectRepository.get(application)

    private val _uiState = MutableStateFlow(UiState())
    val uiState: StateFlow<UiState> = _uiState.asStateFlow()

    init {
        refresh()
    }

    fun refresh() {
        viewModelScope.launch {
            _uiState.update { it.copy(loading = true, error = null) }
            val projects = repository.getProjects()
            _uiState.update {
                it.copy(
                    projects = projects,
                    loading = false,
                    error = if (projects.isEmpty() && repository.serverConfigured().not()) {
                        getApplication<Application>().getString(R.string.settings_disconnected)
                    } else null,
                )
            }
        }
    }

    fun createProject(name: String, description: String, startQbw: String, endQbw: String) {
        if (name.isBlank()) return
        viewModelScope.launch {
            val body = ProjectCreateRequest(
                name = name,
                description = description,
                startTimeQbw = startQbw.toIntOrNull(),
                endTimeQbw = endQbw.toIntOrNull(),
            )
            repository.createProject(body)
            _uiState.update { it.copy(showCreateDialog = false) }
            refresh()
        }
    }

    fun showCreateDialog() = _uiState.update { it.copy(showCreateDialog = true) }
    fun dismissCreateDialog() = _uiState.update { it.copy(showCreateDialog = false) }

    private suspend fun ProjectRepository.serverConfigured(): Boolean {
        return try {
            com.sailzen.app.core.data.SettingsManager.get(getApplication()).serverUrl().isNotBlank()
        } catch (_: Exception) {
            false
        }
    }
}
