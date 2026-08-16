package com.sailzen.app.core.health

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import com.sailzen.app.core.reminder.NotificationHelper
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch

/**
 * 健康闹钟通知动作：「已服用」直接上报服务端并写本地记录。
 */
class HealthAlarmActionReceiver : BroadcastReceiver() {

    companion object {
        const val ACTION_TAKE_MEDICATION = "com.sailzen.app.ACTION_TAKE_MEDICATION"
        const val EXTRA_MEDICATION_ID = "medication_id"
    }

    override fun onReceive(context: Context, intent: Intent) {
        val pendingResult = goAsync()
        CoroutineScope(Dispatchers.IO).launch {
            try {
                when (intent.action) {
                    ACTION_TAKE_MEDICATION -> {
                        val id = intent.getIntExtra(EXTRA_MEDICATION_ID, -1)
                        if (id > 0) {
                            HealthRepository.get(context).takeMedication(id)
                            NotificationHelper.cancel(context, id)
                        }
                    }
                }
            } finally {
                pendingResult.finish()
            }
        }
    }
}
