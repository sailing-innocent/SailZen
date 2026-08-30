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

class ReaderHomeViewModel(application: Application) : AndroidViewModel(application) {

    data class UiState(
        val works: List<CachedWork> = emptyList(),
        val refreshing: Boolean = false,
        val configured: Boolean = true,
    )

    private val repository = TextRepository.get(application)

    private val _uiState = MutableStateFlow(UiState())
    val uiState: StateFlow<UiState> = _uiState.asStateFlow()

    init {
        viewModelScope.launch {
            repository.observeWorks().collect { list ->
                _uiState.update { it.copy(works = list) }
            }
        }
        refresh()
    }

    fun refresh() {
        viewModelScope.launch {
            _uiState.update { it.copy(refreshing = true) }
            repository.syncWorks()
            _uiState.update {
                it.copy(
                    refreshing = false,
                    configured = repository.serverConfigured(),
                )
            }
        }
    }
}
