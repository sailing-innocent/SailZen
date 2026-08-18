-- -*- coding: utf-8 -*-
-- @file 20260818_migrate_project_to_affair.sql
-- @brief Phase 1：projects / milestones / missions 复制进 rhythm_affairs（统一事务模型）
-- @author sailing-innocent
-- @date 2026-08-18
-- @version 1.0
-- ---------------------------------
--
-- 设计说明见 doc/maintain/ProjectToAffairMigration.md
--
-- 幂等保证：每行迁移产物在 ref 内写入 {"migrated_from": <table>, "legacy_id": <id>}，
-- 重复执行时通过 NOT EXISTS 跳过。本脚本只写 rhythm_affairs，不修改旧表。

BEGIN;

-- ---------------------------------------------------------------------------
-- 0. 迁移溯源索引（加速幂等判断与后续回查）
-- ---------------------------------------------------------------------------
CREATE INDEX IF NOT EXISTS ix_rhythm_affairs_migrated
    ON rhythm_affairs ((ref ->> 'migrated_from'), (ref ->> 'legacy_id'));

-- ---------------------------------------------------------------------------
-- 1. projects → affair(kind=venture, domain=career)
--    state 映射：PREPARE(2)/VALID(1) → INBOX，TRACKING(3) → ACTIVE，
--                PENDING(4) → PAUSED，DONE(5) → DONE，CANCELED(6)/INVALID(0) → ARCHIVED
--    kind_meta：target_date 取 timespan 结束日；weekly_budget_hours 默认 6；
--               spare_time_only 默认 true；total_est_hours 由子任务 planned_minutes 汇总
-- ---------------------------------------------------------------------------
INSERT INTO rhythm_affairs (
    title, description, domain, kind, kind_meta, state,
    importance, energy_cost, est_minutes, timespan_id, ref, ctime, mtime
)
SELECT
    COALESCE(p.name, '未命名项目'),
    COALESCE(p.description, ''),
    'career',
    'venture',
    jsonb_build_object(
        'target_date', to_char(d.date, 'YYYY-MM-DD'),
        'weekly_budget_hours', 6,
        'spare_time_only', true,
        'total_est_hours', ROUND(COALESCE(m_agg.total_minutes, 0) / 60.0, 2)
    ),
    CASE p.state
        WHEN 3 THEN 'ACTIVE'
        WHEN 4 THEN 'PAUSED'
        WHEN 5 THEN 'DONE'
        WHEN 6 THEN 'ARCHIVED'
        WHEN 0 THEN 'ARCHIVED'
        ELSE 'INBOX'
    END,
    3,
    10,
    30,
    p.timespan_id,
    jsonb_build_object(
        'migrated_from', 'projects',
        'legacy_id', p.id,
        'legacy_state', p.state,
        'start_time_qbw', p.start_time_qbw,
        'end_time_qbw', p.end_time_qbw
    ),
    COALESCE(p.ctime, current_timestamp),
    COALESCE(p.mtime, current_timestamp)
FROM projects p
LEFT JOIN timespans ts ON ts.id = p.timespan_id
LEFT JOIN days d ON d.id = ts.end_day_id
LEFT JOIN (
    SELECT project_id, SUM(COALESCE(planned_minutes, 0)) AS total_minutes
    FROM missions
    GROUP BY project_id
) m_agg ON m_agg.project_id = p.id
WHERE NOT EXISTS (
    SELECT 1 FROM rhythm_affairs a
    WHERE a.ref ->> 'migrated_from' = 'projects'
      AND a.ref ->> 'legacy_id' = p.id::text
);

-- ---------------------------------------------------------------------------
-- 2. milestones → affair(kind=task_oneoff, parent = venture affair)
--    state 映射：0 pending → PLANNED，1 done → DONE，2 skipped → CANCELED
--    urgency_ddl 取 day 锚点当日 23:59:59
-- ---------------------------------------------------------------------------
INSERT INTO rhythm_affairs (
    title, description, domain, kind, kind_meta, state,
    importance, urgency_ddl, energy_cost, est_minutes, day_id, parent_id, ref, ctime, mtime
)
SELECT
    COALESCE(ms.name, '未命名里程碑'),
    COALESCE(ms.description, ''),
    'career',
    'task_oneoff',
    '{}'::jsonb,
    CASE ms.state WHEN 1 THEN 'DONE' WHEN 2 THEN 'CANCELED' ELSE 'PLANNED' END,
    4,
    CASE WHEN d.date IS NULL THEN NULL ELSE (d.date + TIME '23:59:59') END,
    COALESCE(ms.energy_weight, 10),
    60,
    ms.day_id,
    parent.id,
    jsonb_build_object(
        'migrated_from', 'milestones',
        'legacy_id', ms.id,
        'legacy_state', ms.state,
        'legacy_project_id', ms.project_id
    ),
    current_timestamp,
    current_timestamp
FROM milestones ms
LEFT JOIN days d ON d.id = ms.day_id
LEFT JOIN rhythm_affairs parent
       ON parent.ref ->> 'migrated_from' = 'projects'
      AND parent.ref ->> 'legacy_id' = ms.project_id::text
WHERE NOT EXISTS (
    SELECT 1 FROM rhythm_affairs a
    WHERE a.ref ->> 'migrated_from' = 'milestones'
      AND a.ref ->> 'legacy_id' = ms.id::text
);

-- ---------------------------------------------------------------------------
-- 3. missions → affair(kind=task_oneoff)
--    state 映射：0 pending → INBOX，1 ready → PLANNED，2 doing → DOING，
--                3 done → DONE，4 canceled → CANCELED
--    parent 优先挂 milestone 迁移体，其次挂 project 迁移体（mission 父子关系见第 4 步）
--    mission_id 保留旧主键，便于双写期回查
-- ---------------------------------------------------------------------------
INSERT INTO rhythm_affairs (
    title, description, domain, kind, kind_meta, state,
    importance, urgency_ddl, energy_cost, est_minutes,
    day_id, mission_id, parent_id, ref, ctime, mtime
)
SELECT
    COALESCE(mi.name, '未命名任务'),
    COALESCE(mi.description, ''),
    'work',
    'task_oneoff',
    '{}'::jsonb,
    CASE mi.state
        WHEN 1 THEN 'PLANNED'
        WHEN 2 THEN 'DOING'
        WHEN 3 THEN 'DONE'
        WHEN 4 THEN 'CANCELED'
        ELSE 'INBOX'
    END,
    3,
    mi.ddl,
    COALESCE(NULLIF(mi.energy_cost, 0), 10),
    COALESCE(NULLIF(mi.planned_minutes, 0), 30),
    mi.day_id,
    mi.id,
    COALESCE(ms_affair.id, proj_affair.id),
    jsonb_build_object(
        'migrated_from', 'missions',
        'legacy_id', mi.id,
        'legacy_state', mi.state,
        'legacy_project_id', mi.project_id,
        'legacy_parent_id', mi.parent_id,
        'legacy_milestone_id', mi.milestone_id,
        'actual_minutes', COALESCE(mi.actual_minutes, 0),
        'health_constraint', COALESCE(mi.health_constraint, 'normal')
    ),
    COALESCE(mi.ctime, current_timestamp),
    COALESCE(mi.mtime, current_timestamp)
FROM missions mi
LEFT JOIN rhythm_affairs ms_affair
       ON ms_affair.ref ->> 'migrated_from' = 'milestones'
      AND ms_affair.ref ->> 'legacy_id' = mi.milestone_id::text
LEFT JOIN rhythm_affairs proj_affair
       ON proj_affair.ref ->> 'migrated_from' = 'projects'
      AND proj_affair.ref ->> 'legacy_id' = mi.project_id::text
WHERE NOT EXISTS (
    SELECT 1 FROM rhythm_affairs a
    WHERE a.ref ->> 'migrated_from' = 'missions'
      AND a.ref ->> 'legacy_id' = mi.id::text
);

-- ---------------------------------------------------------------------------
-- 4. mission 自引用父子关系重挂（mission.parent_id 优先于 milestone/project）
-- ---------------------------------------------------------------------------
UPDATE rhythm_affairs child
SET parent_id = parent.id
FROM missions mi
JOIN rhythm_affairs parent
     ON parent.ref ->> 'migrated_from' = 'missions'
    AND parent.ref ->> 'legacy_id' = mi.parent_id::text
WHERE child.ref ->> 'migrated_from' = 'missions'
  AND child.ref ->> 'legacy_id' = mi.id::text
  AND mi.parent_id IS NOT NULL;

COMMIT;

-- ---------------------------------------------------------------------------
-- 校验（人工执行，期望三行 legacy_count = migrated_count）
-- ---------------------------------------------------------------------------
-- SELECT 'projects' AS src,
--        (SELECT count(*) FROM projects) AS legacy_count,
--        (SELECT count(*) FROM rhythm_affairs WHERE ref ->> 'migrated_from' = 'projects') AS migrated_count
-- UNION ALL SELECT 'milestones',
--        (SELECT count(*) FROM milestones),
--        (SELECT count(*) FROM rhythm_affairs WHERE ref ->> 'migrated_from' = 'milestones')
-- UNION ALL SELECT 'missions',
--        (SELECT count(*) FROM missions),
--        (SELECT count(*) FROM rhythm_affairs WHERE ref ->> 'migrated_from' = 'missions');
