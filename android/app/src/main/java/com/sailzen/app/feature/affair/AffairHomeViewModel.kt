package com.sailzen.app.feature.affair

import android.app.Application
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import com.sailzen.app.core.network.dto.AffairActions
import com.sailzen.app.core.network.dto.AffairCreateRequest
import com.sailzen.app.core.network.dto.AffairDto
import com.sailzen.app.core.network.dto.AffairStates
import com.sailzen.app.core.network.dto.LONGTERM_KINDS
import com.sailzen.app.core.network.dto.VentureProgressDto
import com.sailzen.app.core.rhythm.RhythmRepository
import com.sailzen.app.core.rhythm.RhythmTime
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch

/**
 * 统一事务页 ViewModel：
 * - 事业视图：ACTIVE 的 kind=venture + 倒排进度
 * - 任务视图：其余 kind 的事务，按状态分组
 */
class AffairHomeViewModel(application: Application) : AndroidViewModel(application) {

    enum class Tab { VENTURE, TASK }

    data class UiState(
        val tab: Tab = Tab.VENTURE,
        val ventures: List<VentureProgressDto> = emptyList(),
        val tasks: List<AffairDto> = emptyList(),
        val stateFilter: String? = null,
        val loading: Boolean = false,
        val configured: Boolean = true,
        val message: String? = null,
    )

    private val repository = RhythmRepository.get(application)

    private val _uiState = MutableStateFlow(UiState())
    val uiState: StateFlow<UiState> = _uiState.asStateFlow()

    init {
        refresh()
    }

    fun selectTab(tab: Tab) {
        _uiState.update { it.copy(tab = tab) }
        refresh()
    }

    fun selectStateFilter(state: String?) {
        _uiState.update { it.copy(stateFilter = state) }
        refresh()
    }

    fun dismissMessage() = _uiState.update { it.copy(message = null) }

    fun refresh() {
        viewModelScope.launch {
            _uiState.update { it.copy(loading = true) }
            val configured = repository.serverConfigured()
            when (_uiState.value.tab) {
                Tab.VENTURE -> {
                    val progress = repository
                        .listAffairs(state = AffairStates.ACTIVE, kinds = listOf(VENTURE_KIND))
                        .mapNotNull { repository.ventureProgress(it.id) }
                    _uiState.update {
                        it.copy(loading = false, configured = configured, ventures = progress)
                    }
                }

                Tab.TASK -> {
                    val filter = _uiState.value.stateFilter
                    val tasks = repository.listAffairs(state = filter)
                        .filter { it.kind != VENTURE_KIND && it.kind != "buffer" }
                        .sortedWith(compareBy({ RhythmTime.hoursUntil(it.urgencyDdl) }, { -it.importance }))
                    _uiState.update {
                        it.copy(loading = false, configured = configured, tasks = tasks)
                    }
                }
            }
        }
    }

    fun createVenture(title: String, targetDate: String?, weeklyBudgetHours: Double) {
        viewModelScope.launch {
            val meta = buildMap<String, Any> {
                if (!targetDate.isNullOrBlank()) put("target_date", targetDate)
                put("weekly_budget_hours", weeklyBudgetHours)
            }
            val created = repository.createAffair(
                AffairCreateRequest(
                    title = title,
                    kind = VENTURE_KIND,
                    domain = "career",
                    kindMeta = jsonObjectOf(meta),
                ),
            )
            if (created == null) {
                _uiState.update { it.copy(message = "创建失败，请检查网络或服务器配置") }
            } else {
                // venture 为长期流：捕获后置 ACTIVE 才会进入事业视图
                repository.transit(created.id, AffairActions.CONFIRM)
                refresh()
            }
        }
    }

    fun createTask(title: String, kind: String, domain: String?, estMinutes: Int, ddlIso: String?) {
        viewModelScope.launch {
            val created = repository.createAffair(
                AffairCreateRequest(
                    title = title,
                    kind = kind,
                    domain = domain,
                    estMinutes = estMinutes,
                    urgencyDdl = ddlIso,
                ),
            )
            if (created == null) {
                _uiState.update { it.copy(message = "创建失败，请检查网络或服务器配置") }
            } else {
                refresh()
            }
        }
    }

    fun transit(affairId: Int, action: String) {
        viewModelScope.launch {
            val result = repository.transit(affairId, action)
            if (result == null) {
                _uiState.update { it.copy(message = "操作失败：当前状态不允许该动作") }
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

    companion object {
        const val VENTURE_KIND = "venture"

        /** 任务视图可筛选的状态 */
        val TASK_STATE_FILTERS = listOf(
            null,
            AffairStates.INBOX,
            AffairStates.PLANNED,
            AffairStates.SCHEDULED,
            AffairStates.DOING,
            AffairStates.DONE,
        )

        fun isTerminal(state: String): Boolean = state in AffairStates.TERMINAL

        fun isOverdue(urgencyDdl: String?, state: String): Boolean =
            !isTerminal(state) && RhythmTime.hoursUntil(urgencyDdl) < 0

        /** 单个事务在当前状态下可用的动作（与服务端状态机一致） */
        fun availableActions(kind: String, state: String): List<Pair<String, String>> {
            if (isTerminal(state)) return emptyList()
            return if (kind in LONGTERM_KINDS) {
                when (state) {
                    AffairStates.INBOX -> listOf(
                        AffairActions.CONFIRM to "启动",
                        AffairActions.CANCEL to "取消",
                    )
                    AffairStates.ACTIVE -> buildList {
                        add(AffairActions.PAUSE to "暂停")
                        if (kind == VENTURE_KIND) add(AffairActions.GRADUATE to "毕业")
                        add(AffairActions.ARCHIVE to "归档")
                    }
                    AffairStates.PAUSED -> listOf(
                        AffairActions.RESUME to "恢复",
                        AffairActions.ARCHIVE to "归档",
                    )
                    else -> emptyList()
                }
            } else {
                when (state) {
                    AffairStates.INBOX -> listOf(
                        AffairActions.CONFIRM to "确认",
                        AffairActions.CANCEL to "取消",
                    )
                    AffairStates.PLANNED, AffairStates.SCHEDULED -> listOf(
                        AffairActions.START to "开始",
                        AffairActions.FINISH to "完成",
                        AffairActions.CANCEL to "取消",
                    )
                    AffairStates.DOING -> listOf(AffairActions.FINISH to "完成")
                    AffairStates.DEFERRED -> listOf(
                        AffairActions.REPLAN to "重新规划",
                        AffairActions.CANCEL to "取消",
                    )
                    else -> emptyList()
                }
            }
        }

        fun jsonObjectOf(values: Map<String, Any>): kotlinx.serialization.json.JsonObject =
            kotlinx.serialization.json.JsonObject(
                values.mapValues { (_, v) ->
                    when (v) {
                        is Number -> kotlinx.serialization.json.JsonPrimitive(v)
                        is Boolean -> kotlinx.serialization.json.JsonPrimitive(v)
                        else -> kotlinx.serialization.json.JsonPrimitive(v.toString())
                    }
                },
            )
    }
}
