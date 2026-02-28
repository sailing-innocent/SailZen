-- ============================================================================
-- Clear Outlines Related Tables
-- @file clear_outlines.sql
-- @brief 清除大纲相关数据表，用于调试时清理任务流程中crash的数据
-- @author sailing-innocent
-- @date 2025-02-28
-- ============================================================================

-- 注意：此脚本会删除所有大纲相关数据，请谨慎使用！
-- 建议仅在调试或开发环境中使用

-- 开始事务
BEGIN;

-- ============================================================================
-- 1. 清除大纲事件表 (先清除子表)
-- ============================================================================
DELETE FROM outline_events;

-- 重置序列
ALTER SEQUENCE IF EXISTS outline_events_id_seq RESTART WITH 1;

-- ============================================================================
-- 2. 清除大纲节点表
-- ============================================================================
DELETE FROM outline_nodes;

-- 重置序列
ALTER SEQUENCE IF EXISTS outline_nodes_id_seq RESTART WITH 1;

-- ============================================================================
-- 3. 清除大纲表
-- ============================================================================
DELETE FROM outlines;

-- 重置序列
ALTER SEQUENCE IF EXISTS outlines_id_seq RESTART WITH 1;

-- 提交事务
COMMIT;

-- 显示清理结果
SELECT 'outline_events cleared' AS table_name, COUNT(*) AS row_count FROM outline_events
UNION ALL
SELECT 'outline_nodes cleared', COUNT(*) FROM outline_nodes
UNION ALL
SELECT 'outlines cleared', COUNT(*) FROM outlines;
