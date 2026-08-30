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
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch

class ReaderViewModel(application: Application) : AndroidViewModel(application) {

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
        val annotations: List<CachedAnnotation> = emptyList(),
        val settings: ReaderSettings = ReaderSettings(),
        val loading: Boolean = false,
        val error: String? = null,
    )

    private val repository = TextRepository.get(application)

    private val _uiState = MutableStateFlow(UiState())
    val uiState: StateFlow<UiState> = _uiState.asStateFlow()

    private var saveProgressJob: Job? = null
    private var pageSpec: ReaderTextEngine.LayoutSpec? = null

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
            chapter?.let { loadChapter(it, pageIdx) }
        }
    }

    fun loadChapter(chapter: CachedChapter, pageIndex: Int = 0) {
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
            buildPages(full.rawText)
            if (pageIndex in 0 until _uiState.value.pages.size) {
                _uiState.update { it.copy(currentPage = pageIndex) }
            } else {
                _uiState.update { it.copy(currentPage = 0) }
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
            saveProgressDebounced()
        }
    }

    fun setPageSpec(spec: ReaderTextEngine.LayoutSpec) {
        if (pageSpec != spec) {
            pageSpec = spec
            val text = _uiState.value.currentChapter?.rawText ?: return
            buildPages(text)
        }
    }

    private fun buildPages(text: String) {
        val spec = pageSpec ?: return
        viewModelScope.launch {
            val pages = ReaderTextEngine.paginate(text, spec)
            _uiState.update {
                it.copy(
                    pages = pages,
                    currentPage = it.currentPage.coerceIn(0, (pages.size - 1).coerceAtLeast(0)),
                )
            }
        }
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

    fun saveAnnotation(annotation: CachedAnnotation, note: String) {
        viewModelScope.launch {
            val updated = annotation.copy(note = note, updatedAt = nowIso())
            val localId = repository.addAnnotation(updated)
            val withId = updated.copy(localId = localId)
            _uiState.update { state ->
                state.copy(annotations = state.annotations.map { if (it === annotation) withId else it })
            }
            saveProgressDebounced()
        }
    }

    fun deleteAnnotation(annotation: CachedAnnotation) {
        viewModelScope.launch {
            repository.deleteAnnotation(annotation)
            _uiState.update { state ->
                state.copy(annotations = state.annotations.filter { it.localId != annotation.localId })
            }
        }
    }

    fun updateSettings(settings: ReaderSettings) {
        _uiState.update { it.copy(settings = settings) }
        _uiState.value.currentChapter?.let { loadChapter(it, _uiState.value.currentPage) }
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
}
