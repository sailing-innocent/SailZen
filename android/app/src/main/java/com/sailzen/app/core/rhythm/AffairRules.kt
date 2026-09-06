package com.sailzen.app.core.rhythm

import com.sailzen.app.core.network.dto.AffairActions
import com.sailzen.app.core.network.dto.AffairStates
import com.sailzen.app.core.network.dto.LONGTERM_KINDS

/**
 * 事务状态机共享规则（纯函数，源自原 AffairHomeViewModel.Companion）。
 *
 * 供规划页（事务/事业 Tab）、事务详情页与单元测试共同引用，
 * 避免页面合并/删除时产生断裂引用。
 */
object AffairRules {

    const val VENTURE_KIND = "venture"

    /** 任务视图可筛选的状态 */
    val TASK_STATE_FILTERS = listOf(
        AffairStates.ACTIVE,
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
