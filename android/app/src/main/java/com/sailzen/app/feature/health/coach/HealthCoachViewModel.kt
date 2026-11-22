package com.sailzen.app.feature.health.coach

import android.app.Application
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import com.sailzen.app.core.network.dto.DailyReportDto
import com.sailzen.app.core.network.dto.HealthCoachSummaryDto
import com.sailzen.app.core.tick.TickRepository
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch

/**
 * SailTick AI 教练页 ViewModel：
 * - 渐进式提问列表与快速回复 / 暂缓
 * - 随手记餐饮与日常状态（静默收集，无需等待 AI 即时回复）
 * - 每日睡前体重与健康日报浏览
 */
class HealthCoachViewModel(application: Application) : AndroidViewModel(application) {

    data class UiState(
        val summary: HealthCoachSummaryDto? = null,
        val reports: List<DailyReportDto> = emptyList(),
        val selectedReportDate: String? = null,
        val loading: Boolean = false,
        val sending: Boolean = false,
        val feedbackMessage: String? = null,
    )

    private val repo = TickRepository.get(application)

    private val _uiState = MutableStateFlow(UiState())
    val uiState: StateFlow<UiState> = _uiState.asStateFlow()

    init {
        refresh()
    }

    fun refresh() {
        viewModelScope.launch {
            _uiState.update { it.copy(loading = true) }
            val sum = repo.loadCoachSummary()
            val reps = repo.loadDailyReports(14)
            _uiState.update { prev ->
                val activeDate = prev.selectedReportDate?.takeIf { d -> reps.any { it.reportDate == d } }
                    ?: reps.firstOrNull()?.reportDate
                    ?: sum?.latestReport?.reportDate
                prev.copy(
                    summary = sum,
                    reports = reps,
                    selectedReportDate = activeDate,
                    loading = false,
                )
            }
        }
    }

    fun selectReport(date: String) {
        _uiState.update { it.copy(selectedReportDate = date) }
    }

    fun replyTicket(ticketId: Int, reply: String) {
        val text = reply.trim()
        if (text.isEmpty()) return
        viewModelScope.launch {
            _uiState.update { it.copy(sending = true) }
            val res = repo.replyTicket(ticketId, text)
            _uiState.update {
                it.copy(
                    sending = false,
                    feedbackMessage = if (res != null) "已回复教练，下次巡检会自动吸收" else "回复失败，请检查网络",
                )
            }
            if (res != null) refresh()
        }
    }

    fun snoozeTicket(ticketId: Int) {
        viewModelScope.launch {
            val res = repo.snoozeTicket(ticketId, 24)
            _uiState.update {
                it.copy(
                    feedbackMessage = if (res != null) "已暂缓 24 小时" else "操作失败，请检查网络",
                )
            }
            if (res != null) refresh()
        }
    }

    fun sendSilentMessage(content: String, category: String, mealType: String?) {
        val text = content.trim()
        if (text.isEmpty()) return
        viewModelScope.launch {
            _uiState.update { it.copy(sending = true) }
            val res = repo.sendSilentMessage(content = text, category = category, mealType = mealType)
            _uiState.update {
                it.copy(
                    sending = false,
                    feedbackMessage = if (res != null) {
                        "已静默记录，SailTick 将在今晚睡前日报中整合分析"
                    } else {
                        "记录失败，请检查网络"
                    },
                )
            }
            if (res != null) refresh()
        }
    }

    fun clearFeedback() {
        _uiState.update { it.copy(feedbackMessage = null) }
    }
}
