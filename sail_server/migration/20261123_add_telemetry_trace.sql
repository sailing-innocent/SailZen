-- =============================================================================
-- Migration: 20261123_add_telemetry_trace.sql
-- Purpose  : Add indexes for SailZen AI Trace & System Profile telemetry tables
--            (tables themselves are created by SQLAlchemy create_all)
-- Safety   : Fully idempotent, additive only (safe for code rollback)
-- =============================================================================

CREATE UNIQUE INDEX IF NOT EXISTS ix_sys_ai_traces_trace_id
    ON sys_ai_traces (trace_id);
CREATE INDEX IF NOT EXISTS ix_sys_ai_traces_svc_started
    ON sys_ai_traces (service, started_at);
CREATE INDEX IF NOT EXISTS ix_sys_ai_traces_status_started
    ON sys_ai_traces (status, started_at);
CREATE INDEX IF NOT EXISTS ix_sys_ai_traces_slot
    ON sys_ai_traces (slot);

CREATE INDEX IF NOT EXISTS ix_sys_ai_trace_spans_trace_seq
    ON sys_ai_trace_spans (trace_id, seq);
CREATE INDEX IF NOT EXISTS ix_sys_ai_trace_spans_stage
    ON sys_ai_trace_spans (stage);

CREATE INDEX IF NOT EXISTS ix_sys_api_metric_buckets_mod_hour
    ON sys_api_metric_buckets (module, bucket_hour);

CREATE INDEX IF NOT EXISTS ix_sys_telemetry_events_cat_created
    ON sys_telemetry_events (category, created_at);
