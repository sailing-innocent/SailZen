# Project/Mission → Affair 数据迁移手册

> 关联：`doc/design/manager/rhythm.md`（统一事务模型）、`sail_server/migration/20260818_migrate_project_to_affair.sql`
>
> 背景：`projects` / `milestones` / `missions` 与 rhythm 的 `rhythm_affairs` 是两套并存的任务模型，
> 「长期事业（venture）」与「项目任务（mission）」被人为拆成两个模块，导致同一件事在两处维护、
> 客户端要接两套 API、里程碑只在 rhythm 侧有 REST 接口。本次统一到 `rhythm_affairs` 单表。
>
> 客户端现状：Android 端（0.1.0 起）已全量切到 Affair API，不再调用 `/api/v1/project/*`。

## 1. 目标模型映射

| 旧实体 | 新实体 | kind | domain | 说明 |
| --- | --- | --- | --- | --- |
| `projects` | affair | `venture` | `career` | 长期事业主体，`kind_meta` 承载倒排信息 |
| `milestones` | affair | `task_oneoff` | `career` | 挂在 venture 下（`parent_id`），倒排里程碑 |
| `missions` | affair | `task_oneoff` | `work` | 挂在 milestone 或 venture 下；mission 自引用父子保留 |

### 状态映射

**projects.state → affair.state**

| 旧值 | 含义 | 新状态 |
| --- | --- | --- |
| 0 INVALID | 无效 | `ARCHIVED` |
| 1 VALID | 有效 | `INBOX` |
| 2 PREPARE | 准备中 | `INBOX` |
| 3 TRACKING | 跟踪中 | `ACTIVE` |
| 4 PENDING | 挂起 | `PAUSED` |
| 5 DONE | 完成 | `DONE` |
| 6 CANCELED | 取消 | `ARCHIVED` |

**missions.state → affair.state**

| 旧值 | 新状态 |
| --- | --- |
| 0 pending | `INBOX` |
| 1 ready | `PLANNED` |
| 2 doing | `DOING` |
| 3 done | `DONE` |
| 4 canceled | `CANCELED` |

**milestones.state → affair.state**：`0 pending → PLANNED`、`1 done → DONE`、`2 skipped → CANCELED`。

### 字段映射要点

- `missions.ddl` → `urgency_ddl`（两侧都是 naive `TIMESTAMP`，直接搬）
- `missions.planned_minutes` → `est_minutes`（0 视为缺省，落 30）
- `missions.energy_cost` → `energy_cost`（0 视为缺省，落 10）
- `milestones.energy_weight` → `energy_cost`
- `milestones.day_id` → `day_id`，同时推导 `urgency_ddl = 当日 23:59:59`
- `projects.timespan_id` → `timespan_id`；`timespans.end_day_id` 对应日期 → `kind_meta.target_date`
- `kind_meta.total_est_hours` 由该项目下所有 mission 的 `planned_minutes` 汇总换算
- 无法建模的旧字段（`start_time_qbw` / `end_time_qbw` / `actual_minutes` / `health_constraint` / 各级旧主键）
  全部落进 `ref`，保证可回查、可回滚

### 溯源约定

每条迁移产物写入：

```json
{ "migrated_from": "missions", "legacy_id": 123, "legacy_state": 2, "...": "..." }
```

配套索引 `ix_rhythm_affairs_migrated`，既用于幂等判断（重跑跳过），也用于双写期回查。

## 2. 三阶段迁移流程

### Phase 1 — 复制到新表（当前版本，0.2.x）

**目标**：数据双份存在，旧表只读，新表成为唯一写入面。

```bash
# 1) 先备份
pg_dump -t projects -t milestones -t missions -Fc main > backup_project_20260818.dump

# 2) 执行迁移（幂等，可重跑）
psql "$POSTGRE_URI" -f sail_server/migration/20260818_migrate_project_to_affair.sql

# 3) 校验条数（脚本尾部注释里有现成 SQL）
psql "$POSTGRE_URI" -c "
SELECT 'projects' AS src,
       (SELECT count(*) FROM projects) AS legacy_count,
       (SELECT count(*) FROM rhythm_affairs WHERE ref->>'migrated_from'='projects') AS migrated_count
UNION ALL SELECT 'milestones', (SELECT count(*) FROM milestones),
       (SELECT count(*) FROM rhythm_affairs WHERE ref->>'migrated_from'='milestones')
UNION ALL SELECT 'missions', (SELECT count(*) FROM missions),
       (SELECT count(*) FROM rhythm_affairs WHERE ref->>'migrated_from'='missions');"
```

**验收清单**

- [ ] 三类 `legacy_count == migrated_count`
- [ ] 孤儿检查：`SELECT count(*) FROM rhythm_affairs WHERE ref->>'migrated_from'='missions' AND parent_id IS NULL;`
      结果应等于「没有 project 也没有 milestone 的历史 mission」数量
- [ ] `/api/v1/rhythm/affair/?kind=venture&state=ACTIVE` 返回原 TRACKING 项目
- [ ] `/api/v1/rhythm/venture/{id}/progress` 能算出倒排压力（依赖 `kind_meta.target_date`）
- [ ] Android APK「事业」tab 两个子视图数据正确

**本阶段代码约束**

- `/api/v1/project/*` 路由保留，但仅供 web `site/` 只读回看，**禁止新增写入**
- 所有新写入（Android、Agent、CLI）一律走 `/api/v1/rhythm/affair/*`

### Phase 2 — deprecate 旧表（下一个 minor 版本，0.3.0）

前提：Phase 1 上线并稳定运行 ≥ 2 周，且 `site/` 已切到 Affair API。

```sql
BEGIN;
-- 1) 物理改名，暴露所有残留引用（任何漏改的代码会立刻报 relation does not exist）
ALTER TABLE projects   RENAME TO projects_deprecated;
ALTER TABLE milestones RENAME TO milestones_deprecated;
ALTER TABLE missions   RENAME TO missions_deprecated;

-- 2) 留兼容只读视图，给尚未迁移的离线脚本一个缓冲期
CREATE VIEW projects   AS SELECT * FROM projects_deprecated;
CREATE VIEW milestones AS SELECT * FROM milestones_deprecated;
CREATE VIEW missions   AS SELECT * FROM missions_deprecated;

COMMENT ON TABLE projects_deprecated IS 'DEPRECATED 2026-xx-xx, 已迁移至 rhythm_affairs(kind=venture)，计划 0.4.0 删除';
COMMIT;
```

同版本代码动作：

- 删除 `sail_server/router/project.py` 注册，或全部返回 `410 Gone`
- 删除 `sail_server/controller/project.py`、`model/project.py` 写路径
- `rhythm_affairs.mission_id` 标记为 legacy 字段，不再写入新值
- `site/` 项目页改为 Affair 数据源

### Phase 3 — 删除（再一个 minor 版本，0.4.0）

前提：Phase 2 后连续 1 个版本周期内，`*_deprecated` 表零访问（用 `pg_stat_user_tables.seq_scan` / `idx_scan` 确认）。

```sql
-- 访问计数确认，全为 0 才继续
SELECT relname, seq_scan, idx_scan
FROM pg_stat_user_tables
WHERE relname IN ('projects_deprecated','milestones_deprecated','missions_deprecated');

BEGIN;
DROP VIEW IF EXISTS projects, milestones, missions;
DROP TABLE IF EXISTS missions_deprecated;    -- 先删子
DROP TABLE IF EXISTS milestones_deprecated;
DROP TABLE IF EXISTS projects_deprecated;    -- 后删父
COMMIT;
```

同版本代码动作：

- 删除 `infrastructure/orm/project.py`、`application/dto/project.py`
- 删除 `rhythm_affairs.mission_id` 列（`ALTER TABLE rhythm_affairs DROP COLUMN mission_id;`）
- 清理 `ref` 内的 `legacy_*` 键（可选，建议保留作为历史溯源）

## 3. 回滚

| 阶段 | 回滚方式 |
| --- | --- |
| Phase 1 | `DELETE FROM rhythm_affairs WHERE ref->>'migrated_from' IN ('projects','milestones','missions');` 旧表未动，无损 |
| Phase 2 | `DROP VIEW ...; ALTER TABLE *_deprecated RENAME TO ...;` 反向改名即可 |
| Phase 3 | 不可逆，只能从 Phase 1 的 `pg_dump` 备份恢复 |

## 4. 常见问题

**Q: 旧 mission 有多层父子树（`lft/rgt/tree_id`），迁移后还在吗？**
A: 父子关系通过 `parent_id` 自引用保留，嵌套集合索引（`lft/rgt/tree_id`）不迁移 —— affair 侧用递归查询处理子树，不再维护 nested set。

**Q: 一个 mission 既有 `milestone_id` 又有 `project_id` 挂哪里？**
A: 优先挂 milestone 迁移体；milestone 缺失才回落到 venture；若还是没有（历史脏数据），`parent_id` 留 `NULL`，成为顶层任务，可在「任务」看板里手动归位。

**Q: 迁移后旧表还会被 Android 读到吗？**
A: 不会。Android 端已删除 `ProjectApi` / `ProjectRepository` / `feature.project` / `feature.venture`，只保留 `RhythmApi`。
