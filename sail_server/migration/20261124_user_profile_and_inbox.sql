-- =============================================================================
-- Migration: 20261124_user_profile_and_inbox.sql
-- Purpose  : Introduce unified UserProfile surface and UserInbox aggregation
--            with monotonic sync_seq for multi-client real-time reconciliation
--            1) user_profiles table + bootstrap default single-user owner (id=1)
--            2) user_inbox_items & user_inbox_events tables + sync_seq sequence
--            3) Additive user_id / inbox_item_id / device metadata columns on
--               devices, reminders, sail_tick_tickets, sail_tick_messages
-- Safety   : Fully idempotent, additive only (Expand-and-Contract)
-- =============================================================================

-- 1. Unified UserProfile table
CREATE TABLE IF NOT EXISTS user_profiles (
    id SERIAL PRIMARY KEY,
    slug VARCHAR(64) NOT NULL UNIQUE,
    display_name VARCHAR(128) NOT NULL DEFAULT 'SailZen Owner',
    avatar_url VARCHAR(512) DEFAULT '',
    role VARCHAR(32) NOT NULL DEFAULT 'owner',
    status VARCHAR(32) NOT NULL DEFAULT 'active',
    is_default BOOLEAN NOT NULL DEFAULT FALSE,
    timezone VARCHAR(64) NOT NULL DEFAULT 'Asia/Shanghai',
    locale VARCHAR(16) NOT NULL DEFAULT 'zh-CN',
    quiet_hours JSONB DEFAULT '{"enabled": true, "start": "23:00", "end": "08:00"}'::jsonb,
    notification_prefs JSONB DEFAULT '{"android_push": true, "web_realtime": true, "auto_resolve_on_domain_action": true, "digest_time": "21:45"}'::jsonb,
    health_profile JSONB DEFAULT '{}'::jsonb,
    preferences JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS ix_user_profiles_status ON user_profiles (status);
CREATE INDEX IF NOT EXISTS ix_user_profiles_is_default ON user_profiles (is_default);

-- Bootstrap default single-user owner (id=1) idempotently
INSERT INTO user_profiles (id, slug, display_name, role, status, is_default, timezone, locale)
VALUES (1, 'owner', 'SailZen Owner', 'owner', 'active', TRUE, 'Asia/Shanghai', 'zh-CN')
ON CONFLICT (slug) DO NOTHING;

-- Advance user_profiles id sequence safely past max(id)
SELECT setval(
    pg_get_serial_sequence('user_profiles', 'id'),
    GREATEST((SELECT COALESCE(MAX(id), 1) FROM user_profiles), 1)
);

-- 2. Monotonic sequence for UserInbox cursor sync
CREATE SEQUENCE IF NOT EXISTS user_inbox_sync_seq START WITH 1 INCREMENT BY 1;

-- 3. Unified UserInbox tables
CREATE TABLE IF NOT EXISTS user_inbox_items (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL DEFAULT 1,
    sync_seq BIGINT NOT NULL DEFAULT 0,
    source_domain VARCHAR(32) NOT NULL DEFAULT 'system',
    item_kind VARCHAR(32) NOT NULL DEFAULT 'notice',
    topic VARCHAR(128) NOT NULL DEFAULT '',
    dedup_key VARCHAR(191) NOT NULL DEFAULT '',
    ref_type VARCHAR(64) NOT NULL DEFAULT '',
    ref_id INTEGER NULL,
    reminder_id INTEGER NULL,
    ticket_id INTEGER NULL,
    title VARCHAR(255) NOT NULL,
    body TEXT DEFAULT '',
    priority VARCHAR(16) NOT NULL DEFAULT 'normal',
    status VARCHAR(24) NOT NULL DEFAULT 'delivered',
    is_read BOOLEAN NOT NULL DEFAULT FALSE,
    read_at TIMESTAMP NULL,
    action_schema JSONB DEFAULT '{}'::jsonb,
    reply_text TEXT NULL,
    resolution_source VARCHAR(64) NOT NULL DEFAULT '',
    resolution_summary VARCHAR(500) NOT NULL DEFAULT '',
    resolution_ref JSONB DEFAULT '{}'::jsonb,
    trigger_at TIMESTAMP NULL,
    snooze_until TIMESTAMP NULL,
    expires_at TIMESTAMP NULL,
    delivered_at TIMESTAMP NULL,
    resolved_at TIMESTAMP NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS ix_inbox_user_seq ON user_inbox_items (user_id, sync_seq);
CREATE INDEX IF NOT EXISTS ix_inbox_user_status_updated ON user_inbox_items (user_id, status, updated_at);
CREATE INDEX IF NOT EXISTS ix_inbox_user_dedup_status ON user_inbox_items (user_id, dedup_key, status);
CREATE INDEX IF NOT EXISTS ix_inbox_ref ON user_inbox_items (ref_type, ref_id);
CREATE INDEX IF NOT EXISTS ix_user_inbox_items_reminder_id ON user_inbox_items (reminder_id);
CREATE INDEX IF NOT EXISTS ix_user_inbox_items_ticket_id ON user_inbox_items (ticket_id);
CREATE INDEX IF NOT EXISTS ix_user_inbox_items_topic ON user_inbox_items (topic);

CREATE TABLE IF NOT EXISTS user_inbox_events (
    id SERIAL PRIMARY KEY,
    inbox_item_id INTEGER NOT NULL REFERENCES user_inbox_items(id) ON DELETE CASCADE,
    user_id INTEGER NOT NULL DEFAULT 1,
    event VARCHAR(32) NOT NULL,
    actor_client VARCHAR(32) NOT NULL DEFAULT 'system',
    device_id VARCHAR(128) NOT NULL DEFAULT '',
    detail JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS ix_user_inbox_events_item_id ON user_inbox_events (inbox_item_id);
CREATE INDEX IF NOT EXISTS ix_user_inbox_events_user_id ON user_inbox_events (user_id);

-- 4. Additive columns on existing tables (zero-breaking Expand-and-Contract)
ALTER TABLE devices ADD COLUMN IF NOT EXISTS user_id INTEGER DEFAULT 1;
ALTER TABLE devices ADD COLUMN IF NOT EXISTS client_type VARCHAR(32) DEFAULT 'android';
ALTER TABLE devices ADD COLUMN IF NOT EXISTS capabilities JSONB DEFAULT '{}'::jsonb;
ALTER TABLE devices ADD COLUMN IF NOT EXISTS is_active BOOLEAN DEFAULT TRUE;
ALTER TABLE devices ADD COLUMN IF NOT EXISTS last_sync_seq BIGINT DEFAULT 0;
CREATE INDEX IF NOT EXISTS ix_devices_user_id ON devices (user_id);

ALTER TABLE reminders ADD COLUMN IF NOT EXISTS user_id INTEGER DEFAULT 1;
ALTER TABLE reminders ADD COLUMN IF NOT EXISTS inbox_item_id INTEGER NULL;
CREATE INDEX IF NOT EXISTS ix_reminders_user_id ON reminders (user_id);
CREATE INDEX IF NOT EXISTS ix_reminders_inbox_item_id ON reminders (inbox_item_id);

ALTER TABLE sail_tick_tickets ADD COLUMN IF NOT EXISTS user_id INTEGER DEFAULT 1;
ALTER TABLE sail_tick_tickets ADD COLUMN IF NOT EXISTS inbox_item_id INTEGER NULL;
CREATE INDEX IF NOT EXISTS ix_sail_tick_tickets_user_id ON sail_tick_tickets (user_id);
CREATE INDEX IF NOT EXISTS ix_sail_tick_tickets_inbox_item_id ON sail_tick_tickets (inbox_item_id);

ALTER TABLE sail_tick_messages ADD COLUMN IF NOT EXISTS user_id INTEGER DEFAULT 1;
CREATE INDEX IF NOT EXISTS ix_sail_tick_messages_user_id ON sail_tick_messages (user_id);

-- Backfill NULL user_id rows to default owner=1
UPDATE devices SET user_id = 1 WHERE user_id IS NULL;
UPDATE reminders SET user_id = 1 WHERE user_id IS NULL;
UPDATE sail_tick_tickets SET user_id = 1 WHERE user_id IS NULL;
UPDATE sail_tick_messages SET user_id = 1 WHERE user_id IS NULL;
