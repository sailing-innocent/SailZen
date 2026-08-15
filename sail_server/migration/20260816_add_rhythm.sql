-- Migration: 添加 Rhythm（生活/工作节奏综合优先级调节工具）7 张表
-- Date: 2026-08-15
-- Author: sailing-innocent
-- Description: 统一事务（Affair 9 类 kind 双生命周期）、日时间线块、基础节奏模板、
--              戒律/习惯打卡日志、精力画像、守护策略、节奏复盘快照。
--              设计文档: doc/design/manager/rhythm.md

-- ============================================================================
-- rhythm_affairs 统一事务表
-- ============================================================================
CREATE TABLE IF NOT EXISTS rhythm_affairs (
    id SERIAL PRIMARY KEY,
    title VARCHAR(200) NOT NULL,
    description TEXT DEFAULT '',
    domain VARCHAR(16),                       -- life / work / career（generic 可暂空）
    kind VARCHAR(32) NOT NULL DEFAULT 'generic',
    kind_meta JSONB DEFAULT '{}',
    state VARCHAR(16) NOT NULL DEFAULT 'INBOX',
    importance INTEGER DEFAULT 3,
    urgency_ddl TIMESTAMP,
    energy_cost INTEGER DEFAULT 10,
    money_cost NUMERIC(12, 2) DEFAULT 0,
    budget_id INTEGER,                        -- 逻辑引用 finance.budgets(id)
    est_minutes INTEGER DEFAULT 30,
    window_start TIMESTAMP,
    window_end TIMESTAMP,
    splittable BOOLEAN DEFAULT FALSE,
    min_chunk_minutes INTEGER DEFAULT 30,
    fallback_plan TEXT DEFAULT '',
    recurrence_rule_id INTEGER,               -- 逻辑引用 reminder.reminder_rules(id)
    mission_id INTEGER,                       -- 逻辑引用 project.missions(id)
    day_id INTEGER REFERENCES days(id),
    timespan_id INTEGER REFERENCES timespans(id),
    parent_id INTEGER REFERENCES rhythm_affairs(id),
    ai_hint JSONB DEFAULT '{}',
    score NUMERIC(10, 4) DEFAULT 0,
    ref JSONB DEFAULT '{}',
    ctime TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    mtime TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_rhythm_affairs_kind ON rhythm_affairs(kind);
CREATE INDEX IF NOT EXISTS idx_rhythm_affairs_state ON rhythm_affairs(state);
CREATE INDEX IF NOT EXISTS idx_rhythm_affairs_domain ON rhythm_affairs(domain);
CREATE INDEX IF NOT EXISTS idx_rhythm_affairs_day_id ON rhythm_affairs(day_id);

-- ============================================================================
-- rhythm_time_blocks 日时间线块
-- ============================================================================
CREATE TABLE IF NOT EXISTS rhythm_time_blocks (
    id SERIAL PRIMARY KEY,
    day_id INTEGER NOT NULL REFERENCES days(id),
    affair_id INTEGER REFERENCES rhythm_affairs(id),
    block_type VARCHAR(16) NOT NULL,
    start_time TIMESTAMP NOT NULL,
    end_time TIMESTAMP NOT NULL,
    status VARCHAR(16) NOT NULL DEFAULT 'PLANNED',
    pinned BOOLEAN DEFAULT FALSE,
    plan_version INTEGER DEFAULT 1,
    ref JSONB DEFAULT '{}',
    ctime TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    mtime TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_rhythm_time_blocks_day_id ON rhythm_time_blocks(day_id);
CREATE INDEX IF NOT EXISTS idx_rhythm_time_blocks_affair_id ON rhythm_time_blocks(affair_id);
CREATE INDEX IF NOT EXISTS idx_rhythm_time_blocks_type ON rhythm_time_blocks(block_type);
CREATE INDEX IF NOT EXISTS idx_rhythm_time_blocks_status ON rhythm_time_blocks(status);
CREATE INDEX IF NOT EXISTS idx_rhythm_time_blocks_version ON rhythm_time_blocks(plan_version);

-- ============================================================================
-- rhythm_day_templates 基础节奏骨架模板
-- ============================================================================
CREATE TABLE IF NOT EXISTS rhythm_day_templates (
    id SERIAL PRIMARY KEY,
    name VARCHAR(64) NOT NULL UNIQUE,
    description TEXT DEFAULT '',
    weekday_mask JSONB DEFAULT '[]',
    slots JSONB DEFAULT '[]',
    enabled BOOLEAN DEFAULT TRUE,
    priority INTEGER DEFAULT 0,
    ctime TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    mtime TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_rhythm_day_templates_name ON rhythm_day_templates(name);

-- ============================================================================
-- rhythm_discipline_logs 戒律/习惯打卡日志
-- ============================================================================
CREATE TABLE IF NOT EXISTS rhythm_discipline_logs (
    id SERIAL PRIMARY KEY,
    affair_id INTEGER NOT NULL REFERENCES rhythm_affairs(id),
    log_date DATE NOT NULL,
    cycle_key VARCHAR(32) NOT NULL,
    result VARCHAR(16) NOT NULL,              -- kept/violated/exempt/done/missed
    note TEXT DEFAULT '',
    source VARCHAR(16) DEFAULT 'manual',      -- manual/agent/auto
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_rhythm_discipline_logs_affair ON rhythm_discipline_logs(affair_id);
CREATE INDEX IF NOT EXISTS idx_rhythm_discipline_logs_date ON rhythm_discipline_logs(log_date);
CREATE INDEX IF NOT EXISTS idx_rhythm_discipline_logs_cycle ON rhythm_discipline_logs(cycle_key);

-- ============================================================================
-- rhythm_energy_profiles 精力画像（单行配置）
-- ============================================================================
CREATE TABLE IF NOT EXISTS rhythm_energy_profiles (
    id SERIAL PRIMARY KEY,
    name VARCHAR(64) NOT NULL UNIQUE DEFAULT 'default',
    daily_energy_budget INTEGER DEFAULT 100,
    curve_template JSONB DEFAULT '{}',
    sleep_start VARCHAR(8) DEFAULT '23:30',
    sleep_end VARCHAR(8) DEFAULT '07:00',
    work_hours_cap NUMERIC(4, 1) DEFAULT 8.0,
    spare_time_windows JSONB DEFAULT '{}',
    min_buffer_ratio NUMERIC(4, 3) DEFAULT 0.15,
    life_weight NUMERIC(4, 2) DEFAULT 1.0,
    work_weight NUMERIC(4, 2) DEFAULT 1.0,
    career_weight NUMERIC(4, 2) DEFAULT 0.6,
    score_weights JSONB DEFAULT '{}',
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ============================================================================
-- rhythm_policies 节奏守护策略
-- ============================================================================
CREATE TABLE IF NOT EXISTS rhythm_policies (
    id SERIAL PRIMARY KEY,
    name VARCHAR(64) NOT NULL,
    enabled BOOLEAN DEFAULT TRUE,
    rule_type VARCHAR(32) NOT NULL,
    params JSONB DEFAULT '{}',
    scope VARCHAR(8) DEFAULT 'day',
    ctime TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    mtime TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_rhythm_policies_rule_type ON rhythm_policies(rule_type);

-- ============================================================================
-- rhythm_reviews 节奏复盘快照
-- ============================================================================
CREATE TABLE IF NOT EXISTS rhythm_reviews (
    id SERIAL PRIMARY KEY,
    scope VARCHAR(8) NOT NULL,                -- day / week
    period_key VARCHAR(32) NOT NULL,          -- 2026-10-26 / W2026-44
    rhythm_score NUMERIC(6, 2) DEFAULT 0,
    domain_minutes JSONB DEFAULT '{}',
    precept_compliance_rate NUMERIC(5, 4) DEFAULT 0,
    habit_consistency NUMERIC(5, 4) DEFAULT 0,
    sleep_window_keeping NUMERIC(5, 4) DEFAULT 0,
    venture_budget_fulfillment NUMERIC(5, 4) DEFAULT 0,
    buffer_consumed NUMERIC(5, 4) DEFAULT 0,
    encroachments JSONB DEFAULT '[]',
    ai_summary TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_rhythm_reviews_scope ON rhythm_reviews(scope);
CREATE INDEX IF NOT EXISTS idx_rhythm_reviews_period ON rhythm_reviews(period_key);

-- ============================================================================
-- mtime 自动更新触发器
-- ============================================================================
CREATE OR REPLACE FUNCTION update_rhythm_mtime()
RETURNS TRIGGER AS $$
BEGIN
    NEW.mtime = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_rhythm_affairs_mtime ON rhythm_affairs;
CREATE TRIGGER trg_rhythm_affairs_mtime
    BEFORE UPDATE ON rhythm_affairs
    FOR EACH ROW EXECUTE FUNCTION update_rhythm_mtime();

DROP TRIGGER IF EXISTS trg_rhythm_time_blocks_mtime ON rhythm_time_blocks;
CREATE TRIGGER trg_rhythm_time_blocks_mtime
    BEFORE UPDATE ON rhythm_time_blocks
    FOR EACH ROW EXECUTE FUNCTION update_rhythm_mtime();

DROP TRIGGER IF EXISTS trg_rhythm_day_templates_mtime ON rhythm_day_templates;
CREATE TRIGGER trg_rhythm_day_templates_mtime
    BEFORE UPDATE ON rhythm_day_templates
    FOR EACH ROW EXECUTE FUNCTION update_rhythm_mtime();

DROP TRIGGER IF EXISTS trg_rhythm_policies_mtime ON rhythm_policies;
CREATE TRIGGER trg_rhythm_policies_mtime
    BEFORE UPDATE ON rhythm_policies
    FOR EACH ROW EXECUTE FUNCTION update_rhythm_mtime();

DROP TRIGGER IF EXISTS trg_rhythm_energy_profiles_mtime ON rhythm_energy_profiles;
CREATE TRIGGER trg_rhythm_energy_profiles_mtime
    BEFORE UPDATE ON rhythm_energy_profiles
    FOR EACH ROW EXECUTE FUNCTION update_rhythm_mtime();
