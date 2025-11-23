-- 005_create_annotation_batches.sql
-- Annotation batches and items for LLM suggestions and human drafts

CREATE TABLE IF NOT EXISTS annotation_batches (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    edition_id UUID NOT NULL REFERENCES editions(id) ON DELETE CASCADE,
    session_id UUID,  -- nullable for MVP, can be formalized later
    batch_type TEXT NOT NULL,  -- 'llm_suggestion' | 'human_draft' | 'merged'
    source TEXT NOT NULL,      -- e.g., 'deepseek-chat', 'user@123', 'gpt-4'
    status TEXT DEFAULT 'draft',  -- 'draft' | 'pending' | 'approved' | 'rejected' | 'committed'
    confidence JSONB DEFAULT '{}'::jsonb,  -- aggregate confidence scores
    notes TEXT,
    created_by TEXT,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_annotation_batches_edition ON annotation_batches(edition_id);
CREATE INDEX idx_annotation_batches_session ON annotation_batches(session_id) WHERE session_id IS NOT NULL;
CREATE INDEX idx_annotation_batches_status ON annotation_batches(status, batch_type);

CREATE TABLE IF NOT EXISTS annotation_items (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    batch_id UUID NOT NULL REFERENCES annotation_batches(id) ON DELETE CASCADE,
    target_type TEXT NOT NULL,  -- 'node' | 'span' | 'entity' | 'relation' | 'event'
    target_id UUID,             -- nullable for new entities
    span_id UUID REFERENCES text_spans(id) ON DELETE SET NULL,
    payload JSONB NOT NULL,     -- full entity/relation/event data
    confidence NUMERIC(5,4),    -- 0.0000 to 1.0000
    status TEXT DEFAULT 'pending',  -- 'pending' | 'approved' | 'rejected'
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(batch_id, target_type, target_id, span_id)
);

CREATE INDEX idx_annotation_items_batch ON annotation_items(batch_id, status);
CREATE INDEX idx_annotation_items_target ON annotation_items(target_type, target_id);
CREATE INDEX idx_annotation_items_span ON annotation_items(span_id) WHERE span_id IS NOT NULL;

COMMENT ON TABLE annotation_batches IS 'Batches of annotations from LLM or human drafts';
COMMENT ON TABLE annotation_items IS 'Individual annotation items within a batch';
COMMENT ON COLUMN annotation_items.payload IS 'Full JSON payload of suggested entity/relation/event';

