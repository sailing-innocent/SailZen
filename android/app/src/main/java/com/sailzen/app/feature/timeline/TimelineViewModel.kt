package com.sailzen.app.feature.timeline

import android.app.Application
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import com.sailzen.app.core.network.dto.AffairDto
import com.sailzen.app.core.network.dto.DayTimelineDto
import com.sailzen.app.core.network.dto.HealthSignalItemDto
import com.sailzen.app.core.network.dto.ReviewDto
import com.sailzen.app.core.network.dto.RhythmDayViewDto
import com.sailzen.app.core.network.dto.TimeBlockDto
import com.sailzen.app.core.rhythm.RhythmRepository
import java.time.LocalDate
import java.time.LocalDateTime
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch

class TimelineViewModel(application: Application) : AndroidViewModel(application) {

    data class UiState(
        val date: LocalDate = LocalDate.now(),
        val timeline: DayTimelineDto? = null,
        val dayView: RhythmDayViewDto? = null,
        val healthSignals: List<HealthSignalItemDto> = emptyList(),
        val inbox: List<AffairDto> = emptyList(),
        val refreshing: Boolean = false,
        val configured: Boolean = true,
        val queuedCount: Int = 0,
        val planning: Boolean = false,
        val planBBlock: TimeBlockDto? = null, // 长按查看 Plan B 的块
        val planBText: String? = null,
        val captureOpen: Boolean = false, // 快速捕获弹窗
        val weekReview: ReviewDto? = null, // 周节奏卡片
        val weekReviewOpen: Boolean = false, // 周报详情弹窗
    )

    private val repository = RhythmRepository.get(application)

    private val _uiState = MutableStateFlow(UiState())
    val uiState: StateFlow<UiState> = _uiState.asStateFlow()

    init {
        viewModelScope.launch {
            repository.observeQueuedCount().collect { count ->
                _uiState.update { it.copy(queuedCount = count) }
            }
        }
        refresh()
    }

    fun refresh() {
        viewModelScope.launch {
            _uiState.update { it.copy(refreshing = true) }
            repository.flushPending()
            val dayView = repository.dayView(_uiState.value.date)
            val timeline = dayView?.blocks?.let { blocks ->
                DayTimelineDto(
                    date = dayView.date,
                    dayId = dayView.dayId,
                    planVersion = dayView.planVersion,
                    blocks = blocks,
                    domainMinutes = dayView.domainMinutes,
                    energyConsumed = dayView.energyConsumed,
                    energyBudget = dayView.energyBudget,
                    bufferTotalMinutes = dayView.bufferTotalMinutes,
                    bufferFreeMinutes = dayView.bufferFreeMinutes,
                    checkins = dayView.checkins,
                    warnings = dayView.warnings,
                )
            } ?: repository.timeline(_uiState.value.date)
            val inbox = repository.inbox()
            val weekReview = repository.reviewWeek()
            _uiState.update {
                it.copy(
                    timeline = timeline,
                    dayView = dayView,
                    healthSignals = dayView?.healthSignals ?: emptyList(),
                    inbox = inbox,
                    weekReview = weekReview,
                    refreshing = false,
                    configured = repository.serverConfigured(),
                )
            }
        }
    }

    fun openWeekReview() = _uiState.update { it.copy(weekReviewOpen = true) }

    fun closeWeekReview() = _uiState.update { it.copy(weekReviewOpen = false) }

    /** 生成/重生成日计划 */
    fun plan() {
        viewModelScope.launch {
            _uiState.update { it.copy(planning = true) }
            repository.planDay(_uiState.value.date)
            val timeline = repository.timeline(_uiState.value.date)
            _uiState.update { it.copy(timeline = timeline, planning = false) }
        }
    }

    fun doneBlock(blockId: Int) = viewModelScope.launch {
        repository.blockDone(blockId)
        refresh()
    }

    fun skipBlock(blockId: Int) = viewModelScope.launch {
        repository.blockSkip(blockId)
        refresh()
    }

    /** 右滑 defer：推迟到明天 09:00（fixed 块 UI 层不出现该操作） */
    fun deferBlock(block: TimeBlockDto) = viewModelScope.launch {
        val affairId = block.affairId ?: return@launch
        val tomorrow = LocalDate.now().plusDays(1).atTime(9, 0)
        repository.deferAffair(affairId, tomorrow.withNano(0).toString())
        refresh()
    }

    /** 长按查看 Plan B（取 affair.fallback_plan） */
    fun showPlanB(block: TimeBlockDto) = viewModelScope.launch {
        _uiState.update { it.copy(planBBlock = block, planBText = null) }
        val affair = block.affairId?.let { repository.affairDetail(it) }
        _uiState.update {
            it.copy(planBText = affair?.fallbackPlan?.ifBlank { "（无备用方案）" } ?: "（无备用方案）")
        }
    }

    fun dismissPlanB() = _uiState.update { it.copy(planBBlock = null, planBText = null) }

    // ---------------- 快速捕获 ----------------

    fun openCapture() = _uiState.update { it.copy(captureOpen = true) }

    fun closeCapture() = _uiState.update { it.copy(captureOpen = false) }

    fun capture(title: String, kind: String) = viewModelScope.launch {
        if (title.isBlank()) return@launch
        repository.capture(title.trim(), kind)
        _uiState.update { it.copy(captureOpen = false) }
        refresh()
    }

    // ---------------- AI 建议采纳 ----------------

    fun acceptHint(affairId: Int) = viewModelScope.launch {
        repository.acceptHintAndConfirm(affairId)
        refresh()
    }

    fun rejectHint(affairId: Int) = viewModelScope.launch {
        repository.confirmHint(affairId, accept = false)
        refresh()
    }
}
