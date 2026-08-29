package com.sailzen.app.feature.checkin

import android.app.Application
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import com.sailzen.app.core.data.DataChangeBus
import com.sailzen.app.core.data.DataChangeEvent
import com.sailzen.app.core.data.onSuccess
import com.sailzen.app.core.network.dto.CheckinTodayDto
import com.sailzen.app.core.network.dto.CheckinTodayItemDto
import com.sailzen.app.core.rhythm.RhythmRepository
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch

class CheckinViewModel(application: Application) : AndroidViewModel(application) {

    data class UiState(
        val checkins: CheckinTodayDto? = null,
        val refreshing: Boolean = false,
        val configured: Boolean = true,
        val queuedCount: Int = 0,
        // 破戒备注弹窗目标
        val noteTarget: CheckinTodayItemDto? = null,
    )

    private val repository = RhythmRepository.get(application)
    private val bus = DataChangeBus.get()

    private val _uiState = MutableStateFlow(UiState())
    val uiState: StateFlow<UiState> = _uiState.asStateFlow()

    init {
        viewModelScope.launch {
            repository.observeQueuedCount().collect { count ->
                _uiState.update { it.copy(queuedCount = count) }
            }
        }
        viewModelScope.launch {
            bus.events.collect { event ->
                if (event is DataChangeEvent.CheckinChanged || event is DataChangeEvent.AffairChanged) {
                    refresh()
                }
            }
        }
        refresh()
    }

    fun refresh() {
        viewModelScope.launch {
            _uiState.update { it.copy(refreshing = true) }
            repository.flushPending()
            val checkins = repository.checkinToday()
            _uiState.update {
                it.copy(
                    checkins = checkins,
                    refreshing = false,
                    configured = repository.serverConfigured(),
                )
            }
        }
    }

    /** 戒律：kept / violated（带备注弹窗） */
    fun preceptKept(item: CheckinTodayItemDto) = checkin(item.affair.id, "kept")

    fun preceptViolated(item: CheckinTodayItemDto) =
        _uiState.update { it.copy(noteTarget = item) }

    /** 习惯：done / missed */
    fun habitDone(item: CheckinTodayItemDto) = checkin(item.affair.id, "done")

    fun habitMissed(item: CheckinTodayItemDto) = checkin(item.affair.id, "missed")

    fun dismissNote() = _uiState.update { it.copy(noteTarget = null) }

    fun confirmViolate(note: String) {
        val target = _uiState.value.noteTarget ?: return
        _uiState.update { it.copy(noteTarget = null) }
        checkin(target.affair.id, "violated", note)
    }

    private fun checkin(affairId: Int, result: String, note: String = "") =
        viewModelScope.launch {
            repository.checkin(affairId, result, note)
                .onSuccess { refresh() }
        }
}
