package com.sailzen.app.core.bg

import android.app.Service
import android.content.Context
import android.content.Intent
import android.os.IBinder
import android.util.Log
import androidx.core.app.NotificationManagerCompat
import androidx.core.content.ContextCompat
import com.sailzen.app.core.data.SettingsManager
import com.sailzen.app.core.data.db.AppDatabase
import com.sailzen.app.core.network.ApiClient
import com.sailzen.app.core.network.ReminderWebSocket
import com.sailzen.app.core.reminder.NotificationHelper
import com.sailzen.app.core.reminder.ReminderRepository
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.launch

/**
 * 前台 Service：
 * 持有 WebSocket 长连接，收到 reminder.delivered → Repository.processDelivered；
 * 常驻通知显示今日待办数；START_STICKY 被杀后由系统拉起。
 */
class ReminderService : Service() {

    companion object {
        private const val TAG = "ReminderService"
        private const val ACTION_RECONNECT = "com.sailzen.app.action.RECONNECT"

        /** WS 是否已建立连接（设置页/规划页徽标） */
        val connectedState = MutableStateFlow(false)

        /** 细粒度连接状态 */
        val connectionState = MutableStateFlow(ReminderWebSocket.ConnectionState.DISCONNECTED)

        /** 最近一次连接状态明细（用于 UI 展示排查） */
        val connectionDetail = MutableStateFlow("")

        fun start(context: Context) {
            try {
                ContextCompat.startForegroundService(
                    context,
                    Intent(context, ReminderService::class.java),
                )
            } catch (e: Exception) {
                // Android 12+ 后台冷启动可能抛出 ForegroundServiceStartNotAllowedException，
                // 进入 MainActivity 前台时会再次调用 ensureStarted() 补启。
                Log.w(TAG, "startForegroundService deferred: ${e.javaClass.simpleName}: ${e.message}")
            }
        }

        /** 确保前台服务已启动（支持在 Application / Activity 前台幂等调用） */
        fun ensureStarted(context: Context) {
            start(context)
        }

        fun stop(context: Context) {
            context.stopService(Intent(context, ReminderService::class.java))
        }

        /**
         * 原子重连：通过 ACTION_RECONNECT 通知服务重建 WebSocket，
         * 避免 stopService + startForegroundService 竞态导致旧 socket 未释放或忽略新配置。
         */
        fun restart(context: Context) {
            try {
                ContextCompat.startForegroundService(
                    context,
                    Intent(context, ReminderService::class.java).setAction(ACTION_RECONNECT),
                )
            } catch (e: Exception) {
                Log.w(TAG, "restart deferred: ${e.javaClass.simpleName}: ${e.message}")
            }
        }
    }

    private val serviceScope = CoroutineScope(SupervisorJob() + Dispatchers.IO)
    private lateinit var repository: ReminderRepository
    private var webSocket: ReminderWebSocket? = null
    private var refreshJob: Job? = null

    override fun onCreate() {
        super.onCreate()
        repository = ReminderRepository.get(this)
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        startForeground(
            NotificationHelper.SERVICE_NOTIFICATION_ID,
            NotificationHelper.buildServiceNotification(this, 0, connectedState.value),
        )
        val forceReconnect = intent?.action == ACTION_RECONNECT
        startWebSocket(forceReconnect = forceReconnect)
        startPeriodicRefresh()
        serviceScope.launch {
            repository.registerDevice()
            repository.syncPending()
            refreshServiceNotification()
        }
        return START_STICKY
    }

    override fun onBind(intent: Intent?): IBinder? = null

    override fun onDestroy() {
        webSocket?.stop()
        webSocket = null
        refreshJob?.cancel()
        connectedState.value = false
        connectionState.value = ReminderWebSocket.ConnectionState.DISCONNECTED
        super.onDestroy()
    }

    private fun startWebSocket(forceReconnect: Boolean = false) {
        if (webSocket != null && !forceReconnect) return
        if (forceReconnect) {
            Log.i(TAG, "forcing WebSocket reconnect with latest settings")
            webSocket?.stop()
            webSocket = null
        }
        val settings = SettingsManager.get(this)
        webSocket = ReminderWebSocket(
            scope = serviceScope,
            urlProvider = {
                val url = settings.serverUrl()
                if (url.isBlank()) {
                    null
                } else {
                    ApiClient.wsUrl(url, settings.getOrCreateDeviceId(), settings.apiToken())
                }
            },
            onReminder = { dto ->
                serviceScope.launch {
                    repository.processDelivered(dto)
                    refreshServiceNotification()
                }
            },
            onStateChange = { connected -> connectedState.value = connected },
            onDetailedStateChange = { state, detail ->
                Log.d(TAG, "WS state=$state detail=$detail")
                connectionState.value = state
                connectionDetail.value = detail
                serviceScope.launch {
                    refreshServiceNotification()
                }
            },
        ).also { it.start() }
    }

    /** 每 5 分钟刷新一次常驻通知的待办数（WorkManager 15min 补偿之外的轻量刷新） */
    private fun startPeriodicRefresh() {
        refreshJob?.cancel()
        refreshJob = serviceScope.launch {
            while (true) {
                delay(5 * 60 * 1000L)
                repository.syncPending()
                refreshServiceNotification()
            }
        }
    }

    private suspend fun refreshServiceNotification() {
        val summary = repository.summaryToday()
        val count = summary?.pending
            ?: AppDatabase.get(this).reminderDao().activeList().size
        try {
            NotificationManagerCompat.from(this).notify(
                NotificationHelper.SERVICE_NOTIFICATION_ID,
                NotificationHelper.buildServiceNotification(this, count, connectedState.value),
            )
        } catch (_: SecurityException) {
            // 无通知权限时静默
        }
    }
}
