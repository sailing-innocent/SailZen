-- =============================================================================
-- Migration: 20261122_health_sailtick_upgrade.sql
-- Purpose  : Expand-and-Contract schema upgrade for SailTick AI Health Coach
--            1) Extend weight_plans with AI dynamic plan metadata & checkpoints
--            2) Extend sail_tick_tickets with topic & meta JSONB
--            3) Ensure indexes for sail_tick_messages & sail_tick_daily_reports
-- Safety   : Fully idempotent, additive only (safe for code rollback)
-- =============================================================================

-- 1. weight_plans: AI dynamic plan columns
ALTER TABLE weight_plans ADD COLUMN IF NOT EXISTS managed_by VARCHAR DEFAULT 'manual';
ALTER TABLE weight_plans ADD COLUMN IF NOT EXISTS plan_version VARCHAR DEFAULT '';
ALTER TABLE weight_plans ADD COLUMN IF NOT EXISTS phase_name VARCHAR DEFAULT '';
ALTER TABLE weight_plans ADD COLUMN IF NOT EXISTS phase_rationale VARCHAR DEFAULT '';
ALTER TABLE weight_plans ADD COLUMN IF NOT EXISTS focus_notes VARCHAR DEFAULT '';
ALTER TABLE weight_plans ADD COLUMN IF NOT EXISTS daily_targets JSONB DEFAULT '{}'::jsonb;
ALTER TABLE weight_plans ADD COLUMN IF NOT EXISTS tolerance_kg DOUBLE PRECISION DEFAULT 0.5;
ALTER TABLE weight_plans ADD COLUMN IF NOT EXISTS ai_summary VARCHAR DEFAULT '';
ALTER TABLE weight_plans ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP;

-- 2. sail_tick_tickets: topic & meta columns
ALTER TABLE sail_tick_tickets ADD COLUMN IF NOT EXISTS topic VARCHAR DEFAULT '';
ALTER TABLE sail_tick_tickets ADD COLUMN IF NOT EXISTS meta JSONB DEFAULT '{}'::jsonb;

CREATE INDEX IF NOT EXISTS ix_sail_tick_tickets_topic ON sail_tick_tickets (topic);

-- 3. Ensure indexes on new tables (tables themselves are created by SQLAlchemy create_all)
CREATE INDEX IF NOT EXISTS ix_tick_messages_status_created ON sail_tick_messages (status, created_at);
CREATE UNIQUE INDEX IF NOT EXISTS ix_sail_tick_daily_reports_date ON sail_tick_daily_reports (report_date);
