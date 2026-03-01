-- ============================================================================
-- Reset Task Tables
-- 
-- 重新初始化任务相关表格
-- 用于调试过程中清理异常数据，防止中断导致的错误数据使项目进入异常情况
-- 
-- @author sailing-innocent
-- @date 2026-03-01
-- @version 1.0
-- ============================================================================

-- 警告：此脚本将删除所有任务数据！
-- 请在执行前备份重要数据

-- ============================================================================
-- 1. 删除外键约束（避免删除顺序问题）
-- ============================================================================

-- 删除 unified_agent_steps 表的外键约束
ALTER TABLE IF EXISTS unified_agent_steps 
    DROP CONSTRAINT IF EXISTS unified_agent_steps_task_id_fkey;

-- 删除 unified_agent_events 表的外键约束
ALTER TABLE IF EXISTS unified_agent_events 
    DROP CONSTRAINT IF EXISTS unified_agent_events_task_id_fkey;

-- 删除 outline_extraction_checkpoints 表的外键约束
ALTER TABLE IF EXISTS outline_extraction_checkpoints 
    DROP CONSTRAINT IF EXISTS outline_extraction_checkpoints_task_id_fkey;

-- ============================================================================
-- 2. 清空数据表（保留表结构）
-- ============================================================================

-- 清空事件表（先清空，因为依赖 task）
TRUNCATE TABLE unified_agent_events RESTART IDENTITY CASCADE;

-- 清空步骤表
TRUNCATE TABLE unified_agent_steps RESTART IDENTITY CASCADE;

-- 清空检查点表
TRUNCATE TABLE outline_extraction_checkpoints RESTART IDENTITY CASCADE;

-- 清空任务表（最后清空，因为被其他表依赖）
TRUNCATE TABLE unified_agent_tasks RESTART IDENTITY CASCADE;

-- ============================================================================
-- 3. 重新添加外键约束
-- ============================================================================

-- unified_agent_steps 外键
ALTER TABLE unified_agent_steps 
    ADD CONSTRAINT unified_agent_steps_task_id_fkey 
    FOREIGN KEY (task_id) REFERENCES unified_agent_tasks(id) ON DELETE CASCADE;

-- unified_agent_events 外键
ALTER TABLE unified_agent_events 
    ADD CONSTRAINT unified_agent_events_task_id_fkey 
    FOREIGN KEY (task_id) REFERENCES unified_agent_tasks(id) ON DELETE CASCADE;

-- outline_extraction_checkpoints 外键
ALTER TABLE outline_extraction_checkpoints 
    ADD CONSTRAINT outline_extraction_checkpoints_task_id_fkey 
    FOREIGN KEY (task_id) REFERENCES unified_agent_tasks(id) ON DELETE CASCADE;

-- ============================================================================
-- 4. 清理文件系统检查点文件
-- ============================================================================

-- 注意：以下命令需要在 psql 中执行，或者手动删除文件
-- 这里提供 SQL 查询来列出需要删除的文件路径

SELECT '请手动删除以下检查点文件:' AS notice;
SELECT DISTINCT checkpoint_file_path 
FROM outline_extraction_checkpoints 
WHERE checkpoint_file_path IS NOT NULL;

-- ============================================================================
-- 5. 重置序列（确保 ID 从 1 开始）
-- ============================================================================

-- 重置 unified_agent_tasks 序列
SELECT setval('unified_agent_tasks_id_seq', 1, false);

-- 重置 unified_agent_steps 序列
SELECT setval('unified_agent_steps_id_seq', 1, false);

-- 重置 unified_agent_events 序列
SELECT setval('unified_agent_events_id_seq', 1, false);

-- 重置 outline_extraction_checkpoints 序列
SELECT setval('outline_extraction_checkpoints_id_seq', 1, false);

-- ============================================================================
-- 6. 验证清理结果
-- ============================================================================

SELECT '清理后表记录数:' AS verification;

SELECT 'unified_agent_tasks' AS table_name, COUNT(*) AS record_count 
FROM unified_agent_tasks
UNION ALL
SELECT 'unified_agent_steps', COUNT(*) 
FROM unified_agent_steps
UNION ALL
SELECT 'unified_agent_events', COUNT(*) 
FROM unified_agent_events
UNION ALL
SELECT 'outline_extraction_checkpoints', COUNT(*) 
FROM outline_extraction_checkpoints;

-- ============================================================================
-- 7. 完成提示
-- ============================================================================

DO $$
BEGIN
    RAISE NOTICE '===============================================';
    RAISE NOTICE '任务表重新初始化完成！';
    RAISE NOTICE '===============================================';
    RAISE NOTICE '已清空的表:';
    RAISE NOTICE '  - unified_agent_tasks';
    RAISE NOTICE '  - unified_agent_steps';
    RAISE NOTICE '  - unified_agent_events';
    RAISE NOTICE '  - outline_extraction_checkpoints';
    RAISE NOTICE '';
    RAISE NOTICE '序列已重置为 1';
    RAISE NOTICE '';
    RAISE NOTICE '注意：请手动删除 .cache/extraction/ 目录下的检查点文件';
    RAISE NOTICE '===============================================';
END $$;
