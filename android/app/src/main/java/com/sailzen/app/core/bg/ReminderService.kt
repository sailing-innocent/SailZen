package com.sailzen.app.core.bg

import android.app.Service
import android.content.Context
import android.content.Intent
import android.os.IBinder
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
        /** WS 连接状态（设置页徽标） */
        val connectedState = MutableStateFlow(false)

        fun start(context: Context) {
            ContextCompat.startForegroundService(
                context,
                Intent(context, ReminderService::class.java),
            )
        }

        fun stop(context: Context) {
            context.stopService(Intent(context, ReminderService::class.java))
        }

        fun restart(context: Context) {
            stop(context)
            start(context)
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
        startWebSocket()
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
        super.onDestroy()
    }

    private fun startWebSocket() {
        if (webSocket != null) return
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
                android.util.Log.d("ReminderService", "WS state=$state detail=$detail")
                // 连接异常时刷新常驻通知，把状态透出到通知文本
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
