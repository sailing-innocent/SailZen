-- Migration: 添加提醒来源配置表
-- Date: 2026-09-01
-- Author: sailing-innocent
-- Description: 为各提醒来源（rhythm.* / agent / business 等）独立配置通道、默认优先级、
-- 免打扰覆盖策略，支撑 Android 端提醒分级与调度优化。
-- 设计文档: doc/design/android_app/README.md

-- ============================================================================
-- reminder_source_configs 提醒来源配置
-- ============================================================================
CREATE TABLE IF NOT EXISTS reminder_source_configs (
    id SERIAL PRIMARY KEY,
    source VARCHAR(128) NOT NULL,
    source_type VARCHAR(64) DEFAULT '',
    enabled BOOLEAN DEFAULT TRUE,
    default_priority VARCHAR(16) DEFAULT 'normal', -- low | normal | high | urgent
    allowed_channels JSONB DEFAULT '{}',
    quiet_hours_override JSONB,
    description VARCHAR(255) DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_reminder_source_configs_source
    ON reminder_source_configs(source);

CREATE INDEX IF NOT EXISTS idx_reminder_source_configs_source_lookup
    ON reminder_source_configs(source);

-- ============================================================================
-- mtime 自动更新触发器
-- ============================================================================
CREATE OR REPLACE FUNCTION update_reminder_source_config_mtime()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_reminder_source_configs_mtime ON reminder_source_configs;
CREATE TRIGGER trg_reminder_source_configs_mtime
    BEFORE UPDATE ON reminder_source_configs
    FOR EACH ROW EXECUTE FUNCTION update_reminder_source_config_mtime();
