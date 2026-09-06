-- -*- coding: utf-8 -*-
-- @file 20260906_add_rhythm_profile_v2.sql
-- @brief rhythm_energy_profiles 补 v2 排程配置四列（work_windows /
--   morning_health_window / career_buffer_minutes / work_gap_minutes）
-- @author sailing-innocent
-- @date 2026-09-06
-- @version 1.0
-- ---------------------------------
-- 背景：
--   排程器 v2（plan_day Step 2.5/7a/7b）新增四类画像级配置：
--     1) work_windows           有效工作窗（排程权威，优先于模板 work_window 槽位）
--     2) morning_health_window  早间健康窗（健康类 habit 第一候选窗）
--     3) career_buffer_minutes  事业块与睡眠开始的缓冲分钟数（默认 45）
--     4) work_gap_minutes       同片段相邻 focus 块最小间隔（默认 15）
--   create_all 不会给已存在的表补列，因此需要本迁移。
--   存量数据直接采用列默认值（DEFAULT 子句即默认配置），无需额外回填。
--
-- 注意：脚本经 psycopg 执行，全文件禁止出现百分号占位符。
-- 本脚本全部语句幂等（ADD COLUMN IF NOT EXISTS），反复执行均为安全空操作。
-- ---------------------------------------------------------------------------

ALTER TABLE rhythm_energy_profiles
    ADD COLUMN IF NOT EXISTS work_windows JSONB NOT NULL
    DEFAULT '{"weekday": [["10:00","13:00"],["14:00","19:00"]], "weekend": []}'::jsonb;

ALTER TABLE rhythm_energy_profiles
    ADD COLUMN IF NOT EXISTS morning_health_window JSONB NOT NULL
    DEFAULT '{"start": "07:00", "end": "10:00"}'::jsonb;

ALTER TABLE rhythm_energy_profiles
    ADD COLUMN IF NOT EXISTS career_buffer_minutes INTEGER NOT NULL DEFAULT 45;

ALTER TABLE rhythm_energy_profiles
    ADD COLUMN IF NOT EXISTS work_gap_minutes INTEGER NOT NULL DEFAULT 15;
