-- -*- coding: utf-8 -*-
-- @file 20261121_add_mission_pems_columns.sql
-- @brief 补齐 missions 表 PEMS 相关列
-- @author sailing-innocent
-- @date 2026-11-21
-- @version 1.0
-- ---------------------------------

-- 该迁移为幂等：列/索引已存在时跳过。
-- 仅添加列和索引，不添加外键约束，避免旧数据违反引用完整性导致失败。

ALTER TABLE missions
    ADD COLUMN IF NOT EXISTS planned_minutes INTEGER DEFAULT 0,
    ADD COLUMN IF NOT EXISTS actual_minutes  INTEGER DEFAULT 0,
    ADD COLUMN IF NOT EXISTS energy_cost     INTEGER DEFAULT 0,
    ADD COLUMN IF NOT EXISTS day_id          INTEGER,
    ADD COLUMN IF NOT EXISTS milestone_id    INTEGER,
    ADD COLUMN IF NOT EXISTS health_constraint VARCHAR DEFAULT 'normal';

CREATE INDEX IF NOT EXISTS ix_missions_day_id
    ON missions (day_id);

CREATE INDEX IF NOT EXISTS ix_missions_milestone_id
    ON missions (milestone_id);
