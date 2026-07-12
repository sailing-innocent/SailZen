-- Migration: 添加 Day 与 TimeSpan 基础时间表
-- Date: 2026-03-01
-- Author: sailing-innocent
-- Description: 为生活时间管理提供自然日（Day）与通用时间节点（TimeSpan）存储

-- 自然日表
CREATE TABLE IF NOT EXISTS days (
    id SERIAL PRIMARY KEY,
    date DATE NOT NULL UNIQUE,
    ref JSONB DEFAULT '{}',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_days_date ON days(date);

-- 通用时间节点表
CREATE TABLE IF NOT EXISTS timespans (
    id SERIAL PRIMARY KEY,
    class VARCHAR(32) NOT NULL,
    name VARCHAR(64) NOT NULL,
    start_day_id INTEGER NOT NULL REFERENCES days(id),
    end_day_id INTEGER NOT NULL REFERENCES days(id),
    child_span_ids INTEGER[] DEFAULT '{}',
    ref JSONB DEFAULT '{}',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_timespans_class_name UNIQUE (class, name),
    CONSTRAINT chk_timespans_start_end CHECK (start_day_id <= end_day_id)
);

CREATE INDEX IF NOT EXISTS idx_timespans_class ON timespans(class);
CREATE INDEX IF NOT EXISTS idx_timespans_name ON timespans(name);
CREATE INDEX IF NOT EXISTS idx_timespans_start_day_id ON timespans(start_day_id);
CREATE INDEX IF NOT EXISTS idx_timespans_end_day_id ON timespans(end_day_id);
CREATE INDEX IF NOT EXISTS idx_timespans_class_name ON timespans(class, name);

-- 自动更新 days.updated_at 触发器
CREATE OR REPLACE FUNCTION update_days_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_days_updated_at ON days;
CREATE TRIGGER trg_days_updated_at
    BEFORE UPDATE ON days
    FOR EACH ROW
    EXECUTE FUNCTION update_days_updated_at();

-- 自动更新 timespans.updated_at 触发器
CREATE OR REPLACE FUNCTION update_timespans_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_timespans_updated_at ON timespans;
CREATE TRIGGER trg_timespans_updated_at
    BEFORE UPDATE ON timespans
    FOR EACH ROW
    EXECUTE FUNCTION update_timespans_updated_at();
