package com.sailzen.app.core.health

import android.app.AlarmManager
import android.app.PendingIntent
import android.content.Context
import android.content.Intent
import android.os.Build
import android.util.Log
import com.sailzen.app.core.network.dto.MedicationDto
import com.sailzen.app.core.network.dto.SleepScheduleGoalDto
import java.time.LocalDate
import java.time.LocalDateTime
import java.time.LocalTime
import java.time.ZoneId

/**
 * 本地用药/作息提醒调度器。
 * M1：为未服用且时间未到的用药计划设置 AlarmManager；为作息目标设置就寝/起床提醒。
 */
object HealthAlarmScheduler {

    private const val TAG = "HealthAlarmScheduler"
    private const val ACTION_MEDICATION = "com.sailzen.app.ACTION_MEDICATION_ALARM"
    private const val ACTION_BEDTIME = "com.sailzen.app.ACTION_BEDTIME_ALARM"
    private const val ACTION_WAKEUP = "com.sailzen.app.ACTION_WAKEUP_ALARM"

    private const val EXTRA_MEDICATION_ID = "medication_id"
    private const val EXTRA_MEDICATION_NAME = "medication_name"

    fun scheduleMedications(context: Context, medications: List<MedicationDto>) {
        val alarmManager = context.getSystemService(Context.ALARM_SERVICE) as AlarmManager
        val today = LocalDate.now()
        medications.filter { !it.taken && it.plannedDate == today.toString() }.forEach { med ->
            med.scheduleTimes.forEachIndexed { index, timeStr ->
                val time = parseTime(timeStr) ?: return@forEachIndexed
                val trigger = LocalDateTime.of(today, time).atZone(ZoneId.systemDefault()).toEpochSecond() * 1000
                if (trigger <= System.currentTimeMillis()) return@forEachIndexed
                val requestCode = med.id * 10 + index
                val intent = Intent(context, com.sailzen.app.core.reminder.AlarmReceiver::class.java).apply {
                    action = ACTION_MEDICATION
                    putExtra(EXTRA_MEDICATION_ID, med.id)
                    putExtra(EXTRA_MEDICATION_NAME, med.name)
                }
                val pending = PendingIntent.getBroadcast(
                    context,
                    requestCode,
                    intent,
                    PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE,
                )
                try {
                    if (Build.VERSION.SDK_INT >= 31 && !alarmManager.canScheduleExactAlarms()) {
                        alarmManager.setAndAllowWhileIdle(AlarmManager.RTC_WAKEUP, trigger, pending)
                    } else {
                        alarmManager.setExactAndAllowWhileIdle(AlarmManager.RTC_WAKEUP, trigger, pending)
                    }
                } catch (e: SecurityException) {
                    Log.w(TAG, "schedule medication alarm denied: ${e.message}")
                    alarmManager.setAndAllowWhileIdle(AlarmManager.RTC_WAKEUP, trigger, pending)
                }
            }
        }
    }

    fun scheduleSleep(context: Context, goal: SleepScheduleGoalDto?) {
        if (goal == null) return
        val alarmManager = context.getSystemService(Context.ALARM_SERVICE) as AlarmManager
        val today = LocalDate.now()
        scheduleSingle(context, alarmManager, ACTION_BEDTIME, goal.bedTime, -1001, today)
        scheduleSingle(context, alarmManager, ACTION_WAKEUP, goal.wakeTime, -1002, today)
    }

    private fun scheduleSingle(
        context: Context,
        alarmManager: AlarmManager,
        action: String,
        timeStr: String,
        requestCode: Int,
        date: LocalDate,
    ) {
        val time = parseTime(timeStr) ?: return
        val trigger = LocalDateTime.of(date, time).atZone(ZoneId.systemDefault()).toEpochSecond() * 1000
        if (trigger <= System.currentTimeMillis()) return
        val intent = Intent(context, com.sailzen.app.core.reminder.AlarmReceiver::class.java).apply {
            this.action = action
        }
        val pending = PendingIntent.getBroadcast(
            context,
            requestCode,
            intent,
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE,
        )
        try {
            if (Build.VERSION.SDK_INT >= 31 && !alarmManager.canScheduleExactAlarms()) {
                alarmManager.setAndAllowWhileIdle(AlarmManager.RTC_WAKEUP, trigger, pending)
            } else {
                alarmManager.setExactAndAllowWhileIdle(AlarmManager.RTC_WAKEUP, trigger, pending)
            }
        } catch (e: SecurityException) {
            Log.w(TAG, "schedule sleep alarm denied: ${e.message}")
            alarmManager.setAndAllowWhileIdle(AlarmManager.RTC_WAKEUP, trigger, pending)
        }
    }

    private fun parseTime(timeStr: String): LocalTime? = try {
        LocalTime.parse(timeStr)
    } catch (e: Exception) {
        Log.w(TAG, "invalid time $timeStr")
        null
    }

    fun isMedicationAction(action: String?) = action == ACTION_MEDICATION
    fun isBedtimeAction(action: String?) = action == ACTION_BEDTIME
    fun isWakeAction(action: String?) = action == ACTION_WAKEUP
    fun medicationId(intent: Intent): Int = intent.getIntExtra(EXTRA_MEDICATION_ID, -1)
    fun medicationName(intent: Intent): String? = intent.getStringExtra(EXTRA_MEDICATION_NAME)
}
