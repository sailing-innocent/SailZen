-- ============================================================================
-- Outline Extraction Checkpoints Migration
-- 
-- 大纲提取检查点表迁移脚本
-- 支持 Task State - Checkpoint - Resume 体系
-- 
-- @author sailing-innocent
-- @date 2026-03-01
-- @version 1.0
-- ============================================================================

-- ============================================================================
-- 1. 创建大纲提取检查点表
-- ============================================================================
CREATE TABLE IF NOT EXISTS outline_extraction_checkpoints (
    id SERIAL PRIMARY KEY,
    
    -- 关联 Unified Agent 任务
    task_id INTEGER NOT NULL REFERENCES unified_agent_tasks(id) ON DELETE CASCADE,
    
    -- 检查点状态
    phase VARCHAR(50) NOT NULL DEFAULT 'initialized',
    -- 阶段: initialized | content_fetched | batch_started | batch_completed | merging | completed | failed | paused
    
    progress_percent INTEGER NOT NULL DEFAULT 0,
    current_step VARCHAR(200),
    message TEXT,
    
    -- 批次信息
    total_batches INTEGER NOT NULL DEFAULT 0,
    current_batch INTEGER NOT NULL DEFAULT 0,
    completed_batches INTEGER[] DEFAULT '{}',
    failed_batches INTEGER[] DEFAULT '{}',
    
    -- 结果统计
    total_nodes INTEGER DEFAULT 0,
    total_turning_points INTEGER DEFAULT 0,
    
    -- 错误信息
    last_error TEXT,
    last_error_type VARCHAR(50),
    retry_count INTEGER DEFAULT 0,
    
    -- 文件系统检查点路径（完整数据存储在文件系统）
    checkpoint_file_path VARCHAR(500),
    
    -- 时间戳
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 添加表注释
COMMENT ON TABLE outline_extraction_checkpoints IS '大纲提取检查点表 - 支持任务恢复和断点续传';
COMMENT ON COLUMN outline_extraction_checkpoints.phase IS 
    '提取阶段: initialized | content_fetched | batch_started | batch_completed | merging | completed | failed | paused';
COMMENT ON COLUMN outline_extraction_checkpoints.checkpoint_file_path IS 
    '文件系统检查点路径，完整数据存储在 .cache/extraction/{task_id}.json';

-- ============================================================================
-- 2. 创建索引
-- ============================================================================
CREATE INDEX IF NOT EXISTS idx_oec_task_id ON outline_extraction_checkpoints(task_id);
CREATE INDEX IF NOT EXISTS idx_oec_phase ON outline_extraction_checkpoints(phase);
CREATE INDEX IF NOT EXISTS idx_oec_updated ON outline_extraction_checkpoints(updated_at);

-- 唯一索引：每个任务只有一个检查点记录
CREATE UNIQUE INDEX IF NOT EXISTS idx_oec_task_unique 
    ON outline_extraction_checkpoints(task_id);

-- ============================================================================
-- 3. 创建更新时间触发器
-- ============================================================================
CREATE OR REPLACE FUNCTION update_oec_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS update_oec_updated_at ON outline_extraction_checkpoints;
CREATE TRIGGER update_oec_updated_at
    BEFORE UPDATE ON outline_extraction_checkpoints
    FOR EACH ROW
    EXECUTE FUNCTION update_oec_updated_at_column();

-- ============================================================================
-- 4. 创建检查点更新函数（用于原子更新）
-- ============================================================================
CREATE OR REPLACE FUNCTION update_outline_checkpoint(
    p_task_id INTEGER,
    p_phase VARCHAR(50) DEFAULT NULL,
    p_progress_percent INTEGER DEFAULT NULL,
    p_current_step VARCHAR(200) DEFAULT NULL,
    p_message TEXT DEFAULT NULL,
    p_current_batch INTEGER DEFAULT NULL,
    p_completed_batch INTEGER DEFAULT NULL,
    p_failed_batch INTEGER DEFAULT NULL,
    p_total_nodes INTEGER DEFAULT NULL,
    p_total_turning_points INTEGER DEFAULT NULL,
    p_last_error TEXT DEFAULT NULL,
    p_last_error_type VARCHAR(50) DEFAULT NULL,
    p_retry_count INTEGER DEFAULT NULL,
    p_checkpoint_file_path VARCHAR(500) DEFAULT NULL
)
RETURNS VOID AS $$
BEGIN
    INSERT INTO outline_extraction_checkpoints (
        task_id, phase, progress_percent, current_step, message,
        current_batch, completed_batches, failed_batches,
        total_nodes, total_turning_points,
        last_error, last_error_type, retry_count, checkpoint_file_path
    )
    VALUES (
        p_task_id, 
        COALESCE(p_phase, 'initialized'),
        COALESCE(p_progress_percent, 0),
        p_current_step,
        p_message,
        COALESCE(p_current_batch, 0),
        CASE WHEN p_completed_batch IS NOT NULL THEN ARRAY[p_completed_batch] ELSE '{}' END,
        CASE WHEN p_failed_batch IS NOT NULL THEN ARRAY[p_failed_batch] ELSE '{}' END,
        COALESCE(p_total_nodes, 0),
        COALESCE(p_total_turning_points, 0),
        p_last_error,
        p_last_error_type,
        COALESCE(p_retry_count, 0),
        p_checkpoint_file_path
    )
    ON CONFLICT (task_id) DO UPDATE SET
        phase = COALESCE(EXCLUDED.phase, outline_extraction_checkpoints.phase),
        progress_percent = COALESCE(EXCLUDED.progress_percent, outline_extraction_checkpoints.progress_percent),
        current_step = COALESCE(EXCLUDED.current_step, outline_extraction_checkpoints.current_step),
        message = COALESCE(EXCLUDED.message, outline_extraction_checkpoints.message),
        current_batch = COALESCE(EXCLUDED.current_batch, outline_extraction_checkpoints.current_batch),
        completed_batches = CASE 
            WHEN EXCLUDED.completed_batches[1] IS NOT NULL THEN 
                array_append(outline_extraction_checkpoints.completed_batches, EXCLUDED.completed_batches[1])
            ELSE outline_extraction_checkpoints.completed_batches 
        END,
        failed_batches = CASE 
            WHEN EXCLUDED.failed_batches[1] IS NOT NULL THEN 
                array_append(outline_extraction_checkpoints.failed_batches, EXCLUDED.failed_batches[1])
            ELSE outline_extraction_checkpoints.failed_batches 
        END,
        total_nodes = GREATEST(EXCLUDED.total_nodes, outline_extraction_checkpoints.total_nodes),
        total_turning_points = GREATEST(EXCLUDED.total_turning_points, outline_extraction_checkpoints.total_turning_points),
        last_error = COALESCE(EXCLUDED.last_error, outline_extraction_checkpoints.last_error),
        last_error_type = COALESCE(EXCLUDED.last_error_type, outline_extraction_checkpoints.last_error_type),
        retry_count = COALESCE(EXCLUDED.retry_count, outline_extraction_checkpoints.retry_count),
        checkpoint_file_path = COALESCE(EXCLUDED.checkpoint_file_path, outline_extraction_checkpoints.checkpoint_file_path),
        updated_at = CURRENT_TIMESTAMP;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION update_outline_checkpoint IS 
    '原子更新大纲提取检查点，自动处理 INSERT 或 UPDATE';

-- ============================================================================
-- 5. 创建获取可恢复任务视图
-- ============================================================================
CREATE OR REPLACE VIEW recoverable_outline_tasks AS
SELECT 
    uat.id AS task_id,
    uat.edition_id,
    uat.status,
    uat.progress,
    uat.current_phase,
    uat.error_message,
    uat.created_at,
    uat.started_at,
    uat.completed_at,
    oec.phase AS checkpoint_phase,
    oec.progress_percent AS checkpoint_progress,
    oec.total_batches,
    oec.completed_batches,
    oec.failed_batches,
    oec.current_batch,
    oec.total_nodes,
    oec.total_turning_points,
    oec.checkpoint_file_path,
    -- 是否可恢复
    CASE 
        WHEN uat.status IN ('running', 'paused') THEN true
        WHEN uat.status = 'failed' AND oec.checkpoint_file_path IS NOT NULL THEN true
        WHEN uat.status = 'completed' AND oec.total_nodes > 0 THEN true
        ELSE false
    END AS is_recoverable,
    -- 恢复建议
    CASE 
        WHEN uat.status = 'running' THEN '任务正在运行中，可恢复查看进度'
        WHEN uat.status = 'paused' THEN '任务已暂停，可从检查点恢复'
        WHEN uat.status = 'failed' AND oec.checkpoint_file_path IS NOT NULL THEN '任务失败但有检查点，可尝试恢复'
        WHEN uat.status = 'completed' THEN '任务已完成，可查看结果'
        ELSE '任务状态未知'
    END AS recovery_suggestion
FROM unified_agent_tasks uat
LEFT JOIN outline_extraction_checkpoints oec ON uat.id = oec.task_id
WHERE uat.task_type = 'novel_analysis'
  AND uat.sub_type = 'outline_extraction'
  AND uat.status NOT IN ('cancelled', 'pending')
ORDER BY uat.updated_at DESC;

COMMENT ON VIEW recoverable_outline_tasks IS 
    '可恢复的大纲提取任务视图 - 用于前端任务恢复对话框';

-- ============================================================================
-- 6. 创建检查点清理函数（定期清理过期检查点）
-- ============================================================================
CREATE OR REPLACE FUNCTION cleanup_old_outline_checkpoints(
    p_max_age_hours INTEGER DEFAULT 168  -- 默认 7 天
)
RETURNS TABLE (
    deleted_count INTEGER,
    deleted_task_ids INTEGER[]
) AS $$
DECLARE
    v_deleted_count INTEGER := 0;
    v_deleted_ids INTEGER[] := '{}';
BEGIN
    -- 选择要删除的检查点（已完成且超过指定时间的）
    SELECT 
        COUNT(*),
        ARRAY_AGG(task_id)
    INTO v_deleted_count, v_deleted_ids
    FROM outline_extraction_checkpoints
    WHERE phase = 'completed'
      AND updated_at < CURRENT_TIMESTAMP - (p_max_age_hours || ' hours')::INTERVAL;
    
    -- 删除过期的检查点
    DELETE FROM outline_extraction_checkpoints
    WHERE phase = 'completed'
      AND updated_at < CURRENT_TIMESTAMP - (p_max_age_hours || ' hours')::INTERVAL;
    
    RETURN QUERY SELECT v_deleted_count, v_deleted_ids;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION cleanup_old_outline_checkpoints IS 
    '清理已完成且超过指定时间的检查点，默认 7 天';

-- ============================================================================
-- 7. 完成
-- ============================================================================
DO $$
BEGIN
    RAISE NOTICE '===============================================';
    RAISE NOTICE '大纲提取检查点表迁移完成！';
    RAISE NOTICE '===============================================';
    RAISE NOTICE '创建的表:';
    RAISE NOTICE '  - outline_extraction_checkpoints';
    RAISE NOTICE '';
    RAISE NOTICE '创建的视图:';
    RAISE NOTICE '  - recoverable_outline_tasks';
    RAISE NOTICE '';
    RAISE NOTICE '创建的函数:';
    RAISE NOTICE '  - update_outline_checkpoint()';
    RAISE NOTICE '  - cleanup_old_outline_checkpoints()';
    RAISE NOTICE '===============================================';
END $$;
