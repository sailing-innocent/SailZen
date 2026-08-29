package com.sailzen.app.core.data

import java.time.LocalDate

/**
 * 领域数据变更事件：Repository 原子操作成功后广播，各 ViewModel 按业务域订阅并刷新。
 *
 * 设计原则：
 * - 事件按“业务域”划分，不携带完整数据，消费者收到后自行拉取最新状态；
 * - 尽量附带上下文（affairId / date），让详情页/日期页过滤后决定是否刷新，减少无效请求；
 * - 每个事件带时间戳，便于 UI 层去重或排序。
 */
sealed class DataChangeEvent {
    abstract val timestamp: Long

    /** 事务（affair）发生创建、更新、状态转移、删除等变更。 */
    data class AffairChanged(
        val affairId: Int? = null,
        val parentId: Int? = null,
        val action: String = "update",
        override val timestamp: Long = System.currentTimeMillis(),
    ) : DataChangeEvent()

    /** 体重记录发生变化。 */
    data class WeightChanged(
        override val timestamp: Long = System.currentTimeMillis(),
    ) : DataChangeEvent()

    /** 健康首页 dashboard 依赖的其它指标发生变化（运动、睡眠、用药、饮食、心情）。 */
    data class HealthSignalChanged(
        val collectionType: String? = null,
        val date: LocalDate? = null,
        override val timestamp: Long = System.currentTimeMillis(),
    ) : DataChangeEvent()

    /** 日时间线 / dayView 需要刷新（块完成、跳过、推迟、计划重排等）。 */
    data class DayViewChanged(
        val date: LocalDate? = null,
        override val timestamp: Long = System.currentTimeMillis(),
    ) : DataChangeEvent()

    /** 打卡记录发生变化（戒律/习惯打卡）。 */
    data class CheckinChanged(
        val affairId: Int? = null,
        override val timestamp: Long = System.currentTimeMillis(),
    ) : DataChangeEvent()

    /** 收件箱/提醒状态发生变化。 */
    data class InboxChanged(
        override val timestamp: Long = System.currentTimeMillis(),
    ) : DataChangeEvent()
}
