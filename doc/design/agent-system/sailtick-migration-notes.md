# SailTick 迁移说明 — 从 `sailzen.autonomous_agent` 到 `sailtick`

> 版本: v1.0 | 日期: 2026-10-27 | 状态: Phase 0 调研结论
> 关联文档: [sailtick.md](./sailtick.md)（总体设计）、[autonomous-agent.md](./autonomous-agent.md)（旧设计，已被取代）

## 1. 为什么新建 `sailtick/` 包而不是改造 `sailzen/autonomous_agent/`

| 理由 | 说明 |
|---|---|
| 代码已损坏 | 旧 daemon 存在多处确定性 bug（见 §2），从未跑通过；在损坏地基上改造风险高于重写 |
| 身份独立 | SailTick 是与 SailZen 平行的常驻服务（减肥监督教练），顶层包 `sailtick/` 与 `sail_server/`、`sailzen/` 平级，部署、进程、DB 均独立 |
| 不污染共享引擎 | `sailzen/dag_client` 是生产在用的共享引擎（/dag-pipeline 页面），SailTick 只依赖其稳定接口并补了契约测试（`tests/sailtick/test_dag_client_contract.py`），避免把教练域逻辑塞进共享层 |
| 设计哲学保留 | 旧设计文档的隔离原则（独立 SQLite、skill-first、cron-native）全部继承；可运行的骨架（memory / llm_gateway / notification_engine / db schema 思想）迁移修复后复用 |

## 2. 既有缺陷复现记录（计划 §2.2 核对）

以下结论基于 2026-10-27 代码实际复现，与计划稿的预期存在出入的地方已标注。

### B1. `OpencodeAsyncClient` 导入（计划称 ImportError）— 实际未炸，但属于侥幸

- 位置: `sailzen/autonomous_agent/daemon.py:35`
- 计划预期: `opencode_bridge.py` 只导出 `OpenCodeBridge` → ImportError。
- 实际: `opencode_bridge.py:22` 有模块级 `from sail.opencode.client import OpencodeAsyncClient`，
  该名字因此成为模块属性，`from ... import OpencodeAsyncClient` **侥幸可用**。
- 处置: 仍按规范修复 —— SailTick 直接从 `sail.opencode.client` 导入，不依赖这种隐式再导出。

### B2. `DAGScheduler` 构造 — 确认 TypeError，且比预期更严重

- 位置: `sailzen/autonomous_agent/daemon.py:71` `DAGScheduler(self.dag_db, self.event_bus)`
- 确认: `DAGScheduler.__init__(self, db_compat)` 只收 1 个参数 → `TypeError`。
- 更深的坑: 即使去掉第二个参数，`self.dag_db` 是裸 `Database`，而调度器需要
  `DatabaseCompat`（`sailzen/dag_client/repositories.py`）提供 `create_run/get_nodes/update_node_status...`
  方法 —— 裸 Database 会在第一个方法调用处 `AttributeError`。
- 生产正确接线见 `sailzen/dag_client/app.py`: `DAGScheduler(DatabaseCompat(raw_db))`。
- 处置: SailTick daemon 按生产模式接线。

### B3. 通配符触发回调 — 确认，定时触发永不生效

- 位置: `daemon.py:190` `register_trigger_callback("*", cb)` vs `scheduler.py:219`
  `self._trigger_callbacks.get(pipeline_id)`（精确匹配）。
- 确认: 注册键 `"*"` 永远匹配不到任何 pipeline_id → 每次触发走 "No callback registered" 分支。
- 处置: SailTick 侧改为「默认 fallback 回调」语义——先精确查找，未命中用默认回调（见 `sailtick/scheduler.py`）。

### B4. `pipeline_def["id"]` KeyError（计划称模板无 id）— 当前模板均有 id

- 位置: `daemon.py:318`
- 实际: 现存 15 个 pipelines/*.yaml **全部**有顶层 `id` 字段，KeyError 不可复现。
- 处置: SailTick 加载 pipeline 时做防御性 `pipeline_def.get("id", pipeline_id)`，保留兼容。

### B5.（新发现）`DAGScheduler.start()/stop()` 不存在 — daemon 启动即 AttributeError

- 位置: `daemon.py:185,213` 调用 `await self.dag_scheduler.start()` / `.stop()`；
  `sailzen/dag_client/scheduler.py` 的 `DAGScheduler` 只有 `pause/resume/is_paused`。
- 处置: SailTick 不调用不存在的方法（executor 有自己的 start/stop）；必要时给共享引擎补 no-op start/stop。

### B6.（新发现）`repositories.py` 缺 `_NODE_TERMINAL_STATUSES` 导入 — 引擎级 NameError，已修复

- 位置: `sailzen/dag_client/repositories.py:213`（`DAGNodeRepository.update_status`）
- 现象: 任何 `update_node_status(..., force=False)` 调用 → `NameError`。
  即共享引擎在 `/dag-pipeline` 生产路径外的状态推进全部不可用。
- 修复: models 导入列表补上 `_NODE_TERMINAL_STATUSES`（已改，契约测试锁定）。

### B7.（新发现）`scheduler.py` 缺 `AgentStatus` 导入 — 已修复

- 位置: `sailzen/dag_client/scheduler.py:377`（`assign_node` 内 `AgentStatus.BUSY.value`）
- 现象: `assign_node` 被调用即 NameError。SailTick 不依赖该方法，但顺手修复以清死引用。

### B8.（新发现）`create_run` 返回快照而非权威状态

- 位置: `sailzen/dag_client/scheduler.py` `create_run`
- 现象: 返回的 run dict 是创建时快照（status=pending），权威状态需从 DB 重读。
- 处置: 已在契约测试中固化为契约说明，SailTick 侧按 DB 权威状态读取。

## 3. 迁移处置映射

| 来源 | 处置 |
|---|---|
| `autonomous_agent/db.py`（ORM schema 思想） | 迁移扩展 → `sailtick/db.py`（st_* 表族，见设计文档 §9.2） |
| `scheduler.py` 通配符 bug（B3） | 修复为 fallback 回调 |
| `daemon.py` 构造/导入 bug（B1/B2/B5） | 重写 `sailtick/daemon.py`，按生产模式接线 |
| `memory.py` 三层记忆 | 迁移扩展为四层（profile/episodic/semantic/procedural）+ handoff |
| `llm_gateway.py` | 迁移 + 每 Tick token/费用记账入 `st_ticks` |
| `notification_engine.py` quiet-hours/去重 | 迁移保留，新增 ticket/push 通道 |
| `nodes/*`（wellness/lark_notify 等） | 不复用（业务域不同）；SailTick 新建 executor 节点族 |
| `sail_server/utils/reminder_ws.py` | 复用为手机推送通道 |
| `bot.py`/`sail_bot` | P3 复用为飞书/QQ 通道 |
| 旧 pipelines/*.yaml（15 个） | 不迁移；SailTick 新建 4 条初始 pipeline |

## 4. 旧包归档

Phase 9 执行：`sailzen/autonomous_agent/` 移至 `archive/` 并删除，
`autonomous-agent.md` 头部标注「已被 sailtick.md 取代」。
