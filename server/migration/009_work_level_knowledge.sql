-- Migration 009: Work-Level Knowledge Management
-- This migration enables work-level knowledge (entities, relations, events, collections)
-- independent of specific editions, supporting "from-scratch" creative workflows.

-- ============================================================================
-- STEP 1: Alter existing tables to support work-level knowledge
-- ============================================================================

-- Make edition_id nullable in entities table (work-level entities don't need edition)
ALTER TABLE entities ALTER COLUMN edition_id DROP NOT NULL;

-- Make origin_span_id nullable in entities table (work-level entities created from scratch)
ALTER TABLE entities ALTER COLUMN origin_span_id DROP NOT NULL;

-- Make edition_id nullable in entity_relations table
ALTER TABLE entity_relations ALTER COLUMN edition_id DROP NOT NULL;

-- Ensure work_id columns have proper indexes (may already exist)
CREATE INDEX IF NOT EXISTS idx_entities_work ON entities(work_id);
CREATE INDEX IF NOT EXISTS idx_entity_relations_work ON entity_relations(work_id);

-- ============================================================================
-- STEP 2: Create narrative_events table
-- ============================================================================

CREATE TABLE narrative_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    work_id UUID NOT NULL REFERENCES works(id) ON DELETE CASCADE,
    edition_id UUID REFERENCES editions(id) ON DELETE SET NULL,
    title TEXT NOT NULL,
    event_type TEXT DEFAULT 'plot_point', -- plot_point | backstory | foreshadow | climax | resolution
    summary TEXT,
    start_span_id UUID REFERENCES text_spans(id) ON DELETE SET NULL,
    end_span_id UUID REFERENCES text_spans(id) ON DELETE SET NULL,
    parent_id UUID REFERENCES narrative_events(id) ON DELETE SET NULL,
    chronology_order NUMERIC(10,2),
    importance TEXT DEFAULT 'major', -- major | minor | background
    status TEXT DEFAULT 'draft', -- draft | verified | deprecated
    meta_data JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for narrative_events
CREATE INDEX idx_narrative_events_work ON narrative_events(work_id);
CREATE INDEX idx_narrative_events_edition ON narrative_events(edition_id);
CREATE INDEX idx_narrative_events_parent ON narrative_events(parent_id);
CREATE INDEX idx_narrative_events_type ON narrative_events(event_type);
CREATE INDEX idx_narrative_events_chronology ON narrative_events(chronology_order);

-- ============================================================================
-- STEP 3: Create event_participants table
-- ============================================================================

CREATE TABLE event_participants (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    event_id UUID NOT NULL REFERENCES narrative_events(id) ON DELETE CASCADE,
    entity_id UUID NOT NULL REFERENCES entities(id) ON DELETE CASCADE,
    role TEXT DEFAULT 'participant', -- protagonist | antagonist | witness | victim | helper
    contribution TEXT,
    span_id UUID REFERENCES text_spans(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(event_id, entity_id, role)
);

-- Indexes for event_participants
CREATE INDEX idx_event_participants_event ON event_participants(event_id);
CREATE INDEX idx_event_participants_entity ON event_participants(entity_id);

-- ============================================================================
-- STEP 4: Create knowledge_collections table
-- ============================================================================

CREATE TABLE knowledge_collections (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    work_id UUID NOT NULL REFERENCES works(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    collection_type TEXT NOT NULL, -- character_arc | plotline | theme | location_group | faction
    description TEXT,
    meta_data JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(work_id, collection_type, name)
);

-- Indexes for knowledge_collections
CREATE INDEX idx_knowledge_collections_work ON knowledge_collections(work_id);
CREATE INDEX idx_knowledge_collections_type ON knowledge_collections(collection_type);

-- ============================================================================
-- STEP 5: Create collection_items table
-- ============================================================================

CREATE TABLE collection_items (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    collection_id UUID NOT NULL REFERENCES knowledge_collections(id) ON DELETE CASCADE,
    target_type TEXT NOT NULL, -- entity | relation | narrative_event
    target_id UUID NOT NULL,
    sort_order INTEGER,
    role_in_collection TEXT, -- e.g., "arc_beginning", "key_moment", "resolution"
    notes TEXT,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (collection_id, target_type, target_id)
);

-- Indexes for collection_items
CREATE INDEX idx_collection_items_collection ON collection_items(collection_id);
CREATE INDEX idx_collection_items_target ON collection_items(target_type, target_id);
CREATE INDEX idx_collection_items_order ON collection_items(collection_id, sort_order);

-- ============================================================================
-- Migration complete
-- ============================================================================

