package com.sailzen.app.core.data.db

import android.content.Context
import androidx.room.Database
import androidx.room.Room
import androidx.room.RoomDatabase

@Database(
    entities = [
        CachedReminder::class,
        PendingFeedback::class,
        PendingRhythmAction::class,
        CachedSourceConfig::class,
        CachedWork::class,
        CachedChapter::class,
        ReadingProgress::class,
        CachedAnnotation::class,
    ],
    version = 4,
    exportSchema = false,
)
abstract class AppDatabase : RoomDatabase() {

    abstract fun reminderDao(): ReminderDao

    abstract fun feedbackDao(): FeedbackDao

    abstract fun rhythmActionDao(): RhythmActionDao

    abstract fun sourceConfigDao(): SourceConfigDao

    abstract fun readerDao(): ReaderDao

    companion object {
        @Volatile
        private var instance: AppDatabase? = null

        fun get(context: Context): AppDatabase =
            instance ?: synchronized(this) {
                instance ?: Room.databaseBuilder(
                    context.applicationContext,
                    AppDatabase::class.java,
                    "sailzen.db",
                )
                    // 本地仅为缓存与离线队列（Server 是唯一事实源），升级允许重建
                    .fallbackToDestructiveMigration()
                    .build().also { instance = it }
            }
    }
}
