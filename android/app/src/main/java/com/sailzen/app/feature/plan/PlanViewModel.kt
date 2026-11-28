package com.sailzen.app.feature.plan

import android.app.Application
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import com.sailzen.app.core.bg.ReminderService
import com.sailzen.app.core.data.DataChangeBus
import com.sailzen.app.core.data.DataChangeEvent
import com.sailzen.app.core.data.SettingsManager
import com.sailzen.app.core.data.onFailure
import com.sailzen.app.core.data.onSuccess
import com.sailzen.app.core.network.ReminderWebSocket
import com.sailzen.app.core.network.dto.AffairActions
import com.sailzen.app.core.network.dto.AffairCreateRequest
import com.sailzen.app.core.network.dto.AffairDto
import com.sailzen.app.core.network.dto.AffairStates
import com.sailzen.app.core.network.dto.CheckinTodayDto
import com.sailzen.app.core.network.dto.CheckinTodayItemDto
import com.sailzen.app.core.network.dto.DayTimelineDto
import com.sailzen.app.core.network.dto.DomainSummaryDto
import com.sailzen.app.core.network.dto.HealthSignalItemDto
import com.sailzen.app.core.network.dto.OccupancyDto
import com.sailzen.app.core.network.dto.QuickChatHistoryItemDto
import com.sailzen.app.core.network.dto.RhythmDayViewDto
import com.sailzen.app.core.network.dto.TickTicketDto
import com.sailzen.app.core.network.dto.TimeBlockDto
import com.sailzen.app.core.network.dto.VentureProgressDto
import com.sailzen.app.core.rhythm.AffairRules
import com.sailzen.app.core.rhythm.RhythmRepository
import com.sailzen.app.core.rhythm.RhythmTime
import com.sailzen.app.core.tick.TickRepository
import java.time.LocalDate
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch

/**
 * 规划页 ViewModel（Rhythm v2 + SailTick Personal Agent）：
 *
 * - 今日 Tab：优先通过 `/api/v1/rhythm/dashboard` 单请求聚合当日时间线、AI 排程说明、
 *   临时占用、打卡、待分拣与重点项目；顶部内置 SailTick 随身协商入口，一句话调整日程并同步刷新。
 * - 待办 / 项目 Tab：支持按需懒加载与 DataChangeBus 自动联动；项目列表走单接口 `/venture/projects`，
 *   彻底告别旧版 N+1 进度轮询与重型权重/周预算公式。
 */
class PlanViewModel(application: Application) : AndroidViewModel(application) {

    enum class PlanTab { TODAY, AFFAIR, VENTURE }

    data class UiState(
        // 通用
        val date: LocalDate = LocalDate.now(),
        val selectedTab: PlanTab = PlanTab.TODAY,
        val refreshing: Boolean = false,
        val configured: Boolean = true,
        val serverUrl: String = "",
        val connected: Boolean = false,
        val connectionState: ReminderWebSocket.ConnectionState = ReminderWebSocket.ConnectionState.DISCONNECTED,
        val connectionDetail: String = "",
        val queuedCount: Int = 0,
        val message: String? = null,
        // 今日
        val timeline: DayTimelineDto? = null,
        val dayView: RhythmDayViewDto? = null,
        val checkins: CheckinTodayDto? = null,
        val healthSignals: List<HealthSignalItemDto> = emptyList(),
        val inbox: List<AffairDto> = emptyList(),
        val occupancies: List<OccupancyDto> = emptyList(),
        // SailTick 实时协商（节奏规划师分域：多端共享 owner:rhythm）
        val chatBusy: Boolean = false,
        val chatReply: String? = null,
        val chatHistory: List<QuickChatHistoryItemDto> = emptyList(),
        val chatIsAsyncFallback: Boolean = false,
        val domainSummary: DomainSummaryDto? = null,
        val ticketBusyId: Int? = null,
        val occupancyDialogOpen: Boolean = false,
        val planBBlock: TimeBlockDto? = null,
        val planBText: String? = null,
        val captureOpen: Boolean = false, // 磁贴深链快速捕获弹窗
        // 待办
        val tasks: List<AffairDto> = emptyList(),
        val stateFilter: String = AffairStates.ACTIVE,
        val affairsLoaded: Boolean = false,
        // 项目
        val ventures: List<VentureProgressDto> = emptyList(),
        val inboxVentures: List<AffairDto> = emptyList(),
        val venturesLoaded: Boolean = false,
        // 打卡弹窗
        val noteTarget: CheckinTodayItemDto? = null,
    )

    companion object {
        /** 任务排序：逾期优先 → 截止升序 → 重要性降序 */
        fun taskComparator(): Comparator<AffairDto> = compareBy(
            { if (RhythmTime.hoursUntil(it.urgencyDdl) < 0) -1 else 0 },
            { RhythmTime.hoursUntil(it.urgencyDdl) },
            { -it.importance },
        )

        /** 待分拣拆分：AI 建议卡 / 普通 INBOX 卡 */
        fun splitInbox(inbox: List<AffairDto>): Pair<List<AffairDto>, List<AffairDto>> =
            inbox.filter { it.aiHint.isNotEmpty() } to inbox.filter { it.aiHint.isEmpty() }

        /** Tab 切入时是否需要拉取数据（今日始终整体刷新，待办/项目懒加载） */
        fun shouldLazyLoad(tab: PlanTab, affairsLoaded: Boolean, venturesLoaded: Boolean): Boolean =
            when (tab) {
                PlanTab.TODAY -> true
                PlanTab.AFFAIR -> !affairsLoaded
                PlanTab.VENTURE -> !venturesLoaded
            }

        /** 紧凑时长展示：90 -> "1.5h"，45 -> "45m" */
        fun formatMinutesCompact(minutes: Int): String {
            if (minutes <= 0) return "0m"
            return if (minutes >= 60) {
                val hours = minutes / 60.0
                if (minutes % 60 == 0) "${minutes / 60}h" else "%.1fh".format(hours)
            } else {
                "${minutes}m"
            }
        }

        /** 项目目标日倒计时文案与紧急标识（用于项目卡片轻量展示，替代旧倒排压力公式） */
        fun projectDeadlineBadge(daysLeft: Int?): Pair<String, Boolean> = when {
            daysLeft == null -> "未定目标日" to false
            daysLeft < 0 -> "超期 ${-daysLeft} 天" to true
            daysLeft == 0 -> "今日截止" to true
            daysLeft <= 7 -> "剩 $daysLeft 天" to true
            else -> "剩 $daysLeft 天" to false
        }
    }

    private val repository = RhythmRepository.get(application)
    private val tickRepository = TickRepository.get(application)
    private val settings = SettingsManager.get(application)
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
            settings.serverUrlFlow.collect { url ->
                _uiState.update { it.copy(serverUrl = url, configured = url.isNotBlank()) }
            }
        }
        viewModelScope.launch {
            ReminderService.connectedState.collect { connected ->
                _uiState.update { it.copy(connected = connected) }
            }
        }
        viewModelScope.launch {
            ReminderService.connectionState.collect { connState ->
                _uiState.update { it.copy(connectionState = connState) }
            }
        }
        viewModelScope.launch {
            ReminderService.connectionDetail.collect { detail ->
                _uiState.update { it.copy(connectionDetail = detail) }
            }
        }
        viewModelScope.launch {
            bus.events.collect { event ->
                when (event) {
                    is DataChangeEvent.AffairChanged,
                    is DataChangeEvent.DayViewChanged,
                    is DataChangeEvent.CheckinChanged,
                    -> refresh()
                    else -> {}
                }
            }
        }
        refresh()
    }

    // ---------------- 刷新管道 ----------------

    fun refresh() {
        viewModelScope.launch {
            _uiState.update { it.copy(refreshing = true) }
            repository.flushPending()
            val date = _uiState.value.date
            val dash = repository.dashboard(date)
            val dayView = repository.dayView(date)

            val timeline = dash?.timeline
                ?: dayView?.let { dv ->
                    DayTimelineDto(
                        date = dv.date,
                        dayId = dv.dayId,
                        planVersion = dv.planVersion,
                        aiRationale = dv.aiRationale,
                        blocks = dv.blocks,
                        domainMinutes = dv.domainMinutes,
                        checkins = dv.checkins,
                    )
                }
                ?: repository.timeline(date)

            val checkins = dash?.todayCheckins?.takeIf {
                it.precepts.isNotEmpty() || it.habits.isNotEmpty() || it.date.isNotBlank()
            } ?: dayView?.checkins ?: repository.checkinToday()

            val inbox = dash?.inboxAffairs ?: repository.inbox()
            val occupancies = dash?.occupancies ?: emptyList()
            val loadedAffairs = _uiState.value.affairsLoaded
            val loadedVentures = _uiState.value.venturesLoaded
            val domainSum = tickRepository.loadDomainSummary("rhythm")
            val chatHist = tickRepository.loadQuickChatHistory("rhythm", 10)

            _uiState.update { prev ->
                prev.copy(
                    timeline = timeline,
                    dayView = dayView,
                    checkins = checkins,
                    healthSignals = dayView?.healthSignals ?: emptyList(),
                    inbox = inbox,
                    occupancies = occupancies,
                    ventures = dash?.projects ?: prev.ventures,
                    venturesLoaded = if (dash != null) true else prev.venturesLoaded,
                    domainSummary = domainSum ?: prev.domainSummary,
                    chatHistory = if (chatHist.isNotEmpty()) chatHist else prev.chatHistory,
                    refreshing = false,
                    configured = settings.serverUrl().isNotBlank(),
                    serverUrl = settings.serverUrl(),
                    connected = ReminderService.connectedState.value,
                )
            }
            if (loadedAffairs) loadAffairs()
            if (loadedVentures && dash == null) loadVentures()
        }
    }

    /** 待办 Tab 数据（懒加载：首次切入或筛选变化时调用） */
    fun loadAffairs() {
        viewModelScope.launch {
            val filter = _uiState.value.stateFilter
            val tasks = repository.listAffairs(state = filter)
                .filter { it.kind != AffairRules.VENTURE_KIND && it.kind != "buffer" }
                .sortedWith(taskComparator())
            _uiState.update { it.copy(tasks = tasks, affairsLoaded = true) }
        }
    }

    /** 项目 Tab 数据（单请求 `/venture/projects` + INBOX 待启项目） */
    fun loadVentures() {
        viewModelScope.launch {
            val projects = repository.listProjects()
            val inbox = repository.listAffairs(
                state = AffairStates.INBOX,
                kinds = listOf(AffairRules.VENTURE_KIND),
            )
            _uiState.update {
                it.copy(ventures = projects, inboxVentures = inbox, venturesLoaded = true)
            }
        }
    }

    // ---------------- 页内 Tab / 筛选 / 日期 ----------------

    fun selectTab(tab: PlanTab) {
        if (_uiState.value.selectedTab == tab) return
        _uiState.update { it.copy(selectedTab = tab) }
        val s = _uiState.value
        when {
            tab == PlanTab.TODAY -> refresh()
            shouldLazyLoad(tab, s.affairsLoaded, s.venturesLoaded) -> when (tab) {
                PlanTab.AFFAIR -> loadAffairs()
                PlanTab.VENTURE -> loadVentures()
                PlanTab.TODAY -> {}
            }
        }
    }

    fun selectStateFilter(state: String) {
        _uiState.update { it.copy(stateFilter = state) }
        loadAffairs()
    }

    /** 日期切换（◀ ▶） */
    fun selectDate(prev: Boolean) {
        _uiState.update { it.copy(date = it.date.plusDays(if (prev) -1 else 1)) }
        refresh()
    }

    /** 回到今天 */
    fun selectToday() {
        val today = LocalDate.now()
        if (_uiState.value.date != today) {
            _uiState.update { it.copy(date = today) }
            refresh()
        }
    }

    /** 主动触发一次重连与刷新 */
    fun reconnect() {
        val app = getApplication<Application>()
        if (_uiState.value.serverUrl.isNotBlank()) {
            ReminderService.restart(app)
        }
        refresh()
    }

    fun dismissMessage() = _uiState.update { it.copy(message = null) }

    // ---------------- SailTick 实时协商（节奏规划师分域） ----------------

    fun sendQuickChat(text: String) {
        val trimmed = text.trim()
        if (trimmed.isEmpty() || _uiState.value.chatBusy) return
        viewModelScope.launch {
            _uiState.update {
                it.copy(
                    chatBusy = true,
                    chatHistory = (it.chatHistory + QuickChatHistoryItemDto(
                        role = "user",
                        content = trimmed,
                        domain = "rhythm",
                        surface = "android_plan",
                    )).takeLast(12),
                )
            }
            tickRepository.quickChat(
                text = trimmed,
                channel = "android",
                domain = "rhythm",
                surface = "android_plan",
            ).fold(
                onSuccess = { res ->
                    _uiState.update {
                        it.copy(
                            chatBusy = false,
                            chatReply = res.reply,
                            chatHistory = (it.chatHistory + QuickChatHistoryItemDto(
                                role = "assistant",
                                content = res.reply,
                                domain = res.domain,
                            )).takeLast(12),
                            chatIsAsyncFallback = res.fallbackAsync,
                            message = if (res.rhythmUpdated) "节奏规划师已更新今日日程" else null,
                        )
                    }
                    if (res.rhythmUpdated) refresh()
                },
                onFailure = {
                    _uiState.update {
                        it.copy(
                            chatBusy = false,
                            message = "无法发送给 SailTick，请检查网络与服务器配置",
                        )
                    }
                },
            )
        }
    }

    fun replyDomainTicket(ticketId: Int, reply: String) {
        val trimmed = reply.trim()
        if (trimmed.isEmpty() || _uiState.value.ticketBusyId != null) return
        viewModelScope.launch {
            _uiState.update { it.copy(ticketBusyId = ticketId) }
            val res = tickRepository.replyTicket(ticketId, trimmed)
            _uiState.update {
                it.copy(
                    ticketBusyId = null,
                    message = if (res != null) "已回复节奏规划师，多端同步关闭" else "回复失败，请检查网络",
                )
            }
            if (res != null) refresh()
        }
    }

    fun snoozeDomainTicket(ticketId: Int) {
        if (_uiState.value.ticketBusyId != null) return
        viewModelScope.launch {
            _uiState.update { it.copy(ticketBusyId = ticketId) }
            val res = tickRepository.snoozeTicket(ticketId, 24)
            _uiState.update {
                it.copy(
                    ticketBusyId = null,
                    message = if (res != null) "已暂缓 24 小时" else "操作失败，请检查网络",
                )
            }
            if (res != null) refresh()
        }
    }

    fun clearChatReply() = _uiState.update {
        it.copy(chatReply = null, chatIsAsyncFallback = false)
    }

    // ---------------- 临时占用 & 时间线块操作 ----------------

    fun openOccupancyDialog() = _uiState.update { it.copy(occupancyDialogOpen = true) }

    fun closeOccupancyDialog() = _uiState.update { it.copy(occupancyDialogOpen = false) }

    fun createOccupancy(
        occupancyType: String,
        start: String?,
        end: String?,
        wholeDay: Boolean,
        label: String,
        note: String = "",
    ) {
        viewModelScope.launch {
            repository.createOccupancy(
                date = _uiState.value.date,
                occupancyType = occupancyType,
                start = start,
                end = end,
                wholeDay = wholeDay,
                label = label,
                note = note,
            )
                .onSuccess {
                    _uiState.update {
                        it.copy(
                            occupancyDialogOpen = false,
                            message = "已钉住占用时段，AI 排程会自动避开",
                        )
                    }
                    refresh()
                }
                .onFailure {
                    _uiState.update { it.copy(message = "创建占用失败，请检查时间格式 (HH:MM)") }
                }
        }
    }

    fun deleteBlock(blockId: Int) = viewModelScope.launch {
        repository.deleteBlock(blockId)
            .onSuccess { refresh() }
            .onFailure { _uiState.update { it.copy(message = "移除时间块失败") } }
    }

    fun deleteOccupancy(blockId: Int) = viewModelScope.launch {
        repository.deleteOccupancy(blockId)
            .onSuccess {
                _uiState.update { it.copy(message = "已取消该占用时段") }
                refresh()
            }
            .onFailure { _uiState.update { it.copy(message = "取消占用失败") } }
    }

    fun doneBlock(blockId: Int) = viewModelScope.launch {
        repository.blockDone(blockId)
            .onSuccess { refresh() }
    }

    fun skipBlock(blockId: Int) = viewModelScope.launch {
        repository.blockSkip(blockId)
            .onSuccess { refresh() }
    }

    /** 右滑 defer：推迟到明天 09:00（fixed/occupied 块 UI 层不出现该操作） */
    fun deferBlock(block: TimeBlockDto) = viewModelScope.launch {
        val affairId = block.affairId ?: return@launch
        val tomorrow = LocalDate.now().plusDays(1).atTime(9, 0)
        repository.deferAffair(affairId, tomorrow.withNano(0).toString())
            .onSuccess { refresh() }
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

    // ---------------- 快速捕获（磁贴深链弹窗） ----------------

    fun openCapture() = _uiState.update { it.copy(captureOpen = true) }

    fun closeCapture() = _uiState.update { it.copy(captureOpen = false) }

    fun capture(title: String, kind: String = "task_oneoff") = viewModelScope.launch {
        if (title.isBlank()) return@launch
        repository.capture(title.trim(), kind)
            .onSuccess {
                _uiState.update { it.copy(captureOpen = false, message = "已记录到待办") }
                refresh()
            }
    }

    // ---------------- 待分拣 AI 建议采纳 ----------------

    fun acceptHint(affairId: Int) = viewModelScope.launch {
        repository.acceptHintAndConfirm(affairId)
            .onSuccess { refresh() }
    }

    fun rejectHint(affairId: Int) = viewModelScope.launch {
        repository.confirmHint(affairId, accept = false)
            .onSuccess { refresh() }
    }

    // ---------------- 今日：打卡（戒律 / 习惯） ----------------

    fun preceptKept(item: CheckinTodayItemDto) = checkin(item.affair.id, "kept")

    fun preceptViolated(item: CheckinTodayItemDto) =
        _uiState.update { it.copy(noteTarget = item) }

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

    // ---------------- 待办 / 项目 ----------------

    fun createVenture(title: String, targetDate: String?, description: String = "") {
        viewModelScope.launch {
            val meta = buildMap<String, Any> {
                if (!targetDate.isNullOrBlank()) put("target_date", targetDate)
            }
            repository.createAffair(
                AffairCreateRequest(
                    title = title,
                    description = description,
                    kind = AffairRules.VENTURE_KIND,
                    domain = "career",
                    kindMeta = AffairRules.jsonObjectOf(meta),
                ),
            )
                .onSuccess { created ->
                    repository.transit(created.id, AffairActions.CONFIRM)
                    _uiState.update { it.copy(message = "已创建项目，SailTick 会在后续排程中自动推进") }
                    refresh()
                    loadVentures()
                }
                .onFailure { _uiState.update { it.copy(message = "创建项目失败，请检查网络或服务器配置") } }
        }
    }

    fun createTask(
        title: String,
        ddlIso: String? = null,
        estMinutes: Int = 30,
        domain: String? = "work",
        kind: String = "task_oneoff",
    ) {
        viewModelScope.launch {
            repository.createAffair(
                AffairCreateRequest(
                    title = title,
                    kind = kind,
                    domain = domain,
                    estMinutes = estMinutes,
                    urgencyDdl = ddlIso,
                ),
            )
                .onSuccess {
                    _uiState.update { it.copy(message = "已创建待办") }
                    refresh()
                    loadAffairs()
                }
                .onFailure { _uiState.update { it.copy(message = "创建待办失败，请检查网络或服务器配置") } }
        }
    }

    fun transit(affairId: Int, action: String) {
        viewModelScope.launch {
            repository.transit(affairId, action)
                .onSuccess { refresh() }
                .onFailure { _uiState.update { it.copy(message = "操作失败：当前状态不允许该动作") } }
        }
    }

    fun milestoneDone(milestoneId: Int) {
        viewModelScope.launch {
            repository.milestoneDone(milestoneId)
                .onSuccess {
                    refresh()
                    loadVentures()
                }
                .onFailure { _uiState.update { it.copy(message = "操作失败") } }
        }
    }
}
