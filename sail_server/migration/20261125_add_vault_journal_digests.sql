-- =============================================================================
-- Migration: 20261125_add_vault_journal_digests.sql
-- Purpose  : Create vault_journal_digests table for SailTick <-> Local Vault
--            lightweight read-only journal context bridge (Phase 2)
-- Safety   : Fully idempotent, additive only
-- =============================================================================

CREATE TABLE IF NOT EXISTS vault_journal_digests (
    id SERIAL PRIMARY KEY,
    note_date VARCHAR NOT NULL UNIQUE,
    filename VARCHAR DEFAULT '',
    title VARCHAR DEFAULT '',
    summary VARCHAR DEFAULT '',
    excerpt VARCHAR DEFAULT '',
    mood_hints JSONB DEFAULT '[]'::jsonb,
    travel_hints JSONB DEFAULT '[]'::jsonb,
    spend_context_hints JSONB DEFAULT '[]'::jsonb,
    tags JSONB DEFAULT '[]'::jsonb,
    content_hash VARCHAR DEFAULT '',
    source_vault VARCHAR DEFAULT 'local',
    synced_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE UNIQUE INDEX IF NOT EXISTS ix_vault_journal_digests_note_date
    ON vault_journal_digests (note_date);
CREATE INDEX IF NOT EXISTS ix_vault_journal_digests_hash
    ON vault_journal_digests (content_hash);
