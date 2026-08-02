package com.sailzen.app.feature.settings

import android.app.Application
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import com.sailzen.app.core.bg.ReminderService
import com.sailzen.app.core.data.SettingsManager
import com.sailzen.app.core.reminder.ReminderRepository
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch

class SettingsViewModel(application: Application) : AndroidViewModel(application) {

    data class UiState(
        val serverUrl: String = "",
        val apiToken: String = "",
        val quietStart: String = "23:00",
        val quietEnd: String = "08:00",
        val deviceId: String = "",
        val connected: Boolean = false,
        val saved: Boolean = false,
    )

    private val settings = SettingsManager.get(application)

    private val _uiState = MutableStateFlow(UiState())
    val uiState: StateFlow<UiState> = _uiState.asStateFlow()

    init {
        viewModelScope.launch {
            settings.serverUrlFlow.collect { v -> _uiState.update { it.copy(serverUrl = v) } }
        }
        viewModelScope.launch {
            settings.apiTokenFlow.collect { v -> _uiState.update { it.copy(apiToken = v) } }
        }
        viewModelScope.launch {
            settings.quietStartFlow.collect { v -> _uiState.update { it.copy(quietStart = v) } }
        }
        viewModelScope.launch {
            settings.quietEndFlow.collect { v -> _uiState.update { it.copy(quietEnd = v) } }
        }
        viewModelScope.launch {
            settings.deviceIdFlow.collect { v -> _uiState.update { it.copy(deviceId = v) } }
        }
        viewModelScope.launch {
            // 确保 deviceId 已生成
            settings.getOrCreateDeviceId()
        }
        viewModelScope.launch {
            ReminderService.connectedState.collect { c ->
                _uiState.update { it.copy(connected = c) }
            }
        }
    }

    fun onServerUrlChange(value: String) = _uiState.update { it.copy(serverUrl = value) }

    fun onApiTokenChange(value: String) = _uiState.update { it.copy(apiToken = value) }

    fun onQuietStartChange(value: String) = _uiState.update { it.copy(quietStart = value) }

    fun onQuietEndChange(value: String) = _uiState.update { it.copy(quietEnd = value) }

    fun save() {
        val current = _uiState.value
        viewModelScope.launch {
            settings.saveServerConfig(current.serverUrl, current.apiToken)
            settings.saveQuietHours(current.quietStart, current.quietEnd)
            // 重启前台服务以应用新配置
            if (current.serverUrl.isNotBlank()) {
                ReminderService.restart(getApplication())
            } else {
                ReminderService.stop(getApplication())
            }
            _uiState.update { it.copy(saved = true) }
        }
    }

    fun consumeSaved() = _uiState.update { it.copy(saved = false) }
}
