-- =============================================================================
-- Migration: 20261126_content_v2_reading_library.sql
-- Purpose  : Expand-Only schema upgrade for Content 2.0 (Phase 1)
--            1) Extend works with pillar, reading_status, reading_track, priority,
--               source_url, vault_slug, is_original
--            2) Add volume/tree indexes on document_nodes
--            3) Create reading_progress, reading_sessions, content_topics,
--               content_topic_works, content_assets, vault_note_index
-- Safety   : Fully idempotent, additive only (safe for code rollback)
-- =============================================================================

-- 1. works additive columns
ALTER TABLE works ADD COLUMN IF NOT EXISTS pillar VARCHAR(32) DEFAULT 'fiction';
ALTER TABLE works ADD COLUMN IF NOT EXISTS reading_status VARCHAR(24) DEFAULT 'queued';
ALTER TABLE works ADD COLUMN IF NOT EXISTS reading_track VARCHAR(24) DEFAULT 'leisure';
ALTER TABLE works ADD COLUMN IF NOT EXISTS priority INTEGER DEFAULT 3;
ALTER TABLE works ADD COLUMN IF NOT EXISTS source_url VARCHAR(512) NULL;
ALTER TABLE works ADD COLUMN IF NOT EXISTS vault_slug VARCHAR(128) NULL;
ALTER TABLE works ADD COLUMN IF NOT EXISTS is_original BOOLEAN DEFAULT FALSE;

CREATE INDEX IF NOT EXISTS ix_works_pillar ON works (pillar);
CREATE INDEX IF NOT EXISTS ix_works_reading_status ON works (reading_status);
CREATE INDEX IF NOT EXISTS ix_works_reading_track ON works (reading_track);

-- 2. document_nodes hot indexes for volume tree & TOC queries
CREATE INDEX IF NOT EXISTS ix_doc_nodes_edition_type_sort
    ON document_nodes (edition_id, node_type, sort_index);
CREATE INDEX IF NOT EXISTS ix_doc_nodes_edition_parent_sort
    ON document_nodes (edition_id, parent_id, sort_index);

-- 3. reading_progress
CREATE TABLE IF NOT EXISTS reading_progress (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL DEFAULT 1,
    work_id INTEGER NOT NULL REFERENCES works(id) ON DELETE CASCADE,
    edition_id INTEGER NOT NULL REFERENCES editions(id) ON DELETE CASCADE,
    node_id INTEGER NULL REFERENCES document_nodes(id) ON DELETE SET NULL,
    sort_index INTEGER NOT NULL DEFAULT 0,
    char_offset INTEGER NOT NULL DEFAULT 0,
    scroll_offset INTEGER NOT NULL DEFAULT 0,
    page_index INTEGER NOT NULL DEFAULT 0,
    mode VARCHAR(16) NOT NULL DEFAULT 'scroll',
    progress_pct DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    total_read_seconds INTEGER NOT NULL DEFAULT 0,
    client_device VARCHAR(64) DEFAULT '',
    last_read_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_reading_progress_user_work UNIQUE (user_id, work_id)
);

CREATE INDEX IF NOT EXISTS ix_reading_progress_user_last
    ON reading_progress (user_id, last_read_at DESC);

-- 4. reading_sessions
CREATE TABLE IF NOT EXISTS reading_sessions (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL DEFAULT 1,
    work_id INTEGER NOT NULL REFERENCES works(id) ON DELETE CASCADE,
    edition_id INTEGER NOT NULL REFERENCES editions(id) ON DELETE CASCADE,
    start_node_id INTEGER NULL REFERENCES document_nodes(id) ON DELETE SET NULL,
    end_node_id INTEGER NULL REFERENCES document_nodes(id) ON DELETE SET NULL,
    duration_sec INTEGER NOT NULL DEFAULT 0,
    chars_read INTEGER NOT NULL DEFAULT 0,
    source_client VARCHAR(32) DEFAULT 'web',
    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    ended_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS ix_reading_sessions_work_started
    ON reading_sessions (work_id, started_at DESC);
CREATE INDEX IF NOT EXISTS ix_reading_sessions_user_started
    ON reading_sessions (user_id, started_at DESC);

-- 5. content_topics
CREATE TABLE IF NOT EXISTS content_topics (
    id SERIAL PRIMARY KEY,
    slug VARCHAR(128) UNIQUE NOT NULL,
    title VARCHAR(200) NOT NULL,
    description TEXT DEFAULT '',
    pillar VARCHAR(32) DEFAULT 'tech',
    status VARCHAR(24) DEFAULT 'active',
    rhythm_venture_id INTEGER NULL,
    vault_prefix VARCHAR(128) NULL,
    keywords JSONB DEFAULT '[]'::jsonb,
    meta_data JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS ix_content_topics_pillar_status
    ON content_topics (pillar, status);
CREATE INDEX IF NOT EXISTS ix_content_topics_venture
    ON content_topics (rhythm_venture_id);

-- 6. content_topic_works
CREATE TABLE IF NOT EXISTS content_topic_works (
    id SERIAL PRIMARY KEY,
    topic_id INTEGER NOT NULL REFERENCES content_topics(id) ON DELETE CASCADE,
    work_id INTEGER NOT NULL REFERENCES works(id) ON DELETE CASCADE,
    role VARCHAR(24) DEFAULT 'core',
    sort_index INTEGER DEFAULT 0,
    note TEXT DEFAULT '',
    added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_content_topic_work UNIQUE (topic_id, work_id)
);

CREATE INDEX IF NOT EXISTS ix_content_topic_works_topic
    ON content_topic_works (topic_id, sort_index);
CREATE INDEX IF NOT EXISTS ix_content_topic_works_work
    ON content_topic_works (work_id);

-- 7. content_assets
CREATE TABLE IF NOT EXISTS content_assets (
    id SERIAL PRIMARY KEY,
    work_id INTEGER NULL REFERENCES works(id) ON DELETE CASCADE,
    topic_id INTEGER NULL REFERENCES content_topics(id) ON DELETE SET NULL,
    asset_kind VARCHAR(32) DEFAULT 'attachment',
    storage_key VARCHAR(255) NOT NULL,
    original_name VARCHAR(255) NOT NULL,
    mime_type VARCHAR(128) DEFAULT 'application/octet-stream',
    size_bytes INTEGER DEFAULT 0,
    sha256 VARCHAR(64) DEFAULT '',
    meta_data JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS ix_content_assets_work
    ON content_assets (work_id);
CREATE INDEX IF NOT EXISTS ix_content_assets_topic
    ON content_assets (topic_id);

-- 8. vault_note_index
CREATE TABLE IF NOT EXISTS vault_note_index (
    id SERIAL PRIMARY KEY,
    fname VARCHAR(200) UNIQUE NOT NULL,
    namespace VARCHAR(32) DEFAULT 'read',
    title VARCHAR(255) DEFAULT '',
    summary TEXT DEFAULT '',
    tags JSONB DEFAULT '[]'::jsonb,
    links JSONB DEFAULT '[]'::jsonb,
    work_id INTEGER NULL REFERENCES works(id) ON DELETE SET NULL,
    topic_id INTEGER NULL REFERENCES content_topics(id) ON DELETE SET NULL,
    pillar VARCHAR(32) NULL,
    era VARCHAR(64) NULL,
    year_start INTEGER NULL,
    year_end INTEGER NULL,
    content_hash VARCHAR(64) DEFAULT '',
    source_vault VARCHAR(64) DEFAULT 'local',
    synced_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS ix_vault_note_index_ns_pillar
    ON vault_note_index (namespace, pillar);
CREATE INDEX IF NOT EXISTS ix_vault_note_index_work
    ON vault_note_index (work_id);
CREATE INDEX IF NOT EXISTS ix_vault_note_index_topic
    ON vault_note_index (topic_id);
