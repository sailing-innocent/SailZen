package com.sailzen.app.core.text

import android.content.Context
import android.util.Log
import com.sailzen.app.core.data.SettingsManager
import com.sailzen.app.core.data.db.AppDatabase
import com.sailzen.app.core.data.db.CachedAnnotation
import com.sailzen.app.core.data.db.CachedChapter
import com.sailzen.app.core.data.db.CachedWork
import com.sailzen.app.core.data.db.ReadingProgress
import com.sailzen.app.core.network.ApiClient
import com.sailzen.app.core.network.TextApi
import com.sailzen.app.core.network.dto.ChapterListItemDto
import com.sailzen.app.core.network.dto.DocumentNodeDto
import com.sailzen.app.core.network.dto.EditionDto
import com.sailzen.app.core.network.dto.NoteContentUpdateRequest
import com.sailzen.app.core.network.dto.NoteItemCreateRequest
import com.sailzen.app.core.network.dto.NoteItemUpdateRequest
import com.sailzen.app.core.network.dto.WorkDto
import java.time.LocalDateTime
import kotlinx.coroutines.flow.Flow
import kotlinx.serialization.json.JsonElement
import kotlinx.serialization.json.JsonPrimitive

private fun JsonElement?.jsonPrimitive(): JsonPrimitive? = this as? JsonPrimitive

/** 组装批注锚点 meta，与 create 接口的锚点字段保持一致 */
private fun annotationMeta(item: CachedAnnotation): Map<String, JsonElement?> = mapOf(
    "node_id" to JsonPrimitive(item.nodeId),
    "start_offset" to JsonPrimitive(item.startOffset),
    "end_offset" to JsonPrimitive(item.endOffset),
    "selected_text" to JsonPrimitive(item.selectedText),
    "color" to JsonPrimitive(item.color),
)

/**
 * 阅读模块 Repository：作品/章节缓存、阅读进度、批注同步。
 */
class TextRepository private constructor(private val context: Context) {

    companion object {
        private const val TAG = "TextRepository"

        @Volatile
        private var instance: TextRepository? = null

        fun get(context: Context): TextRepository =
            instance ?: synchronized(this) {
                instance ?: TextRepository(context.applicationContext).also { instance = it }
            }

        fun nowIso(): String = LocalDateTime.now().withNano(0).toString()

        fun WorkDto.toCached(): CachedWork = CachedWork(
            id = id,
            slug = slug,
            title = title,
            author = author,
            synopsis = synopsis,
            updatedAt = updatedAt ?: nowIso(),
        )

        fun ChapterListItemDto.toCached(editionId: Int): CachedChapter = CachedChapter(
            id = id,
            editionId = editionId,
            sortIndex = sortIndex,
            label = label,
            title = title,
            rawText = "",
            charCount = charCount,
            updatedAt = nowIso(),
        )

        fun DocumentNodeDto.toCached(): CachedChapter = CachedChapter(
            id = id,
            editionId = editionId,
            sortIndex = sortIndex,
            label = title,
            title = title,
            rawText = rawText ?: "",
            charCount = charCount,
            updatedAt = updatedAt ?: nowIso(),
        )
    }

    private val db = AppDatabase.get(context)
    private val settings = SettingsManager.get(context)

    private suspend fun apiOrNull(): TextApi? {
        val url = settings.serverUrl()
        if (url.isBlank()) return null
        return try {
            ApiClient.textApi(url, settings.apiToken())
        } catch (e: Exception) {
            Log.w(TAG, "api build failed: ${e.message}")
            null
        }
    }

    suspend fun serverConfigured(): Boolean = settings.serverUrl().isNotBlank()

    // ------------------------------------------------------------------
    // 作品 / 版本 / 章节
    // ------------------------------------------------------------------

    fun observeWorks(): Flow<List<CachedWork>> = db.readerDao().observeWorks()

    suspend fun syncWorks(): Int {
        val api = apiOrNull() ?: return 0
        return try {
            val list = api.works()
            db.readerDao().upsertWorks(list.map { it.toCached() })
            list.size
        } catch (e: Exception) {
            Log.w(TAG, "syncWorks failed: ${e.message}")
            0
        }
    }

    suspend fun editionsByWork(workId: Int): List<EditionDto> {
        val api = apiOrNull() ?: return emptyList()
        return try {
            api.editionsByWork(workId)
        } catch (e: Exception) {
            Log.w(TAG, "editionsByWork failed: ${e.message}")
            emptyList()
        }
    }

    suspend fun chapterList(editionId: Int): List<CachedChapter> {
        val cached = db.readerDao().chaptersByEdition(editionId)
        val api = apiOrNull() ?: return cached
        return try {
            val list = api.chapterList(editionId)
            list.forEach { db.readerDao().upsertChapter(it.toCached(editionId)) }
            db.readerDao().chaptersByEdition(editionId)
        } catch (e: Exception) {
            Log.w(TAG, "chapterList failed: ${e.message}")
            cached
        }
    }

    suspend fun chapterContent(editionId: Int, sortIndex: Int): CachedChapter? {
        val cached = db.readerDao().chapterByIndex(editionId, sortIndex)
        val api = apiOrNull() ?: return cached
        return try {
            val node = api.chapterContent(editionId, sortIndex)
            val chapter = node.toCached()
            db.readerDao().upsertChapter(chapter)
            chapter
        } catch (e: Exception) {
            Log.w(TAG, "chapterContent failed: ${e.message}")
            cached
        }
    }

    // ------------------------------------------------------------------
    // 阅读进度
    // ------------------------------------------------------------------

    suspend fun saveProgress(progress: ReadingProgress) {
        db.readerDao().upsertProgress(progress.copy(updatedAt = nowIso()))
    }

    suspend fun progressByWork(workId: Int): ReadingProgress? =
        db.readerDao().progressByWork(workId)

    suspend fun workById(workId: Int): CachedWork? = db.readerDao().workById(workId)

    // ------------------------------------------------------------------
    // 批注
    // ------------------------------------------------------------------

    suspend fun annotationsByNode(nodeId: Int): List<CachedAnnotation> =
        db.readerDao().annotationsByNode(nodeId)

    /**
     * 新建批注：本地 insert 后触发同步。返回落库后的完整记录（含 localId/remoteId）。
     */
    suspend fun createAnnotation(annotation: CachedAnnotation): CachedAnnotation {
        val localId = db.readerDao().insertAnnotation(
            annotation.copy(updatedAt = nowIso(), synced = false),
        )
        syncAnnotations()
        return db.readerDao().annotationsByNode(annotation.nodeId).find { it.localId == localId }
            ?: annotation.copy(localId = localId)
    }

    /**
     * 更新批注：本地 upsert（@Upsert 按主键更新，已存在记录不会主键冲突）后触发同步。
     */
    suspend fun updateAnnotation(annotation: CachedAnnotation): CachedAnnotation {
        db.readerDao().upsertAnnotation(annotation.copy(updatedAt = nowIso(), synced = false))
        syncAnnotations()
        return db.readerDao().annotationsByNode(annotation.nodeId)
            .find { it.localId == annotation.localId } ?: annotation
    }

    suspend fun deleteAnnotation(annotation: CachedAnnotation) {
        if (annotation.remoteId != null) {
            db.readerDao().markAnnotationDeleted(annotation.localId, nowIso())
        } else {
            db.readerDao().deleteAnnotationByLocalId(annotation.localId)
        }
        syncAnnotations()
    }

    /**
     * 同步未同步批注与待删除批注，并可选拉取指定版本的远端批注。
     */
    suspend fun syncAnnotations(pullEditionIds: List<Int> = emptyList()): Int {
        val api = apiOrNull() ?: return 0
        var synced = 0

        // 1. 上传未同步批注：remoteId == null 走新建；已存在（remoteId != null）走更新，
        //    避免服务端产生重复批注、旧 remoteId 被覆盖成孤儿数据。
        val pending = db.readerDao().pendingAnnotations()
        for (item in pending) {
            try {
                val remoteId = item.remoteId
                if (remoteId == null) {
                    val remote = api.createNote(
                        NoteItemCreateRequest(
                            category = "annotation",
                            workId = item.workId,
                            editionId = item.editionId,
                            title = item.selectedText.take(20),
                            content = item.note,
                            nodeId = item.nodeId,
                            startOffset = item.startOffset,
                            endOffset = item.endOffset,
                            selectedText = item.selectedText,
                            color = item.color,
                        )
                    )
                    db.readerDao().markAnnotationSynced(item.localId, remote.id, nowIso())
                } else {
                    api.updateNote(
                        remoteId,
                        NoteItemUpdateRequest(
                            title = item.selectedText.take(20),
                            metaData = annotationMeta(item),
                        ),
                    )
                    // 正文更新失败不阻断同步流程，下次 pending 会重试
                    try {
                        api.updateNoteContent(remoteId, NoteContentUpdateRequest(content = item.note))
                    } catch (e: Exception) {
                        Log.w(TAG, "update note content ${item.localId} failed: ${e.message}")
                    }
                    db.readerDao().markAnnotationSynced(item.localId, remoteId, nowIso())
                }
                synced++
            } catch (e: Exception) {
                Log.w(TAG, "sync annotation ${item.localId} failed: ${e.message}")
            }
        }

        // 2. 删除服务端批注
        val deletions = db.readerDao().pendingDeletions()
        for (item in deletions) {
            try {
                item.remoteId?.let { api.deleteNote(it) }
                db.readerDao().deleteAnnotationByLocalId(item.localId)
                synced++
            } catch (e: Exception) {
                Log.w(TAG, "delete annotation ${item.localId} failed: ${e.message}")
            }
        }

        // 3. 拉取远端批注（以服务端为准，补充本地没有的）
        try {
            val editionIds = (pending.map { it.editionId } + pullEditionIds).toSet()
            for (editionId in editionIds) {
                val remote = api.notes(category = "annotation", editionId = editionId)
                for (note in remote.notes) {
                    val meta = note.metaData
                    val nodeId = meta["node_id"]?.jsonPrimitive()?.content?.toIntOrNull() ?: continue
                    val startOffset = meta["start_offset"]?.jsonPrimitive()?.content?.toIntOrNull() ?: continue
                    val endOffset = meta["end_offset"]?.jsonPrimitive()?.content?.toIntOrNull() ?: continue
                    val selectedText = meta["selected_text"]?.jsonPrimitive()?.content ?: ""
                    val color = meta["color"]?.jsonPrimitive()?.content ?: "yellow"
                    val existing = db.readerDao().annotationsByNode(nodeId)
                        .find { it.remoteId == note.id }
                    if (existing == null) {
                        // S4：服务端批注正文在 md 文件里，列表接口只返回 meta，需补拉正文
                        val content = try {
                            api.noteContent(note.id).content
                        } catch (e: Exception) {
                            Log.w(TAG, "pull note content ${note.id} failed: ${e.message}")
                            ""
                        }
                        db.readerDao().insertAnnotation(
                            CachedAnnotation(
                                workId = note.workId ?: 0,
                                editionId = note.editionId ?: editionId,
                                nodeId = nodeId,
                                startOffset = startOffset,
                                endOffset = endOffset,
                                selectedText = selectedText,
                                note = content,
                                color = color,
                                createdAt = note.createdAt ?: nowIso(),
                                updatedAt = note.updatedAt ?: nowIso(),
                                synced = true,
                                remoteId = note.id,
                            )
                        )
                    }
                }
            }
        } catch (e: Exception) {
            Log.w(TAG, "pull annotations failed: ${e.message}")
        }

        return synced
    }
}
