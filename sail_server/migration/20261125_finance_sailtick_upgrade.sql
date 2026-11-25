-- =============================================================================
-- Migration: 20261125_finance_sailtick_upgrade.sql
-- Purpose  : Expand-Only schema upgrade for Finance 2.0 (SailTick Secretary)
--            1) Extend transactions with entry_kind, exclude_from_stats, meta JSONB
--            2) Extend accounts with meta JSONB
--            3) Create finance_balance_checkpoints & finance_hygiene_proposals tables
--            4) Ensure hot indexes for hygiene queries & stats filtering
-- Safety   : Fully idempotent, additive only (safe for code rollback)
-- =============================================================================

-- 1. transactions additive columns
ALTER TABLE transactions ADD COLUMN IF NOT EXISTS entry_kind VARCHAR DEFAULT 'normal';
ALTER TABLE transactions ADD COLUMN IF NOT EXISTS exclude_from_stats BOOLEAN DEFAULT FALSE;
ALTER TABLE transactions ADD COLUMN IF NOT EXISTS meta JSONB DEFAULT '{}'::jsonb;

CREATE INDEX IF NOT EXISTS ix_transactions_exclude_htime
    ON transactions (exclude_from_stats, htime DESC);

CREATE INDEX IF NOT EXISTS ix_transactions_entry_kind
    ON transactions (entry_kind);

-- 2. accounts additive column
ALTER TABLE accounts ADD COLUMN IF NOT EXISTS meta JSONB DEFAULT '{}'::jsonb;

-- 3. finance_balance_checkpoints
CREATE TABLE IF NOT EXISTS finance_balance_checkpoints (
    id SERIAL PRIMARY KEY,
    account_id INTEGER NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
    reported_balance VARCHAR NOT NULL,
    book_balance VARCHAR NOT NULL,
    drift_amount VARCHAR NOT NULL DEFAULT '0.00',
    handling VARCHAR NOT NULL DEFAULT 'exact',
    adjustment_tx_id INTEGER NULL REFERENCES transactions(id) ON DELETE SET NULL,
    note VARCHAR DEFAULT '',
    source VARCHAR DEFAULT 'manual',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS ix_finance_checkpoints_acc_created
    ON finance_balance_checkpoints (account_id, created_at DESC);

-- 4. finance_hygiene_proposals
CREATE TABLE IF NOT EXISTS finance_hygiene_proposals (
    id SERIAL PRIMARY KEY,
    proposal_type VARCHAR NOT NULL,
    autonomy_level VARCHAR NOT NULL DEFAULT 'needs_review',
    status VARCHAR NOT NULL DEFAULT 'pending',
    target_tx_ids JSONB DEFAULT '[]'::jsonb,
    confidence DOUBLE PRECISION DEFAULT 0.0,
    title VARCHAR NOT NULL,
    reason VARCHAR DEFAULT '',
    before_snapshot JSONB DEFAULT '{}'::jsonb,
    after_payload JSONB DEFAULT '{}'::jsonb,
    created_by VARCHAR DEFAULT 'sailtick',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    resolved_at TIMESTAMP NULL
);

CREATE INDEX IF NOT EXISTS ix_finance_hygiene_status_created
    ON finance_hygiene_proposals (status, created_at DESC);

CREATE INDEX IF NOT EXISTS ix_finance_hygiene_type_status
    ON finance_hygiene_proposals (proposal_type, status);
