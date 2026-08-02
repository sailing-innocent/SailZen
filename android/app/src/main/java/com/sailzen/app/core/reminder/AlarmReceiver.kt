package com.sailzen.app.core.reminder

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import com.sailzen.app.core.data.SettingsManager
import com.sailzen.app.core.data.db.AppDatabase
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch

/**
 * 本地闹钟触发：从 Room 读缓存直接弹通知（断网兜底）。
 * 已终结（RESOLVED/IGNORED/CANCELED/ARCHIVED）的提醒不再弹出。
 */
class AlarmReceiver : BroadcastReceiver() {

    companion object {
        private val TERMINAL_STATES = setOf("RESOLVED", "IGNORED", "CANCELED", "ARCHIVED")
    }

    override fun onReceive(context: Context, intent: Intent) {
        val reminderId = intent.getIntExtra(ReminderActionReceiver.EXTRA_REMINDER_ID, -1)
        if (reminderId <= 0) return
        val pendingResult = goAsync()
        CoroutineScope(Dispatchers.IO).launch {
            try {
                val db = AppDatabase.get(context)
                val cached = db.reminderDao().byId(reminderId) ?: return@launch
                if (cached.state in TERMINAL_STATES) return@launch
                val quiet = cached.priority != "urgent" &&
                    SettingsManager.get(context).isQuietNow()
                NotificationHelper.notifyReminder(
                    context,
                    cached.id,
                    cached.title,
                    cached.body,
                    cached.priority,
                    quiet,
                )
            } finally {
                pendingResult.finish()
            }
        }
    }
}
