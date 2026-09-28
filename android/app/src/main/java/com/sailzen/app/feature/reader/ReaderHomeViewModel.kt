package com.sailzen.app.feature.reader

import android.app.Application
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import com.sailzen.app.core.data.db.CachedWork
import com.sailzen.app.core.text.TextRepository
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch

/**
 * 阅读首页 ViewModel：作品列表（Room 观察）+ 同步状态 + 全本缓存进度。
 * 缓存管理以「版本」为单位：作品 → 首个版本 → 全本缓存。
 */
class ReaderHomeViewModel(application: Application) : AndroidViewModel(application) {

    /** 作品的缓存概况 */
    data class WorkCacheInfo(
        val editionId: Int,
        val cachedCount: Int,
        val totalCount: Int,
    ) {
        val fullyCached: Boolean get() = totalCount > 0 && cachedCount >= totalCount
    }

    data class UiState(
        val works: List<CachedWork> = emptyList(),
        val refreshing: Boolean = false,
        val configured: Boolean = true,
        /** workId → 缓存概况（目录章节数 + 已缓存正文数） */
        val cacheInfo: Map<Int, WorkCacheInfo> = emptyMap(),
        /** 正在执行全本缓存的 workId（避免重复点击） */
        val cachingWorkId: Int? = null,
    )

    private val repository = TextRepository.get(application)

    private val _uiState = MutableStateFlow(UiState())
    val uiState: StateFlow<UiState> = _uiState.asStateFlow()

    /** 同步状态（离线/同步中/已同步）与全本缓存进度 */
    val syncState = repository.syncState
    val cacheProgress = repository.cacheProgress

    init {
        viewModelScope.launch {
            repository.observeWorks().collect { list ->
                _uiState.update { it.copy(works = list) }
                refreshCacheInfo(list.map { it.id })
            }
        }
        refresh()
    }

    fun refresh() {
        viewModelScope.launch {
            _uiState.update { it.copy(refreshing = true) }
            repository.refreshWorks()
            _uiState.update {
                it.copy(
                    refreshing = false,
                    configured = repository.serverConfigured(),
                )
            }
            refreshCacheInfo(_uiState.value.works.map { it.id })
        }
    }

    /** 全本缓存：顺序下载该作品首版本的全部章节正文，进度经 repository.cacheProgress 发布 */
    fun cacheWholeWork(workId: Int) {
        if (_uiState.value.cachingWorkId != null) return
        viewModelScope.launch {
            val editionId = resolveEditionId(workId) ?: return@launch
            _uiState.update { it.copy(cachingWorkId = workId) }
            try {
                repository.cacheEdition(editionId)
            } finally {
                _uiState.update { it.copy(cachingWorkId = null) }
                repository.clearCacheProgress()
                refreshCacheInfo(listOf(workId))
            }
        }
    }

    /** 刷新作品的缓存概况（目录与已缓存正文计数） */
    private suspend fun refreshCacheInfo(workIds: List<Int>) {
        val updated = _uiState.value.cacheInfo.toMutableMap()
        for (workId in workIds) {
            val editionId = resolveEditionId(workId)
            if (editionId == null) {
                updated.remove(workId)
                continue
            }
            val chapters = repository.chaptersSnapshot(editionId)
            updated[workId] = WorkCacheInfo(
                editionId = editionId,
                cachedCount = repository.cachedChapterCount(editionId),
                totalCount = chapters.size,
            )
        }
        _uiState.update { it.copy(cacheInfo = updated) }
    }

    /** 作品 → 首个版本 id：优先本地缓存，未命中则后台拉取一次 */
    private suspend fun resolveEditionId(workId: Int): Int? {
        repository.editionsSnapshot(workId).firstOrNull()?.let { return it.id }
        if (repository.refreshEditions(workId)) {
            return repository.editionsSnapshot(workId).firstOrNull()?.id
        }
        return null
    }
}
