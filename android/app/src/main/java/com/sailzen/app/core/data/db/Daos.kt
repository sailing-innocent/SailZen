package com.sailzen.app.core.data.db

import androidx.room.Dao
import androidx.room.Insert
import androidx.room.Query
import androidx.room.Upsert
import kotlinx.coroutines.flow.Flow

@Dao
interface ReminderDao {

    @Upsert
    suspend fun upsert(item: CachedReminder)

    @Upsert
    suspend fun upsertAll(items: List<CachedReminder>)

    @Query("SELECT * FROM reminder_cache WHERE id = :id")
    suspend fun byId(id: Int): CachedReminder?

    @Query(
        "SELECT * FROM reminder_cache " +
            "WHERE state IN ('PENDING', 'DELIVERED', 'SNOOZED', 'OPENED') " +
            "ORDER BY triggerTime ASC"
    )
    fun observeActive(): Flow<List<CachedReminder>>

    @Query(
        "SELECT * FROM reminder_cache " +
            "WHERE state IN ('PENDING', 'DELIVERED', 'SNOOZED', 'OPENED')"
    )
    suspend fun activeList(): List<CachedReminder>

    /** 未来需要排本地闹钟的提醒（PENDING 且 triggerTime > nowIso） */
    @Query(
        "SELECT * FROM reminder_cache WHERE state = 'PENDING' AND triggerTime > :nowIso"
    )
    suspend fun futurePending(nowIso: String): List<CachedReminder>

    @Query("DELETE FROM reminder_cache WHERE id = :id")
    suspend fun delete(id: Int)

    @Query("DELETE FROM reminder_cache")
    suspend fun clear()
}

@Dao
interface FeedbackDao {

    @Insert
    suspend fun insert(item: PendingFeedback): Long

    @Query("SELECT * FROM pending_feedback ORDER BY autoId ASC")
    suspend fun all(): List<PendingFeedback>

    @Query("DELETE FROM pending_feedback WHERE autoId = :autoId")
    suspend fun delete(autoId: Long)

    @Query("UPDATE pending_feedback SET retryCount = retryCount + 1 WHERE autoId = :autoId")
    suspend fun bumpRetry(autoId: Long)

    @Query("SELECT COUNT(*) FROM pending_feedback")
    fun observeCount(): Flow<Int>
}

@Dao
interface RhythmActionDao {

    @Insert
    suspend fun insert(item: PendingRhythmAction): Long

    @Query("SELECT * FROM pending_rhythm_action ORDER BY autoId ASC")
    suspend fun all(): List<PendingRhythmAction>

    @Query("DELETE FROM pending_rhythm_action WHERE autoId = :autoId")
    suspend fun delete(autoId: Long)

    @Query("UPDATE pending_rhythm_action SET retryCount = retryCount + 1 WHERE autoId = :autoId")
    suspend fun bumpRetry(autoId: Long)

    @Query("SELECT COUNT(*) FROM pending_rhythm_action")
    fun observeCount(): Flow<Int>
}

@Dao
interface SourceConfigDao {
    @Upsert
    suspend fun upsert(item: CachedSourceConfig)

    @Upsert
    suspend fun upsertAll(items: List<CachedSourceConfig>)

    @Query("SELECT * FROM source_config_cache WHERE source = :source")
    suspend fun bySource(source: String): CachedSourceConfig?

    @Query("SELECT * FROM source_config_cache ORDER BY source ASC")
    fun observeAll(): Flow<List<CachedSourceConfig>>

    @Query("DELETE FROM source_config_cache")
    suspend fun clear()
}
