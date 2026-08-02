package com.sailzen.app.feature.inbox

import android.app.Application
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import com.sailzen.app.core.data.db.CachedReminder
import com.sailzen.app.core.network.dto.ReminderDto
import com.sailzen.app.core.network.dto.SummaryDto
import com.sailzen.app.core.reminder.ReminderRepository
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch

class InboxViewModel(application: Application) : AndroidViewModel(application) {

    data class UiState(
        val pending: List<CachedReminder> = emptyList(),
        val history: List<ReminderDto> = emptyList(),
        val summary: SummaryDto? = null,
        val refreshing: Boolean = false,
        val configured: Boolean = true,
    )

    private val repository = ReminderRepository.get(application)

    private val _uiState = MutableStateFlow(UiState())
    val uiState: StateFlow<UiState> = _uiState.asStateFlow()

    init {
        // 待处理列表直接订阅 Room 缓存（WS 投递/反馈动作会实时反映）
        viewModelScope.launch {
            repository.observeActive().collect { list ->
                _uiState.update { it.copy(pending = list) }
            }
        }
        refresh()
    }

    fun refresh() {
        viewModelScope.launch {
            _uiState.update { it.copy(refreshing = true) }
            repository.syncPending()
            val summary = repository.summaryToday()
            val history = repository.historyToday()
            _uiState.update {
                it.copy(
                    summary = summary,
                    history = history,
                    refreshing = false,
                    configured = repository.serverConfigured(),
                )
            }
        }
    }

    fun open(reminderId: Int) = feedback(reminderId, "open")

    fun resolve(reminderId: Int) = feedback(reminderId, "resolve")

    fun dismiss(reminderId: Int) = feedback(reminderId, "dismiss")

    fun snooze(reminderId: Int, option: String) = feedback(reminderId, "snooze", option)

    private fun feedback(reminderId: Int, action: String, option: String? = null) {
        viewModelScope.launch {
            repository.sendFeedback(reminderId, action, option)
            // 反馈后刷新小结与历史
            val summary = repository.summaryToday()
            val history = repository.historyToday()
            _uiState.update { it.copy(summary = summary, history = history) }
        }
    }
}
