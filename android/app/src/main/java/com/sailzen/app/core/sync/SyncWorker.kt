package com.sailzen.app.core.sync

import android.content.Context
import androidx.work.Constraints
import androidx.work.CoroutineWorker
import androidx.work.ExistingPeriodicWorkPolicy
import androidx.work.NetworkType
import androidx.work.PeriodicWorkRequestBuilder
import androidx.work.WorkManager
import androidx.work.WorkerParameters
import com.sailzen.app.core.reminder.ReminderRepository
import java.util.concurrent.TimeUnit

/**
 * WorkManager 周期补偿（设计文档通道 2，最小间隔 15min，联网约束）：
 * 拉取 /pending 对账缓存 + 冲刷离线反馈队列。
 */
class SyncWorker(
    context: Context,
    params: WorkerParameters,
) : CoroutineWorker(context, params) {

    companion object {
        private const val WORK_NAME = "sailzen_reminder_sync"

        fun enqueue(context: Context) {
            val constraints = Constraints.Builder()
                .setRequiredNetworkType(NetworkType.CONNECTED)
                .build()
            val request = PeriodicWorkRequestBuilder<SyncWorker>(15, TimeUnit.MINUTES)
                .setConstraints(constraints)
                .build()
            WorkManager.getInstance(context).enqueueUniquePeriodicWork(
                WORK_NAME,
                ExistingPeriodicWorkPolicy.UPDATE,
                request,
            )
        }
    }

    override suspend fun doWork(): Result {
        return try {
            val repository = ReminderRepository.get(applicationContext)
            if (!repository.serverConfigured()) {
                Result.success()
            } else {
                repository.syncPending()
                repository.flushPendingFeedback()
                Result.success()
            }
        } catch (e: Exception) {
            Result.retry()
        }
    }
}
