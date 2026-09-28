package com.sailzen.app.feature.reader

import android.app.Application
import android.util.Log
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import com.sailzen.app.core.data.db.CachedAnnotation
import com.sailzen.app.core.data.db.CachedChapter
import com.sailzen.app.core.data.db.CachedEdition
import com.sailzen.app.core.data.db.ReadingProgress
import com.sailzen.app.core.text.TextRepository
import java.time.LocalDateTime
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.withContext
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch

/**
 * 阅读页 ViewModel —— **离线优先 + 零等待首屏**：
 *
 * - loadWork/loadChapter 两阶段：先用 Room 本地快照立即渲染（分页缓存命中即零耗时），
 *   再后台刷新网络内容，有差异时以当前字符偏移为锚点重排（不打断阅读）；
 * - 排版结果进 [PageLayoutCache]（LRU），字号微调/旋转/重进不重排；
 * - 滚动进度等高频上报只写内部字段 + 防抖落库，**不进 UiState**（修滚动全屏重组）；
 * - 阅读过程中后台预取后 2 章并预排版下一章，离线向前阅读无空白。
 */
class ReaderViewModel(application: Application) : AndroidViewModel(application) {

    companion object {
        private const val TAG = "ReaderViewModel"
        private const val PREFETCH_AHEAD_COUNT = 2
    }

    data class ReaderSettings(
        val fontSize: Int = 18,
        val lineHeight: Float = 1.5f,
        val theme: ReaderTheme = ReaderTheme.LIGHT,
        val mode: ReaderMode = ReaderMode.PAGE,
    )

    enum class ReaderTheme { LIGHT, DARK }
    enum class ReaderMode { PAGE, SCROLL }

    data class UiState(
        val workId: Int = 0,
        val workTitle: String = "",
        val edition: CachedEdition? = null,
        val chapters: List<CachedChapter> = emptyList(),
        val currentChapter: CachedChapter? = null,
        val currentSortIndex: Int = 0,
        val pages: List<ReaderTextEngine.Page> = emptyList(),
        val currentPage: Int = 0,
        /** 已缓存正文的章节 id 集合（目录缓存标记；目录列表本身不持有正文） */
        val cachedChapterIds: Set<Int> = emptySet(),
        /** 章节切换时的一次性阅读位置（滚动/翻页恢复共用），滚动过程不更新 */
        val charOffset: Int = 0,
        val annotations: List<CachedAnnotation> = emptyList(),
        val settings: ReaderSettings = ReaderSettings(),
        val loading: Boolean = false,
        /** 当前章无本地缓存正文（离线未预取时可能出现） */
        val contentMissing: Boolean = false,
        val error: String? = null,
        /**
         * 滚动模式排版派生量：spec + 测量行高。
         * 低频变化（仅字号/行距/布局变化时更新），滚动过程不变。
         */
        val scrollLayout: ScrollLayout? = null,
        /** 滚动模式行序列（VM 预排版，引用稳定；item 高度恒定） */
        val scrollLines: List<ReaderTextEngine.Line> = emptyList(),
    )

    /** 滚动模式布局派生量 */
    data class ScrollLayout(
        val spec: ReaderTextEngine.LayoutSpec,
        /** 单行像素高（含行距倍数，StaticLayout 两行探针实测） */
        val lineAdvancePx: Float,
    )

    private val repository = TextRepository.get(application)

    private val _uiState = MutableStateFlow(UiState())
    val uiState: StateFlow<UiState> = _uiState.asStateFlow()

    /** 同步状态（离线/同步中/已同步）与批注待同步数：独立 flow，不影响阅读内容重组 */
    val syncState = repository.syncState
    val cacheProgress = repository.cacheProgress
    private val _pendingAnnotationCount = MutableStateFlow(0)
    val pendingAnnotationCount: StateFlow<Int> = _pendingAnnotationCount.asStateFlow()

    private var saveProgressJob: Job? = null

    /** 当前阅读位置的全局字符偏移（跨模式复用 scrollOffset 列持久化；不进 UiState） */
    private var currentCharOffset: Int = 0
    private var specJob: Job? = null
    private var pageSpec: ReaderTextEngine.LayoutSpec? = null
    private val textMeasurer = ReaderTextEngine.StaticLayoutMeasurer()
    private val pageCache = PageLayoutCache()
    private val lineCache = LineLayoutCache()

    // ------------------------------------------------------------------
    // 载入
    // ------------------------------------------------------------------

    fun loadWork(workId: Int, workTitle: String, editionId: Int? = null) {
        viewModelScope.launch {
            _uiState.update { it.copy(workId = workId, workTitle = workTitle, loading = true) }

            // ---- 阶段 1：本地快照立即渲染（离线/弱网首帧不空白） ----
            val work = repository.workById(workId)
            val displayTitle = work?.title ?: workTitle
            val progress = repository.progressByWork(workId)
            val editions = repository.editionsSnapshot(workId)
            val edition = editions.find { it.id == editionId }
                ?: editions.firstOrNull()
                ?: progress?.editionId?.takeIf { it > 0 }?.let { cachedId ->
                    // 离线且无版本缓存：用进度中的 editionId 兜底，章节结构仍可能可读
                    CachedEdition(cachedId, workId, null, "zh", true, "unknown", nowIso())
                }

            // 目录列表只保留元信息（正文字段置空，避免 UiState 持有全文）
            val chapters = edition?.let { ed ->
                repository.chaptersSnapshot(ed.id).map { it.copy(rawText = "") }
            } ?: emptyList()

            val sortIndex = progress?.sortIndex?.takeIf { it < chapters.size } ?: 0
            val chapterMeta = chapters.getOrNull(sortIndex) ?: chapters.firstOrNull()
            val localChapter = edition?.let { ed ->
                chapterMeta?.let { repository.chapterContentLocal(ed.id, it.sortIndex) }
            }
            val cachedIds = edition?.let { repository.cachedChapterIds(it.id) }?.toSet() ?: emptySet()

            val settings = progress?.let {
                ReaderSettings(
                    fontSize = it.fontSize,
                    lineHeight = it.lineHeight,
                    theme = if (it.theme == "dark") ReaderTheme.DARK else ReaderTheme.LIGHT,
                    mode = if (it.mode == "scroll") ReaderMode.SCROLL else ReaderMode.PAGE,
                )
            } ?: ReaderSettings()

            val pageIdx = progress?.pageIndex?.coerceAtLeast(0) ?: 0
            val restoreOffset = progress?.scrollOffset?.takeIf { it > 0 }

            _uiState.update {
                it.copy(
                    workTitle = displayTitle,
                    edition = edition,
                    chapters = chapters,
                    currentChapter = localChapter,
                    currentSortIndex = localChapter?.sortIndex ?: chapterMeta?.sortIndex ?: 0,
                    cachedChapterIds = cachedIds,
                    settings = settings,
                    currentPage = pageIdx,
                    loading = false,
                )
            }
            refreshPendingCount()

            localChapter?.let { presentChapter(it, pageIdx, restoreOffset) }
            if ((localChapter == null || localChapter.rawText.isEmpty()) &&
                !repository.syncState.value.online
            ) {
                // 离线且无本地缓存：立即给出提示；在线则等后台刷新链路判定，避免首启提示闪烁
                _uiState.update { it.copy(contentMissing = true) }
            }

            // ---- 阶段 2：后台刷新（作品→版本→目录→正文→批注→预取） ----
            launch { refreshWorkData(workId) }
        }
    }

    /** 后台刷新链：任何一步失败都不影响已渲染内容 */
    private suspend fun refreshWorkData(workId: Int) {
        var edition = _uiState.value.edition
        if (edition == null) {
            // 首次在线打开（本地无任何缓存）：版本 → 目录 → 首章正文 从无到有
            if (!repository.refreshEditions(workId)) return
            edition = repository.editionsSnapshot(workId).firstOrNull() ?: return
            _uiState.update { it.copy(edition = edition) }
            repository.refreshChapterList(edition.id)
            val chapters = repository.chaptersSnapshot(edition.id).map { it.copy(rawText = "") }
            _uiState.update { it.copy(chapters = chapters) }
            val first = chapters.getOrNull(_uiState.value.currentSortIndex) ?: chapters.firstOrNull()
            if (first != null) {
                val fresh = repository.refreshChapterContent(edition.id, first.sortIndex)
                if (fresh != null && fresh.rawText.isNotEmpty()) {
                    presentChapter(fresh, _uiState.value.currentPage, null)
                } else {
                    _uiState.update { it.copy(contentMissing = true) }
                }
            }
            repository.prefetchAhead(edition.id, 0, PREFETCH_AHEAD_COUNT)
            return
        }
        val editionId = edition.id

        if (repository.refreshChapterList(editionId)) {
            val freshChapters = repository.chaptersSnapshot(editionId).map { it.copy(rawText = "") }
            _uiState.update {
                it.copy(
                    chapters = freshChapters,
                    cachedChapterIds = repository.cachedChapterIds(editionId).toSet(),
                )
            }
        }

        // 当前章正文后台刷新：内容变化时以当前偏移为锚点重排。
        // 守卫：返回时若用户已切走（currentChapter 已变），不得覆盖新章节。
        val current = _uiState.value.currentChapter
        if (current != null && current.rawText.isNotEmpty()) {
            val fresh = repository.refreshChapterContent(editionId, current.sortIndex)
            val cur = _uiState.value.currentChapter
            if (cur?.id == current.id &&
                fresh != null && fresh.rawText.isNotEmpty() && fresh.rawText != cur.rawText
            ) {
                presentChapter(fresh, charOffset = currentCharOffset)
            }
        } else if (current != null) {
            // 本地无缓存（stub）：尝试在线拉取
            val fresh = repository.refreshChapterContent(editionId, current.sortIndex)
            if (fresh != null && fresh.rawText.isNotEmpty()) {
                presentChapter(fresh, 0, null)
            } else {
                _uiState.update { it.copy(contentMissing = true) }
            }
        }

        repository.syncAnnotations(pullEditionIds = listOf(editionId))
        refreshAnnotations()
        repository.prefetchAhead(editionId, _uiState.value.currentSortIndex, PREFETCH_AHEAD_COUNT)
        _uiState.update {
            it.copy(cachedChapterIds = repository.cachedChapterIds(editionId).toSet())
        }
        prepaginateNeighbor(+1)
    }

    fun loadChapter(chapter: CachedChapter, pageIndex: Int = 0, charOffset: Int? = null) {
        viewModelScope.launch {
            // 阶段 1：本地内容立即渲染（分页缓存命中则零耗时）
            val local = repository.chapterContentLocal(chapter.editionId, chapter.sortIndex)
            if (local != null && local.rawText.isNotEmpty()) {
                presentChapter(local, pageIndex, charOffset)
            } else {
                _uiState.update {
                    it.copy(
                        currentChapter = local ?: chapter,
                        currentSortIndex = chapter.sortIndex,
                        pages = emptyList(),
                        contentMissing = true,
                    )
                }
            }

            // 阶段 2：后台刷新正文 + 批注 + 预取。
            // 守卫：返回时若用户已切走（currentChapter 已变），不得覆盖新章节。
            launch {
                val fresh = repository.refreshChapterContent(chapter.editionId, chapter.sortIndex)
                val cur = _uiState.value.currentChapter
                if (cur?.id == chapter.id &&
                    fresh != null && fresh.rawText.isNotEmpty() && fresh.rawText != cur.rawText
                ) {
                    presentChapter(fresh, charOffset = currentCharOffset)
                } else if (fresh == null && _uiState.value.currentChapter?.id == chapter.id) {
                    val now = _uiState.value.currentChapter
                    if (now == null || now.rawText.isEmpty()) {
                        _uiState.update { it.copy(contentMissing = true) }
                    }
                }
                repository.syncAnnotations(pullEditionIds = listOf(chapter.editionId))
                refreshAnnotations()
                repository.prefetchAhead(chapter.editionId, chapter.sortIndex, PREFETCH_AHEAD_COUNT)
                _uiState.update {
                    it.copy(cachedChapterIds = repository.cachedChapterIds(chapter.editionId).toSet())
                }
                prepaginateNeighbor(+1)
            }
        }
    }

    /** 渲染章节：分页+行序（走 LRU 缓存）→ 定位 → 更新状态 → 防抖存进度 */
    private suspend fun presentChapter(
        chapter: CachedChapter,
        pageIndex: Int = 0,
        charOffset: Int? = null,
    ) {
        val pages = paginateCached(chapter)
        val spec = pageSpec
        val lines = if (spec != null) linesCached(chapter, spec) else emptyList()
        val layout = spec?.let { ScrollLayout(it, textMeasurer.lineAdvance(it)) }
        val target = when {
            charOffset != null -> ReaderTextEngine.findPageForOffset(pages, charOffset)
            pageIndex in pages.indices -> pageIndex
            else -> 0
        }
        // spec 未就绪的单页兜底：保留请求偏移，待 setPageSpec 重排后按偏移精确定位
        currentCharOffset = charOffset ?: pages.getOrNull(target)?.startOffset ?: 0
        _uiState.update {
            it.copy(
                currentChapter = chapter,
                currentSortIndex = chapter.sortIndex,
                pages = pages,
                currentPage = target,
                charOffset = currentCharOffset,
                contentMissing = chapter.rawText.isEmpty(),
                scrollLayout = layout,
                scrollLines = lines,
            )
        }
        saveProgressDebounced()
    }

    /** 行序排版：缓存命中直接返回；未命中在 Default 线程排版后入缓存 */
    private suspend fun linesCached(
        chapter: CachedChapter,
        spec: ReaderTextEngine.LayoutSpec,
    ): List<ReaderTextEngine.Line> {
        val text = chapter.rawText
        if (text.isEmpty()) return emptyList()
        val key = PageLayoutCache.Key.of(chapter.id, spec)
        lineCache.get(key)?.let { return it }
        val lines = withContext(Dispatchers.Default) {
            ReaderTextEngine.layoutLines(text, ParagraphSplitter.split(text), spec, textMeasurer)
        }
        lineCache.put(key, lines)
        return lines
    }

    /** 分页：缓存命中直接返回；未命中在 Default 线程排版后入缓存 */
    private suspend fun paginateCached(chapter: CachedChapter): List<ReaderTextEngine.Page> {
        val text = chapter.rawText
        val spec = pageSpec
        if (text.isEmpty()) return emptyList()
        if (spec == null) {
            // 布局尚未测量完成（首帧竞态）：整章单页兜底，
            // setPageSpec 到达后经 rebuildPages 重新分页
            return listOf(ReaderTextEngine.Page(text, 0, text.length))
        }
        val key = PageLayoutCache.Key.of(chapter.id, spec)
        pageCache.get(key)?.let { return it }
        val pages = withContext(Dispatchers.Default) {
            ReaderTextEngine.paginate(text, ParagraphSplitter.split(text), spec, textMeasurer)
        }
        pageCache.put(key, pages)
        return pages
    }

    /** 后台预排版下一章（当前布局参数），切章时分页零耗时 */
    private fun prepaginateNeighbor(offset: Int) {
        val spec = pageSpec ?: return
        val state = _uiState.value
        val editionId = state.edition?.id ?: return
        val neighbor = state.chapters.getOrNull(state.currentSortIndex + offset) ?: return
        viewModelScope.launch(Dispatchers.Default) {
            val local = repository.chapterContentLocal(editionId, neighbor.sortIndex)
            if (local == null || local.rawText.isEmpty()) return@launch
            val key = PageLayoutCache.Key.of(local.id, spec)
            if (pageCache.get(key) != null) return@launch
            val pages = ReaderTextEngine.paginate(
                local.rawText,
                ParagraphSplitter.split(local.rawText),
                spec,
                textMeasurer,
            )
            pageCache.put(key, pages)
        }
    }

    private suspend fun refreshAnnotations() {
        val nodeId = _uiState.value.currentChapter?.id ?: return
        val fresh = repository.annotationsByNode(nodeId)
        _uiState.update { if (it.annotations == fresh) it else it.copy(annotations = fresh) }
        refreshPendingCount()
    }

    private fun refreshPendingCount() {
        viewModelScope.launch {
            _pendingAnnotationCount.value = repository.pendingAnnotationCount()
        }
    }

    // ------------------------------------------------------------------
    // 翻页 / 滚动
    // ------------------------------------------------------------------

    fun previousChapter() {
        val state = _uiState.value
        val prev = state.chapters.getOrNull(state.currentSortIndex - 1) ?: return
        loadChapter(prev, 0)
    }

    fun nextChapter() {
        val state = _uiState.value
        val next = state.chapters.getOrNull(state.currentSortIndex + 1) ?: return
        loadChapter(next, 0)
    }

    fun goToPage(pageIndex: Int) {
        val pages = _uiState.value.pages
        if (pageIndex in pages.indices) {
            currentCharOffset = pages[pageIndex].startOffset
            _uiState.update { it.copy(currentPage = pageIndex, charOffset = currentCharOffset) }
            saveProgressDebounced()
        }
    }

    /**
     * 滚动模式进度上报：只更新内部偏移并防抖落库，**不触发 UiState 发射**，
     * 消除滚动过程中的全屏重组（修滚动卡顿主因）。
     */
    fun onScrollCharOffset(charOffset: Int) {
        if (currentCharOffset != charOffset) {
            currentCharOffset = charOffset
            saveProgressDebounced()
        }
    }

    /** pager 滑动落定后的回写入口（snapshotFlow{settledPage} 驱动，低频） */
    fun onPageSettled(pageIndex: Int) {
        if (_uiState.value.currentPage != pageIndex) {
            goToPage(pageIndex)
        }
    }

    /**
     * 布局参数变化（字号/行距/可用宽高）：
     * 已有分页结果时 300ms 防抖（字号微调不连续重排）；
     * 尚无结果（首帧）时立即排版，消灭开书空白窗口。
     */
    fun setPageSpec(spec: ReaderTextEngine.LayoutSpec) {
        if (spec == pageSpec) return
        val hasLayout = pageSpec != null
        pageSpec = spec
        specJob?.cancel()
        specJob = viewModelScope.launch {
            if (hasLayout) delay(300)
            rebuildDerived()
        }
    }

    /**
     * 以当前阅读字符偏移为锚点重排（字号/行距/布局变化），定位粒度优于整页回退。
     * 同时刷新翻页分页与滚动行序两份派生数据，二者引用稳定，未变化时跳过发射。
     */
    private suspend fun rebuildDerived() {
        val state = _uiState.value
        val chapter = state.currentChapter ?: return
        if (chapter.rawText.isEmpty()) return
        val spec = pageSpec ?: return
        val pages = paginateCached(chapter)
        val lines = linesCached(chapter, spec)
        val layout = ScrollLayout(spec, textMeasurer.lineAdvance(spec))
        if (pages === state.pages && lines === state.scrollLines &&
            layout == state.scrollLayout
        ) {
            return
        }
        val anchor = state.charOffset
        val newPage = ReaderTextEngine.findPageForOffset(pages, anchor)
        currentCharOffset = pages.getOrNull(newPage)?.startOffset ?: anchor
        _uiState.update {
            it.copy(
                pages = pages,
                currentPage = newPage,
                charOffset = currentCharOffset,
                scrollLayout = layout,
                scrollLines = lines,
            )
        }
    }

    /** 手动重试同步（同步状态 chip 点按）：批注 + 当前章正文一并刷新 */
    fun refreshSync() {
        val editionId = _uiState.value.edition?.id ?: return
        viewModelScope.launch {
            val chapter = _uiState.value.currentChapter
            if (chapter != null) {
                val fresh = repository.refreshChapterContent(editionId, chapter.sortIndex)
                val cur = _uiState.value.currentChapter
                if (cur?.id == chapter.id &&
                    fresh != null && fresh.rawText.isNotEmpty() && fresh.rawText != cur.rawText
                ) {
                    presentChapter(fresh, charOffset = currentCharOffset)
                }
            }
            repository.syncAnnotations(pullEditionIds = listOf(editionId))
            refreshAnnotations()
        }
    }

    // ------------------------------------------------------------------
    // 批注
    // ------------------------------------------------------------------

    fun onSelection(
        pageIndex: Int,
        pageSelectionStart: Int,
        pageSelectionEnd: Int,
        selectedText: String,
    ): CachedAnnotation? {
        val page = _uiState.value.pages.getOrNull(pageIndex) ?: return null
        val annotation = buildAnnotation(
            page.startOffset + pageSelectionStart,
            page.startOffset + pageSelectionEnd,
            selectedText,
        ) ?: return null
        _uiState.update { it.copy(annotations = it.annotations + annotation) }
        return annotation
    }

    /** 滚动模式（整章单页）选中：偏移即章节绝对偏移，无需页映射 */
    fun onScrollSelection(start: Int, end: Int, selectedText: String): CachedAnnotation? {
        val annotation = buildAnnotation(start, end, selectedText) ?: return null
        _uiState.update { it.copy(annotations = it.annotations + annotation) }
        return annotation
    }

    private fun buildAnnotation(start: Int, end: Int, selectedText: String): CachedAnnotation? {
        if (start >= end) return null
        val chapter = _uiState.value.currentChapter ?: return null
        return CachedAnnotation(
            workId = _uiState.value.workId,
            editionId = chapter.editionId,
            nodeId = chapter.id,
            startOffset = start,
            endOffset = end,
            selectedText = selectedText,
            note = "",
            color = "yellow",
            createdAt = nowIso(),
            updatedAt = nowIso(),
        )
    }

    /** 新建批注（localId == 0 的草稿）。任何异常仅回滚 UI，不再向外抛出。 */
    fun createAnnotation(annotation: CachedAnnotation) {
        if (annotation.localId != 0L) {
            updateAnnotation(annotation)
            return
        }
        viewModelScope.launch {
            try {
                val saved = repository.createAnnotation(annotation)
                _uiState.update { state ->
                    state.copy(
                        annotations = state.annotations.map {
                            if (it.localId == 0L && sameAnchor(it, annotation)) saved else it
                        },
                    )
                }
                refreshPendingCount()
            } catch (e: Exception) {
                Log.w(TAG, "createAnnotation failed: ${e.message}")
                _uiState.update { state ->
                    state.copy(annotations = state.annotations.filterNot {
                        it.localId == 0L && sameAnchor(it, annotation)
                    })
                }
            }
        }
    }

    /** 更新已落库批注（localId != 0）。写库/同步异常仅记录日志，不再闪退。 */
    fun updateAnnotation(annotation: CachedAnnotation) {
        if (annotation.localId == 0L) {
            createAnnotation(annotation)
            return
        }
        viewModelScope.launch {
            try {
                val saved = repository.updateAnnotation(annotation.copy(updatedAt = nowIso()))
                _uiState.update { state ->
                    state.copy(
                        annotations = state.annotations.map {
                            if (it.localId == annotation.localId) saved else it
                        },
                    )
                }
                refreshPendingCount()
            } catch (e: Exception) {
                Log.w(TAG, "updateAnnotation failed: ${e.message}")
            }
        }
    }

    fun deleteAnnotation(annotation: CachedAnnotation) {
        viewModelScope.launch {
            try {
                repository.deleteAnnotation(annotation)
                _uiState.update { state ->
                    state.copy(annotations = state.annotations.filter { it.localId != annotation.localId })
                }
                refreshPendingCount()
            } catch (e: Exception) {
                Log.w(TAG, "deleteAnnotation failed: ${e.message}")
            }
        }
    }

    /** 放弃未保存的批注草稿（localId == 0）：仅回滚 UI 中的临时高亮，不动数据库。 */
    fun discardDraft(annotation: CachedAnnotation) {
        if (annotation.localId != 0L) return
        _uiState.update { state ->
            state.copy(annotations = state.annotations.filterNot {
                it.localId == 0L && sameAnchor(it, annotation)
            })
        }
    }

    /** 设置更新：仅更新状态并持久化。重排版由 setPageSpec 防抖驱动。 */
    fun updateSettings(settings: ReaderSettings) {
        _uiState.update { it.copy(settings = settings) }
        saveProgressDebounced()
    }

    // ------------------------------------------------------------------
    // 进度持久化
    // ------------------------------------------------------------------

    private fun saveProgressDebounced() {
        saveProgressJob?.cancel()
        saveProgressJob = viewModelScope.launch {
            delay(500)
            saveProgressNow()
        }
    }

    private suspend fun saveProgressNow() {
        val state = _uiState.value
        val chapter = state.currentChapter ?: return
        repository.saveProgress(
            ReadingProgress(
                workId = state.workId,
                editionId = state.edition?.id ?: chapter.editionId,
                nodeId = chapter.id,
                sortIndex = chapter.sortIndex,
                mode = if (state.settings.mode == ReaderMode.SCROLL) "scroll" else "page",
                pageIndex = state.currentPage,
                scrollOffset = currentCharOffset,
                fontSize = state.settings.fontSize,
                lineHeight = state.settings.lineHeight,
                theme = if (state.settings.theme == ReaderTheme.DARK) "dark" else "light",
                updatedAt = nowIso(),
            )
        )
    }

    override fun onCleared() {
        viewModelScope.launch { saveProgressNow() }
        super.onCleared()
    }

    private fun nowIso(): String = LocalDateTime.now().withNano(0).toString()

    private fun sameAnchor(a: CachedAnnotation, b: CachedAnnotation): Boolean =
        a.nodeId == b.nodeId && a.startOffset == b.startOffset && a.endOffset == b.endOffset
}
