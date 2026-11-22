package com.sailzen.app

import android.app.Application
import com.sailzen.app.core.bg.ReminderService
import com.sailzen.app.core.data.SettingsManager
import com.sailzen.app.core.reminder.NotificationHelper
import com.sailzen.app.core.sync.SyncWorker
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch

class SailZenApp : Application() {

    override fun onCreate() {
        super.onCreate()
        // 通知渠道（urgent / reminder / silent / service）
        NotificationHelper.createChannels(this)
        // WorkManager 15min 周期补偿（通道 2）
        SyncWorker.enqueue(this)
        // 已配置服务器则尝试启动前台 Service（通道 1；若在后台冷启被系统限制，进入 MainActivity 会再次补启）
        CoroutineScope(Dispatchers.IO).launch {
            if (SettingsManager.get(this@SailZenApp).serverUrl().isNotBlank()) {
                ReminderService.ensureStarted(this@SailZenApp)
            }
        }
    }
}
