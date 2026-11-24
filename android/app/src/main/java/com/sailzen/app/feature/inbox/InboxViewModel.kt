package com.sailzen.app.feature.inbox

import android.app.Application
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import com.sailzen.app.core.data.db.CachedInboxItem
import com.sailzen.app.core.network.dto.InboxSummaryDto
import com.sailzen.app.core.reminder.ReminderRepository
import com.sailzen.app.core.user.UserInboxRepository
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch

/**
 * 统一收件箱 ViewModel：
 * 订阅 Room `inbox_cache`（由单调游标 sync_seq 与 User WS 实时维护），
 * 任一端回复/记餐/关闭后立即从待处理移除并展示在历史中（附带消解来源说明）。
 */
class InboxViewModel(application: Application) : AndroidViewModel(application) {

    data class UiState(
        val pending: List<CachedInboxItem> = emptyList(),
        val history: List<CachedInboxItem> = emptyList(),
        val summary: InboxSummaryDto? = null,
        val refreshing: Boolean = false,
        val configured: Boolean = true,
    )

    private val userInboxRepo = UserInboxRepository.get(application)
    private val reminderRepo = ReminderRepository.get(application)

    private val _uiState = MutableStateFlow(UiState())
    val uiState: StateFlow<UiState> = _uiState.asStateFlow()

    init {
        viewModelScope.launch {
            userInboxRepo.observeActive().collect { list ->
                _uiState.update { it.copy(pending = list) }
            }
        }
        viewModelScope.launch {
            userInboxRepo.observeHistory().collect { list ->
                _uiState.update { it.copy(history = list) }
            }
        }
        refresh()
    }

    fun refresh() {
        viewModelScope.launch {
            _uiState.update { it.copy(refreshing = true) }
            userInboxRepo.syncInbox(full = true)
            reminderRepo.syncPending()
            val summary = userInboxRepo.summaryToday()
            _uiState.update {
                it.copy(
                    summary = summary,
                    refreshing = false,
                    configured = reminderRepo.serverConfigured(),
                )
            }
        }
    }

    fun reply(itemId: Int, reply: String) {
        val text = reply.trim()
        if (text.isEmpty()) return
        viewModelScope.launch {
            userInboxRepo.replyItem(itemId, text)
            val summary = userInboxRepo.summaryToday()
            _uiState.update { it.copy(summary = summary) }
        }
    }

    fun resolve(itemId: Int) {
        viewModelScope.launch {
            userInboxRepo.resolveItem(itemId)
            val summary = userInboxRepo.summaryToday()
            _uiState.update { it.copy(summary = summary) }
        }
    }

    fun dismiss(itemId: Int) {
        viewModelScope.launch {
            userInboxRepo.dismissItem(itemId)
            val summary = userInboxRepo.summaryToday()
            _uiState.update { it.copy(summary = summary) }
        }
    }

    fun snooze(itemId: Int, option: String) {
        viewModelScope.launch {
            userInboxRepo.snoozeItem(itemId, option)
            val summary = userInboxRepo.summaryToday()
            _uiState.update { it.copy(summary = summary) }
        }
    }
}
