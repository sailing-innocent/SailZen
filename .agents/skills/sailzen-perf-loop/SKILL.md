---
name: sailzen-perf-loop
description: |
  SailZen 生产遥测驱动的性能分析、优化与验收自主闭环技能（Telemetry → Triage → Local Profile → Optimize → Verify → Release → Compare）。
  覆盖：只读拉取线上 Telemetry 快照、优先级诊断（P0 仪表体检 / P1 错误热点 / P2 慢接口 / P3 大包与索引 / P4 AI Trace）、
  基于本地生产快照库（.env.dev）的 SQL 计数与 EXPLAIN 复现、前后量化基准对比、幂等 SQL 索引迁移与回归单测、
  以及联动 sailzen-ops 上线后的生产前后快照对比验收。
---

# SailZen Telemetry 性能分析与优化闭环（Perf Loop Skill）

本技能沉淀 SailZen **「用线上真实遥测发现问题 → 用本地生产快照复现与量化 → 最小改动高 ROI 优化 → 用测试与生产前后对比验收」** 的标准自主迭代闭环。

关联工具与文档：
- 闭环 CLI：`scripts/ops/perf_loop.py`（`collect` / `bench-local` / `audit-indexes` / `compare-snapshots`）
- 运维与发布联动：`.agents/skills/sailzen-ops/SKILL.md`、`scripts/ops/deploy_cloud.py`、`scripts/ops/restore_local_db.py`
- Telemetry 架构：`doc/design/observability/telemetry-trace-profile.md`、`sail_server/model/telemetry.py`、`sail_server/utils/telemetry_collector.py`
- 回归测试：`tests/server/test_telemetry_api.py`、`tests/server/test_perf_optimizations.py`

---

## 0. 核心原则与红线

1. **先验仪表，再诊业务（Measure the Meter First）**：
   - 每次分析生产 Telemetry 时，先核查观测口径本身是否失真（例如：分位数聚合是否被单个大文件下载拉偏、动态路径/文件名是否导致 bucket 基数爆炸、常规慢请求告警是否混入二进制下载）。
2. **只读拉生产，本地真数据复现**：
   - 严禁直接在生产库跑 `EXPLAIN ANALYZE` 写操作或压测；所有 SQL 计数、索引实验、压测与基准必须在本地调试库（`.env.dev` → `localhost:5432/main`，由 `restore_local_db.py` 从生产快照还原）完成。
   - `perf_loop.py` 的 `bench-local` 与 `audit-indexes` 内置 `assert_local_pg_target` 硬护栏。
3. **无基线不优化，无对比不结案**：
   - 任何优化都必须先存下 **Before 基线**（生产快照 + 本地 `SQL#` / `Avg ms` / `P50` / `Max`），优化后再跑 **After 基准** 与 **结果 100% 等价性断言**。
4. **只做有证据的高 ROI 改动**：
   - 优先打掉 `impact_score = avg_ms * log2(req_count + 1)` 排名前列且有明确结构性根因（N+1、缺索引、循环查库、GET 写放大）的热点，不做无依据的微观重构。
5. **索引变更必须幂等 SQL 化**：
   - 新增 PostgreSQL 索引必须以 `CREATE INDEX IF NOT EXISTS ...` 写入 `sail_server/migration/YYYYMMDD_<name>.sql` 并注册到 `sail_server/migration/__init__.py` 的 `SQL_MIGRATIONS`（严禁新增 Python 迁移脚本）。
6. **发布遵循 `sailzen-ops` 门禁与 Git 约束**：
   - 不随意直接 `git push origin`（受 `$ALLOW_PUSH` 约束）；上线前必跑测试、前端构建与 `deploy_cloud.py --dry-run`。

---

## 1. 六步标准闭环（SOP）

### Step 1：只读采集生产 Telemetry 并生成分级诊断榜单（Collect & Triage）

```powershell
# 拉取近 72h API Profile + 7d Modules/AI Trace + Runtime + SailTick Live
uv run python scripts/ops/perf_loop.py collect --env prod --hours 72 --days 7 `
    --out data/perf_snapshots/prod_before_roundN.json
```

按以下 **5 级优先级** 审阅诊断输出：

| 级别 | 检查维度 | 判定信号 |
|---|---|---|
| **P0** | Telemetry 仪表自身健康 | 全局 P50 显著高于高频模块 P50；出现未归一化文件名/ID 桶（如 `.apk`）；大文件下载触发 `api_slow` 误报 |
| **P1** | 稳定性与错误热点 | 任意接口 `5xx > 0`、`error_rate >= 5%`、`recent_client_errors` 出现未捕获异常（如 409/500 `unhandledrejection`） |
| **P2** | 高影响力业务慢接口 | 剥离二进制下载后，按 `impact = avg_ms * log2(req_count + 1)` 排序 Top 5 端点（或 `p95 >= 50ms` / `max >= 150ms`） |
| **P3** | 带宽重包与 DB 索引缺口 | 单次出流量 `>= 12 KB/req` 或总出流量 `>= 500 KB`；运行 `audit-indexes` 标记行数 `>= 500` 且仅主键索引的表 |
| **P4** | SailTick AI Trace 效率 | `fallback_rate > 10%`、非 LLM 阶段耗时异常、`completion_tokens` 膨胀或超时 |

---

### Step 2：准备本地生产快照并捕获本地基线（Local Snapshot + Baseline）

```powershell
# 如本地调试库落后于生产较多，先同步最新快照（只读拉云端 + 覆盖本机 main）
# uv run python scripts/ops/restore_local_db.py --pull

# 1. 审计本地调试库的表行数、顺序扫描与索引覆盖
uv run python scripts/ops/perf_loop.py audit-indexes

# 2. 运行本地基准并落盘基线（记录每个热点的 SQL# 与 Avg/P50/Max ms）
uv run python scripts/ops/perf_loop.py bench-local --runs 5 `
    --save data/perf_snapshots/local_before_roundN.json
```

> **若本轮发现新热点端点**：将其补充到 `scripts/ops/perf_loop.py` 的 `cmd_bench_local` 用例列表中，使基准套件随系统演进持续覆盖新热点。

---

### Step 3：根因定位（SQL 计数 + 代码走查 + EXPLAIN ANALYZE）

定位热点代码时，优先排查以下 **SailZen 高发反模式**：

| 反模式 | 典型症状 | 根治手法 |
|---|---|---|
| **批处理接口循环查库** | `POST .../batch` 触发 N 次全表扫描 + ORM 实例化 | 合并为单次轻量列投影 SQL（`with_entities`）+ 时间有序 `bisect` 切片内存聚合；复杂参数优雅回退原路径 |
| **列表接口 N+1 统计查询** | 仅 20 条记录耗时 60–100ms，SQL 数 `1 + 2N` 或 `1 + 3N` | 改为 1~2 次 `GROUP BY` 聚合查询并批量映射回列表对象 |
| **只读 GET 隐式 `db.commit()`** | `GET` 接口延迟 20–60ms 且随并发抖动 | 落库缓存前做字段脏检查，无变更直接返回，消除无意义 PostgreSQL WAL 刷盘 |
| **区间统计逐日循环调子函数** | 周报/看板重复查 `Day` / `Policy` / `Profile` 7 次 | 区间内一次预取全部 `blocks` / `affairs` / `policies`，将单日计算抽成纯内存函数复用 |
| **大表缺少高频过滤/关联索引** | `audit-indexes` 显示高 `seq_scan` 且 `Idx# == 1` | 新增幂等 `.sql` 迁移创建组合/时间索引，再用 `EXPLAIN (ANALYZE, BUFFERS)` 验证命中 `Index Only Scan` / `Index Scan` |
| **同表多次 `COUNT(*)` 往返** | 聚合页触发 30–50 条独立 `SELECT count(*)` | 用 SQLAlchemy `func.count(case((cond, 1)))` 将同表多条件计数合并为 1 条 SQL |
| **Telemetry 离群值拉偏分位** | 1 次大文件下载把全局 P50 拉高数倍 | 跨桶聚合用请求量加权分位数（`_weighted_quantile`）替代加权平均；路径归一并排除大文件下载慢告警 |

对疑似慢 SQL，在本地 `.env.dev` 执行 `EXPLAIN (ANALYZE, BUFFERS)` 确认执行计划（注意新索引刚创建后先 `ANALYZE <table>;` 再看计划，避免统计信息过期）。

---

### Step 4：实施优化、验证等价性与前后基准（Optimize & Verify）

1. **实施最小高 ROI 改动**（后端 / 幂等 SQL 索引 / 必要的前端错误修复）。
2. **如新增 SQL 迁移**，先在本地 `.env.dev` 执行验证幂等性：
   ```powershell
   uv run python -c "from sail.utils import read_env; read_env('dev'); from sail_server.migration import run_migrations; run_migrations()"
   ```
3. **跑本地前后基准对比**：
   ```powershell
   uv run python scripts/ops/perf_loop.py bench-local --runs 5 `
       --baseline data/perf_snapshots/local_before_roundN.json `
       --save data/perf_snapshots/local_after_roundN.json
   ```
4. **编写回归测试锁定优化成果**：
   - 在 `tests/server/test_perf_optimizations.py`（或对应模块测试）中通过 SQLAlchemy `before_cursor_execute` 断言 **SQL 数量上限** 与 **输出 100% 等价性**，防止后续代码退化回 N+1。
5. **通过全部本地发布门禁**：
   ```powershell
   uv run pytest tests/server/test_perf_optimizations.py tests/server/test_telemetry_api.py tests/server/test_router_mount.py tests/unit/test_ops_scripts.py -v
   uv run python scripts/generate_body_metrics.py --check
   pnpm run build-site   # 若改动了 site/
   ```

---

### Step 5：提交与云端发布（配合 `commit-current-change` & `sailzen-ops`）

1. 按 `commit-current-change` skill 清理 `nul` 并以 `perf:` 提交本地变更。
2. 按 `sailzen-ops` 门禁执行发布预演与上线：
   ```powershell
   # 先 dry-run 核对远端状态与变更内容
   uv run python scripts/ops/deploy_cloud.py --dry-run

   # 确认无误后发布（未 push origin 时使用 --sync-mode patch）
   # uv run python scripts/ops/deploy_cloud.py --sync-mode patch
   ```
3. 发布后立即校验线上健康与新索引生效：
   ```powershell
   uv run python scripts/ops/health_check.py --env prod --with-sailtick
   ```

---

### Step 6：上线后 Telemetry 对比验收与经验沉淀（Post-Deploy Compare）

待生产端积累一轮真实访问（通常数小时至 24 小时后，或手动触发关键页面/API 后）：

```powershell
# 1. 采集优化后生产快照
uv run python scripts/ops/perf_loop.py collect --env prod --hours 24 --days 7 `
    --out data/perf_snapshots/prod_after_roundN.json

# 2. 生成生产端 Before vs After 对比报告
uv run python scripts/ops/perf_loop.py compare-snapshots `
    data/perf_snapshots/prod_before_roundN.json `
    data/perf_snapshots/prod_after_roundN.json
```

核对验收标准：
- [ ] 目标慢接口生产 `avg_ms` / `p95_ms` 明显下降，无新慢接口回归
- [ ] P1 错误热点（4xx/5xx/前端 `client_error`）归零或显著下降
- [ ] P0 仪表告警消失（全局 P50 与高频模块一致、无未归一化路径桶）
- [ ] 将本轮发现的新模式追加记录到本文件第 2 节的优化台账中

---

## 2. 历轮优化台账（Optimization Log）

### Round 1（2026-11-24 — Telemetry 首轮自主分析与闭环搭建）

**生产基线诊断（1,365 reqs / 72h）**：
- **P0 仪表问题**：`get_api_profile_impl` 对分位数使用 `_weighted_avg` 导致 1 次 25.17s APK 下载把全局 P50 拉偏至 `25.7ms`；`/app/release/download/*.apk` 未归一化且触发 `api_slow` 误报。
- **P1 错误热点**：`POST /api/v1/rhythm/affair/{id}/state` 40% 4xx（4/10），前端 `/main` 产生 4 条 `409 Conflict` 未捕获异常（勾选 `PLANNED` 事务直接调 `finish`）。
- **P2/P3 慢接口与索引缺口**：
  - `POST /api/v1/finance/transaction/stats/batch`（生产 avg `248.2ms` / max `289.8ms`）：循环逐条查询全表。
  - `GET /api/v1/text/work`（生产 22 次，avg `79.5ms` / max `107.7ms`）：三重 N+1 + `document_nodes`（24,097 行）无索引。
  - `GET /api/v1/rhythm/review/week`（生产 27 次，avg `27.2ms` / max `57.0ms`）与 `/rhythm/dashboard`（`48.1ms`）：7 日循环调 `detect_conflicts_impl` + GET 请求无条件 `db.commit()`。
  - `GET /api/v1/telemetry/profile/modules`（生产 avg `120.8ms` / max `237.8ms`）：42 次串行单表 `COUNT(*)`。
  - 索引审计发现 `document_nodes`、`editions`、`transactions`、`weights` 缺失核心索引。

**实施变更与本地生产快照实测效果**：

| 目标 | 变更摘要 | SQL# (Before → After) | 本地 Avg ms (Before → After) | 提速 |
|---|---|---:|---:|---:|
| `POST /finance/transaction/stats/batch` (82q) | 单次列投影 SQL + `htime` 二分切片内存聚合 + `ix_transactions_htime` | `82 → 1` | `98.94 → 2.97` | **33.3x** |
| `GET /text/work` (limit=20) | 批量 `GROUP BY` 替代三重 N+1 + `ix_document_nodes_edition_type`（命中 Index Only Scan）+ `ix_editions_work_id` | `61 → 3` | `71.27 → 4.33` | **16.5x** |
| `GET /rhythm/review/week` | 合并事务/日志预取 + 内存批量侵占检测 + 无变更跳过 `db.commit()` | `38 → 7` | `24.10 → 4.91` | **4.9x** |
| `GET /rhythm/dashboard` | 受益于日/周评批处理与免写事务优化 | `74 → 36` | `47.41 → 24.93` | **1.9x** |
| `GET /telemetry/profile/modules` | 同表条件聚合 `func.count(case(...))` + 跳过冗余 notable 查询 | `42 → 30` | `23.31 → 16.86` | **1.4x** |
| Telemetry 仪表准确性 | `_weighted_quantile` 替代加权平均；APK 下载路径归一为 `{filename}` 且免报 `api_slow` | — | 单测验证 25s 下载下 P50 保持 `5.0ms` | 消除失真 |
| `/main` 事务勾选 409 | `AffairCard.handleComplete` 自动补齐前置状态转移并捕获异常 | — | 消除 `PLANNED` → `finish` 409 与 `unhandledrejection` | 4xx→0 |

**下轮候选（Round 2 Backlog）**：
- `GET /api/v1/rhythm/affair`（115 次调用，总流量 2.07 MB，均包 18 KB）与 `GET /api/v1/finance/transaction`（均包 175 KB）：评估前端默认分页/精简字段或启用 HTTP Gzip 压缩中间件（Litestar `CompressionConfig`）一次性削减 70%+ 公网传输体积。
- `audit-indexes` 发现 23 组历史遗留重复单列索引（`idx_*` 与 `ix_*` 并存），后续可在低峰期写幂等清理迁移减轻写放大。
- `SailTick` AI Trace 样本积累至 30+ 次后，按 Slot 分析 `evening_review`（33.3s）/ `pre_sleep_report`（27.2s）的 Prompt/Completion 体积优化空间。
