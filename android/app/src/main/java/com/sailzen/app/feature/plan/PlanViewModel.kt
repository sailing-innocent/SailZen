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
import com.sailzen.app.core.network.dto.AffairActions
import com.sailzen.app.core.network.dto.AffairCreateRequest
import com.sailzen.app.core.network.dto.AffairDto
import com.sailzen.app.core.network.dto.AffairStates
import com.sailzen.app.core.network.dto.CheckinTodayDto
import com.sailzen.app.core.network.dto.CheckinTodayItemDto
import com.sailzen.app.core.network.dto.DayTimelineDto
import com.sailzen.app.core.network.dto.HealthSignalItemDto
import com.sailzen.app.core.network.dto.ReviewDto
import com.sailzen.app.core.network.dto.RhythmDayViewDto
import com.sailzen.app.core.network.dto.TimeBlockDto
import com.sailzen.app.core.network.dto.VentureProgressDto
import com.sailzen.app.core.rhythm.AffairRules
import com.sailzen.app.core.rhythm.RhythmRepository
import com.sailzen.app.core.rhythm.RhythmTime
import java.time.LocalDate
import java.time.LocalDateTime
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch

/**
 * 规划页 ViewModel：合并原 时间线 / 打卡 / 事业 三个页面状态。
 *
 * - 今日 Tab：dayView(date) 一次聚合请求同时携带 blocks + checkins + healthSignals，
 *   inbox() 待分拣，reviewWeek() 周节奏卡；checkinToday() 仅作 dayView 缺 checkins 时的兜底。
 * - 事务 / 事业 Tab：懒加载（首次切入时拉取），切回今日不重复拉取；
 *   已加载过的 Tab 在 refresh() 时联动刷新（DataChangeBus 事件驱动）。
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
        val queuedCount: Int = 0,
        val message: String? = null,
        // 今日
        val timeline: DayTimelineDto? = null,
        val dayView: RhythmDayViewDto? = null,
        val checkins: CheckinTodayDto? = null,
        val healthSignals: List<HealthSignalItemDto> = emptyList(),
        val inbox: List<AffairDto> = emptyList(),
        val weekReview: ReviewDto? = null,
        val weekReviewOpen: Boolean = false,
        val planning: Boolean = false,
        val planBBlock: TimeBlockDto? = null,
        val planBText: String? = null,
        val captureOpen: Boolean = false, // 磁贴深链快速捕获弹窗
        // 事务
        val tasks: List<AffairDto> = emptyList(),
        val stateFilter: String = AffairStates.ACTIVE,
        val affairsLoaded: Boolean = false,
        // 事业
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

        /** Tab 切入时是否需要拉取数据（今日始终整体刷新，事务/事业懒加载） */
        fun shouldLazyLoad(tab: PlanTab, affairsLoaded: Boolean, venturesLoaded: Boolean): Boolean =
            when (tab) {
                PlanTab.TODAY -> true
                PlanTab.AFFAIR -> !affairsLoaded
                PlanTab.VENTURE -> !venturesLoaded
            }
    }

    private val repository = RhythmRepository.get(application)
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
            val dayView = repository.dayView(date)
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
            } ?: repository.timeline(date)
            // 打卡主源 dayView.checkins，服务端缺失时回退专用接口
            val checkins = dayView?.checkins ?: repository.checkinToday()
            val inbox = repository.inbox()
            val weekReview = repository.reviewWeek()
            val loadedAffairs = _uiState.value.affairsLoaded
            val loadedVentures = _uiState.value.venturesLoaded
            _uiState.update {
                it.copy(
                    timeline = timeline,
                    dayView = dayView,
                    checkins = checkins,
                    healthSignals = dayView?.healthSignals ?: emptyList(),
                    inbox = inbox,
                    weekReview = weekReview,
                    refreshing = false,
                    configured = settings.serverUrl().isNotBlank(),
                    serverUrl = settings.serverUrl(),
                    connected = ReminderService.connectedState.value,
                )
            }
            // 已加载过的 Tab 联动刷新（如：今日页启动事务后事务 Tab 列表同步）
            if (loadedAffairs) loadAffairs()
            if (loadedVentures) loadVentures()
        }
    }

    /** 事务 Tab 数据（懒加载：首次切入或筛选变化时调用） */
    fun loadAffairs() {
        viewModelScope.launch {
            val filter = _uiState.value.stateFilter
            val tasks = repository.listAffairs(state = filter)
                .filter { it.kind != AffairRules.VENTURE_KIND && it.kind != "buffer" }
                .sortedWith(taskComparator())
            _uiState.update { it.copy(tasks = tasks, affairsLoaded = true) }
        }
    }

    /** 事业 Tab 数据（懒加载） */
    fun loadVentures() {
        viewModelScope.launch {
            val all = repository.listAffairs(kinds = listOf(AffairRules.VENTURE_KIND))
            val activeIds = all.filter { it.state == AffairStates.ACTIVE }
            val progress = activeIds.mapNotNull { repository.ventureProgress(it.id) }
            val inbox = all.filter { it.state == AffairStates.INBOX }
            _uiState.update {
                it.copy(ventures = progress, inboxVentures = inbox, venturesLoaded = true)
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

    /** 日期切换（◀ ▶），重置事务/事业懒加载标记后整体刷新 */
    fun selectDate(prev: Boolean) {
        _uiState.update { it.copy(date = it.date.plusDays(if (prev) -1 else 1)) }
        refresh()
    }

    fun dismissMessage() = _uiState.update { it.copy(message = null) }

    // ---------------- 今日：日计划 / 时间线 ----------------

    /** 生成/重生成日计划 */
    fun plan() {
        viewModelScope.launch {
            _uiState.update { it.copy(planning = true) }
            repository.planDay(_uiState.value.date)
                .onSuccess {
                    refresh()
                    _uiState.update { it.copy(planning = false) }
                }
                .onFailure { _uiState.update { it.copy(planning = false) } }
        }
    }

    fun doneBlock(blockId: Int) = viewModelScope.launch {
        repository.blockDone(blockId)
            .onSuccess { refresh() }
    }

    fun skipBlock(blockId: Int) = viewModelScope.launch {
        repository.blockSkip(blockId)
            .onSuccess { refresh() }
    }

    /** 右滑 defer：推迟到明天 09:00（fixed 块 UI 层不出现该操作） */
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

    fun openWeekReview() = _uiState.update { it.copy(weekReviewOpen = true) }

    fun closeWeekReview() = _uiState.update { it.copy(weekReviewOpen = false) }

    // ---------------- 今日：快速捕获（CaptureBar + 磁贴深链弹窗） ----------------

    fun openCapture() = _uiState.update { it.copy(captureOpen = true) }

    fun closeCapture() = _uiState.update { it.copy(captureOpen = false) }

    fun capture(title: String, kind: String) = viewModelScope.launch {
        if (title.isBlank()) return@launch
        repository.capture(title.trim(), kind)
            .onSuccess {
                _uiState.update { it.copy(captureOpen = false) }
                refresh()
            }
    }

    // ---------------- 今日：AI 建议采纳 ----------------

    fun acceptHint(affairId: Int) = viewModelScope.launch {
        repository.acceptHintAndConfirm(affairId)
            .onSuccess { refresh() }
    }

    fun rejectHint(affairId: Int) = viewModelScope.launch {
        repository.confirmHint(affairId, accept = false)
            .onSuccess { refresh() }
    }

    // ---------------- 今日：打卡（戒律 / 习惯） ----------------

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

    // ---------------- 事务 / 事业 ----------------

    fun createVenture(title: String, targetDate: String?, weeklyBudgetHours: Double) {
        viewModelScope.launch {
            val meta = buildMap<String, Any> {
                if (!targetDate.isNullOrBlank()) put("target_date", targetDate)
                put("weekly_budget_hours", weeklyBudgetHours)
            }
            repository.createAffair(
                AffairCreateRequest(
                    title = title,
                    kind = AffairRules.VENTURE_KIND,
                    domain = "career",
                    kindMeta = AffairRules.jsonObjectOf(meta),
                ),
            )
                .onSuccess { created ->
                    // venture 为长期流：捕获后置 ACTIVE 才会进入事业视图
                    repository.transit(created.id, AffairActions.CONFIRM)
                    refresh()
                }
                .onFailure { _uiState.update { it.copy(message = "创建失败，请检查网络或服务器配置") } }
        }
    }

    fun createTask(title: String, kind: String, domain: String?, estMinutes: Int, ddlIso: String?) {
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
                .onSuccess { refresh() }
                .onFailure { _uiState.update { it.copy(message = "创建失败，请检查网络或服务器配置") } }
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
                .onSuccess { refresh() }
                .onFailure { _uiState.update { it.copy(message = "操作失败") } }
        }
    }
}
