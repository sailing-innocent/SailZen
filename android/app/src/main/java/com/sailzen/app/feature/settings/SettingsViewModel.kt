package com.sailzen.app.feature.settings

import android.app.Application
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import com.sailzen.app.BuildConfig
import com.sailzen.app.core.bg.ReminderService
import com.sailzen.app.core.data.SettingsManager
import com.sailzen.app.core.network.ApiClient
import com.sailzen.app.core.network.AppReleaseDto
import com.sailzen.app.core.network.ReminderWebSocket
import com.sailzen.app.core.update.AppInstallEvent
import com.sailzen.app.core.update.AppInstallReceiver
import com.sailzen.app.core.update.AppUpdateManager
import com.sailzen.app.core.update.AppUpdateState
import com.sailzen.app.core.user.UserInboxRepository
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import okhttp3.Request

class SettingsViewModel(application: Application) : AndroidViewModel(application) {

    data class UiState(
        val userDisplayName: String = "SailZen Owner",
        val userSlug: String = "owner",
        val serverUrl: String = "",
        val serverUrlLocked: Boolean = false,
        val apiToken: String = "",
        val quietStart: String = "23:00",
        val quietEnd: String = "08:00",
        val deviceId: String = "",
        val connected: Boolean = false,
        val connectionState: ReminderWebSocket.ConnectionState = ReminderWebSocket.ConnectionState.DISCONNECTED,
        val connectionDetail: String = "",
        val testingConnection: Boolean = false,
        val connectionTestResult: String? = null,
        val connectionTestOk: Boolean? = null,
        val saved: Boolean = false,
        val currentVersionName: String = BuildConfig.VERSION_NAME,
        val currentVersionCode: Int = BuildConfig.VERSION_CODE,
        val updateState: AppUpdateState = AppUpdateState.Idle,
    )

    private val settings = SettingsManager.get(application)
    private val userInboxRepo = UserInboxRepository.get(application)

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
            settings.userDisplayNameFlow.collect { v -> _uiState.update { it.copy(userDisplayName = v) } }
        }
        viewModelScope.launch {
            settings.userSlugFlow.collect { v -> _uiState.update { it.copy(userSlug = v) } }
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
        viewModelScope.launch {
            ReminderService.connectionState.collect { st ->
                _uiState.update { it.copy(connectionState = st) }
            }
        }
        viewModelScope.launch {
            ReminderService.connectionDetail.collect { detail ->
                _uiState.update { it.copy(connectionDetail = detail) }
            }
        }
        viewModelScope.launch {
            AppInstallReceiver.events.collect { ev ->
                when (ev) {
                    is AppInstallEvent.PendingUserAction -> {
                        val cur = _uiState.value.updateState
                        if (cur is AppUpdateState.Installing) {
                            _uiState.update {
                                it.copy(
                                    updateState = cur.copy(
                                        hint = "已提交至系统安装器，请在系统弹窗中确认安装",
                                    ),
                                )
                            }
                        }
                    }
                    is AppInstallEvent.Success -> {
                        _uiState.update { it.copy(updateState = AppUpdateState.Idle) }
                    }
                    is AppInstallEvent.Failure -> {
                        _uiState.update {
                            it.copy(updateState = AppUpdateState.Error(ev.message))
                        }
                        ReminderService.ensureStarted(getApplication())
                    }
                }
            }
        }
    }

    fun onUserDisplayNameChange(value: String) = _uiState.update { it.copy(userDisplayName = value) }

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
            userInboxRepo.updateProfile(
                displayName = current.userDisplayName,
                quietStart = current.quietStart,
                quietEnd = current.quietEnd,
            )
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

    /** 主动探测 /api/v1/health，返回真实耗时或具体报错，便于现场排查端口/网络/鉴权问题 */
    fun testConnection() {
        val current = _uiState.value
        if (current.testingConnection) return
        viewModelScope.launch {
            val rawUrl = if (current.serverUrlLocked) settings.defaultServerUrl() else current.serverUrl
            val normalized = ApiClient.normalizeBaseUrl(rawUrl)
            if (normalized.isBlank()) {
                _uiState.update {
                    it.copy(
                        connectionTestOk = false,
                        connectionTestResult = "未填写服务器地址",
                    )
                }
                return@launch
            }
            _uiState.update {
                it.copy(testingConnection = true, connectionTestResult = null, connectionTestOk = null)
            }
            val startMs = System.currentTimeMillis()
            val healthUrl = "$normalized/api/v1/health"
            val result = withContext(Dispatchers.IO) {
                runCatching {
                    val req = Request.Builder().url(healthUrl).get().build()
                    ApiClient.downloadClient(current.apiToken).newCall(req).execute().use { resp ->
                        val elapsed = System.currentTimeMillis() - startMs
                        if (resp.isSuccessful) {
                            true to "HTTP ${resp.code} 连通成功（${elapsed}ms）"
                        } else {
                            false to "HTTP ${resp.code}：请检查地址或 Token（$healthUrl）"
                        }
                    }
                }
            }
            result.fold(
                onSuccess = { (ok, msg) ->
                    _uiState.update {
                        it.copy(
                            testingConnection = false,
                            connectionTestOk = ok,
                            connectionTestResult = msg,
                        )
                    }
                },
                onFailure = { err ->
                    _uiState.update {
                        it.copy(
                            testingConnection = false,
                            connectionTestOk = false,
                            connectionTestResult = "连接失败：${err.javaClass.simpleName}: ${err.message ?: "未知错误"}（$healthUrl）",
                        )
                    }
                },
            )
        }
    }

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
                    if (canInstall) {
                        launchSessionInstall(release, apkFile)
                    } else {
                        _uiState.update {
                            it.copy(
                                updateState = AppUpdateState.ReadyToInstall(
                                    release = release,
                                    apkFile = apkFile,
                                    needsInstallPermission = true,
                                ),
                            )
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

    private fun launchSessionInstall(release: AppReleaseDto, apkFile: java.io.File) {
        viewModelScope.launch {
            val app = getApplication<Application>()
            _uiState.update {
                it.copy(
                    updateState = AppUpdateState.Installing(
                        release = release,
                        apkFile = apkFile,
                        hint = "正在写入系统安装会话，稍后弹出系统确认框…",
                    ),
                )
            }
            AppUpdateManager.installApkViaSession(app, apkFile)
                .onFailure { err ->
                    runCatching {
                        AppUpdateManager.installApk(app, apkFile)
                        _uiState.update {
                            it.copy(
                                updateState = AppUpdateState.ReadyToInstall(
                                    release = release,
                                    apkFile = apkFile,
                                    needsInstallPermission = false,
                                ),
                            )
                        }
                    }.onFailure { fallbackErr ->
                        _uiState.update {
                            it.copy(
                                updateState = AppUpdateState.Error(
                                    "拉起安装器失败: ${fallbackErr.message ?: err.message}",
                                ),
                            )
                        }
                    }
                }
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
        launchSessionInstall(ready.release, ready.apkFile)
    }

    fun triggerFallbackInstall() {
        val apkFile = when (val st = _uiState.value.updateState) {
            is AppUpdateState.Installing -> st.apkFile
            is AppUpdateState.ReadyToInstall -> st.apkFile
            else -> return
        }
        val app = getApplication<Application>()
        runCatching { AppUpdateManager.installApk(app, apkFile) }
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
