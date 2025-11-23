-- 006_create_change_sets.sql
-- Change sets and change items for versioning and audit trail

CREATE TABLE IF NOT EXISTS change_sets (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    edition_id UUID REFERENCES editions(id) ON DELETE CASCADE,
    session_id UUID,  -- nullable, links to collaborative session if applicable
    source TEXT NOT NULL,  -- 'manual' | 'llm_auto' | 'script' | 'collaboration_commit'
    reason TEXT,
    status TEXT DEFAULT 'pending',  -- 'pending' | 'applied' | 'rolled_back' | 'failed'
    created_by TEXT,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    applied_at TIMESTAMPTZ,
    rolled_back_at TIMESTAMPTZ,
    error_message TEXT
);

CREATE INDEX idx_change_sets_edition ON change_sets(edition_id);
CREATE INDEX idx_change_sets_session ON change_sets(session_id) WHERE session_id IS NOT NULL;
CREATE INDEX idx_change_sets_status ON change_sets(status, created_at DESC);

CREATE TABLE IF NOT EXISTS change_items (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    change_set_id UUID NOT NULL REFERENCES change_sets(id) ON DELETE CASCADE,
    target_table TEXT NOT NULL,  -- 'entities' | 'entity_mentions' | 'relations' | etc.
    target_id UUID,              -- ID of the affected row
    operation TEXT NOT NULL,     -- 'insert' | 'update' | 'delete'
    column_name TEXT,            -- for updates, which column changed
    old_value JSONB,             -- previous value (for rollback)
    new_value JSONB,             -- new value
    span_id UUID REFERENCES text_spans(id) ON DELETE SET NULL,
    notes TEXT
);

CREATE INDEX idx_change_items_changeset ON change_items(change_set_id);
CREATE INDEX idx_change_items_target ON change_items(target_table, target_id);
CREATE INDEX idx_change_items_operation ON change_items(operation);

COMMENT ON TABLE change_sets IS 'Groups of changes to be applied atomically';
COMMENT ON TABLE change_items IS 'Individual changes within a change set';
COMMENT ON COLUMN change_items.old_value IS 'Previous value for rollback support';
COMMENT ON COLUMN change_items.new_value IS 'New value to be applied';

