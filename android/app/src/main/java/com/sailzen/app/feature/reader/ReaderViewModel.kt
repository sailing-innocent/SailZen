package com.sailzen.app.feature.reader

import android.app.Application
import android.util.Log
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import com.sailzen.app.core.data.db.CachedAnnotation
import com.sailzen.app.core.data.db.CachedChapter
import com.sailzen.app.core.data.db.ReadingProgress
import com.sailzen.app.core.network.dto.EditionDto
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

class ReaderViewModel(application: Application) : AndroidViewModel(application) {

    companion object {
        private const val TAG = "ReaderViewModel"
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
        val edition: EditionDto? = null,
        val chapters: List<CachedChapter> = emptyList(),
        val currentChapter: CachedChapter? = null,
        val currentSortIndex: Int = 0,
            val pages: List<ReaderTextEngine.Page> = emptyList(),
            val currentPage: Int = 0,
            /** 当前阅读位置的全局字符偏移（跨模式持久化到 scrollOffset 列） */
            val charOffset: Int = 0,
        val annotations: List<CachedAnnotation> = emptyList(),
        val settings: ReaderSettings = ReaderSettings(),
        val loading: Boolean = false,
        val error: String? = null,
    )

    private val repository = TextRepository.get(application)

    private val _uiState = MutableStateFlow(UiState())
    val uiState: StateFlow<UiState> = _uiState.asStateFlow()

    private var saveProgressJob: Job? = null

    /** 当前阅读位置的全局字符偏移（跨模式复用 scrollOffset 列持久化） */
    private var currentCharOffset: Int = 0
    private var specJob: Job? = null
    private var pageSpec: ReaderTextEngine.LayoutSpec? = null
    private val textMeasurer = ReaderTextEngine.StaticLayoutMeasurer()

    fun loadWork(workId: Int, workTitle: String, editionId: Int? = null) {
        viewModelScope.launch {
            _uiState.update { it.copy(workId = workId, workTitle = workTitle, loading = true) }

            val work = repository.workById(workId)
            val displayTitle = work?.title ?: workTitle

            // 恢复阅读进度
            val progress = repository.progressByWork(workId)
            val editions = repository.editionsByWork(workId)
            val edition = editionId?.let { id -> editions.find { it.id == id } }
                ?: editions.firstOrNull()
            val targetEditionId = edition?.id ?: progress?.editionId ?: 0

            val chapters = if (targetEditionId > 0) repository.chapterList(targetEditionId) else emptyList()
            val sortIndex = progress?.sortIndex?.takeIf { it < chapters.size } ?: 0
            val chapter = chapters.getOrNull(sortIndex)?.let {
                repository.chapterContent(targetEditionId, it.sortIndex)
            } ?: chapters.firstOrNull()

            val settings = progress?.let {
                ReaderSettings(
                    fontSize = it.fontSize,
                    lineHeight = it.lineHeight,
                    theme = if (it.theme == "dark") ReaderTheme.DARK else ReaderTheme.LIGHT,
                    mode = if (it.mode == "scroll") ReaderMode.SCROLL else ReaderMode.PAGE,
                )
            } ?: ReaderSettings()

            val pageIdx = progress?.pageIndex?.coerceAtLeast(0) ?: 0
            // 滚动模式：scrollOffset 列复用为字符偏移，用于恢复到上次阅读位置
            val charOffset = progress?.scrollOffset?.takeIf {
                it > 0 && (progress.mode == "scroll")
            }
            _uiState.update {
                it.copy(
                    workTitle = displayTitle,
                    edition = edition,
                    chapters = chapters,
                    currentChapter = chapter,
                    currentSortIndex = chapter?.sortIndex ?: 0,
                    settings = settings,
                    currentPage = pageIdx,
                    loading = false,
                )
            }
            chapter?.let { loadChapter(it, pageIdx, charOffset = charOffset) }
        }
    }

    fun loadChapter(chapter: CachedChapter, pageIndex: Int = 0, charOffset: Int? = null) {
        viewModelScope.launch {
            _uiState.update { it.copy(loading = true) }
            val full = repository.chapterContent(chapter.editionId, chapter.sortIndex)
                ?: chapter
            repository.syncAnnotations(pullEditionIds = listOf(full.editionId))
            val annotations = repository.annotationsByNode(full.id)
            _uiState.update {
                it.copy(
                    currentChapter = full,
                    currentSortIndex = full.sortIndex,
                    annotations = annotations,
                    loading = false,
                )
            }
            val pages = paginateNow(full.rawText)
            val target = when {
                charOffset != null -> ReaderTextEngine.findPageForOffset(pages, charOffset)
                pageIndex in pages.indices -> pageIndex
                else -> 0
            }
            currentCharOffset = pages.getOrNull(target)?.startOffset ?: 0
            _uiState.update {
                it.copy(pages = pages, currentPage = target, charOffset = currentCharOffset)
            }
            saveProgressDebounced()
        }
    }

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
 if (pageIndex in 0 until _uiState.value.pages.size) {
 _uiState.update { it.copy(currentPage = pageIndex) }
 currentCharOffset = _uiState.value.pages.getOrNull(pageIndex)?.startOffset ?: 0
 _uiState.update { it.copy(charOffset = currentCharOffset) }
 saveProgressDebounced()
 }
 }

 /** 滚动模式：上报当前首个可见段落的首字符偏移（全局） */
 fun onScrollCharOffset(charOffset: Int) {
 if (currentCharOffset != charOffset) {
 currentCharOffset = charOffset
 _uiState.update { it.copy(charOffset = charOffset) }
 saveProgressDebounced()
 }
 }

 /**
 * pager 滑动落定后的回写入口（由 snapshotFlow{settledPage} 驱动）。
 * 在 ViewModel 内做页码比较，避免组合期捕获的 state 过期造成回环。
 */
 fun onPageSettled(pageIndex: Int) {
 if (_uiState.value.currentPage != pageIndex) {
 goToPage(pageIndex)
 }
 }

    }

    /**
     * 布局参数变化（字号/行距/可用宽高）：300ms 防抖后重建分页，
     * 并以当前页首字符偏移重定位页码，避免简单回第 0 页。
     */
    fun setPageSpec(spec: ReaderTextEngine.LayoutSpec) {
        if (spec == pageSpec) return
        pageSpec = spec
        specJob?.cancel()
        specJob = viewModelScope.launch {
            delay(300)
            rebuildPages()
        }
    }

    private suspend fun paginateNow(text: String): List<ReaderTextEngine.Page> =
        withContext(Dispatchers.Default) {
            ReaderTextEngine.paginate(text, ParagraphSplitter.split(text), textMeasurer)
        }

    private suspend fun rebuildPages() {
        val state = _uiState.value
        val text = state.currentChapter?.rawText ?: return
        val spec = pageSpec ?: return
        val anchor = state.pages.getOrNull(state.currentPage)?.startOffset ?: 0
        val pages = withContext(Dispatchers.Default) {
            ReaderTextEngine.paginate(text, ParagraphSplitter.split(text), spec, textMeasurer)
        }
        _uiState.update {
            it.copy(
                pages = pages,
                currentPage = ReaderTextEngine.findPageForOffset(pages, anchor),
                charOffset = anchor,
            )
        }
        currentCharOffset = anchor
    }

    fun onSelection(
        pageIndex: Int,
        pageSelectionStart: Int,
        pageSelectionEnd: Int,
        selectedText: String,
    ): CachedAnnotation? {
        val page = _uiState.value.pages.getOrNull(pageIndex) ?: return null
        val start = page.startOffset + pageSelectionStart
        val end = page.startOffset + pageSelectionEnd
        val chapter = _uiState.value.currentChapter
        val annotation = CachedAnnotation(
            workId = _uiState.value.workId,
            editionId = chapter?.editionId ?: _uiState.value.edition?.id ?: 0,
            nodeId = chapter?.id ?: 0,
            startOffset = start,
            endOffset = end,
            selectedText = selectedText,
            note = "",
            color = "yellow",
            createdAt = nowIso(),
            updatedAt = nowIso(),
        )
        _uiState.update { it.copy(annotations = it.annotations + annotation) }
        return annotation
    }

    /**
     * 新建批注（localId == 0 的草稿）。任何异常仅回滚 UI，不再向外抛出。
     */
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

    /**
     * 更新已落库批注（localId != 0）。写库/同步异常仅记录日志，不再闪退。
     */
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
            } catch (e: Exception) {
                Log.w(TAG, "deleteAnnotation failed: ${e.message}")
            }
        }
    }

    /**
     * 设置更新：仅更新状态并持久化。翻页模式的重排版由 setPageSpec 防抖驱动，
     * 不再整章重载（避免章节内容闪烁与批注重拉）。
     */
    fun updateSettings(settings: ReaderSettings) {
        _uiState.update { it.copy(settings = settings) }
        saveProgressDebounced()
    }

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
                // 翻页模式存当前页首字符偏移，滚动模式存首个可见段落偏移；
                // 切模式后旧值自然失效，由新模式的首次上报覆盖
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

    /**
     * 放弃未保存的批注草稿（localId == 0）：仅回滚 UI 中的临时高亮，不动数据库。
     */
    fun discardDraft(annotation: CachedAnnotation) {
        if (annotation.localId != 0L) return
        _uiState.update { state ->
            state.copy(annotations = state.annotations.filterNot {
                it.localId == 0L && sameAnchor(it, annotation)
            })
        }
    }
}
