package com.sailzen.app.core.bg

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import com.sailzen.app.core.reminder.ReminderRepository
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch

/** 开机重启：拉起前台 Service（已配置服务器时）+ 重排未来闹钟 */
class BootReceiver : BroadcastReceiver() {

    override fun onReceive(context: Context, intent: Intent) {
        if (intent.action != Intent.ACTION_BOOT_COMPLETED) return
        val pendingResult = goAsync()
        CoroutineScope(Dispatchers.IO).launch {
            try {
                val repository = ReminderRepository.get(context)
                if (repository.serverConfigured()) {
                    ReminderService.start(context)
                }
                repository.rescheduleAllAlarms()
            } finally {
                pendingResult.finish()
            }
        }
    }
}
