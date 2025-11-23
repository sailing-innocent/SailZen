-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- Universes: Shared worldview across multiple works
CREATE TABLE universes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    slug TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    description TEXT,
    meta_data JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

-- Works: Individual novels/stories
CREATE TABLE works (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    slug TEXT UNIQUE NOT NULL,
    title TEXT NOT NULL,
    original_title TEXT,
    author TEXT,
    language_primary TEXT NOT NULL,
    work_type TEXT DEFAULT 'web_novel',
    status TEXT DEFAULT 'ongoing', -- ongoing | completed | hiatus
    synopsis TEXT,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

-- Universe memberships: Link works to universes
CREATE TABLE universe_memberships (
    universe_id UUID NOT NULL REFERENCES universes(id) ON DELETE CASCADE,
    work_id UUID NOT NULL REFERENCES works(id) ON DELETE CASCADE,
    membership_role TEXT DEFAULT 'primary', -- primary | side_story | cameo
    notes TEXT,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (universe_id, work_id)
);

-- Work aliases: Alternative names for works
CREATE TABLE work_aliases (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    work_id UUID NOT NULL REFERENCES works(id) ON DELETE CASCADE,
    alias TEXT NOT NULL,
    language TEXT,
    alias_type TEXT DEFAULT 'title', -- title | tag | abbreviation
    is_primary BOOLEAN DEFAULT FALSE,
    UNIQUE(work_id, alias)
);

-- Editions: Different versions/translations of works
CREATE TABLE editions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    work_id UUID NOT NULL REFERENCES works(id) ON DELETE CASCADE,
    edition_name TEXT,
    language TEXT NOT NULL,
    source_format TEXT DEFAULT 'txt',
    canonical BOOLEAN DEFAULT FALSE,
    source_path TEXT,
    source_checksum TEXT,
    ingest_version INTEGER DEFAULT 1,
    publication_year INTEGER,
    word_count INTEGER,
    description TEXT,
    status TEXT DEFAULT 'draft', -- draft | active | archived
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(work_id, language, ingest_version)
);

-- Edition files: Storage references for edition source files
CREATE TABLE edition_files (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    edition_id UUID NOT NULL REFERENCES editions(id) ON DELETE CASCADE,
    file_role TEXT DEFAULT 'source', -- source | cleaned | tokenized
    storage_uri TEXT NOT NULL,
    checksum TEXT,
    byte_length BIGINT,
    encoding TEXT,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

-- Edition tags: Tag system for editions
CREATE TABLE edition_tags (
    edition_id UUID NOT NULL REFERENCES editions(id) ON DELETE CASCADE,
    tag TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (edition_id, tag)
);

-- Create indexes
CREATE INDEX idx_works_slug ON works(slug);
CREATE INDEX idx_works_status ON works(status);
CREATE INDEX idx_editions_work ON editions(work_id);
CREATE INDEX idx_editions_status ON editions(status);

