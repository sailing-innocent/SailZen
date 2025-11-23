-- 007_create_review_tasks.sql
-- Review tasks for human approval of change sets

CREATE TABLE IF NOT EXISTS review_tasks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    change_set_id UUID NOT NULL REFERENCES change_sets(id) ON DELETE CASCADE,
    reviewer TEXT NOT NULL,  -- user identifier or role
    status TEXT DEFAULT 'pending',  -- 'pending' | 'approved' | 'rejected' | 'cancelled'
    decided_at TIMESTAMPTZ,
    decision TEXT,  -- 'approve' | 'reject' | 'request_changes'
    comments TEXT,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_review_tasks_changeset ON review_tasks(change_set_id);
CREATE INDEX idx_review_tasks_status ON review_tasks(status, reviewer);
CREATE INDEX idx_review_tasks_reviewer ON review_tasks(reviewer, created_at DESC);

COMMENT ON TABLE review_tasks IS 'Human review tasks for change set approval';
COMMENT ON COLUMN review_tasks.reviewer IS 'User identifier or role (e.g., "user:123" or "role:editor")';

