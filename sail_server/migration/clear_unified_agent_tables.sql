-- -*- coding: utf-8 -*-
-- @file clear_unified_agent_tables.sql
-- @brief 清空 Unified Agent 相关表
-- @author sailing-innocent
-- @date 2026-02-28
-- ---------------------------------
--
-- 清空所有 Unified Agent 相关的表数据
-- 注意：此操作会删除所有任务数据，请谨慎使用！

-- 开始事务
BEGIN;

-- 清空事件表（先清空子表，避免外键约束错误）
TRUNCATE TABLE unified_agent_events CASCADE;

-- 清空步骤表
TRUNCATE TABLE unified_agent_steps CASCADE;

-- 清空任务表
TRUNCATE TABLE unified_agent_tasks CASCADE;

-- 提交事务
COMMIT;

-- 重置序列（如果需要）
-- 注意：PostgreSQL 9.5+ 使用以下语法
-- 如果表使用了 SERIAL 或 GENERATED ALWAYS AS IDENTITY，可能需要重置序列

-- 检查并重置 unified_agent_tasks 表的序列
SELECT setval(
    (SELECT pg_get_serial_sequence('unified_agent_tasks', 'id')),
    COALESCE((SELECT MAX(id) FROM unified_agent_tasks), 0) + 1,
    false
);

SELECT setval(
    (SELECT pg_get_serial_sequence('unified_agent_steps', 'id')),
    COALESCE((SELECT MAX(id) FROM unified_agent_steps), 0) + 1,
    false
);

SELECT setval(
    (SELECT pg_get_serial_sequence('unified_agent_events', 'id')),
    COALESCE((SELECT MAX(id) FROM unified_agent_events), 0) + 1,
    false
);
