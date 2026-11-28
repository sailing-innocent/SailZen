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
import com.sailzen.app.core.health.HealthAlarmActionReceiver
import com.sailzen.app.core.data.SettingsManager
import com.sailzen.app.core.data.db.CachedSourceConfig

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

    const val CHANNEL_HEALTH = "health"
    const val CHANNEL_AFFAIR = "affair"
    const val CHANNEL_SAILTICK_HEALTH = "sailtick_health"
    const val CHANNEL_SAILTICK_RHYTHM = "sailtick_rhythm"
    const val CHANNEL_SAILTICK_FINANCE = "sailtick_finance"
    const val CHANNEL_SAILTICK_DIGEST = "sailtick_digest"

    const val SERVICE_NOTIFICATION_ID = 1
    const val AFFAIR_NOTIFICATION_ID_OFFSET = 10_000

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
                    CHANNEL_HEALTH,
                    context.getString(R.string.channel_health_name),
                    NotificationManager.IMPORTANCE_DEFAULT,
                ).apply {
                    description = context.getString(R.string.channel_health_desc)
                },
                NotificationChannel(
                    CHANNEL_AFFAIR,
                    context.getString(R.string.channel_affair_name),
                    NotificationManager.IMPORTANCE_DEFAULT,
                ).apply {
                    description = context.getString(R.string.channel_affair_desc)
                },
                NotificationChannel(
                    CHANNEL_SAILTICK_HEALTH,
                    "健康教练",
                    NotificationManager.IMPORTANCE_DEFAULT,
                ).apply {
                    description = "SailTick 健康教练提问、饮食/称重提醒"
                },
                NotificationChannel(
                    CHANNEL_SAILTICK_RHYTHM,
                    "节奏规划师",
                    NotificationManager.IMPORTANCE_DEFAULT,
                ).apply {
                    description = "SailTick 日程排期、项目倒排与时间块提醒"
                },
                NotificationChannel(
                    CHANNEL_SAILTICK_FINANCE,
                    "财务秘书",
                    NotificationManager.IMPORTANCE_DEFAULT,
                ).apply {
                    description = "SailTick 账单清理、余额核对与消费提醒"
                },
                NotificationChannel(
                    CHANNEL_SAILTICK_DIGEST,
                    "每日总览",
                    NotificationManager.IMPORTANCE_LOW,
                ).apply {
                    description = "SailTick 睡前今日生活总览（低打扰）"
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
     * @param source 提醒来源，用于匹配来源配置
     * @param sourceConfig 服务端来源配置缓存（为空时使用默认规则）
     * @param domain 规范业务域（health|rhythm|finance|general）
     * @param deepLink 点击通知后的直达深链（如 /rhythm、/money、/health/coach）
     */
    fun notifyReminder(
        context: Context,
        reminderId: Int,
        title: String,
        body: String,
        priority: String,
        isQuiet: Boolean,
        source: String = "",
        sourceConfig: CachedSourceConfig? = null,
        domain: String = "",
        deepLink: String = "",
    ) {
        if (Build.VERSION.SDK_INT >= 33 &&
            ContextCompat.checkSelfPermission(context, Manifest.permission.POST_NOTIFICATIONS) !=
            PackageManager.PERMISSION_GRANTED
        ) {
            return
        }
        val settings = SettingsManager.get(context)
        val decision = NotificationDecisionEngine(settings).decide(sourceConfig, priority, isQuiet, source)
        val resolvedChannel = when {
            decision.channelId == CHANNEL_URGENT || decision.channelId == CHANNEL_SILENT -> decision.channelId
            deepLink.contains("report") || title.contains("今日总览") || title.contains("睡前") -> CHANNEL_SAILTICK_DIGEST
            domain == "health" -> CHANNEL_SAILTICK_HEALTH
            domain == "rhythm" -> CHANNEL_SAILTICK_RHYTHM
            domain == "finance" -> CHANNEL_SAILTICK_FINANCE
            else -> decision.channelId
        }
        ensureChannel(context, resolvedChannel, decision.importance)
        if (!decision.shouldNotify && !decision.useAlarm) {
            return
        }
        val notification = buildReminderNotification(
            context,
            resolvedChannel,
            reminderId,
            title,
            body,
            decision.useFullScreenIntent,
            domain = domain,
            deepLink = deepLink,
        )
        NotificationManagerCompat.from(context).notify(reminderId, notification)
    }

    private fun ensureChannel(context: Context, channelId: String, importance: Int) {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.O) return
        val manager = context.getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
        if (manager.getNotificationChannel(channelId) != null) return
        val (name, description) = when (channelId) {
            CHANNEL_URGENT -> context.getString(R.string.channel_urgent_name) to context.getString(
                R.string.channel_urgent_desc
            )
            CHANNEL_REMINDER -> context.getString(R.string.channel_reminder_name) to context.getString(
                R.string.channel_reminder_desc
            )
            CHANNEL_SILENT -> context.getString(R.string.channel_silent_name) to context.getString(
                R.string.channel_silent_desc
            )
            CHANNEL_SAILTICK_HEALTH -> "健康教练" to "SailTick 健康教练提问、饮食/称重提醒"
            CHANNEL_SAILTICK_RHYTHM -> "节奏规划师" to "SailTick 日程排期、项目倒排与时间块提醒"
            CHANNEL_SAILTICK_FINANCE -> "财务秘书" to "SailTick 账单清理、余额核对与消费提醒"
            CHANNEL_SAILTICK_DIGEST -> "每日总览" to "SailTick 睡前今日生活总览（低打扰）"
            CHANNEL_SERVICE -> context.getString(R.string.channel_service_name) to context.getString(
                R.string.channel_service_desc
            )
            else -> channelId to ""
        }
        manager.createNotificationChannel(
            NotificationChannel(channelId, name, importance).apply {
                this.description = description
            }
        )
    }

    private fun buildReminderNotification(
        context: Context,
        channel: String,
        reminderId: Int,
        title: String,
        body: String,
        useFullScreen: Boolean = false,
        domain: String = "",
        deepLink: String = "",
    ): Notification {
        // 点击通知本体 = 处理（打开 App 并按 deepLink / domain 路由至对应业务页）
        val contentIntent = PendingIntent.getActivity(
            context,
            reminderId,
            Intent(context, MainActivity::class.java)
                .putExtra(ReminderActionReceiver.EXTRA_REMINDER_ID, reminderId)
                .putExtra(ReminderActionReceiver.EXTRA_DOMAIN, domain)
                .putExtra(ReminderActionReceiver.EXTRA_DEEP_LINK, deepLink),
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE,
        )

        fun actionIntent(action: String, offset: Int): PendingIntent =
            PendingIntent.getBroadcast(
                context,
                reminderId * 8 + offset,
                Intent(context, ReminderActionReceiver::class.java)
                    .setAction(action)
                    .putExtra(ReminderActionReceiver.EXTRA_REMINDER_ID, reminderId)
                    .putExtra(ReminderActionReceiver.EXTRA_DOMAIN, domain)
                    .putExtra(ReminderActionReceiver.EXTRA_DEEP_LINK, deepLink),
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

    /**
     * 用药提醒通知。
     */
    fun notifyMedication(context: Context, medicationId: Int, name: String) {
        if (Build.VERSION.SDK_INT >= 33 &&
            ContextCompat.checkSelfPermission(context, Manifest.permission.POST_NOTIFICATIONS) !=
            PackageManager.PERMISSION_GRANTED
        ) {
            return
        }
        val contentIntent = PendingIntent.getActivity(
            context,
            medicationId,
            Intent(context, com.sailzen.app.MainActivity::class.java),
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE,
        )
        val takeIntent = PendingIntent.getBroadcast(
            context,
            medicationId,
            Intent(context, HealthAlarmActionReceiver::class.java)
                .setAction(HealthAlarmActionReceiver.ACTION_TAKE_MEDICATION)
                .putExtra(HealthAlarmActionReceiver.EXTRA_MEDICATION_ID, medicationId),
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE,
        )
        val notification = NotificationCompat.Builder(context, CHANNEL_HEALTH)
            .setSmallIcon(R.drawable.ic_notification)
            .setContentTitle("用药提醒")
            .setContentText("记得服用 $name")
            .setAutoCancel(true)
            .setContentIntent(contentIntent)
            .addAction(0, context.getString(R.string.health_taken), takeIntent)
            .build()
        NotificationManagerCompat.from(context).notify(medicationId, notification)
    }

    /**
     * 作息提醒通知。
     */
    fun notifySleep(context: Context, isBedtime: Boolean) {
        if (Build.VERSION.SDK_INT >= 33 &&
            ContextCompat.checkSelfPermission(context, Manifest.permission.POST_NOTIFICATIONS) !=
            PackageManager.PERMISSION_GRANTED
        ) {
            return
        }
        val contentIntent = PendingIntent.getActivity(
            context,
            0,
            Intent(context, com.sailzen.app.MainActivity::class.java),
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE,
        )
        val title = if (isBedtime) "就寝提醒" else "起床提醒"
        val text = if (isBedtime) "该准备睡觉了" else "该起床了"
        val notification = NotificationCompat.Builder(context, CHANNEL_HEALTH)
            .setSmallIcon(R.drawable.ic_notification)
            .setContentTitle(title)
            .setContentText(text)
            .setAutoCancel(true)
            .setContentIntent(contentIntent)
            .build()
        NotificationManagerCompat.from(context).notify(if (isBedtime) 2001 else 2002, notification)
    }

    /**
     * 事务逾期/临近提醒通知。
     */
    fun notifyAffairReminder(
        context: Context,
        affairId: Int,
        title: String,
        body: String,
        isOverdue: Boolean,
    ) {
        if (Build.VERSION.SDK_INT >= 33 &&
            ContextCompat.checkSelfPermission(context, Manifest.permission.POST_NOTIFICATIONS) !=
            PackageManager.PERMISSION_GRANTED
        ) {
            return
        }
        val notificationId = AFFAIR_NOTIFICATION_ID_OFFSET + affairId
        val channel = if (isOverdue) CHANNEL_URGENT else CHANNEL_AFFAIR
        val contentIntent = PendingIntent.getActivity(
            context,
            notificationId,
            Intent(context, MainActivity::class.java)
                .putExtra(ReminderActionReceiver.EXTRA_AFFAIR_ID, affairId),
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE,
        )
        val notification = NotificationCompat.Builder(context, channel)
            .setSmallIcon(R.drawable.ic_notification)
            .setContentTitle(title)
            .setContentText(body)
            .setStyle(NotificationCompat.BigTextStyle().bigText(body))
            .setContentIntent(contentIntent)
            .setAutoCancel(true)
            .setCategory(NotificationCompat.CATEGORY_REMINDER)
            .setVisibility(NotificationCompat.VISIBILITY_PUBLIC)
            .build()
        NotificationManagerCompat.from(context).notify(notificationId, notification)
    }

    /** 前台服务常驻通知（今日待办数） */
    fun buildServiceNotification(
        context: Context,
        pendingCount: Int,
        connected: Boolean = false,
    ): Notification {
        val contentIntent = PendingIntent.getActivity(
            context,
            0,
            Intent(context, MainActivity::class.java),
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE,
        )
        val statusText = if (connected) {
            context.getString(R.string.service_status_connected)
        } else {
            context.getString(R.string.service_status_reconnecting)
        }
        return NotificationCompat.Builder(context, CHANNEL_SERVICE)
            .setSmallIcon(R.drawable.ic_notification)
            .setContentTitle(context.getString(R.string.service_notification_title))
            .setContentText(
                context.getString(
                    R.string.service_notification_text,
                    pendingCount,
                    statusText,
                )
            )
            .setContentIntent(contentIntent)
            .setOngoing(true)
            .setShowWhen(false)
            .build()
    }

    fun cancel(context: Context, reminderId: Int) {
        NotificationManagerCompat.from(context).cancel(reminderId)
    }
}
