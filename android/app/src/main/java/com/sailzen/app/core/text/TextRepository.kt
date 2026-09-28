package com.sailzen.app.core.text

import android.content.Context
import android.util.Log
import com.sailzen.app.core.data.SettingsManager
import com.sailzen.app.core.data.db.AppDatabase
import com.sailzen.app.core.data.db.CachedAnnotation
import com.sailzen.app.core.data.db.CachedChapter
import com.sailzen.app.core.data.db.CachedEdition
import com.sailzen.app.core.data.db.CachedWork
import com.sailzen.app.core.data.db.ReadingProgress
import com.sailzen.app.core.network.ApiClient
import com.sailzen.app.core.network.ConnectivityObserver
import com.sailzen.app.core.network.TextApi
import com.sailzen.app.core.network.dto.ChapterListItemDto
import com.sailzen.app.core.network.dto.DocumentNodeDto
import com.sailzen.app.core.network.dto.EditionDto
import com.sailzen.app.core.network.dto.NoteContentUpdateRequest
import com.sailzen.app.core.network.dto.NoteItemCreateRequest
import com.sailzen.app.core.network.dto.NoteItemUpdateRequest
import com.sailzen.app.core.network.dto.WorkDto
import java.time.LocalDateTime
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.launch
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
 * 阅读模块 Repository —— **离线优先（offline-first）**：
 *
 * - Room 是事实源，所有读取先走本地缓存，首帧即可渲染；
 * - 网络只做后台刷新：refresh* 系列方法不阻塞 UI，成功后 upsert 进 Room；
 * - [ConnectivityObserver] 离线时跳过网络调用（避免弱网干等 10~20s 超时），
 *   并把同步状态归约到 [ReaderSyncState]，供界面展示同步状态 chip；
 * - 目录 stub 刷新**永不覆盖**已缓存的正文（修 stub 清空全文的老 bug）；
 * - 章节预取与全本缓存让断网/弱网下向前阅读始终有内容。
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

        fun EditionDto.toCached(): CachedEdition = CachedEdition(
            id = id,
            workId = workId,
            editionName = editionName,
            language = language,
            canonical = canonical,
            status = status,
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

    private val appScope = CoroutineScope(SupervisorJob() + Dispatchers.IO)
    private val db = AppDatabase.get(context)
    private val settings = SettingsManager.get(context)
    private val connectivity = ConnectivityObserver(context)

    // ------------------------------------------------------------------
    // 同步状态（离线 / 同步中 / 已同步 / 失败）
    // ------------------------------------------------------------------

    private val syncReducer = ReaderSyncStateReducer()
    private val _syncState = MutableStateFlow(ReaderSyncState())
    val syncState: StateFlow<ReaderSyncState> = _syncState.asStateFlow()

    /** 全本缓存进度（null = 未在缓存） */
    data class CacheProgress(val cachedCount: Int, val totalCount: Int, val currentTitle: String)

    private val _cacheProgress = MutableStateFlow<CacheProgress?>(null)
    val cacheProgress: StateFlow<CacheProgress?> = _cacheProgress.asStateFlow()

    init {
        appScope.launch {
            connectivity.isOnline.collect { online ->
                _syncState.value = syncReducer.onOnlineChanged(online)
            }
        }
    }

    /** 离线时跳过网络调用，避免弱网空等超时 */
    private suspend fun onlineNow(): Boolean =
        connectivity.isOnline.first()

    private inline fun <T> trackSync(block: () -> T): T {
        _syncState.value = syncReducer.onSyncStart()
        return try {
            block().also { _syncState.value = syncReducer.onSyncSuccess() }
        } catch (e: Exception) {
            _syncState.value = syncReducer.onSyncFailure(e.message)
            throw e
        }
    }

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
    // 作品 / 版本 / 章节 —— 本地快照（首帧渲染用）
    // ------------------------------------------------------------------

    fun observeWorks(): Flow<List<CachedWork>> = db.readerDao().observeWorks()

    suspend fun worksSnapshot(): List<CachedWork> = db.readerDao().worksSnapshot()

    suspend fun workById(workId: Int): CachedWork? = db.readerDao().workById(workId)

    suspend fun editionsSnapshot(workId: Int): List<CachedEdition> =
        db.readerDao().editionsByWork(workId)

    suspend fun chaptersSnapshot(editionId: Int): List<CachedChapter> =
        db.readerDao().chaptersByEdition(editionId)

    /** 正文本地直读：离线/首帧渲染的唯一内容来源 */
    suspend fun chapterContentLocal(editionId: Int, sortIndex: Int): CachedChapter? =
        db.readerDao().chapterByIndex(editionId, sortIndex)

    suspend fun cachedChapterCount(editionId: Int): Int =
        db.readerDao().cachedChapterCount(editionId)

    suspend fun cachedChapterIds(editionId: Int): List<Int> =
        db.readerDao().cachedChapterIds(editionId)

    // ------------------------------------------------------------------
    // 网络刷新（后台调用；返回 true 表示成功落库）
    // ------------------------------------------------------------------

    suspend fun refreshWorks(): Boolean {
        if (!onlineNow()) return false
        val api = apiOrNull() ?: return false
        return try {
            trackSync {
                val list = api.works()
                db.readerDao().upsertWorks(list.map { it.toCached() })
            }
            true
        } catch (e: Exception) {
            Log.w(TAG, "refreshWorks failed: ${e.message}")
            false
        }
    }

    suspend fun refreshEditions(workId: Int): Boolean {
        if (!onlineNow()) return false
        val api = apiOrNull() ?: return false
        return try {
            val list = api.editionsByWork(workId)
            db.readerDao().upsertEditions(list.map { it.toCached() })
            true
        } catch (e: Exception) {
            Log.w(TAG, "refreshEditions failed: ${e.message}")
            false
        }
    }

    /**
     * 刷新章节目录：stub 合并且**保留已缓存正文**，
     * 远端新增的章节插入 stub（正文为空，待按需缓存）。
     */
    suspend fun refreshChapterList(editionId: Int): Boolean {
        if (!onlineNow()) return false
        val api = apiOrNull() ?: return false
        return try {
            val remote = api.chapterList(editionId)
            val localById = db.readerDao().chaptersByEdition(editionId).associateBy { it.id }
            for (item in remote) {
                val local = localById[item.id]
                if (local != null && local.contentCached) {
                    // 已缓存全文的章节只更新元信息，不动 rawText
                    db.readerDao().updateChapterMeta(
                        item.id, item.label, item.title, item.charCount, nowIso(),
                    )
                } else {
                    db.readerDao().upsertChapter(item.toCached(editionId))
                }
            }
            true
        } catch (e: Exception) {
            Log.w(TAG, "refreshChapterList failed: ${e.message}")
            false
        }
    }

    /**
     * 刷新单章正文：成功返回最新章节并落库；失败（离线/弱网）返回 null，
     * 调用方继续使用本地缓存，不产生可见卡顿。
     */
    suspend fun refreshChapterContent(editionId: Int, sortIndex: Int): CachedChapter? {
        if (!onlineNow()) return null
        val api = apiOrNull() ?: return null
        return try {
            val node = api.chapterContent(editionId, sortIndex)
            val chapter = node.toCached()
            db.readerDao().upsertChapter(chapter)
            chapter
        } catch (e: Exception) {
            Log.w(TAG, "refreshChapterContent($editionId,$sortIndex) failed: ${e.message}")
            null
        }
    }

    /**
     * 向后预取 count 章正文（跳过已缓存章节），供离线向前阅读。
     * 任一章节拉取失败即停止，避免弱网空转。
     */
    suspend fun prefetchAhead(editionId: Int, fromSortIndex: Int, count: Int = 2) {
        if (!onlineNow()) return
        val chapters = db.readerDao().chaptersByEdition(editionId)
        val targets = chapters
            .filter { it.sortIndex in (fromSortIndex + 1)..(fromSortIndex + count) && !it.contentCached }
            .sortedBy { it.sortIndex }
        for (ch in targets) {
            val fresh = refreshChapterContent(editionId, ch.sortIndex) ?: return
            if (fresh.rawText.isEmpty()) return
        }
    }

    /**
     * 全本缓存：顺序拉取该版本全部未缓存章节，进度发布到 [cacheProgress]。
     * 返回 true 表示全部缓存完成；失败返回 false（已缓存部分保留）。
     */
    suspend fun cacheEdition(editionId: Int): Boolean {
        val chapters = db.readerDao().chaptersByEdition(editionId)
        val targets = chapters.filter { !it.contentCached }.sortedBy { it.sortIndex }
        if (targets.isEmpty()) {
            _cacheProgress.value = CacheProgress(chapters.size, chapters.size, "")
            return true
        }
        _syncState.value = syncReducer.onSyncStart()
        var done = 0
        for (ch in targets) {
            _cacheProgress.value = CacheProgress(
                cachedCount = chapters.size - targets.size + done,
                totalCount = chapters.size,
                currentTitle = ch.title.ifBlank { ch.label },
            )
            val fresh = refreshChapterContent(editionId, ch.sortIndex)
            if (fresh == null || fresh.rawText.isEmpty()) {
                _cacheProgress.value = null
                _syncState.value = syncReducer.onSyncFailure("cache edition interrupted")
                return false
            }
            done++
        }
        _cacheProgress.value = CacheProgress(chapters.size, chapters.size, "")
        _syncState.value = syncReducer.onSyncSuccess()
        return true
    }

    fun clearCacheProgress() {
        _cacheProgress.value = null
    }

    /** 清除某版本正文缓存（保留目录），便于重新拉取最新内容 */
    suspend fun clearEditionContent(editionId: Int) {
        db.readerDao().clearEditionContent(editionId)
    }

    // ------------------------------------------------------------------
    // 阅读进度
    // ------------------------------------------------------------------

    suspend fun saveProgress(progress: ReadingProgress) {
        db.readerDao().upsertProgress(progress.copy(updatedAt = nowIso()))
    }

    suspend fun progressByWork(workId: Int): ReadingProgress? =
        db.readerDao().progressByWork(workId)

    // ------------------------------------------------------------------
    // 批注（本地即写 + 后台同步）
    // ------------------------------------------------------------------

    suspend fun annotationsByNode(nodeId: Int): List<CachedAnnotation> =
        db.readerDao().annotationsByNode(nodeId)

    suspend fun pendingAnnotationCount(): Int =
        db.readerDao().pendingAnnotations().size + db.readerDao().pendingDeletions().size

    /**
     * 新建批注：本地 insert 后立即返回（离线可用），同步在后台进行。
     * 返回落库后的完整记录（含 localId/remoteId）。
     */
    suspend fun createAnnotation(annotation: CachedAnnotation): CachedAnnotation {
        val localId = db.readerDao().insertAnnotation(
            annotation.copy(updatedAt = nowIso(), synced = false),
        )
        appScope.launch { runCatching { syncAnnotations() } }
        return db.readerDao().annotationsByNode(annotation.nodeId).find { it.localId == localId }
            ?: annotation.copy(localId = localId)
    }

    /**
     * 更新批注：本地 upsert（@Upsert 按主键更新）后立即返回，后台同步。
     */
    suspend fun updateAnnotation(annotation: CachedAnnotation): CachedAnnotation {
        db.readerDao().upsertAnnotation(annotation.copy(updatedAt = nowIso(), synced = false))
        appScope.launch { runCatching { syncAnnotations() } }
        return db.readerDao().annotationsByNode(annotation.nodeId)
            .find { it.localId == annotation.localId } ?: annotation
    }

    suspend fun deleteAnnotation(annotation: CachedAnnotation) {
        if (annotation.remoteId != null) {
            db.readerDao().markAnnotationDeleted(annotation.localId, nowIso())
        } else {
            db.readerDao().deleteAnnotationByLocalId(annotation.localId)
        }
        appScope.launch { runCatching { syncAnnotations() } }
    }

    /**
     * 同步未同步批注与待删除批注，并可选拉取指定版本的远端批注。
     * 离线时直接跳过（不更新错误状态，离线状态本身已可见）。
     */
    suspend fun syncAnnotations(pullEditionIds: List<Int> = emptyList()): Int {
        if (!onlineNow()) return 0
        val api = apiOrNull() ?: return 0
        var synced = 0

        _syncState.value = syncReducer.onSyncStart()
        try {
            // 1. 上传未同步批注：remoteId == null 走新建；已存在走更新
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
            val editionIds = (pending.map { it.editionId } + pullEditionIds).toSet()
            for (editionId in editionIds) {
                try {
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
                } catch (e: Exception) {
                    Log.w(TAG, "pull annotations for edition $editionId failed: ${e.message}")
                }
            }
            _syncState.value = syncReducer.onSyncSuccess()
        } catch (e: Exception) {
            // 只在整体不可用时记录失败；单项失败已在上面的 catch 中跳过
            _syncState.value = syncReducer.onSyncFailure(e.message)
            Log.w(TAG, "syncAnnotations failed: ${e.message}")
        }
        return synced
    }
}
