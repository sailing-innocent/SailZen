-- =============================================================================
-- Migration: 20261124_perf_hot_indexes.sql
-- Purpose  : Add missing hot-path B-tree indexes identified by production
--            telemetry & EXPLAIN profiling (Text / Finance / Rhythm).
-- Safety   : Fully idempotent, additive only (safe for code rollback)
-- =============================================================================

CREATE INDEX IF NOT EXISTS ix_document_nodes_edition_type
    ON document_nodes (edition_id, node_type);

CREATE INDEX IF NOT EXISTS ix_editions_work_id
    ON editions (work_id);

CREATE INDEX IF NOT EXISTS ix_transactions_htime
    ON transactions (htime);

CREATE INDEX IF NOT EXISTS ix_weights_htime
    ON weights (htime);

CREATE INDEX IF NOT EXISTS ix_rhythm_time_blocks_day_status
    ON rhythm_time_blocks (day_id, status);

CREATE INDEX IF NOT EXISTS ix_rhythm_discipline_logs_date_affair
    ON rhythm_discipline_logs (log_date, affair_id);
