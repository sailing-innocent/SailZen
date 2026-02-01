-- ============================================================================
-- LLM Analysis Extension Tables
-- 
-- 为 LLM 辅助分析功能添加扩展表和字段
-- 
-- @author sailing-innocent
-- @date 2025-02-01
-- ============================================================================

-- ============================================================================
-- 1. 扩展 analysis_tasks 表
-- ============================================================================

-- 添加执行模式字段
ALTER TABLE analysis_tasks 
ADD COLUMN IF NOT EXISTS execution_mode VARCHAR DEFAULT 'prompt_only';

-- 添加分块进度字段
ALTER TABLE analysis_tasks 
ADD COLUMN IF NOT EXISTS total_chunks INTEGER;

ALTER TABLE analysis_tasks 
ADD COLUMN IF NOT EXISTS completed_chunks INTEGER DEFAULT 0;

ALTER TABLE analysis_tasks 
ADD COLUMN IF NOT EXISTS current_chunk_info VARCHAR;

-- 添加预计完成时间
ALTER TABLE analysis_tasks 
ADD COLUMN IF NOT EXISTS estimated_completion_at TIMESTAMP WITH TIME ZONE;

-- 添加暂停时间
ALTER TABLE analysis_tasks 
ADD COLUMN IF NOT EXISTS paused_at TIMESTAMP WITH TIME ZONE;

COMMENT ON COLUMN analysis_tasks.execution_mode IS '执行模式: llm_direct(直接调用) | prompt_only(仅生成Prompt) | manual(人工)';
COMMENT ON COLUMN analysis_tasks.total_chunks IS '总分块数';
COMMENT ON COLUMN analysis_tasks.completed_chunks IS '已完成分块数';
COMMENT ON COLUMN analysis_tasks.current_chunk_info IS '当前处理分块信息';

-- ============================================================================
-- 2. 创建 LLM 配置表
-- ============================================================================

CREATE TABLE IF NOT EXISTS llm_configs (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR,                    -- 用户标识（可选）
    provider VARCHAR NOT NULL,          -- openai | anthropic | local | external
    api_key_encrypted TEXT,             -- 加密存储的 API Key（实际使用时需要加密）
    default_model VARCHAR,
    default_temperature NUMERIC(3, 2) DEFAULT 0.3,
    api_base VARCHAR,                   -- 自定义 API 端点
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_llm_configs_user ON llm_configs(user_id);
CREATE INDEX IF NOT EXISTS idx_llm_configs_active ON llm_configs(is_active);

COMMENT ON TABLE llm_configs IS 'LLM 配置表 - 存储用户的 LLM API 配置';
COMMENT ON COLUMN llm_configs.provider IS 'LLM 提供商: openai | anthropic | local | external';

-- ============================================================================
-- 3. 创建任务执行日志表
-- ============================================================================

CREATE TABLE IF NOT EXISTS task_execution_logs (
    id SERIAL PRIMARY KEY,
    task_id INTEGER NOT NULL REFERENCES analysis_tasks(id) ON DELETE CASCADE,
    log_type VARCHAR NOT NULL,          -- start | progress | chunk_complete | error | complete
    message TEXT,
    details JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_task_logs_task ON task_execution_logs(task_id);
CREATE INDEX IF NOT EXISTS idx_task_logs_created ON task_execution_logs(created_at);
CREATE INDEX IF NOT EXISTS idx_task_logs_type ON task_execution_logs(log_type);

COMMENT ON TABLE task_execution_logs IS '任务执行日志表 - 记录任务执行过程';
COMMENT ON COLUMN task_execution_logs.log_type IS '日志类型: start | progress | chunk_complete | error | complete';

-- ============================================================================
-- 4. 创建导出的 Prompt 存储表（可选，用于持久化存储）
-- ============================================================================

CREATE TABLE IF NOT EXISTS exported_prompts (
    id SERIAL PRIMARY KEY,
    task_id INTEGER NOT NULL REFERENCES analysis_tasks(id) ON DELETE CASCADE,
    chunk_index INTEGER NOT NULL,
    prompt_template_id VARCHAR NOT NULL,
    rendered_system TEXT,
    rendered_user TEXT,
    token_estimate INTEGER,
    external_result TEXT,               -- 存储从外部导入的结果
    external_result_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(task_id, chunk_index)
);

CREATE INDEX IF NOT EXISTS idx_exported_prompts_task ON exported_prompts(task_id);

COMMENT ON TABLE exported_prompts IS '导出的 Prompt 表 - 存储生成的 Prompt 和外部导入的结果';

-- ============================================================================
-- 5. 添加 analysis_tasks 的 LLM 配置外键（可选）
-- ============================================================================

ALTER TABLE analysis_tasks 
ADD COLUMN IF NOT EXISTS llm_config_id INTEGER REFERENCES llm_configs(id);

-- ============================================================================
-- 6. 创建索引优化查询性能
-- ============================================================================

-- 任务状态和类型的复合索引
CREATE INDEX IF NOT EXISTS idx_analysis_tasks_status_type 
ON analysis_tasks(status, task_type);

-- 结果审核状态索引
CREATE INDEX IF NOT EXISTS idx_analysis_results_applied 
ON analysis_results(applied) WHERE applied = FALSE;

-- ============================================================================
-- 完成
-- ============================================================================

-- 输出迁移信息
DO $$
BEGIN
    RAISE NOTICE 'LLM Analysis tables migration completed successfully.';
    RAISE NOTICE 'New tables: llm_configs, task_execution_logs, exported_prompts';
    RAISE NOTICE 'Extended: analysis_tasks (execution_mode, chunks tracking)';
END $$;
