# SailTick 生产首周 Telemetry 复盘与 Round 2 推进文档

> **日期**: 2026-11-28 | **状态**: Batch A 已落地，Batch B 待排期推进
> **关联文档**: [sailtick.md](./sailtick.md) · [sailtick-testing.md](./sailtick-testing.md) · [sailzen-perf-loop](../../../.agents/skills/sailzen-perf-loop/SKILL.md)
> **采样基线快照**: `data/perf_snapshots/prod_week_20261128.json`（7d / 168h）、`data/perf_snapshots/prod_48h_20261128.json`（48h）

---

## 1. 埋点上线首周（2026-11-22 ~ 11-28）运行总览

| 观测维度 | 近 7 天 (`168h`) | 近 48 小时 (`48h`) | 诊断结论 |
|---|---:|---:|---|
| **总 API 请求** | `8,159` | `2,521` | 系统稳定，**零 5xx**；客户端占比 Android `48.3%` / SailTick `33.3%` / Web `13.1%` / VSCode `15.3%`(@48h) |
| **API 4xx / 5xx** | `157` / `0` (`1.92%`) | `19` / `0` (`0.75%`) | 4xx 集中在 11-24 Android 反馈重试（124 次）与 11-25 起 `ai-sync` 100% 失败（19 次） |
| **响应延迟** | P50 `3.5ms` / P95 `25.8ms` | P50 `3.5ms` / P95 `29.5ms` | Round 1 优化稳定生效，长尾集中在 AI 识图与少数聚合查询 |
| **JSON 出流量（不含下载）** | `55.8 MB` | `19.8 MB` | 未开启 Gzip 压缩，高频 JSON 端点带宽偏大 |
| **前端运行时异常** | `18` 次 | `7` 次 | Round 1 的 `409` 已归零，但 `pems.ts` 兼容 Rhythm v2 出现 `forEach` 崩溃（14 次） |
| **SailTick AI Trace** | `29` 次（完成率 `100%`） | `11` 次（fallback `1` 次） | **动作失败率 16.7%@48h**；**Prompt 6 天暴涨 4 倍**；**夜间维护飙至 145~200s** |
| **服务运行时** | RSS `188.9 MB` | 同左 | 埋点表轻量（`sys_api_metric_buckets` 2,368 行 / `sys_telemetry_events` 164 行） |

### 已落地的 Batch A（止血 + 高 ROI 基础设施，2026-11-28）

1. **修复 `POST /api/v1/rhythm/timeline/ai-sync` 100% 400 Bad Request**：在 `sail_server/application/dto/rhythm.py` 的 `AITimelineBlockInput` 增加 `block_type` 别名容错与兜底映射（修复 LLM 输出 `routine` 导致连续 19 次失败），同步在 `sailtick/tick_engine.py` 与 `sailtick/quick_agent.py` Prompt 中显式列出合法 `block_type` 枚举。
2. **修复 Web 首页 `/` 与 `/main` 持续崩溃**：在 `site/src/lib/data/pems.ts` 为 Rhythm v2 缺失字段（`warnings`/`insights`/`health_signals`/`energy_*`）补全空值防御并统一状态大小写判断，消除 14 次 `TypeError: Cannot read properties of undefined (reading 'forEach')`。
3. **全站启用 HTTP Gzip 压缩**：在 `server.py` 配置 `CompressionConfig(backend="gzip", minimum_size=1024)`，并在 `sail_server/middleware/logging_middleware.py` 跳过压缩体日志解码，预计削减 75%~85% JSON 公网出流量。
4. **补齐 Telemetry 观测盲区**：
   - `ApiProfileResponse` 新增 `top_error_endpoints`（后端 + `scripts/ops/perf_loop.py` + Web 端 `ApiProfilePanel` 错误热点 Tab）；
   - `telemetry_collector.py` 补齐 `/api/v1/app/release/latest.apk`、`/api/v1/workbench/release/latest.vsix` 及 `/workbench/release/download/{filename}` 归一化与二进制慢告警豁免；
   - `packages/sailzen-workbench/src/core/server/apiClient.ts` 默认附带 `X-SailZen-Client: vscode`，消除 `other` 桶 15.3% 模糊流量；
   - `site/src/lib/telemetry.ts` 前端错误上报补充 `stack`（前 600 字符）。

---

## 2. Batch B 优化需求清单（深度提速、AI 控本与稳定性加固）

### B1 [P1 · AI 稳定性与控本] SailTick Prompt 记忆预算控制与 JSON 自动修复

- **线上数据证据**：
  - 日总 Token 消耗在 6 天内呈线性暴涨：`11-23: 26,959` → `11-24: 38,099` → `11-25: 49,783` → `11-26: 62,741` → `11-27: 66,448`（周总计 `284,119` tokens / `\$0.53`）。
  - 单次 `prompt_tokens` 从 `2,587` 膨胀至 `9,392 ~ 10,288`（`prompt_chars` 从 `7,221` 涨至 `18,169`）。
  - 拆解 `2026-11-28 midday_checkin`（`17,322` 字符）：
    - **`# 用户画像与记忆` 独占 `7,626` 字符（44.0%）**，其中 `[Semantic]` 21 条占 `4,833` 字符（均条 ~230 字），`[Profile]` 21 条占 `1,588` 字符，`[Procedural]` 8 条占 `1,193` 字符；
    - **`# 任务` Schema 模板占 `3,265` 字符（18.8%）**，每个窗口重复注入全部 18 种 action 模板。
  - `2026-11-27 12:00 midday_checkin` 在输入 `10,288` + 输出 `5,252` tokens 后触发 `JSONDecodeError: Expecting ',' delimiter: line 155 column 63 (char 4899)`，整轮 38.2s 推理白费并跌落 `fallback_error`。
- **代码根因**：
  - `sailtick/memory.py` 的 `summary_for_prompt()` 注释标称预算 `~2k`，实际仅按条数截断（`semantic[:20]`、`procedural[:10]`），无单条字符上限、无总预算上限、无过期/相似记忆压缩合并。
  - `sailtick/tick_engine.py` 在 `json.loads()` 失败后直接跌落 `fallback_error`，缺少轻量 JSON 语法自愈或重试。
- **实施方案**：
  1. **硬预算截断**：在 `AgentMemory.summary_for_prompt()` 增加单条摘要上限（如 `<= 120` 字）与分段总字符预算（如 `[Profile] <= 1200`、`[Semantic] <= 1500`、`[Procedural] <= 800`，总计 `<= 3500` 字符），按最近更新时间/置信度优先保留。
  2. **夜间记忆压缩去重**：在 `nightly_maintenance` 增加语义记忆整理步骤，对同主题/冗余 `st_memories` 执行归并或设置合理 TTL，防止随运行周数无限膨胀。
  3. **JSON 解析自愈**：在 `tick_engine.py` `_extract_json` 之后增加轻量 JSON 修复（去除尾逗号/截断补全或引入 `json-repair`），若仍失败再执行 1 次低成本修复调用，再兜底 fallback。
  4. **按窗口裁剪 Schema & 模型路由评估**：对 `morning_checkin` 等轻量窗口按需裁剪不相关的 action 模板（如跳过 `nightly_*`/`finance_run_hygiene`），并评估是否所有窗口都需要 `deepseek-reasoner`（单次 CoT 输出达 `3.6k ~ 5.3k` completion tokens）。
- **验收标准**：
  - 单次 Tick `prompt_tokens` 稳定控制在 `<= 5,000`（较当前降幅 `>= 45%`），日均总 Token 回落至 `<= 35,000`；
  - 连续 7 天生产运行 `fallback_error` 归零；
  - 补充 `tests/sailtick/` 单元测试断言 `summary_for_prompt()` 字符预算上限与损坏 JSON 自愈用例。

---

### B2 [P1 · 夜间任务治理与可观测性] `nightly_maintenance` 耗时压降（145~200s → <45s）与真实 Span 计时

- **线上数据证据**：
  - `nightly_maintenance` 总耗时突变：`11-24: 9.6s` → `11-25: 200.5s` → `11-26: 158.9s` → `11-27: 164.0s` → `11-28: 145.2s`（其中 `WORK` 阶段独占 `120.8s`）。
  - `11-28` 的 `nightly_food_research` 候选词为：`["约贝纳颂蓝山咖啡含糖咖啡饮品", "一整条约的软质甜面包", "主食", "甜饮为主", "蔬菜"]`，将泛词和整句饮食描述串行发起了 5 次重型调研。
  - `sailtick/nightly.py` 对 `nightly_modeling`、`nightly_rhythm_analytics`、`nightly_finance_backfill`、`nightly_finance_analytics`、`nightly_food_research`、`nightly_knowledge` 全部使用 `tracer.record_instant_span(...)`，导致 Trace 面板中这 6 个阶段全部显示 `0.0ms`，真实耗时和额外 LLM Token 被黑盒吞没在 `WORK` 父 Span 中。
  - `quick_chat` Trace 记录了 `cost_usd=0.006832`，但 `prompt_tokens`、`completion_tokens`、`total_tokens` 均记为 `0`。
- **实施方案**：
  1. **食物调研候选词清洗**：在 `sailtick/knowledge.py` 增加泛词停用表（如 `"主食"`, `"蔬菜"`, `"水果"`, `"零食"`, `"甜饮为主"`, `"家常菜"` 等）及文本规范化/长度限制（跳过无明确单品名的长句），减少无效调研与营养库脏数据。
  2. **夜间调研并发与超时预算**：对 `run_nightly_food_research` 实施有限并发（如 `asyncio.Semaphore(2)`）和单次/阶段总超时保护（如阶段总上限 `45s`），避免单次外部调研拖垮整条 Tick。
  3. **真实 Span 计时与 Token 记账**：将 `sailtick/nightly.py` 中的 `record_instant_span` 全部替换为上下文管理器（`with tracer.span(...):`），准确记录每个夜间子阶段的真实耗时与内部 LLM Token；同时修复 `sailtick/quick_agent.py` 上报 `quick_chat` Trace 时的 Token 字段映射。
- **验收标准**：
  - `nightly_maintenance` 生产耗时从 `145~200s` 降至 `< 45s`；
  - Trace 面板完整呈现每个 `nightly_*` 子阶段真实毫秒耗时，`quick_chat` Trace 显示非零 Token 统计；
  - `st_food_nutrition` 不再新增泛词垃圾记录。

---

### B3 [P2 · 移动端核心体验] `POST /api/v1/tick/intake/analyze` 识图延迟优化

- **线上数据证据**：
  - Android 端最高频重操作：近 7 天 `37` 次、近 48h `13` 次；
  - 延迟表现：7d 均值 `4.79s`、近 48h 均值 `6.09s`、P95 **`15.36s`**、峰值 **`19.91s`**，占据近 48h 全部 14 条 `api_slow` 告警中的 13 条。
- **代码根因**：
  - `sail_server/model/tick_intake.py`（L525–L568）对所有上传图片一律使用 `detail="high"` 调用 Vision 模型；
  - 当图片长宽比 `>= 2.4`（手机长截图）时，先**串行**调用 `deepseek_ocr_file`，完成后再**串行**调用 `deepseek_vision_chat(detail="high")`，双重网络往返把长尾拉到 10~20 秒。
- **实施方案**：
  1. **分级清晰度与图片预处理**：常规食物/体重拍照默认用 `detail="auto"` 并限制上传压缩后的最大边长（如长边 `<= 1280px`），仅在账单/长截图/显式 OCR 场景使用 `detail="high"`。
  2. **OCR 精准触发与延迟打点**：将 `ocr_latency_ms` 与 `vision_latency_ms` 写入日志/可观测统计，验证长截图场景耗时占比；优化 OCR 提示词避免冗余输出。
  3. **（可选进阶）异步草稿体验**：若模型本身首字延迟仍 >4s，可将 Android 端改造为“上传即返回 `analyzing` 草稿 ID → 后台分析完成经 WS 推送结果”，彻底消除前端 5~20s 阻塞等待。
- **验收标准**：
  - 常规识图生产均值 `< 3.5s`，P95 `< 8.0s`；识图字段提取准确率无回退。

---

### B4 [P2 · 后端 DB 性能与卫生] `GET /api/v1/finance/overview` 去全表 ORM 扫描 + 32 组重复索引清理

- **线上数据证据**：
  - `GET /api/v1/finance/overview` 近 48h 调用 `24` 次，avg **`68.7ms`**、P95 **`193.3ms`**、max **`201.0ms`**（当前纯数据库类慢接口 Top 1）。
  - `uv run python scripts/ops/perf_loop.py audit-indexes` 检出本地生产快照库存在 **32 组**同表同列重复单列索引（含 `rhythm_affairs`、`rhythm_time_blocks`、`rhythm_discipline_logs`、`timespans`、`content_assets`、`vault_note_index`、`vault_journal_digests`、`user_inbox_events` 等）。
- **代码根因**：
  - `sail_server/model/finance/hygiene.py`（L923–L945）在计算全库标签覆盖率与沉默账户最后交易时间时，执行 `db.query(Transaction).filter(...).all()` **全表加载并 ORM 实例化全部 2,715 条 Transaction 对象**在 Python 中遍历。
  - 历史 SQL 迁移脚本（`idx_*`）与 SQLAlchemy ORM `index=True`（`ix_*`）命名不一致导致重复建索引。
- **实施方案**：
  1. **SQL 聚合重构 `get_finance_overview_impl`**：改用单次列投影或 SQL 条件聚合（`func.count(case(...))` + `func.max(Transaction.htime)` 按账户分组）计算标签覆盖率、隔离交易数与各账户最后活跃时间，同时合并或复用本月/今日收支查询。
  2. **新增幂等 SQL 迁移清理 32 组重复索引**：在 `sail_server/migration/` 新增幂等 `.sql`（`DROP INDEX IF EXISTS ...`），保留与 ORM 定义一致的 `ix_*` 索引，删除重复的旧命名索引，并注册到 `SQL_MIGRATIONS`。
  3. **基准与单测锁定**：将 `GET /finance/overview` 加入 `scripts/ops/perf_loop.py` `bench-local` 用例，并在 `tests/server/test_perf_optimizations.py` 锁定 SQL 次数上限与输出等价性。
- **验收标准**：
  - `GET /finance/overview` 本地生产快照库 Avg 从 `~70ms` 降至 `< 10ms`；
  - `perf_loop.py audit-indexes` 重复索引告警清零。

---

### B5 [P2 · 端侧稳定性与数据卫生] Android 4xx 重试止损、设备收敛与大包分页

- **线上数据证据**：
  - `POST /api/v1/reminder/{id}/feedback`（Android）在 `2026-11-24 15:00 ~ 23:00` 8 小时内死循环重试 **124 次**且全部返回 4xx；
  - 7 天内两套设备注册接口合计被调 **446 次**（`/user/devices/register` 249 次 + `/reminder/device/register` 197 次），`Reminder` 侧残留 25 台已注册设备（实际 `/user/devices` 8 台、在线 1 台）；
  - `GET /api/v1/finance/transaction` 近 48h 单次响应高达 **`634.4 KB`**（无分页全量拉取 2,715 条）；
  - `sys_telemetry_events` 中 `web_vital` 记录为 `0` 条（前端尚未接入）。
- **实施方案**：
  1. **Android 离线反馈队列止损**：排查 `android/` 中反馈重试队列，明确区分 `4xx`（400/404/409 视为终态，记录日志并丢弃，禁止无限重试）与 `5xx`/网络超时（指数退避 + 最大重试次数上限）。
  2. **设备注册收敛与清理**：推动端侧统一走 `/user/devices/register`，清理 `Reminder` 旧设备表僵尸记录。
  3. **大包分页与 Web Vitals**：评估 Web 财务页 `finance/transaction` 默认按近 3 个月/分页加载；在 `site/src/lib/telemetry.ts` 接入核心 Web Vitals（LCP/INP/CLS）低频上报。
- **验收标准**：
  - 端侧遇到 4xx 提醒反馈不再触发重试风暴；
  - 已注册设备与真实活跃终端一致（无僵尸膨胀）；
  - `web_vital` 事件正常入库可查。

---

## 3. 验收与闭环流程（遵循 `sailzen-perf-loop` & `sailzen-ops`）

每完成一批次（Batch A / Batch B）后，按标准闭环验收：

```powershell
# 1. 本地生产快照基准对比
uv run python scripts/ops/perf_loop.py bench-local --runs 5 --save data/perf_snapshots/local_after_round2.json
uv run python scripts/ops/perf_loop.py audit-indexes

# 2. 全量门禁测试
uv run pytest tests/server/test_telemetry_api.py tests/server/test_perf_optimizations.py tests/sailtick -v
uv run python scripts/generate_body_metrics.py --check
pnpm run build-site; pnpm run test:workbench; pnpm run build-workbench

# 3. 预演并发布上云
uv run python scripts/ops/deploy_cloud.py --dry-run
# uv run python scripts/ops/deploy_cloud.py --sync-mode patch
uv run python scripts/ops/health_check.py --env prod --with-sailtick

# 4. 上线 24h 后采集生产快照并与基线对比
uv run python scripts/ops/perf_loop.py collect --env prod --hours 24 --days 7 --out data/perf_snapshots/prod_after_round2.json
uv run python scripts/ops/perf_loop.py compare-snapshots data/perf_snapshots/prod_48h_20261128.json data/perf_snapshots/prod_after_round2.json
```
