package com.sailzen.app.feature.affair

import android.app.Application
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import com.sailzen.app.core.data.DataChangeBus
import com.sailzen.app.core.data.DataChangeEvent
import com.sailzen.app.core.data.onFailure
import com.sailzen.app.core.data.onSuccess
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
    private val bus = DataChangeBus.get()

    private val _uiState = MutableStateFlow(UiState())
    val uiState: StateFlow<UiState> = _uiState.asStateFlow()

    init {
        viewModelScope.launch {
            bus.events.collect { event ->
                if (event is DataChangeEvent.AffairChanged || event is DataChangeEvent.CheckinChanged) {
                    // 若事件针对当前 affair 或其子事务/父事务，刷新详情
                    val (eventAffairId, eventParentId) = when (event) {
                        is DataChangeEvent.AffairChanged -> event.affairId to event.parentId
                        is DataChangeEvent.CheckinChanged -> event.affairId to null
                        else -> null to null
                    }
                    if (eventAffairId == null && eventParentId == null) {
                        refresh()
                    } else if (eventAffairId == affairId || eventParentId == affairId) {
                        refresh()
                    }
                }
            }
        }
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
            repository.transit(affairId, action)
                .onSuccess { refresh() }
                .onFailure { _uiState.update { it.copy(message = "操作失败：当前状态不允许该动作") } }
        }
    }

    fun transitChild(childId: Int, action: String) {
        viewModelScope.launch {
            repository.transit(childId, action)
                .onSuccess { refresh() }
                .onFailure { _uiState.update { it.copy(message = "子事务操作失败") } }
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
                .onSuccess { refresh() }
                .onFailure { _uiState.update { it.copy(message = "更新失败") } }
        }
    }

    fun addMilestone(title: String, estMinutes: Int?) {
        viewModelScope.launch {
            repository.addMilestone(
                affairId,
                VentureMilestoneRequest(title = title, estMinutes = estMinutes),
            )
                .onSuccess { refresh() }
                .onFailure { _uiState.update { it.copy(message = "里程碑添加失败") } }
        }
    }

    fun milestoneDone(milestoneId: Int) {
        viewModelScope.launch {
            repository.milestoneDone(milestoneId)
                .onSuccess { refresh() }
                .onFailure { _uiState.update { it.copy(message = "操作失败") } }
        }
    }

    fun delete() {
        viewModelScope.launch {
            repository.deleteAffair(affairId)
                .onSuccess { _uiState.update { it.copy(deleted = true) } }
                .onFailure { _uiState.update { it.copy(message = "删除失败") } }
        }
    }
}
