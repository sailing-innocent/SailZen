package com.sailzen.app.core.data.db

import androidx.room.Entity
import androidx.room.PrimaryKey

/**
 * 提醒本地缓存（Server 是唯一事实源，这里只是缓存）。
 * 时间字段一律 ISO-8601 字符串（服务端 naive 本地时间），避免时区换算。
 */
@Entity(tableName = "reminder_cache")
data class CachedReminder(
    @PrimaryKey val id: Int,
    val type: String,
    val title: String,
    val body: String,
    val priority: String,
    val state: String,
    val triggerTime: String,
    val expireAfterMinutes: Int,
    val snoozeCount: Int,
    val payloadJson: String,
    val updatedAt: String,
)

/**
 * 离线反馈队列：网络不可用时暂存，联网后按序批量上报，
 * 服务端按 client_event_ts 还原时序。
 */
@Entity(tableName = "pending_feedback")
data class PendingFeedback(
    @PrimaryKey(autoGenerate = true) val autoId: Long = 0,
    val reminderId: Int,
    val action: String, // dismiss | snooze | open | resolve
    val option: String?, // snooze: 15m | 1h | tonight | tomorrow
    val clientEventTs: String,
    val retryCount: Int = 0,
)

/**
 * Rhythm 离线动作队列（M3）：网络不可用时暂存 done/defer/checkin/capture，
 * 联网后按序批量补传（复用提醒“离线排队补传”模式）。
 */
@Entity(tableName = "pending_rhythm_action")
data class PendingRhythmAction(
    @PrimaryKey(autoGenerate = true) val autoId: Long = 0,
    val actionType: String, // block_done | block_skip | block_move | checkin | capture | defer
    val targetId: Int = 0, // block_id / affair_id（capture 为 0）
    val payloadJson: String = "{}", // 请求体 JSON
    val clientEventTs: String,
    val retryCount: Int = 0,
)
