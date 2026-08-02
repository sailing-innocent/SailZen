package com.sailzen.app.core.reminder

import android.Manifest
import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.os.Build
import androidx.core.app.NotificationCompat
import androidx.core.app.NotificationManagerCompat
import androidx.core.content.ContextCompat
import com.sailzen.app.MainActivity
import com.sailzen.app.R

/**
 * 通知构建器（设计文档 §6.2 / 附录 C）。
 *
 * 渠道：urgent（强提醒）/ reminder（常规）/ silent（安静时段非 urgent）/ service（常驻）。
 * 三动作：处理 / 延后 / 忽略；"完成"动作在 Inbox 卡片内提供（M1 约定）。
 */
object NotificationHelper {

    const val CHANNEL_URGENT = "urgent"
    const val CHANNEL_REMINDER = "reminder"
    const val CHANNEL_SILENT = "silent"
    const val CHANNEL_SERVICE = "service"

    const val SERVICE_NOTIFICATION_ID = 1

    fun createChannels(context: Context) {
        val manager = context.getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
        manager.createNotificationChannels(
            listOf(
                NotificationChannel(
                    CHANNEL_URGENT,
                    context.getString(R.string.channel_urgent_name),
                    NotificationManager.IMPORTANCE_HIGH,
                ).apply {
                    description = context.getString(R.string.channel_urgent_desc)
                    enableVibration(true)
                },
                NotificationChannel(
                    CHANNEL_REMINDER,
                    context.getString(R.string.channel_reminder_name),
                    NotificationManager.IMPORTANCE_DEFAULT,
                ).apply {
                    description = context.getString(R.string.channel_reminder_desc)
                },
                NotificationChannel(
                    CHANNEL_SILENT,
                    context.getString(R.string.channel_silent_name),
                    NotificationManager.IMPORTANCE_LOW,
                ).apply {
                    description = context.getString(R.string.channel_silent_desc)
                },
                NotificationChannel(
                    CHANNEL_SERVICE,
                    context.getString(R.string.channel_service_name),
                    NotificationManager.IMPORTANCE_MIN,
                ).apply {
                    description = context.getString(R.string.channel_service_desc)
                    setShowBadge(false)
                },
            )
        )
    }

    /**
     * 弹出提醒通知。
     * @param isQuiet 当前处于安静时段（仅影响非 urgent 的渠道选择）
     */
    fun notifyReminder(
        context: Context,
        reminderId: Int,
        title: String,
        body: String,
        priority: String,
        isQuiet: Boolean,
    ) {
        if (Build.VERSION.SDK_INT >= 33 &&
            ContextCompat.checkSelfPermission(context, Manifest.permission.POST_NOTIFICATIONS) !=
            PackageManager.PERMISSION_GRANTED
        ) {
            return
        }
        val channel = when {
            priority == "urgent" -> CHANNEL_URGENT
            isQuiet -> CHANNEL_SILENT
            else -> CHANNEL_REMINDER
        }
        val notification = buildReminderNotification(context, channel, reminderId, title, body)
        NotificationManagerCompat.from(context).notify(reminderId, notification)
    }

    private fun buildReminderNotification(
        context: Context,
        channel: String,
        reminderId: Int,
        title: String,
        body: String,
    ): Notification {
        // 点击通知本体 = 处理（打开 App 并定位该提醒）
        val contentIntent = PendingIntent.getActivity(
            context,
            reminderId,
            Intent(context, MainActivity::class.java)
                .putExtra(ReminderActionReceiver.EXTRA_REMINDER_ID, reminderId),
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE,
        )

        fun actionIntent(action: String, offset: Int): PendingIntent =
            PendingIntent.getBroadcast(
                context,
                reminderId * 8 + offset,
                Intent(context, ReminderActionReceiver::class.java)
                    .setAction(action)
                    .putExtra(ReminderActionReceiver.EXTRA_REMINDER_ID, reminderId),
                PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE,
            )

        return NotificationCompat.Builder(context, channel)
            .setSmallIcon(R.drawable.ic_notification)
            .setContentTitle(title)
            .setContentText(body)
            .setStyle(NotificationCompat.BigTextStyle().bigText(body))
            .setContentIntent(contentIntent)
            .setAutoCancel(true)
            .setCategory(NotificationCompat.CATEGORY_REMINDER)
            .setVisibility(NotificationCompat.VISIBILITY_PUBLIC)
            .addAction(
                0,
                context.getString(R.string.action_handle),
                actionIntent(ReminderActionReceiver.ACTION_HANDLE, 1),
            )
            .addAction(
                0,
                context.getString(R.string.action_snooze),
                actionIntent(ReminderActionReceiver.ACTION_SNOOZE, 2),
            )
            .addAction(
                0,
                context.getString(R.string.action_dismiss),
                actionIntent(ReminderActionReceiver.ACTION_DISMISS, 3),
            )
            .build()
    }

    /** 前台服务常驻通知（今日待办数） */
    fun buildServiceNotification(context: Context, pendingCount: Int): Notification {
        val contentIntent = PendingIntent.getActivity(
            context,
            0,
            Intent(context, MainActivity::class.java),
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE,
        )
        return NotificationCompat.Builder(context, CHANNEL_SERVICE)
            .setSmallIcon(R.drawable.ic_notification)
            .setContentTitle(context.getString(R.string.service_notification_title))
            .setContentText(context.getString(R.string.service_notification_text, pendingCount))
            .setContentIntent(contentIntent)
            .setOngoing(true)
            .setShowWhen(false)
            .build()
    }

    fun cancel(context: Context, reminderId: Int) {
        NotificationManagerCompat.from(context).cancel(reminderId)
    }
}
