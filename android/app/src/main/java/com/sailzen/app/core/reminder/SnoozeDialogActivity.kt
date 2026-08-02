package com.sailzen.app.core.reminder

import android.app.AlertDialog
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.lifecycle.lifecycleScope
import com.sailzen.app.R
import kotlinx.coroutines.launch

/**
 * 延后二级选项弹窗（透明 Dialog Activity，无需打开 App 主界面）。
 * 选项与服务端 snooze option 契约一一对应：15m / 1h / tonight / tomorrow。
 */
class SnoozeDialogActivity : ComponentActivity() {

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)

        val reminderId = intent.getIntExtra(ReminderActionReceiver.EXTRA_REMINDER_ID, -1)
        if (reminderId <= 0) {
            finish()
            return
        }

        val labels = arrayOf(
            getString(R.string.snooze_15m),
            getString(R.string.snooze_1h),
            getString(R.string.snooze_tonight),
            getString(R.string.snooze_tomorrow),
        )
        val options = arrayOf("15m", "1h", "tonight", "tomorrow")

        AlertDialog.Builder(this)
            .setTitle(getString(R.string.snooze_dialog_title))
            .setItems(labels) { _, which ->
                val option = options[which]
                lifecycleScope.launch {
                    ReminderRepository.get(applicationContext)
                        .sendFeedback(reminderId, "snooze", option)
                }
                finish()
            }
            .setOnCancelListener { finish() }
            .show()
    }
}
