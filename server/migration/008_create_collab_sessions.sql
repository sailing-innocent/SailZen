-- 008_create_collab_sessions.sql
-- Optional dedicated table for collaborative editing sessions
-- This provides explicit session tracking beyond annotation_batches

CREATE TABLE IF NOT EXISTS collab_sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    edition_id UUID NOT NULL REFERENCES editions(id) ON DELETE CASCADE,
    target_type TEXT NOT NULL,  -- 'node' | 'entity' | 'relation' | 'event'
    target_id UUID NOT NULL,    -- ID of the target being edited
    lock_scope TEXT DEFAULT 'node',  -- 'node' | 'entity' | 'span' | 'edition'
    state TEXT DEFAULT 'active',  -- 'active' | 'has_draft' | 'committed' | 'closed' | 'needs_merge'
    state_reason TEXT,
    meta_data JSONB DEFAULT '{}'::jsonb,  -- additional context, UI state
    created_by TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    closed_at TIMESTAMPTZ
);

CREATE INDEX idx_collab_sessions_edition ON collab_sessions(edition_id);
CREATE INDEX idx_collab_sessions_target ON collab_sessions(target_type, target_id);
CREATE INDEX idx_collab_sessions_state ON collab_sessions(state, created_by);
CREATE INDEX idx_collab_sessions_active ON collab_sessions(edition_id, state) 
    WHERE state IN ('active', 'has_draft');

-- Add session_id foreign key to annotation_batches if not exists
DO $$ 
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.table_constraints 
        WHERE constraint_name = 'annotation_batches_session_id_fkey'
    ) THEN
        ALTER TABLE annotation_batches 
        ADD CONSTRAINT annotation_batches_session_id_fkey 
        FOREIGN KEY (session_id) REFERENCES collab_sessions(id) ON DELETE CASCADE;
    END IF;
END $$;

-- Add session_id foreign key to change_sets if not exists
DO $$ 
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.table_constraints 
        WHERE constraint_name = 'change_sets_session_id_fkey'
    ) THEN
        ALTER TABLE change_sets 
        ADD CONSTRAINT change_sets_session_id_fkey 
        FOREIGN KEY (session_id) REFERENCES collab_sessions(id) ON DELETE SET NULL;
    END IF;
END $$;

COMMENT ON TABLE collab_sessions IS 'Collaborative editing sessions for tracking human-LLM interaction';
COMMENT ON COLUMN collab_sessions.lock_scope IS 'Granularity of edit lock';
COMMENT ON COLUMN collab_sessions.state IS 'Current state of the session';
COMMENT ON COLUMN collab_sessions.meta_data IS 'Additional context and UI state';

