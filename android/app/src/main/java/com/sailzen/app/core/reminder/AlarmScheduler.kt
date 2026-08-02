package com.sailzen.app.core.reminder

import android.app.AlarmManager
import android.app.PendingIntent
import android.content.Context
import android.content.Intent
import android.os.Build
import android.util.Log

/**
 * AlarmManager 本地兜底闹钟（设计文档通道 3）：
 * 同步到缓存的未来 PENDING 提醒一律排本地闹钟，断网/杀进程仍准时弹出。
 */
object AlarmScheduler {

    private const val TAG = "AlarmScheduler"

    fun schedule(context: Context, reminderId: Int, triggerAtMillis: Long) {
        val alarmManager = context.getSystemService(Context.ALARM_SERVICE) as AlarmManager
        val pendingIntent = buildPendingIntent(context, reminderId)
        try {
            if (canScheduleExact(context)) {
                alarmManager.setExactAndAllowWhileIdle(
                    AlarmManager.RTC_WAKEUP,
                    triggerAtMillis,
                    pendingIntent,
                )
            } else {
                // API 31+ 未授权 exact alarm 时降级为 inexact（系统可批处理延迟）
                alarmManager.setAndAllowWhileIdle(
                    AlarmManager.RTC_WAKEUP,
                    triggerAtMillis,
                    pendingIntent,
                )
                Log.w(TAG, "exact alarm not allowed, fallback to inexact")
            }
        } catch (e: SecurityException) {
            Log.w(TAG, "schedule alarm denied: ${e.message}")
            alarmManager.setAndAllowWhileIdle(
                AlarmManager.RTC_WAKEUP,
                triggerAtMillis,
                pendingIntent,
            )
        }
    }

    fun cancel(context: Context, reminderId: Int) {
        val alarmManager = context.getSystemService(Context.ALARM_SERVICE) as AlarmManager
        alarmManager.cancel(buildPendingIntent(context, reminderId))
    }

    fun canScheduleExact(context: Context): Boolean {
        if (Build.VERSION.SDK_INT < 31) return true
        val alarmManager = context.getSystemService(Context.ALARM_SERVICE) as AlarmManager
        return alarmManager.canScheduleExactAlarms()
    }

    private fun buildPendingIntent(context: Context, reminderId: Int): PendingIntent =
        PendingIntent.getBroadcast(
            context,
            reminderId,
            Intent(context, AlarmReceiver::class.java)
                .putExtra(ReminderActionReceiver.EXTRA_REMINDER_ID, reminderId),
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE,
        )
}
