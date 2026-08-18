package com.sailzen.app.feature.affair

import android.app.Application
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import com.sailzen.app.core.network.dto.AffairDto
import com.sailzen.app.core.network.dto.AffairUpdateRequest
import com.sailzen.app.core.network.dto.VentureMilestoneRequest
import com.sailzen.app.core.network.dto.VentureProgressDto
import com.sailzen.app.core.rhythm.RhythmRepository
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch

/**
 * 事务详情：任一 affair 都可展开子树；kind=venture 时附带倒排进度与里程碑管理。
 */
class AffairDetailViewModel(
    application: Application,
    private val affairId: Int,
) : AndroidViewModel(application) {

    data class UiState(
        val affair: AffairDto? = null,
        val children: List<AffairDto> = emptyList(),
        val progress: VentureProgressDto? = null,
        val loading: Boolean = false,
        val deleted: Boolean = false,
        val message: String? = null,
    )

    private val repository = RhythmRepository.get(application)

    private val _uiState = MutableStateFlow(UiState())
    val uiState: StateFlow<UiState> = _uiState.asStateFlow()

    init {
        refresh()
    }

    fun dismissMessage() = _uiState.update { it.copy(message = null) }

    fun refresh() {
        viewModelScope.launch {
            _uiState.update { it.copy(loading = true) }
            val affair = repository.affairDetail(affairId)
            val children = repository.listAffairs(parentId = affairId)
            val progress = if (affair?.kind == AffairHomeViewModel.VENTURE_KIND) {
                repository.ventureProgress(affairId)
            } else {
                null
            }
            _uiState.update {
                it.copy(loading = false, affair = affair, children = children, progress = progress)
            }
        }
    }

    fun transit(action: String) {
        viewModelScope.launch {
            if (repository.transit(affairId, action) == null) {
                _uiState.update { it.copy(message = "操作失败：当前状态不允许该动作") }
            }
            refresh()
        }
    }

    fun transitChild(childId: Int, action: String) {
        viewModelScope.launch {
            repository.transit(childId, action)
            refresh()
        }
    }

    fun updateAffair(title: String, description: String, estMinutes: Int, importance: Int) {
        viewModelScope.launch {
            repository.updateAffair(
                affairId,
                AffairUpdateRequest(
                    title = title,
                    description = description,
                    estMinutes = estMinutes,
                    importance = importance,
                ),
            )
            refresh()
        }
    }

    fun addMilestone(title: String, estMinutes: Int?) {
        viewModelScope.launch {
            val created = repository.addMilestone(
                affairId,
                VentureMilestoneRequest(title = title, estMinutes = estMinutes),
            )
            if (created == null) {
                _uiState.update { it.copy(message = "里程碑添加失败") }
            }
            refresh()
        }
    }

    fun milestoneDone(milestoneId: Int) {
        viewModelScope.launch {
            repository.milestoneDone(milestoneId)
            refresh()
        }
    }

    fun delete() {
        viewModelScope.launch {
            if (repository.deleteAffair(affairId)) {
                _uiState.update { it.copy(deleted = true) }
            } else {
                _uiState.update { it.copy(message = "删除失败") }
            }
        }
    }
}
