-- ============================================================================
-- Unified Agent System Rollback
-- 
-- 统一 Agent 系统数据库迁移回滚脚本
-- 
-- ⚠️ 警告: 此脚本会删除迁移创建的所有表和视图！
-- ⚠️ 仅在必要时使用，且使用前请确保已备份数据！
-- 
-- @author sailing-innocent
-- @date 2026-02-27
-- @version 1.0
-- ============================================================================

-- ============================================================================
-- 0. 回滚前确认
-- ============================================================================
DO $$
BEGIN
    RAISE NOTICE '';
    RAISE NOTICE '===============================================';
    RAISE NOTICE '⚠️  警告: 即将执行回滚操作！';
    RAISE NOTICE '===============================================';
    RAISE NOTICE '';
    RAISE NOTICE '此操作将删除以下对象:';
    RAISE NOTICE '  - 表: unified_agent_tasks';
    RAISE NOTICE '  - 表: unified_agent_steps';
    RAISE NOTICE '  - 表: unified_agent_events';
    RAISE NOTICE '  - 表: migration_meta';
    RAISE NOTICE '  - 视图: analysis_tasks_v';
    RAISE NOTICE '  - 视图: agent_tasks_v';
    RAISE NOTICE '  - 视图: agent_steps_v';
    RAISE NOTICE '  - 视图: task_execution_logs_v';
    RAISE NOTICE '  - 触发器: update_uat_updated_at';
    RAISE NOTICE '  - 函数: update_uat_updated_at_column()';
    RAISE NOTICE '';
    RAISE NOTICE '⚠️  所有在统一表中的数据将丢失！';
    RAISE NOTICE '';
    RAISE NOTICE '如果你只是想恢复使用旧表，数据仍会保留在:';
    RAISE NOTICE '  - analysis_tasks (原始数据)';
    RAISE NOTICE '  - agent_tasks (原始数据)';
    RAISE NOTICE '  - agent_steps (原始数据)';
    RAISE NOTICE '  - task_execution_logs (原始数据)';
    RAISE NOTICE '';
    RAISE NOTICE '===============================================';
END $$;

-- ============================================================================
-- 1. 开启事务
-- ============================================================================
BEGIN;

-- ============================================================================
-- 2. 删除视图
-- ============================================================================
-- 先删除视图，因为它们依赖表
DROP VIEW IF EXISTS analysis_tasks_v CASCADE;
DROP VIEW IF EXISTS agent_tasks_v CASCADE;
DROP VIEW IF EXISTS agent_steps_v CASCADE;
DROP VIEW IF EXISTS task_execution_logs_v CASCADE;

DO $$
BEGIN
    RAISE NOTICE '[1/5] 兼容视图已删除';
END $$;

-- ============================================================================
-- 3. 删除触发器和函数
-- ============================================================================
DROP TRIGGER IF EXISTS update_uat_updated_at ON unified_agent_tasks;
DROP FUNCTION IF EXISTS update_uat_updated_at_column();

DO $$
BEGIN
    RAISE NOTICE '[2/5] 触发器和函数已删除';
END $$;

-- ============================================================================
-- 4. 删除表
-- ============================================================================
-- 按照外键依赖顺序删除：先删除依赖表，再删除被依赖表
DROP TABLE IF EXISTS unified_agent_events CASCADE;
DROP TABLE IF EXISTS unified_agent_steps CASCADE;
DROP TABLE IF EXISTS unified_agent_tasks CASCADE;
DROP TABLE IF EXISTS migration_meta CASCADE;

DO $$
BEGIN
    RAISE NOTICE '[3/5] 统一表已删除';
END $$;

-- ============================================================================
-- 5. 验证原表是否仍然存在
-- ============================================================================
DO $$
DECLARE
    analysis_exists BOOLEAN;
    agent_exists BOOLEAN;
    agent_steps_exists BOOLEAN;
    logs_exists BOOLEAN;
BEGIN
    SELECT EXISTS (
        SELECT 1 FROM information_schema.tables WHERE table_name = 'analysis_tasks'
    ) INTO analysis_exists;
    
    SELECT EXISTS (
        SELECT 1 FROM information_schema.tables WHERE table_name = 'agent_tasks'
    ) INTO agent_exists;
    
    SELECT EXISTS (
        SELECT 1 FROM information_schema.tables WHERE table_name = 'agent_steps'
    ) INTO agent_steps_exists;
    
    SELECT EXISTS (
        SELECT 1 FROM information_schema.tables WHERE table_name = 'task_execution_logs'
    ) INTO logs_exists;
    
    RAISE NOTICE '[4/5] 原始表状态:';
    RAISE NOTICE '  - analysis_tasks: %', CASE WHEN analysis_exists THEN '✓ 存在' ELSE '✗ 不存在' END;
    RAISE NOTICE '  - agent_tasks: %', CASE WHEN agent_exists THEN '✓ 存在' ELSE '✗ 不存在' END;
    RAISE NOTICE '  - agent_steps: %', CASE WHEN agent_steps_exists THEN '✓ 存在' ELSE '✗ 不存在' END;
    RAISE NOTICE '  - task_execution_logs: %', CASE WHEN logs_exists THEN '✓ 存在' ELSE '✗ 不存在' END;
    
    IF NOT analysis_exists OR NOT agent_exists THEN
        RAISE WARNING '⚠️  部分原始表不存在！数据可能已丢失！';
    END IF;
END $$;

-- ============================================================================
-- 6. 完成回滚
-- ============================================================================
COMMIT;

DO $$
BEGIN
    RAISE NOTICE '[5/5] 回滚完成！';
    RAISE NOTICE '';
    RAISE NOTICE '===============================================';
    RAISE NOTICE '回滚操作已完成';
    RAISE NOTICE '===============================================';
    RAISE NOTICE '';
    RAISE NOTICE '系统已恢复到迁移前状态:';
    RAISE NOTICE '  - 统一表已删除';
    RAISE NOTICE '  - 原始表 (analysis_tasks, agent_tasks 等) 仍然可用';
    RAISE NOTICE '';
    RAISE NOTICE '应用代码应回滚到使用原始表版本';
    RAISE NOTICE '===============================================';
END $$;
