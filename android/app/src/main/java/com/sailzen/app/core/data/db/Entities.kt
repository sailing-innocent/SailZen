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
    val payloadJson: String,
    val clientEventTs: String,
    val retryCount: Int = 0,
)

/**
 * 提醒来源配置本地缓存（服务端 source_config 表）。
 */
@Entity(tableName = "source_config_cache")
data class CachedSourceConfig(
    @PrimaryKey val source: String,
    val sourceType: String,
    val enabled: Boolean,
    val defaultPriority: String,
    val allowedChannelsJson: String,
    val quietHoursOverrideJson: String?,
    val description: String,
    val updatedAt: String,
)

// ------------------------------------------------------------------
// 文本阅读模块本地缓存
// ------------------------------------------------------------------

@Entity(tableName = "cached_work")
data class CachedWork(
    @PrimaryKey val id: Int,
    val slug: String,
    val title: String,
    val author: String?,
    val synopsis: String?,
    val updatedAt: String,
)

@Entity(tableName = "cached_chapter")
data class CachedChapter(
    @PrimaryKey val id: Int,
    val editionId: Int,
    val sortIndex: Int,
    val label: String,
    val title: String,
    val rawText: String,
    val charCount: Int?,
    val updatedAt: String,
)

@Entity(tableName = "reading_progress")
data class ReadingProgress(
    @PrimaryKey val workId: Int,
    val editionId: Int,
    val nodeId: Int,
    val sortIndex: Int,
    val mode: String, // "page" | "scroll"
    val pageIndex: Int = 0,
    val scrollOffset: Int = 0,
    val fontSize: Int = 18,
    val lineHeight: Float = 1.5f,
    val theme: String = "light",
    val updatedAt: String,
)

@Entity(tableName = "cached_annotation")
data class CachedAnnotation(
    @PrimaryKey(autoGenerate = true) val localId: Long = 0,
    val workId: Int,
    val editionId: Int,
    val nodeId: Int,
    val startOffset: Int,
    val endOffset: Int,
    val selectedText: String,
    val note: String,
    val color: String,
    val createdAt: String,
    val updatedAt: String,
    val synced: Boolean = false,
    val remoteId: Int? = null,
    val deleted: Boolean = false,
)
