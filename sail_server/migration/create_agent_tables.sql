-- Migration: Create Agent System Tables
-- Date: 2025-02-25

-- 用户提示表
CREATE TABLE IF NOT EXISTS user_prompts (
    id SERIAL PRIMARY KEY,
    content TEXT NOT NULL,
    prompt_type VARCHAR(50) DEFAULT 'general',
    context JSONB DEFAULT '{}',
    priority INTEGER DEFAULT 5,
    status VARCHAR(50) DEFAULT 'pending',
    created_by VARCHAR(255),
    session_id VARCHAR(255),
    parent_prompt_id INTEGER REFERENCES user_prompts(id) ON DELETE SET NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    scheduled_at TIMESTAMP,
    started_at TIMESTAMP,
    completed_at TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_user_prompts_status ON user_prompts(status);
CREATE INDEX IF NOT EXISTS idx_user_prompts_priority ON user_prompts(priority);
CREATE INDEX IF NOT EXISTS idx_user_prompts_created_at ON user_prompts(created_at);

-- Agent 任务表
CREATE TABLE IF NOT EXISTS agent_tasks (
    id SERIAL PRIMARY KEY,
    prompt_id INTEGER NOT NULL REFERENCES user_prompts(id) ON DELETE CASCADE,
    agent_type VARCHAR(50) DEFAULT 'general',
    agent_config JSONB DEFAULT '{}',
    status VARCHAR(50) DEFAULT 'created',
    progress INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    started_at TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP,
    error_message TEXT,
    error_code VARCHAR(100),
    max_iterations INTEGER DEFAULT 100,
    timeout_seconds INTEGER DEFAULT 3600
);

CREATE INDEX IF NOT EXISTS idx_agent_tasks_status ON agent_tasks(status);
CREATE INDEX IF NOT EXISTS idx_agent_tasks_prompt_id ON agent_tasks(prompt_id);

-- Agent 步骤表
CREATE TABLE IF NOT EXISTS agent_steps (
    id SERIAL PRIMARY KEY,
    task_id INTEGER NOT NULL REFERENCES agent_tasks(id) ON DELETE CASCADE,
    step_number INTEGER NOT NULL,
    step_type VARCHAR(50) NOT NULL,
    title VARCHAR(255),
    content TEXT,
    content_summary VARCHAR(200),
    meta_data JSONB DEFAULT '{}',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    duration_ms INTEGER
);

CREATE INDEX IF NOT EXISTS idx_agent_steps_task_id ON agent_steps(task_id);
CREATE INDEX IF NOT EXISTS idx_agent_steps_step_number ON agent_steps(task_id, step_number);

-- Agent 输出表
CREATE TABLE IF NOT EXISTS agent_outputs (
    id SERIAL PRIMARY KEY,
    task_id INTEGER NOT NULL REFERENCES agent_tasks(id) ON DELETE CASCADE,
    output_type VARCHAR(50) NOT NULL,
    content TEXT,
    file_path VARCHAR(500),
    meta_data JSONB DEFAULT '{}',
    review_status VARCHAR(50) DEFAULT 'pending',
    reviewed_by VARCHAR(255),
    reviewed_at TIMESTAMP,
    review_notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_agent_outputs_task_id ON agent_outputs(task_id);

-- 调度器状态表（单例）
CREATE TABLE IF NOT EXISTS agent_scheduler_state (
    id INTEGER PRIMARY KEY DEFAULT 1 CHECK (id = 1),
    is_running BOOLEAN DEFAULT FALSE,
    last_poll_at TIMESTAMP,
    active_agent_count INTEGER DEFAULT 0,
    max_concurrent_agents INTEGER DEFAULT 3,
    total_processed INTEGER DEFAULT 0,
    total_failed INTEGER DEFAULT 0,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 初始化调度器状态
INSERT INTO agent_scheduler_state (id) VALUES (1) ON CONFLICT DO NOTHING;
