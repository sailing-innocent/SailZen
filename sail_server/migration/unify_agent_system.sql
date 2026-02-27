-- ============================================================================
-- Unified Agent System Migration
-- 
-- 统一 Agent 系统数据库迁移脚本
-- 整合 Agent 系统和小说分析系统的任务模型
-- 
-- @author sailing-innocent
-- @date 2026-02-27
-- @version 1.0
-- ============================================================================

-- ============================================================================
-- 0. 迁移前检查与准备
-- ============================================================================
DO $$
BEGIN
    -- 检查必要表是否存在
    IF NOT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'analysis_tasks') THEN
        RAISE EXCEPTION '表 analysis_tasks 不存在，无法迁移';
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'agent_tasks') THEN
        RAISE EXCEPTION '表 agent_tasks 不存在，无法迁移';
    END IF;
    
    RAISE NOTICE '前置检查通过，开始迁移...';
END $$;

-- ============================================================================
-- 1. 开启事务
-- ============================================================================
BEGIN;

-- ============================================================================
-- 2. 创建统一任务表
-- ============================================================================
CREATE TABLE IF NOT EXISTS unified_agent_tasks (
    id SERIAL PRIMARY KEY,
    
    -- 任务分类
    task_type VARCHAR(50) NOT NULL,  -- 'novel_analysis' | 'code' | 'writing' | 'general' | 'data'
    sub_type VARCHAR(50),  -- 如 'outline_extraction', 'character_detection' 等
    
    -- 关联信息 (小说分析用)
    edition_id INTEGER REFERENCES editions(id) ON DELETE SET NULL,
    target_node_ids INTEGER[],  -- 目标章节节点 ID 列表
    target_scope VARCHAR(20),  -- 'full' | 'range' | 'chapter'
    
    -- LLM 配置
    llm_provider VARCHAR(50),  -- 'google' | 'openai' | 'moonshot' | 'anthropic'
    llm_model VARCHAR(100),
    prompt_template_id VARCHAR(100),
    
    -- 执行状态
    status VARCHAR(50) NOT NULL DEFAULT 'pending',  -- pending | scheduled | running | paused | completed | failed | cancelled
    progress INTEGER NOT NULL DEFAULT 0,  -- 0-100
    current_phase VARCHAR(100),
    priority INTEGER NOT NULL DEFAULT 5,  -- 1-10, 1为最高
    
    -- 错误信息
    error_message TEXT,
    error_code VARCHAR(50),
    
    -- 成本追踪
    estimated_tokens INTEGER,
    actual_tokens INTEGER NOT NULL DEFAULT 0,
    estimated_cost NUMERIC(10, 6),
    actual_cost NUMERIC(10, 6) NOT NULL DEFAULT 0.0,
    
    -- 结果数据
    result_data JSONB,
    review_status VARCHAR(50) NOT NULL DEFAULT 'pending',  -- pending | approved | rejected | modified
    
    -- 配置参数 (原 agent_config / parameters)
    config JSONB DEFAULT '{}',
    
    -- 创建者信息
    created_by VARCHAR(255),
    
    -- 时间戳
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    cancelled_at TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 添加表注释
COMMENT ON TABLE unified_agent_tasks IS '统一 Agent 任务表 - 整合 AgentTask 和 AnalysisTask';
COMMENT ON COLUMN unified_agent_tasks.task_type IS '任务类型: novel_analysis | code | writing | general | data';
COMMENT ON COLUMN unified_agent_tasks.sub_type IS '子类型: outline_extraction, character_detection, setting_extraction 等';
COMMENT ON COLUMN unified_agent_tasks.status IS '任务状态: pending | scheduled | running | paused | completed | failed | cancelled';
COMMENT ON COLUMN unified_agent_tasks.target_scope IS '目标范围: full(全书) | range(范围) | chapter(单章)';

-- ============================================================================
-- 3. 创建统一步骤表
-- ============================================================================
CREATE TABLE IF NOT EXISTS unified_agent_steps (
    id SERIAL PRIMARY KEY,
    task_id INTEGER NOT NULL REFERENCES unified_agent_tasks(id) ON DELETE CASCADE,
    
    -- 步骤信息
    step_number INTEGER NOT NULL,
    step_type VARCHAR(50) NOT NULL,  -- thought | action | observation | llm_call | data_processing | error | completion
    title VARCHAR(200),
    content TEXT,
    content_summary VARCHAR(500),
    
    -- LLM 调用追踪
    llm_provider VARCHAR(50),
    llm_model VARCHAR(100),
    prompt_tokens INTEGER NOT NULL DEFAULT 0,
    completion_tokens INTEGER NOT NULL DEFAULT 0,
    cost NUMERIC(10, 6) NOT NULL DEFAULT 0.0,
    
    -- 元数据
    meta_data JSONB DEFAULT '{}',
    
    -- 时间戳
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    duration_ms INTEGER
);

COMMENT ON TABLE unified_agent_steps IS '统一 Agent 步骤表 - 追踪任务执行步骤和 LLM 调用';
COMMENT ON COLUMN unified_agent_steps.step_type IS '步骤类型: thought | action | observation | llm_call | data_processing | error | completion';

-- ============================================================================
-- 4. 创建统一事件表
-- ============================================================================
CREATE TABLE IF NOT EXISTS unified_agent_events (
    id SERIAL PRIMARY KEY,
    task_id INTEGER NOT NULL REFERENCES unified_agent_tasks(id) ON DELETE CASCADE,
    event_type VARCHAR(50) NOT NULL,  -- task_started | step_completed | llm_called | progress_update | error | task_completed
    event_data JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE unified_agent_events IS '统一 Agent 事件日志表 - 记录任务执行关键事件';

-- ============================================================================
-- 5. 创建索引
-- ============================================================================
-- 任务表索引
CREATE INDEX IF NOT EXISTS idx_uat_task_type ON unified_agent_tasks(task_type);
CREATE INDEX IF NOT EXISTS idx_uat_status ON unified_agent_tasks(status);
CREATE INDEX IF NOT EXISTS idx_uat_edition ON unified_agent_tasks(edition_id) WHERE edition_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_uat_created_at ON unified_agent_tasks(created_at);
CREATE INDEX IF NOT EXISTS idx_uat_pending ON unified_agent_tasks(status, priority) WHERE status = 'pending';
CREATE INDEX IF NOT EXISTS idx_uat_review ON unified_agent_tasks(review_status) WHERE review_status = 'pending';

-- 步骤表索引
CREATE INDEX IF NOT EXISTS idx_uas_task_id ON unified_agent_steps(task_id);
CREATE INDEX IF NOT EXISTS idx_uas_task_step ON unified_agent_steps(task_id, step_number);

-- 事件表索引
CREATE INDEX IF NOT EXISTS idx_uae_task ON unified_agent_events(task_id);
CREATE INDEX IF NOT EXISTS idx_uae_event_type ON unified_agent_events(event_type);
CREATE INDEX IF NOT EXISTS idx_uae_created ON unified_agent_events(created_at);

-- ============================================================================
-- 6. 创建更新时间触发器
-- ============================================================================
CREATE OR REPLACE FUNCTION update_uat_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS update_uat_updated_at ON unified_agent_tasks;
CREATE TRIGGER update_uat_updated_at
    BEFORE UPDATE ON unified_agent_tasks
    FOR EACH ROW
    EXECUTE FUNCTION update_uat_updated_at_column();

-- ============================================================================
-- 7. 迁移 AnalysisTask 数据
-- ============================================================================
INSERT INTO unified_agent_tasks (
    id,  -- 保留原ID以维护关联关系
    task_type,
    sub_type,
    edition_id,
    target_node_ids,
    target_scope,
    llm_provider,
    llm_model,
    prompt_template_id,
    status,
    progress,
    priority,
    error_message,
    estimated_tokens,
    actual_tokens,
    estimated_cost,
    actual_cost,
    result_data,
    review_status,
    config,
    created_by,
    created_at,
    started_at,
    completed_at
)
SELECT 
    id,
    'novel_analysis' AS task_type,
    task_type AS sub_type,  -- 原 task_type 变为 sub_type
    edition_id,
    target_node_ids,
    target_scope,
    CASE 
        WHEN llm_model LIKE 'gemini%' THEN 'google'
        WHEN llm_model LIKE 'gpt%' THEN 'openai'
        WHEN llm_model LIKE 'moonshot%' THEN 'moonshot'
        ELSE NULL
    END AS llm_provider,
    llm_model,
    llm_prompt_template AS prompt_template_id,
    status,
    COALESCE(
        CASE 
            WHEN total_chunks > 0 THEN (completed_chunks::FLOAT / total_chunks * 100)::INTEGER
            ELSE 0
        END, 0
    ) AS progress,
    priority,
    error_message,
    NULL AS estimated_tokens,  -- 原表没有预估
    0 AS actual_tokens,  -- 原表没有记录，后续从日志计算
    NULL AS estimated_cost,
    0.0 AS actual_cost,
    result_summary AS result_data,
    'pending' AS review_status,  -- 默认待审核，从 analysis_results 更新
    parameters AS config,
    created_by,
    created_at,
    started_at,
    completed_at
FROM analysis_tasks;

-- 更新 review_status 从 analysis_results
UPDATE unified_agent_tasks uat
SET review_status = COALESCE(
    (SELECT ar.review_status 
     FROM analysis_results ar 
     WHERE ar.task_id = uat.id 
     ORDER BY ar.created_at DESC 
     LIMIT 1),
    'pending'
)
WHERE uat.task_type = 'novel_analysis';

-- 设置正确的序列值
SELECT setval('unified_agent_tasks_id_seq', COALESCE((SELECT MAX(id) FROM unified_agent_tasks), 1));

-- ============================================================================
-- 8. 迁移 AgentTask 数据
-- ============================================================================
-- 先找到最大的 analysis_tasks id，确保不冲突
DO $$
DECLARE
    max_analysis_id INTEGER;
    max_agent_id INTEGER;
BEGIN
    SELECT COALESCE(MAX(id), 0) INTO max_analysis_id FROM analysis_tasks;
    SELECT COALESCE(MAX(id), 0) INTO max_agent_id FROM agent_tasks;
    
    IF max_agent_id > 0 THEN
        -- 调整 sequence 以容纳新数据
        PERFORM setval('unified_agent_tasks_id_seq', GREATEST(max_analysis_id, max_agent_id) + 1);
    END IF;
END $$;

INSERT INTO unified_agent_tasks (
    task_type,
    sub_type,
    edition_id,
    target_node_ids,
    target_scope,
    llm_provider,
    llm_model,
    prompt_template_id,
    status,
    progress,
    priority,
    current_phase,
    error_message,
    error_code,
    estimated_tokens,
    actual_tokens,
    estimated_cost,
    actual_cost,
    result_data,
    review_status,
    config,
    created_by,
    created_at,
    started_at,
    completed_at,
    updated_at
)
SELECT 
    'general' AS task_type,  -- 默认 general，可根据 agent_type 扩展
    agent_type AS sub_type,
    NULL AS edition_id,  -- AgentTask 没有 edition 关联
    NULL AS target_node_ids,
    NULL AS target_scope,
    NULL AS llm_provider,  -- 从 agent_config 解析或后续补充
    NULL AS llm_model,
    NULL AS prompt_template_id,
    CASE 
        WHEN status = 'created' THEN 'pending'
        WHEN status = 'running' THEN 'running'
        WHEN status = 'completed' THEN 'completed'
        WHEN status = 'failed' THEN 'failed'
        ELSE status
    END AS status,
    progress,
    5 AS priority,  -- 默认中等优先级
    NULL AS current_phase,
    error_message,
    error_code,
    NULL AS estimated_tokens,
    0 AS actual_tokens,
    NULL AS estimated_cost,
    0.0 AS actual_cost,
    NULL AS result_data,
    'pending' AS review_status,
    agent_config AS config,
    NULL AS created_by,  -- agent_tasks 表没有 created_by 字段
    created_at,
    started_at,
    completed_at,
    updated_at
FROM agent_tasks at
WHERE NOT EXISTS (
    SELECT 1 FROM unified_agent_tasks uat WHERE uat.id = at.id
);

-- ============================================================================
-- 9. 迁移 AgentStep 数据到 UnifiedAgentStep
-- ============================================================================
-- 只迁移与已迁移的 AgentTask 关联的步骤
INSERT INTO unified_agent_steps (
    task_id,
    step_number,
    step_type,
    title,
    content,
    content_summary,
    llm_provider,
    llm_model,
    prompt_tokens,
    completion_tokens,
    cost,
    meta_data,
    created_at,
    duration_ms
)
SELECT 
    ast.task_id,
    ast.step_number,
    ast.step_type,
    ast.title,
    ast.content,
    ast.content_summary,
    NULL AS llm_provider,  -- 原表没有，后续从元数据解析
    NULL AS llm_model,
    0 AS prompt_tokens,
    0 AS completion_tokens,
    0.0 AS cost,
    ast.meta_data,
    ast.created_at,
    ast.duration_ms
FROM agent_steps ast
INNER JOIN unified_agent_tasks uat ON ast.task_id = uat.id
WHERE uat.task_type = 'general';  -- 只迁移通用 Agent 的步骤

-- ============================================================================
-- 10. 迁移 TaskExecutionLog 到 UnifiedAgentEvent
-- ============================================================================
INSERT INTO unified_agent_events (
    task_id,
    event_type,
    event_data,
    created_at
)
SELECT 
    tel.task_id,
    CASE 
        WHEN tel.log_type = 'start' THEN 'task_started'
        WHEN tel.log_type = 'progress' THEN 'progress_update'
        WHEN tel.log_type = 'chunk_complete' THEN 'step_completed'
        WHEN tel.log_type = 'error' THEN 'error'
        WHEN tel.log_type = 'complete' THEN 'task_completed'
        ELSE tel.log_type
    END AS event_type,
    jsonb_build_object(
        'message', tel.message,
        'details', tel.details
    ) AS event_data,
    tel.created_at
FROM task_execution_logs tel
INNER JOIN unified_agent_tasks uat ON tel.task_id = uat.id;

-- ============================================================================
-- 11. 创建兼容视图
-- ============================================================================

-- 11.1 analysis_tasks 兼容视图
CREATE OR REPLACE VIEW analysis_tasks_v AS
SELECT 
    id,
    edition_id,
    COALESCE(sub_type, task_type) AS task_type,
    target_scope,
    target_node_ids,
    config AS parameters,
    llm_model,
    prompt_template_id AS llm_prompt_template,
    status,
    priority,
    NULL::TIMESTAMP WITH TIME ZONE AS scheduled_at,
    started_at,
    completed_at,
    error_message,
    result_data AS result_summary,
    'prompt_only'::VARCHAR AS execution_mode,
    NULL::INTEGER AS total_chunks,
    (progress::FLOAT / 100 * 10)::INTEGER AS completed_chunks,  -- 估算
    current_phase AS current_chunk_info,
    NULL::TIMESTAMP WITH TIME ZONE AS estimated_completion_at,
    NULL::TIMESTAMP WITH TIME ZONE AS paused_at,
    created_by,
    created_at
FROM unified_agent_tasks
WHERE task_type = 'novel_analysis';

COMMENT ON VIEW analysis_tasks_v IS 'analysis_tasks 兼容视图 - 映射到统一任务表';

-- 11.2 agent_tasks 兼容视图
CREATE OR REPLACE VIEW agent_tasks_v AS
SELECT 
    id,
    COALESCE((config->>'prompt_id')::INTEGER, id) AS prompt_id,
    COALESCE(sub_type, 'general') AS agent_type,
    config AS agent_config,
    status,
    progress,
    created_at,
    started_at,
    updated_at,
    completed_at,
    error_message,
    error_code,
    COALESCE((config->>'max_iterations')::INTEGER, 100) AS max_iterations,
    COALESCE((config->>'timeout_seconds')::INTEGER, 3600) AS timeout_seconds
FROM unified_agent_tasks
WHERE task_type IN ('code', 'writing', 'general', 'data')
   OR (task_type = 'general' AND edition_id IS NULL);

COMMENT ON VIEW agent_tasks_v IS 'agent_tasks 兼容视图 - 映射到统一任务表';

-- 11.3 agent_steps 兼容视图
CREATE OR REPLACE VIEW agent_steps_v AS
SELECT 
    id,
    task_id,
    step_number,
    step_type,
    title,
    content,
    content_summary,
    meta_data,
    created_at,
    duration_ms
FROM unified_agent_steps
WHERE task_id IN (
    SELECT id FROM unified_agent_tasks 
    WHERE task_type IN ('code', 'writing', 'general', 'data')
);

COMMENT ON VIEW agent_steps_v IS 'agent_steps 兼容视图 - 映射到统一步骤表';

-- 11.4 task_execution_logs 兼容视图
CREATE OR REPLACE VIEW task_execution_logs_v AS
SELECT 
    id,
    task_id,
    CASE 
        WHEN event_type = 'task_started' THEN 'start'
        WHEN event_type = 'progress_update' THEN 'progress'
        WHEN event_type = 'step_completed' THEN 'chunk_complete'
        WHEN event_type = 'error' THEN 'error'
        WHEN event_type = 'task_completed' THEN 'complete'
        ELSE event_type
    END AS log_type,
    event_data->>'message' AS message,
    event_data->'details' AS details,
    created_at
FROM unified_agent_events;

COMMENT ON VIEW task_execution_logs_v IS 'task_execution_logs 兼容视图 - 映射到统一事件表';

-- ============================================================================
-- 12. 创建迁移元数据记录表
-- ============================================================================
CREATE TABLE IF NOT EXISTS migration_meta (
    id SERIAL PRIMARY KEY,
    migration_name VARCHAR(100) NOT NULL,
    migration_version VARCHAR(20) NOT NULL,
    executed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    executed_by VARCHAR(100),
    source_record_count JSONB,  -- 记录迁移前各表记录数
    target_record_count JSONB,  -- 记录迁移后各表记录数
    notes TEXT
);

-- 记录本次迁移信息
INSERT INTO migration_meta (
    migration_name,
    migration_version,
    executed_by,
    source_record_count,
    target_record_count,
    notes
)
SELECT 
    'unify_agent_system',
    '1.0',
    CURRENT_USER,
    jsonb_build_object(
        'analysis_tasks', (SELECT COUNT(*) FROM analysis_tasks),
        'agent_tasks', (SELECT COUNT(*) FROM agent_tasks),
        'agent_steps', (SELECT COUNT(*) FROM agent_steps),
        'task_execution_logs', (SELECT COUNT(*) FROM task_execution_logs)
    ),
    jsonb_build_object(
        'unified_agent_tasks', (SELECT COUNT(*) FROM unified_agent_tasks),
        'unified_agent_steps', (SELECT COUNT(*) FROM unified_agent_steps),
        'unified_agent_events', (SELECT COUNT(*) FROM unified_agent_events)
    ),
    'Phase 2: 统一 Agent 系统数据库迁移完成';

-- ============================================================================
-- 13. 完成
-- ============================================================================
COMMIT;

DO $$
DECLARE
    task_count INTEGER;
    step_count INTEGER;
    event_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO task_count FROM unified_agent_tasks;
    SELECT COUNT(*) INTO step_count FROM unified_agent_steps;
    SELECT COUNT(*) INTO event_count FROM unified_agent_events;
    
    RAISE NOTICE '===============================================';
    RAISE NOTICE '统一 Agent 系统迁移完成！';
    RAISE NOTICE '===============================================';
    RAISE NOTICE 'unified_agent_tasks: % 条记录', task_count;
    RAISE NOTICE 'unified_agent_steps: % 条记录', step_count;
    RAISE NOTICE 'unified_agent_events: % 条记录', event_count;
    RAISE NOTICE '';
    RAISE NOTICE '已创建兼容视图:';
    RAISE NOTICE '  - analysis_tasks_v';
    RAISE NOTICE '  - agent_tasks_v';
    RAISE NOTICE '  - agent_steps_v';
    RAISE NOTICE '  - task_execution_logs_v';
    RAISE NOTICE '';
    RAISE NOTICE '请运行 verify_migration.py 验证数据完整性';
    RAISE NOTICE '===============================================';
END $$;
