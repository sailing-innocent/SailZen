-- ============================================================================
-- Text Management Tables Migration
-- @file create_text_tables.sql
-- @brief Creates tables for text/novel content management
-- @author sailing-innocent
-- @date 2025-01-29
-- ============================================================================

-- 注意: 如果使用 SQLAlchemy ORM 的 create_all()，这些表会自动创建
-- 此脚本用于手动迁移或了解表结构

-- 确保启用 pgcrypto 扩展（如果需要 UUID）
-- CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- ============================================================================
-- 1. 作品表 (works)
-- ============================================================================
CREATE TABLE IF NOT EXISTS works (
    id SERIAL PRIMARY KEY,
    slug VARCHAR NOT NULL UNIQUE,
    title VARCHAR NOT NULL,
    original_title VARCHAR,
    author VARCHAR,
    language_primary VARCHAR NOT NULL DEFAULT 'zh',
    work_type VARCHAR DEFAULT 'web_novel',
    status VARCHAR DEFAULT 'ongoing',
    synopsis TEXT,
    meta_data JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_works_title ON works(title);
CREATE INDEX IF NOT EXISTS idx_works_author ON works(author);
CREATE INDEX IF NOT EXISTS idx_works_status ON works(status);

COMMENT ON TABLE works IS '作品表 - 存储小说/书籍的基本信息';
COMMENT ON COLUMN works.slug IS '唯一标识符，用于URL';
COMMENT ON COLUMN works.title IS '作品标题';
COMMENT ON COLUMN works.original_title IS '原文标题（如有翻译）';
COMMENT ON COLUMN works.author IS '作者';
COMMENT ON COLUMN works.language_primary IS '主要语言: zh, en 等';
COMMENT ON COLUMN works.work_type IS '作品类型: web_novel, novel, essay';
COMMENT ON COLUMN works.status IS '状态: ongoing, completed, hiatus';
COMMENT ON COLUMN works.synopsis IS '作品简介';

-- ============================================================================
-- 2. 版本表 (editions)
-- ============================================================================
CREATE TABLE IF NOT EXISTS editions (
    id SERIAL PRIMARY KEY,
    work_id INTEGER NOT NULL REFERENCES works(id) ON DELETE CASCADE,
    edition_name VARCHAR,
    language VARCHAR NOT NULL DEFAULT 'zh',
    source_format VARCHAR DEFAULT 'txt',
    canonical BOOLEAN DEFAULT FALSE,
    source_path VARCHAR,
    source_checksum VARCHAR,
    ingest_version INTEGER DEFAULT 1,
    word_count INTEGER,
    char_count INTEGER,
    description TEXT,
    status VARCHAR DEFAULT 'draft',
    meta_data JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_editions_work_id ON editions(work_id);
CREATE INDEX IF NOT EXISTS idx_editions_status ON editions(status);

COMMENT ON TABLE editions IS '版本表 - 存储作品的不同版本/译本';
COMMENT ON COLUMN editions.work_id IS '所属作品ID';
COMMENT ON COLUMN editions.edition_name IS '版本名称';
COMMENT ON COLUMN editions.language IS '版本语言';
COMMENT ON COLUMN editions.source_format IS '源文件格式: txt, md, epub 等';
COMMENT ON COLUMN editions.canonical IS '是否为标准版本';
COMMENT ON COLUMN editions.source_path IS '原始文件路径';
COMMENT ON COLUMN editions.source_checksum IS '内容校验和';
COMMENT ON COLUMN editions.status IS '状态: draft, active, archived';

-- ============================================================================
-- 3. 文档节点表 (document_nodes)
-- ============================================================================
CREATE TABLE IF NOT EXISTS document_nodes (
    id SERIAL PRIMARY KEY,
    edition_id INTEGER NOT NULL REFERENCES editions(id) ON DELETE CASCADE,
    parent_id INTEGER REFERENCES document_nodes(id) ON DELETE CASCADE,
    node_type VARCHAR NOT NULL,
    sort_index INTEGER NOT NULL,
    depth INTEGER NOT NULL,
    label VARCHAR,
    title VARCHAR,
    raw_text TEXT,
    word_count INTEGER,
    char_count INTEGER,
    path VARCHAR NOT NULL,
    status VARCHAR DEFAULT 'active',
    meta_data JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_document_nodes_edition_id ON document_nodes(edition_id);
CREATE INDEX IF NOT EXISTS idx_document_nodes_parent_id ON document_nodes(parent_id);
CREATE INDEX IF NOT EXISTS idx_document_nodes_type ON document_nodes(edition_id, node_type);
CREATE INDEX IF NOT EXISTS idx_document_nodes_path ON document_nodes(edition_id, path);
CREATE INDEX IF NOT EXISTS idx_document_nodes_sort ON document_nodes(edition_id, sort_index);

COMMENT ON TABLE document_nodes IS '文档节点表 - 树形结构存储文本内容';
COMMENT ON COLUMN document_nodes.edition_id IS '所属版本ID';
COMMENT ON COLUMN document_nodes.parent_id IS '父节点ID（树形结构）';
COMMENT ON COLUMN document_nodes.node_type IS '节点类型: volume, part, chapter, section, paragraph';
COMMENT ON COLUMN document_nodes.sort_index IS '排序索引';
COMMENT ON COLUMN document_nodes.depth IS '节点深度（从0开始）';
COMMENT ON COLUMN document_nodes.label IS '显示标签，如"第一章"';
COMMENT ON COLUMN document_nodes.title IS '标题';
COMMENT ON COLUMN document_nodes.raw_text IS '原始文本内容';
COMMENT ON COLUMN document_nodes.path IS '物化路径，如 "0001.0003"';
COMMENT ON COLUMN document_nodes.status IS '状态: active, deprecated, superseded';

-- ============================================================================
-- 4. 导入作业表 (ingest_jobs)
-- ============================================================================
CREATE TABLE IF NOT EXISTS ingest_jobs (
    id SERIAL PRIMARY KEY,
    edition_id INTEGER NOT NULL REFERENCES editions(id) ON DELETE CASCADE,
    job_type VARCHAR DEFAULT 'initial_import',
    status VARCHAR DEFAULT 'pending',
    payload JSONB DEFAULT '{}'::jsonb,
    started_at TIMESTAMP WITH TIME ZONE,
    finished_at TIMESTAMP WITH TIME ZONE,
    error_message TEXT,
    progress INTEGER DEFAULT 0,
    total_items INTEGER DEFAULT 0,
    processed_items INTEGER DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_ingest_jobs_edition_id ON ingest_jobs(edition_id);
CREATE INDEX IF NOT EXISTS idx_ingest_jobs_status ON ingest_jobs(status);

COMMENT ON TABLE ingest_jobs IS '导入作业表 - 跟踪文本导入任务';
COMMENT ON COLUMN ingest_jobs.job_type IS '作业类型: initial_import, append, reprocess';
COMMENT ON COLUMN ingest_jobs.status IS '状态: pending, running, completed, failed';
COMMENT ON COLUMN ingest_jobs.progress IS '进度百分比 0-100';

-- ============================================================================
-- 更新触发器（可选）
-- ============================================================================

-- 自动更新 updated_at 字段的触发器函数
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

-- 为各表创建更新触发器
DROP TRIGGER IF EXISTS update_works_updated_at ON works;
CREATE TRIGGER update_works_updated_at
    BEFORE UPDATE ON works
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS update_editions_updated_at ON editions;
CREATE TRIGGER update_editions_updated_at
    BEFORE UPDATE ON editions
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS update_document_nodes_updated_at ON document_nodes;
CREATE TRIGGER update_document_nodes_updated_at
    BEFORE UPDATE ON document_nodes
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();
