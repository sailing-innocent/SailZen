package com.sailzen.app.feature.health.coach

import android.app.Application
import android.net.Uri
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import com.sailzen.app.core.network.dto.DailyReportDto
import com.sailzen.app.core.network.dto.HealthCoachSummaryDto
import com.sailzen.app.core.network.dto.ImageIntakeCommitRequest
import com.sailzen.app.core.network.dto.ImageIntakeDraftDto
import com.sailzen.app.core.network.dto.IntakeEntryDto
import com.sailzen.app.core.tick.SharedImageInbox
import com.sailzen.app.core.tick.TickRepository
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import kotlinx.serialization.json.JsonElement
import kotlinx.serialization.json.JsonObject

/**
 * SailTick AI 教练页 ViewModel：
 * - 拍照/选图/系统分享 → DeepSeek 识图 → 人工微调确认 → 落库
 * - 渐进式提问列表与快速回复 / 传图回复 / 暂缓
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
        val analyzingImage: Boolean = false,
        val committingDraft: Boolean = false,
        val activeDraft: ImageIntakeDraftDto? = null,
        val draftEntries: List<IntakeEntryDto> = emptyList(),
        val draftSummary: String = "",
        val draftReplyText: String = "",
        val previewImageBytes: ByteArray? = null,
        val errorBanner: String? = null,
        val feedbackMessage: String? = null,
    )

    private val repo = TickRepository.get(application)

    private val _uiState = MutableStateFlow(UiState())
    val uiState: StateFlow<UiState> = _uiState.asStateFlow()

    init {
        refresh()
        observeSharedImages()
    }

    private fun observeSharedImages() {
        viewModelScope.launch {
            SharedImageInbox.pending.collect { payload ->
                if (payload != null) {
                    val consumed = SharedImageInbox.consume() ?: return@collect
                    analyzeImageUri(
                        uri = consumed.uri,
                        note = consumed.note,
                        sourceChannel = consumed.sourceChannel,
                        ticketId = null,
                        forceOcr = false,
                    )
                }
            }
        }
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

    fun analyzeImageUri(
        uri: Uri,
        note: String = "",
        sourceChannel: String = "android",
        ticketId: Int? = null,
        forceOcr: Boolean = false,
    ) {
        viewModelScope.launch {
            _uiState.update {
                it.copy(
                    analyzingImage = true,
                    errorBanner = null,
                )
            }
            val bytesResult = repo.readAndCompressUri(uri)
            val bytes = bytesResult.getOrElse { err ->
                _uiState.update {
                    it.copy(
                        analyzingImage = false,
                        errorBanner = "读取图片失败：${err.message}",
                    )
                }
                return@launch
            }
            _uiState.update { it.copy(previewImageBytes = bytes) }

            val analyzeResult = repo.analyzeImageIntake(
                imageBytes = bytes,
                filename = "intake_${System.currentTimeMillis()}.jpg",
                note = note,
                sourceChannel = sourceChannel,
                ticketId = ticketId,
                useOcrAssist = if (forceOcr) "true" else "auto",
            )
            analyzeResult.fold(
                onSuccess = { draft ->
                    _uiState.update {
                        it.copy(
                            analyzingImage = false,
                            activeDraft = draft,
                            draftEntries = draft.entries,
                            draftSummary = draft.summary,
                            draftReplyText = "",
                            errorBanner = null,
                        )
                    }
                },
                onFailure = { err ->
                    _uiState.update {
                        it.copy(
                            analyzingImage = false,
                            errorBanner = "AI 识图失败：${err.message ?: "请检查网络与 DeepSeek 配置"}",
                        )
                    }
                },
            )
        }
    }

    fun openPendingDraft(draft: ImageIntakeDraftDto) {
        _uiState.update {
            it.copy(
                activeDraft = draft,
                draftEntries = draft.entries,
                draftSummary = draft.summary,
                draftReplyText = "",
                previewImageBytes = null,
            )
        }
        viewModelScope.launch {
            val bytes = repo.fetchMediaBytes(draft.mediaUrl)
            if (bytes != null && _uiState.value.activeDraft?.id == draft.id) {
                _uiState.update { it.copy(previewImageBytes = bytes) }
            }
        }
    }

    fun closeDraftSheet() {
        _uiState.update {
            it.copy(
                activeDraft = null,
                draftEntries = emptyList(),
                draftSummary = "",
                draftReplyText = "",
                previewImageBytes = null,
            )
        }
    }

    fun updateDraftSummary(summary: String) {
        _uiState.update { it.copy(draftSummary = summary) }
    }

    fun updateDraftReplyText(replyText: String) {
        _uiState.update { it.copy(draftReplyText = replyText) }
    }

    fun toggleEntrySelected(index: Int, selected: Boolean) {
        _uiState.update { prev ->
            prev.copy(
                draftEntries = prev.draftEntries.mapIndexed { i, item ->
                    if (i == index) item.copy(selected = selected) else item
                },
            )
        }
    }

    fun updateEntryKind(index: Int, kind: String) {
        _uiState.update { prev ->
            prev.copy(
                draftEntries = prev.draftEntries.mapIndexed { i, item ->
                    if (i == index) item.copy(kind = kind) else item
                },
            )
        }
    }

    fun updateEntryTitle(index: Int, title: String) {
        _uiState.update { prev ->
            prev.copy(
                draftEntries = prev.draftEntries.mapIndexed { i, item ->
                    if (i == index) item.copy(title = title) else item
                },
            )
        }
    }

    fun updateEntryDataField(index: Int, key: String, value: JsonElement) {
        _uiState.update { prev ->
            prev.copy(
                draftEntries = prev.draftEntries.mapIndexed { i, item ->
                    if (i != index) return@mapIndexed item
                    val mutable = item.data.toMutableMap()
                    mutable[key] = value
                    item.copy(data = JsonObject(mutable))
                },
            )
        }
    }

    fun commitActiveDraft() {
        val state = _uiState.value
        val draft = state.activeDraft ?: return
        if (state.draftEntries.none { it.selected }) {
            _uiState.update { it.copy(feedbackMessage = "请至少勾选一条要落库的记录") }
            return
        }
        viewModelScope.launch {
            _uiState.update { it.copy(committingDraft = true) }
            val result = repo.commitIntakeDraft(
                draftId = draft.id,
                request = ImageIntakeCommitRequest(
                    entries = state.draftEntries,
                    summary = state.draftSummary.trim().ifBlank { draft.summary },
                    ticketId = draft.ticketId,
                    replyText = state.draftReplyText.trim().ifBlank { null },
                ),
            )
            result.fold(
                onSuccess = { committed ->
                    val labels = committed.committedRefs.mapNotNull { it.label.takeIf(String::isNotBlank) }
                    val msg = if (labels.isNotEmpty()) {
                        "已确认落库：${labels.joinToString(" · ")}"
                    } else {
                        "识图记录已落库并同步给 SailTick"
                    }
                    _uiState.update {
                        it.copy(
                            committingDraft = false,
                            activeDraft = null,
                            draftEntries = emptyList(),
                            draftSummary = "",
                            draftReplyText = "",
                            previewImageBytes = null,
                            feedbackMessage = msg,
                        )
                    }
                    refresh()
                },
                onFailure = { err ->
                    _uiState.update {
                        it.copy(
                            committingDraft = false,
                            feedbackMessage = "落库失败：${err.message ?: "请稍后重试"}",
                        )
                    }
                },
            )
        }
    }

    fun discardActiveDraft() {
        val draft = _uiState.value.activeDraft ?: return
        viewModelScope.launch {
            repo.discardIntakeDraft(draft.id)
            _uiState.update {
                it.copy(
                    activeDraft = null,
                    draftEntries = emptyList(),
                    draftSummary = "",
                    draftReplyText = "",
                    previewImageBytes = null,
                    feedbackMessage = "已丢弃该识图草稿",
                )
            }
            refresh()
        }
    }

    fun dismissErrorBanner() {
        _uiState.update { it.copy(errorBanner = null) }
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
