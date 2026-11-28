-- =============================================================================
-- 20261128_sailtick_domain_routing.sql
-- SailTick Round 2: 消息类型 × 业务域/交互角色 × 多端分流增量迁移（Expand-Only 幂等）
-- =============================================================================

-- 1. sail_tick_tickets 增量列与索引
ALTER TABLE sail_tick_tickets ADD COLUMN IF NOT EXISTS domain VARCHAR(32) DEFAULT 'general';
ALTER TABLE sail_tick_tickets ADD COLUMN IF NOT EXISTS persona VARCHAR(32) DEFAULT '';
ALTER TABLE sail_tick_tickets ADD COLUMN IF NOT EXISTS target_clients JSONB DEFAULT '[]'::jsonb;
ALTER TABLE sail_tick_tickets ADD COLUMN IF NOT EXISTS deep_link VARCHAR(128) DEFAULT '';

CREATE INDEX IF NOT EXISTS ix_tick_tickets_domain_status
    ON sail_tick_tickets (domain, status);

-- 2. sail_tick_messages 增量列
ALTER TABLE sail_tick_messages ADD COLUMN IF NOT EXISTS domain VARCHAR(32) DEFAULT 'general';
ALTER TABLE sail_tick_messages ADD COLUMN IF NOT EXISTS surface VARCHAR(32) DEFAULT '';

-- 3. sail_tick_daily_reports 分节结构化内容列
ALTER TABLE sail_tick_daily_reports ADD COLUMN IF NOT EXISTS sections JSONB DEFAULT '{}'::jsonb;

-- 4. user_inbox_items 增量分流列与索引
ALTER TABLE user_inbox_items ADD COLUMN IF NOT EXISTS target_domain VARCHAR(32) NOT NULL DEFAULT '';
ALTER TABLE user_inbox_items ADD COLUMN IF NOT EXISTS persona VARCHAR(32) NOT NULL DEFAULT '';
ALTER TABLE user_inbox_items ADD COLUMN IF NOT EXISTS target_clients JSONB DEFAULT '[]'::jsonb;

CREATE INDEX IF NOT EXISTS ix_inbox_user_target_domain
    ON user_inbox_items (user_id, target_domain, status);

-- 5. 存量历史票据按 topic 幂等回填（仅更新仍为空或默认 general 的记录）
UPDATE sail_tick_tickets
SET domain = 'health', persona = 'health_coach',
    target_clients = '["android","web"]'::jsonb,
    deep_link = '/health/coach?ticket=' || id
WHERE (domain IS NULL OR domain = '' OR domain = 'general')
  AND (
      lower(coalesce(topic, '')) LIKE 'diet%'
      OR lower(coalesce(topic, '')) LIKE 'weight%'
      OR lower(coalesce(topic, '')) LIKE 'sleep%'
      OR lower(coalesce(topic, '')) LIKE 'exercise%'
      OR lower(coalesce(topic, '')) IN ('canteen', 'lunch_source', 'dinner_habit', 'gym_access', 'height', 'current_weight', 'morning_weight')
  );

UPDATE sail_tick_tickets
SET domain = 'rhythm', persona = 'rhythm_planner',
    target_clients = '["android","web","vscode"]'::jsonb,
    deep_link = '/plan?ticket=' || id
WHERE (domain IS NULL OR domain = '' OR domain = 'general')
  AND (
      lower(coalesce(topic, '')) LIKE 'rhythm%'
      OR lower(coalesce(topic, '')) LIKE 'project%'
      OR lower(coalesce(topic, '')) LIKE 'schedule%'
      OR lower(coalesce(topic, '')) LIKE 'focus%'
      OR lower(coalesce(topic, '')) IN ('wake_time', 'profile_wake_time', 'spare_time_preference')
  );

UPDATE sail_tick_tickets
SET domain = 'finance', persona = 'finance_secretary',
    target_clients = '["android","web"]'::jsonb,
    deep_link = '/money?ticket=' || id
WHERE (domain IS NULL OR domain = '' OR domain = 'general')
  AND (
      lower(coalesce(topic, '')) LIKE 'finance%'
      OR lower(coalesce(topic, '')) LIKE 'bill%'
      OR lower(coalesce(topic, '')) LIKE 'budget%'
      OR lower(coalesce(topic, '')) LIKE 'reconcile%'
  );

-- 6. 同步回填 user_inbox_items 的 target_domain 与 persona
UPDATE user_inbox_items u
SET target_domain = t.domain,
    persona = t.persona,
    target_clients = t.target_clients
FROM sail_tick_tickets t
WHERE u.ticket_id = t.id
  AND (u.target_domain IS NULL OR u.target_domain = '')
  AND t.domain IS NOT NULL AND t.domain <> '';

UPDATE user_inbox_items
SET target_domain = CASE
        WHEN source_domain IN ('health', 'rhythm', 'finance') THEN source_domain
        ELSE 'general'
    END,
    persona = CASE
        WHEN source_domain = 'health' THEN 'health_coach'
        WHEN source_domain = 'rhythm' THEN 'rhythm_planner'
        WHEN source_domain = 'finance' THEN 'finance_secretary'
        ELSE 'chief_steward'
    END
WHERE target_domain IS NULL OR target_domain = '';
