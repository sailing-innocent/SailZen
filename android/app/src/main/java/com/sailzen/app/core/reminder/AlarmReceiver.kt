package com.sailzen.app.core.reminder

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import com.sailzen.app.core.data.SettingsManager
import com.sailzen.app.core.data.db.AppDatabase
import com.sailzen.app.core.health.HealthAlarmScheduler
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch

/**
 * 本地闹钟触发：
 * - 提醒兜底：从 Room 读缓存直接弹通知（断网兜底）。
 * - 健康提醒：用药/作息本地闹钟直接弹通知。
 * 已终结（RESOLVED/IGNORED/CANCELED/ARCHIVED）的提醒不再弹出。
 */
class AlarmReceiver : BroadcastReceiver() {

    companion object {
        private val TERMINAL_STATES = setOf("RESOLVED", "IGNORED", "CANCELED", "ARCHIVED")
    }

    override fun onReceive(context: Context, intent: Intent) {
        val pendingResult = goAsync()
        CoroutineScope(Dispatchers.IO).launch {
            try {
                when {
                    HealthAlarmScheduler.isMedicationAction(intent.action) -> {
                        val id = HealthAlarmScheduler.medicationId(intent)
                        val name = HealthAlarmScheduler.medicationName(intent) ?: "用药"
                        NotificationHelper.notifyMedication(context, id, name)
                    }
                    HealthAlarmScheduler.isBedtimeAction(intent.action) -> {
                        NotificationHelper.notifySleep(context, isBedtime = true)
                    }
                    HealthAlarmScheduler.isWakeAction(intent.action) -> {
                        NotificationHelper.notifySleep(context, isBedtime = false)
                    }
                    else -> handleReminder(context, intent)
                }
            } finally {
                pendingResult.finish()
            }
        }
    }

    private suspend fun handleReminder(context: Context, intent: Intent) {
        val reminderId = intent.getIntExtra(ReminderActionReceiver.EXTRA_REMINDER_ID, -1)
        if (reminderId <= 0) return
        val db = AppDatabase.get(context)
        val cached = db.reminderDao().byId(reminderId) ?: return
        if (cached.state in TERMINAL_STATES) return
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
    }
}
