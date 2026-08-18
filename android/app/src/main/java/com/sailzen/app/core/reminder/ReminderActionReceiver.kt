package com.sailzen.app.core.reminder

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import com.sailzen.app.MainActivity
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch

/**
 * 通知三动作路由：
 * - 处理 (HANDLE)：上报 open + 拉起 MainActivity（Inbox 高亮该卡）
 * - 延后 (SNOOZE)：打开 SnoozeDialogActivity 二级选项
 * - 忽略 (DISMISS)：上报 dismiss + 取消通知
 */
class ReminderActionReceiver : BroadcastReceiver() {

    companion object {
        const val ACTION_HANDLE = "com.sailzen.app.action.HANDLE"
        const val ACTION_SNOOZE = "com.sailzen.app.action.SNOOZE"
        const val ACTION_DISMISS = "com.sailzen.app.action.DISMISS"
        const val EXTRA_REMINDER_ID = "reminder_id"
        const val EXTRA_MISSION_ID = "mission_id"
        const val EXTRA_PROJECT_ID = "project_id"
        const val EXTRA_DESTINATION = "destination"
        const val DESTINATION_MISSION_BOARD = "mission_board"
        const val DESTINATION_MISSION_DETAIL = "mission_detail"
    }

    override fun onReceive(context: Context, intent: Intent) {
        val reminderId = intent.getIntExtra(EXTRA_REMINDER_ID, -1)
        if (reminderId <= 0) return
        val repository = ReminderRepository.get(context)

        when (intent.action) {
            ACTION_HANDLE -> {
                NotificationHelper.cancel(context, reminderId)
                launchAsync { repository.sendFeedback(reminderId, "open") }
                val launch = Intent(context, MainActivity::class.java)
                    .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
                    .putExtra(EXTRA_REMINDER_ID, reminderId)
                context.startActivity(launch)
            }

            ACTION_SNOOZE -> {
                val launch = Intent(context, SnoozeDialogActivity::class.java)
                    .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
                    .putExtra(EXTRA_REMINDER_ID, reminderId)
                context.startActivity(launch)
            }

            ACTION_DISMISS -> {
                NotificationHelper.cancel(context, reminderId)
                launchAsync { repository.sendFeedback(reminderId, "dismiss") }
            }
        }
    }

    private fun BroadcastReceiver.launchAsync(block: suspend () -> Unit) {
        val pendingResult = goAsync()
        CoroutineScope(Dispatchers.IO).launch {
            try {
                block()
            } finally {
                pendingResult.finish()
            }
        }
    }
}
