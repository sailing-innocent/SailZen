package com.sailzen.app.feature.settings

import android.app.Application
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import com.sailzen.app.BuildConfig
import com.sailzen.app.core.bg.ReminderService
import com.sailzen.app.core.data.SettingsManager
import com.sailzen.app.core.network.AppReleaseDto
import com.sailzen.app.core.update.AppUpdateManager
import com.sailzen.app.core.update.AppUpdateState
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch

class SettingsViewModel(application: Application) : AndroidViewModel(application) {

    data class UiState(
        val serverUrl: String = "",
        val serverUrlLocked: Boolean = false,
        val apiToken: String = "",
        val quietStart: String = "23:00",
        val quietEnd: String = "08:00",
        val deviceId: String = "",
        val connected: Boolean = false,
        val saved: Boolean = false,
        val currentVersionName: String = BuildConfig.VERSION_NAME,
        val currentVersionCode: Int = BuildConfig.VERSION_CODE,
        val updateState: AppUpdateState = AppUpdateState.Idle,
    )

    private val settings = SettingsManager.get(application)

    private val _uiState = MutableStateFlow(UiState())
    val uiState: StateFlow<UiState> = _uiState.asStateFlow()

    init {
        _uiState.update { it.copy(serverUrlLocked = settings.isServerUrlLocked()) }
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
            val url = if (current.serverUrlLocked) settings.defaultServerUrl() else current.serverUrl
            settings.saveServerConfig(url, current.apiToken)
            settings.saveQuietHours(current.quietStart, current.quietEnd)
            // 重启前台服务以应用新配置
            if (settings.serverUrl().isNotBlank()) {
                ReminderService.restart(getApplication())
            } else {
                ReminderService.stop(getApplication())
            }
            _uiState.update { it.copy(saved = true) }
        }
    }

    fun consumeSaved() = _uiState.update { it.copy(saved = false) }

    fun checkForUpdate() {
        val current = _uiState.value
        if (current.updateState is AppUpdateState.Checking ||
            current.updateState is AppUpdateState.Downloading
        ) {
            return
        }
        viewModelScope.launch {
            val baseUrl = settings.serverUrl().ifBlank { current.serverUrl }
            val token = settings.apiToken().ifBlank { current.apiToken }
            if (baseUrl.isBlank()) {
                _uiState.update { it.copy(updateState = AppUpdateState.Error("请先配置服务器地址")) }
                return@launch
            }
            _uiState.update { it.copy(updateState = AppUpdateState.Checking) }
            val result = AppUpdateManager.checkForUpdate(baseUrl, token)
            result.fold(
                onSuccess = { release ->
                    if (release != null) {
                        _uiState.update { it.copy(updateState = AppUpdateState.UpdateAvailable(release)) }
                    } else {
                        _uiState.update {
                            it.copy(
                                updateState = AppUpdateState.UpToDate(
                                    BuildConfig.VERSION_NAME,
                                    BuildConfig.VERSION_CODE,
                                ),
                            )
                        }
                    }
                },
                onFailure = { err ->
                    _uiState.update {
                        it.copy(updateState = AppUpdateState.Error(err.message ?: "检查更新失败"))
                    }
                },
            )
        }
    }

    fun downloadAndInstall(release: AppReleaseDto) {
        if (_uiState.value.updateState is AppUpdateState.Downloading) return
        viewModelScope.launch {
            val app = getApplication<Application>()
            val baseUrl = settings.serverUrl().ifBlank { _uiState.value.serverUrl }
            val token = settings.apiToken().ifBlank { _uiState.value.apiToken }
            _uiState.update {
                it.copy(updateState = AppUpdateState.Downloading(release, 0L, release.size))
            }
            val result = AppUpdateManager.downloadApk(
                context = app,
                baseUrl = baseUrl,
                token = token,
                release = release,
            ) { read, total ->
                _uiState.update {
                    it.copy(updateState = AppUpdateState.Downloading(release, read, total))
                }
            }
            result.fold(
                onSuccess = { apkFile ->
                    val canInstall = AppUpdateManager.canInstallPackages(app)
                    _uiState.update {
                        it.copy(
                            updateState = AppUpdateState.ReadyToInstall(
                                release = release,
                                apkFile = apkFile,
                                needsInstallPermission = !canInstall,
                            ),
                        )
                    }
                    if (canInstall) {
                        runCatching { AppUpdateManager.installApk(app, apkFile) }
                            .onFailure { err ->
                                _uiState.update {
                                    it.copy(updateState = AppUpdateState.Error("拉起安装器失败: ${err.message}"))
                                }
                            }
                    }
                },
                onFailure = { err ->
                    _uiState.update {
                        it.copy(updateState = AppUpdateState.Error(err.message ?: "下载失败"))
                    }
                },
            )
        }
    }

    fun triggerInstall() {
        val ready = _uiState.value.updateState as? AppUpdateState.ReadyToInstall ?: return
        val app = getApplication<Application>()
        if (!AppUpdateManager.canInstallPackages(app)) {
            _uiState.update {
                it.copy(updateState = ready.copy(needsInstallPermission = true))
            }
            runCatching { app.startActivity(AppUpdateManager.buildInstallPermissionIntent(app)) }
            return
        }
        _uiState.update { it.copy(updateState = ready.copy(needsInstallPermission = false)) }
        runCatching { AppUpdateManager.installApk(app, ready.apkFile) }
            .onFailure { err ->
                _uiState.update {
                    it.copy(updateState = AppUpdateState.Error("拉起安装器失败: ${err.message}"))
                }
            }
    }

    fun openInstallPermissionSettings() {
        val app = getApplication<Application>()
        runCatching { app.startActivity(AppUpdateManager.buildInstallPermissionIntent(app)) }
    }
}
