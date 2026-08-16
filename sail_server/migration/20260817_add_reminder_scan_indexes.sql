-- Migration: 添加提醒调度器扫描索引
-- Date: 2026-08-17
-- Author: sailing-innocent
-- Description: 为 reminders 表增加复合索引，避免调度器扫描时全表遍历/加载全部历史 DELIVERED 行，
--              解决启动阻塞与 Android 重连延迟问题。

CREATE INDEX IF NOT EXISTS ix_reminders_state_trigger_time
    ON reminders (state, trigger_time);

CREATE INDEX IF NOT EXISTS ix_reminders_state_next_trigger_time
    ON reminders (state, next_trigger_time);

CREATE INDEX IF NOT EXISTS ix_reminders_state_updated_at
    ON reminders (state, updated_at);

CREATE INDEX IF NOT EXISTS ix_reminders_state_last_delivered_at
    ON reminders (state, last_delivered_at);
