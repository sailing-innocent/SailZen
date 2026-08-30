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

@Dao
interface ReaderDao {

    @Upsert
    suspend fun upsertWork(item: CachedWork)

    @Upsert
    suspend fun upsertWorks(items: List<CachedWork>)

    @Query("SELECT * FROM cached_work ORDER BY updatedAt DESC")
    fun observeWorks(): Flow<List<CachedWork>>

    @Query("SELECT * FROM cached_work WHERE id = :workId")
    suspend fun workById(workId: Int): CachedWork?

    @Upsert
    suspend fun upsertChapter(item: CachedChapter)

    @Query("SELECT * FROM cached_chapter WHERE editionId = :editionId ORDER BY sortIndex ASC")
    suspend fun chaptersByEdition(editionId: Int): List<CachedChapter>

    @Query("SELECT * FROM cached_chapter WHERE editionId = :editionId AND sortIndex = :sortIndex LIMIT 1")
    suspend fun chapterByIndex(editionId: Int, sortIndex: Int): CachedChapter?

    @Upsert
    suspend fun upsertProgress(item: ReadingProgress)

    @Query("SELECT * FROM reading_progress WHERE workId = :workId LIMIT 1")
    suspend fun progressByWork(workId: Int): ReadingProgress?

    @Insert
    suspend fun insertAnnotation(item: CachedAnnotation): Long

    @Upsert
    suspend fun upsertAnnotation(item: CachedAnnotation)

    @Query("SELECT * FROM cached_annotation WHERE nodeId = :nodeId AND deleted = 0 ORDER BY startOffset ASC")
    suspend fun annotationsByNode(nodeId: Int): List<CachedAnnotation>

    @Query("SELECT * FROM cached_annotation WHERE editionId = :editionId AND deleted = 0 ORDER BY updatedAt DESC")
    suspend fun annotationsByEdition(editionId: Int): List<CachedAnnotation>

    @Query("SELECT * FROM cached_annotation WHERE synced = 0 AND deleted = 0 ORDER BY updatedAt ASC")
    suspend fun pendingAnnotations(): List<CachedAnnotation>

    @Query("SELECT * FROM cached_annotation WHERE deleted = 1 AND remoteId IS NOT NULL ORDER BY updatedAt ASC")
    suspend fun pendingDeletions(): List<CachedAnnotation>

    @Query("UPDATE cached_annotation SET synced = 1, remoteId = :remoteId, updatedAt = :updatedAt WHERE localId = :localId")
    suspend fun markAnnotationSynced(localId: Long, remoteId: Int, updatedAt: String)

    @Query("DELETE FROM cached_annotation WHERE localId = :localId")
    suspend fun deleteAnnotationByLocalId(localId: Long)

    @Query("UPDATE cached_annotation SET deleted = 1, synced = 0, updatedAt = :updatedAt WHERE localId = :localId")
    suspend fun markAnnotationDeleted(localId: Long, updatedAt: String)
}
