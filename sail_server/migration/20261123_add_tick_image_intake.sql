-- =============================================================================
-- Migration: 20261123_add_tick_image_intake.sql
-- Purpose  : Add sail_tick_intake_drafts table for SailTick universal image
--            intake (DeepSeek Vision/OCR -> human confirmation -> DB commit)
-- Safety   : Fully idempotent, additive only (safe for code rollback)
-- =============================================================================

CREATE TABLE IF NOT EXISTS sail_tick_intake_drafts (
    id SERIAL PRIMARY KEY,
    status VARCHAR DEFAULT 'pending_confirm',
    source_channel VARCHAR DEFAULT 'android',
    ticket_id INTEGER NULL,
    media_key VARCHAR NOT NULL,
    media_mime VARCHAR DEFAULT 'image/jpeg',
    media_size INTEGER DEFAULT 0,
    original_filename VARCHAR DEFAULT '',
    user_note VARCHAR DEFAULT '',
    scene VARCHAR DEFAULT 'general',
    summary VARCHAR DEFAULT '',
    coach_advice VARCHAR DEFAULT '',
    ocr_text VARCHAR DEFAULT '',
    entries JSONB DEFAULT '[]'::jsonb,
    committed_refs JSONB DEFAULT '[]'::jsonb,
    model_used VARCHAR DEFAULT 'deepseek-flash',
    usage JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    committed_at TIMESTAMP NULL
);

CREATE INDEX IF NOT EXISTS ix_sail_tick_intake_drafts_status
    ON sail_tick_intake_drafts (status);
CREATE INDEX IF NOT EXISTS ix_sail_tick_intake_drafts_scene
    ON sail_tick_intake_drafts (scene);
CREATE INDEX IF NOT EXISTS ix_sail_tick_intake_drafts_ticket_id
    ON sail_tick_intake_drafts (ticket_id);
CREATE INDEX IF NOT EXISTS ix_tick_intake_drafts_status_created
    ON sail_tick_intake_drafts (status, created_at);
