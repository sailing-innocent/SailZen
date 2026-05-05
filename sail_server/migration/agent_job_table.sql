-- Migration: Add Agent Job tables for Shadow Agent
-- Run: uv run sail_server/migration/agent_job_table.sql
-- Or execute via your preferred DB client

CREATE TABLE IF NOT EXISTS agent_jobs (
    id              SERIAL PRIMARY KEY,
    job_type        VARCHAR(64) NOT NULL,
    status          VARCHAR(32) DEFAULT 'pending',
    params          JSONB DEFAULT '{}',
    result          JSONB DEFAULT NULL,
    error_message   TEXT,
    auto_approved   BOOLEAN DEFAULT FALSE,
    created_by      VARCHAR(32) DEFAULT 'system',
    started_at      TIMESTAMP,
    completed_at    TIMESTAMP,
    ctime           TIMESTAMP DEFAULT NOW(),
    mtime           TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_agent_jobs_status ON agent_jobs(status);
CREATE INDEX IF NOT EXISTS idx_agent_jobs_type ON agent_jobs(job_type);
CREATE INDEX IF NOT EXISTS idx_agent_jobs_ctime ON agent_jobs(ctime DESC);

CREATE TABLE IF NOT EXISTS sail_configs (
    key   VARCHAR(128) PRIMARY KEY,
    value JSONB NOT NULL,
    mtime TIMESTAMP DEFAULT NOW()
);

-- Seed default config
INSERT INTO sail_configs (key, value) VALUES ('agent_enabled', 'true')
ON CONFLICT (key) DO NOTHING;
