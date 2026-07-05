-- Migration: 添加 note_items 表，支持 Markdown 笔记索引
-- Date: 2026-08-06
-- Author: sailing-innocent
-- Description: 为文本/创作笔记管理提供轻量级数据库索引

CREATE TABLE IF NOT EXISTS note_items (
    id SERIAL PRIMARY KEY,
    category VARCHAR NOT NULL,
    setting_file VARCHAR NOT NULL,
    work_id INTEGER REFERENCES works(id) ON DELETE SET NULL,
    edition_id INTEGER REFERENCES editions(id) ON DELETE SET NULL,
    title VARCHAR,
    slug VARCHAR UNIQUE,
    meta_data JSONB DEFAULT '{}',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_note_items_category ON note_items(category);
CREATE INDEX IF NOT EXISTS idx_note_items_work_id ON note_items(work_id);
CREATE INDEX IF NOT EXISTS idx_note_items_edition_id ON note_items(edition_id);

-- 自动更新 updated_at 触发器（PostgreSQL）
CREATE OR REPLACE FUNCTION update_note_items_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_note_items_updated_at ON note_items;
CREATE TRIGGER trg_note_items_updated_at
    BEFORE UPDATE ON note_items
    FOR EACH ROW
    EXECUTE FUNCTION update_note_items_updated_at();
