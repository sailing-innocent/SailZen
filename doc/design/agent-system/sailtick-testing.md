# SailTick 四层辅助测试与灰度监控体系

> 版本: v1.0 | 适用: SailTick (`sailtick/`) | 关联: [sailtick.md](./sailtick.md) · [SailTickAcceptance.md](../../maintain/SailTickAcceptance.md)

## 1. 为什么 SailTick 需要专门的测试体系

SailTick 属于 **长周期、有状态、异步交互、LLM 驱动的常驻 Daemon**，传统 CRUD 测试存在四个盲区：

1. **周期太长**：生产每 6 小时唤醒一次，无法在开发阶段等 24 小时验证跨 Tick 交接与票据超期。
2. **输出非确定性**：真实 LLM 随时可能输出格式漂移、过度打扰或触发限流，导致周边硬组件回归不稳定。
3. **跨组件隐性状态**：问题往往出在「Prompt 没注入上轮回复」「安静时段误推」「重启丢状态」「记账重复叠加」等衔接点。
4. **上线风控缺口**：LLM 代理直接接管票据/推送/自我开发后，需要无需改代码、秒级生效的一键降级总闸与可观测告警。

因此构建 **四层递进测试与灰度体系**：

```
┌─────────────────────────────────────────────────────────────────────────┐
│ Layer 4: 一键开关 & 监控灰度测试 (sailtick/canary.py + /canary + /monitor) │
│   off(总闸) → shadow(暗跑零副作用) → canary(限流无推) → live + 自动熔断   │
├─────────────────────────────────────────────────────────────────────────┤
│ Layer 3: 真实 API 短周期可控沙盒 (sailtick/testing/sandbox.py)            │
│   真接 Kimi/DeepSeek API · 秒级唤醒 · 临时库+仿真服务端 · 自动质量评估    │
├─────────────────────────────────────────────────────────────────────────┤
│ Layer 2: Mock LLM 轨迹回放测试 (sailtick/testing/trajectory.py)           │
│   ScriptedLLM + VirtualClock + SimulatedSailServer(真 httpx 协议)        │
├─────────────────────────────────────────────────────────────────────────┤
│ Layer 1: 基础单元测试 & 组件功能测试 (tests/sailtick/ + tests/server/)    │
│   Config / DB / Handoff / Memory / Notify / LLM / Nodes / Guard / API   │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 2. 各层能力与运行命令

### Layer 1：单元与组件功能测试（CI 必跑，毫秒~秒级，无外网依赖）

覆盖配置解析、隔离 SQLite、Handoff 往返、四层记忆 TTL、通知引擎安静时段/去重、LLMGateway 记账与 Kimi 参数适配、Executor 节点、自我开发硬护栏、dag_client 契约与服务端票据 API。

```bash
# 运行全部非外网 SailTick 测试（包含 Layer 1 / 2 / 4 及 Layer 3 离线逻辑）
uv run pytest tests/sailtick -m "not live_llm" -v
```

### Layer 2：Mock LLM 轨迹回放测试（周边硬组件全链路回归）

核心基础设施位于 [sailtick/testing/](../../../sailtick/testing/)：
- **VirtualClock** ([clock.py](../../../sailtick/testing/clock.py))：可任意拨动时间（跨天、跨 23:00 安静时段、超 24h 票据过期）。
- **SimulatedSailServer** ([fake_server.py](../../../sailtick/testing/fake_server.py))：通过 `httpx.MockTransport` 接管真实 `TicketInbox` 与 `DataScanner` 的 HTTP 请求，完整模拟票据状态机、超期、健康数据与故障注入。
- **ScriptedLLM + TrajectoryRunner** ([trajectory.py](../../../sailtick/testing/trajectory.py))：按脚本回放 LLM 响应（含非法 JSON、503 异常、超 token 上限、自研任务），并**反向断言 Prompt 确实注入了上轮 Handoff、用户回复与体征数据**。

内置轨迹场景：
1. `onboarding_reply_loop`：早间建基线 → 模拟用户回复 → 午间 Prompt 注入回复与交接 → 晚间写语义记忆。
2. `fault_injection_and_recovery`：非法 JSON 降级 → `sail_server` 宕机本地维护 → LLM 503 → 全面恢复。
3. `quiet_hours_and_expiry`：23:30 安静时段 normal 不推 / urgent 推送 → 推进 26h 自动 `expired`。
4. `canary_circuit_breaker`：canary 模式连续失败自动熔断降级至 `shadow`。
5. `test_trajectory_shadow_canary_live_matrix`：同一轨迹在 `shadow/canary/live` 下的副作用矩阵。
6. `test_trajectory_self_dev_guardrails_end_to_end`：夜间自研任务非法路径拦截 + 合法分支提交与 approval 票据。

```bash
# 通过 CLI 一键回放全部内置轨迹
uv run python -m sailtick replay --scenario all

# 或通过 pytest 运行完整轨迹套件
uv run pytest tests/sailtick/test_trajectory_replay.py -v
```

### Layer 3：真实 API 短周期可控沙盒测试（接 Kimi / DeepSeek）

核心实现见 [sandbox.py](../../../sailtick/testing/sandbox.py)：
- **强隔离**：全部运行于临时目录与内存仿真服务端，绝不污染生产 `data/sailtick/` 与主库票据。
- **短周期可控**：支持秒级唤醒（`--interval 2`）、限定次数（`--ticks 2`）与单 Tick token 硬上限（`--token-cap 20000`）。
- **Kimi 自动识别**：自动读取 `KIMI_API_KEY` / `MOONSHOT_API_KEY`（兜底读 `.env.dev`），自动适配 `kimi-k2.5` 的 `temperature=1.0` 约束。
- **自动质量评估（`SandboxEvaluator`）**：校验完成率、真实 LLM JSON 合规率（非降级）、票据节流（<=2）、Handoff 完整性、温和教练语气护栏，并落盘 `sandbox_report.json` 与 `sandbox_report.md`。
- **API 阻塞容错**：探活失败或未配置 Key 时返回 `status=api_blocked`，加 `--allow-skip` 或在 pytest 中自动 `skip`。

```bash
# 运行 Kimi 真实 API 短周期沙盒（保留报告到 scratch 目录）
uv run python -m sailtick sandbox --provider kimi --scenario quick_ping --interval 2 --ticks 2 --allow-skip

# 压力优先场景 / 真实 API 灰度切换场景
uv run python -m sailtick sandbox --provider kimi --scenario stress_override --allow-skip
uv run python -m sailtick sandbox --provider kimi --scenario canary_shadow_live --allow-skip

# pytest 运行真实 API 沙盒测试
uv run pytest tests/sailtick/test_sandbox_live.py -m live_llm -v -s
```

### Layer 4：一键开关与监控的灰度体系

核心实现见 [canary.py](../../../sailtick/canary.py)，状态持久化于 `st_runtime_state`（重启不丢失）。

#### 四态模式矩阵

| 模式 | LLM 调用 | 创建真实票据 | 单 Tick 上限 | 手机强推 | 自我开发 | 适用阶段 |
|---|---|---|---|---|---|---|
| `off` | ❌ | ❌ | 0 | ❌ | ❌ | 紧急停机 / 维护 |
| `shadow` | ✅ | ❌（仅记 `shadow_work`） | 2（模拟） | ❌ | ❌ | 新 Prompt / 新模型暗跑验证 |
| `canary` | ✅ | ✅（可选前缀/slot白名单） | **1** | ❌ | ❌ | 灰度放量，观察回复与体感 |
| `live` | ✅ | ✅ | 2 | ✅（遵循安静时段） | ✅（受护栏保护） | 正式生产运行 |

#### 一键控制（CLI + HTTP API）

```bash
# 查看当前灰度模式与策略
uv run python -m sailtick canary status

# 渐进灰度切换（运行中 daemon 走热切 API，未启动时直接写库）
uv run python -m sailtick canary set shadow --reason "新 prompt 暗跑 24h"
uv run python -m sailtick canary set canary --prefix "[Canary] " --reason "开启限量灰度"
uv run python -m sailtick canary set live --reason "灰度指标健康，全量上线"

# 紧急一键总闸关停 / 解除熔断恢复
uv run python -m sailtick canary kill --reason "异常刷票据紧急止损"
uv run python -m sailtick canary resume --to canary --reason "修复后恢复灰度"

# 查看运行监控与告警快照
uv run python -m sailtick monitor
uv run python -m sailtick monitor --json
```

HTTP 管理端点（默认 `:9070`）：
- `GET  /canary` — 当前灰度模式、策略与熔断状态
- `POST /canary/switch` — 热切换模式及细粒度开关
- `POST /canary/kill` — 紧急总闸关停（切至 `off`）
- `POST /canary/resume` — 清除熔断器并恢复至目标模式
- `GET  /monitor` — 完整监控指标（成功率、LLM 降级率、平均耗时、今日 Token/USD 占比、Handoff 覆盖率、影子票据数）与结构化告警（`CIRCUIT_BREAKER_OPEN` / `HIGH_FALLBACK_RATE` / `HIGH_TICK_FAILURE_RATE` / `TOKEN_BUDGET_HIGH` / `STALE_RUNNING_TICKS` / `DEPENDENCY_DOWN_*`）

#### 自动熔断规则

当 `canary` 或 `live` 模式下连续发生 `auto_downgrade_failures`（默认 3 次）Tick 失败或 LLM 异常降级时，系统自动切换至 `auto_downgrade_target`（默认 `shadow`），打开熔断器并在 `/monitor` 触发 `CRITICAL: CIRCUIT_BREAKER_OPEN` 告警，直到人工执行 `canary resume`。
