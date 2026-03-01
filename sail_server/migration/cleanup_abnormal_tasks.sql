-- ============================================================================
-- Cleanup Abnormal Tasks
-- 
-- 清理状态异常的任务数据
-- 用于修复调试过程中产生的中断、失败等异常状态任务
-- 
-- @author sailing-innocent
-- @date 2026-03-01
-- @version 1.0
-- ============================================================================

-- 此脚本会清理以下异常任务：
-- 1. 状态为 'running' 但长时间没有更新的任务（可能已中断）
-- 2. 状态为 'failed' 的任务
-- 3. 状态为 'cancelled' 的任务
-- 4. 状态异常（非标准状态值）的任务

-- ============================================================================
-- 1. 查看当前任务状态统计
-- ============================================================================

SELECT '清理前任务状态统计:' AS info;

SELECT 
    status, 
    COUNT(*) AS task_count,
    MAX(updated_at) AS last_update,
    MIN(created_at) AS oldest_task
FROM unified_agent_tasks
WHERE task_type = 'novel_analysis'
  AND sub_type = 'outline_extraction'
GROUP BY status
ORDER BY task_count DESC;

-- ============================================================================
-- 2. 识别异常任务
-- ============================================================================

-- 查看运行中但超过 30 分钟未更新的任务（可能已中断）
SELECT 
    '可能中断的运行中任务:' AS warning,
    id,
    status,
    current_phase,
    updated_at,
    EXTRACT(EPOCH FROM (CURRENT_TIMESTAMP - updated_at))/60 AS idle_minutes
FROM unified_agent_tasks
WHERE status = 'running'
  AND updated_at < CURRENT_TIMESTAMP - INTERVAL '30 minutes';

-- ============================================================================
-- 3. 清理异常任务（使用事务确保安全）
-- ============================================================================

BEGIN;

-- 创建临时表保存要删除的任务 ID
CREATE TEMP TABLE tasks_to_cleanup AS
SELECT id 
FROM unified_agent_tasks
WHERE task_type = 'novel_analysis'
  AND sub_type = 'outline_extraction'
  AND (
      -- 已失败的任务
      status = 'failed'
      -- 已取消的任务
      OR status = 'cancelled'
      -- 运行中但超过 30 分钟未更新（可能已中断）
      OR (status = 'running' AND updated_at < CURRENT_TIMESTAMP - INTERVAL '30 minutes')
      -- 状态异常（非标准值）
      OR status NOT IN ('pending', 'scheduled', 'running', 'paused', 'completed', 'failed', 'cancelled')
  );

-- 查看将要清理的任务
SELECT 
    '将要清理的任务:' AS info,
    COUNT(*) AS task_count
FROM tasks_to_cleanup;

SELECT 
    t.id,
    t.status,
    t.current_phase,
    t.error_message,
    t.created_at,
    t.updated_at
FROM unified_agent_tasks t
JOIN tasks_to_cleanup c ON t.id = c.id
ORDER BY t.id;

-- ============================================================================
-- 4. 执行清理
-- ============================================================================

-- 删除相关的事件记录
DELETE FROM unified_agent_events
WHERE task_id IN (SELECT id FROM tasks_to_cleanup);

-- 删除相关的步骤记录
DELETE FROM unified_agent_steps
WHERE task_id IN (SELECT id FROM tasks_to_cleanup);

-- 删除相关的检查点记录
DELETE FROM outline_extraction_checkpoints
WHERE task_id IN (SELECT id FROM tasks_to_cleanup);

-- 删除任务本身
DELETE FROM unified_agent_tasks
WHERE id IN (SELECT id FROM tasks_to_cleanup);

-- ============================================================================
-- 5. 提交事务
-- ============================================================================

COMMIT;

-- 清理临时表
DROP TABLE IF EXISTS tasks_to_cleanup;

-- ============================================================================
-- 6. 验证清理结果
-- ============================================================================

SELECT '清理后任务状态统计:' AS info;

SELECT 
    status, 
    COUNT(*) AS task_count,
    MAX(updated_at) AS last_update
FROM unified_agent_tasks
WHERE task_type = 'novel_analysis'
  AND sub_type = 'outline_extraction'
GROUP BY status
ORDER BY task_count DESC;

-- ============================================================================
-- 7. 重置序列（可选）
-- ============================================================================

-- 如果需要重置序列，取消下面的注释
-- SELECT setval('unified_agent_tasks_id_seq', COALESCE((SELECT MAX(id) FROM unified_agent_tasks), 0) + 1, false);
-- SELECT setval('unified_agent_steps_id_seq', COALESCE((SELECT MAX(id) FROM unified_agent_steps), 0) + 1, false);
-- SELECT setval('unified_agent_events_id_seq', COALESCE((SELECT MAX(id) FROM unified_agent_events), 0) + 1, false);
-- SELECT setval('outline_extraction_checkpoints_id_seq', COALESCE((SELECT MAX(id) FROM outline_extraction_checkpoints), 0) + 1, false);

-- ============================================================================
-- 8. 完成提示
-- ============================================================================

DO $$
BEGIN
    RAISE NOTICE '===============================================';
    RAISE NOTICE '异常任务清理完成！';
    RAISE NOTICE '===============================================';
    RAISE NOTICE '清理的任务状态包括:';
    RAISE NOTICE '  - failed (失败)';
    RAISE NOTICE '  - cancelled (已取消)';
    RAISE NOTICE '  - running 但超过 30 分钟未更新 (可能中断)';
    RAISE NOTICE '  - 状态值异常的任务';
    RAISE NOTICE '';
    RAISE NOTICE '保留的任务状态:';
    RAISE NOTICE '  - pending (等待中)';
    RAISE NOTICE '  - scheduled (已调度)';
    RAISE NOTICE '  - running (运行中且活跃)';
    RAISE NOTICE '  - paused (已暂停)';
    RAISE NOTICE '  - completed (已完成)';
    RAISE NOTICE '===============================================';
END $$;
