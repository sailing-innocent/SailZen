-- Migration: 扩展 weight_plans 表，支持起始体重、目标曲线、Rhythm 提醒与反馈联动
-- Date: 2026-11-15
-- Author: sailing-innocent
-- Description: 为体重计划增加 initial_weight/curve_type/notify_enabled/notify_time/rhythm_affair_id/feedback_enabled 字段。
--              全部使用 ADD COLUMN IF NOT EXISTS，幂等可安全重复执行。

ALTER TABLE weight_plans
    ADD COLUMN IF NOT EXISTS initial_weight VARCHAR,
    ADD COLUMN IF NOT EXISTS curve_type VARCHAR DEFAULT 'linear',
    ADD COLUMN IF NOT EXISTS notify_enabled BOOLEAN DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS notify_time VARCHAR DEFAULT '08:30',
    ADD COLUMN IF NOT EXISTS rhythm_affair_id INTEGER REFERENCES rhythm_affairs(id),
    ADD COLUMN IF NOT EXISTS feedback_enabled BOOLEAN DEFAULT FALSE;

CREATE INDEX IF NOT EXISTS idx_weight_plans_rhythm_affair_id ON weight_plans(rhythm_affair_id);
