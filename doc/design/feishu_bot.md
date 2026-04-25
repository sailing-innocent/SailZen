# Feishu Bot (sail_bot)

> **版本**: v2.0 | **更新**: 2026-04-08 | **状态**: Phase 0 可用

Feishu Bot 是 SailZen 的飞书端控制台，通过飞书长连接接收用户消息，经 LLM 意图识别后驱动 OpenCode 开发环境执行任务。

---

## 架构总览

```
Feishu (长连接 SDK)
    │
    ▼
FeishuBotAgent                     ← 入口协调器
    ├── FeishuMessagingClient       ← 消息收发 (含速率限制)
    ├── SessionStateStore           ← 会话状态机 (持久化)
    ├── OpenCodeSessionManager      ← 进程生命周期管理
    ├── BotBrain                    ← 意图识别 (三级降级)
    ├── ConversationContext          ← 对话上下文 (per-chat)
    └── HandlerContext              ← 依赖注入容器
         ├── MessageHandler         ← 消息入口 (去重 + 线程池)
         ├── CardActionHandler      ← 卡片按钮交互
         ├── PlanExecutor           ← Action 路由注册表
         │    ├── HelpHandler
         │    ├── StatusHandler
         │    ├── StartWorkspaceHandler
         │    ├── StopWorkspaceHandler
         │    ├── SwitchWorkspaceHandler
         │    ├── TaskHandler       ← 异步任务提交
         │    └── SelfUpdateHandler
         ├── WelcomeHandler         ← 首次对话欢迎
         └── LifecycleManager       ← 启停/清理/通知
```

---

## 消息处理流水线

```
1. Feishu SDK 长连接收到消息
2. MessageHandler.handle()
   ├── 消息去重 (_MessageDeduplicator, TTL 300s)
   ├── 提取 text / chat_id / message_id
   └── 提交到 ThreadPoolExecutor (8 worker)
3. _process_message() [线程池线程]
   ├── 去除 @mention
   ├── 获取 ConversationContext
   ├── 检查 pending confirmation
   └── BotBrain.think_with_feedback()
        ├── Level 1: 正则/关键词匹配 (无 LLM 调用)
        ├── Level 2: LLM 语义理解 (显示 thinking card)
        └── Level 3: 优雅降级到 chat/clarify
4. 返回 ActionPlan
   ├── 风险分级: SAFE / GUARDED / CONFIRM_REQUIRED
   └── 需确认 → 生成确认卡片, 等待用户回应
5. PlanExecutor.execute() → 注册表分发到对应 Handler
6. Handler 执行 → CardRenderer 生成结果卡片 → FeishuMessagingClient 发送
```

---

## 核心模块

### BotBrain (意图识别)

三级渐进式意图识别:

| 级别 | 方式 | 延迟 | 可靠性 |
|------|------|------|--------|
| Level 1 | 正则/关键词 | <1ms | 高 |
| Level 2 | LLM (moonshot/openai/...) | 1-5s | 中 |
| Level 3 | 降级到通用 chat | 0ms | 回退 |

**双模式处理:**
- **idle 模式**: 三级意图匹配, 识别启动/停止/帮助等指令
- **coding 模式**: 非感叹号消息直接转发给 OpenCode; `!` 开头的消息在 Bot 层执行控制指令

### AsyncTaskManager (异步任务)

基于 SSE 事件流实时追踪 OpenCode 任务执行:

- 独立 asyncio 事件循环线程 (`task-mgr-loop`)
- SSE 流式接收 OpenCode 事件 (`message.part.updated`, `session.idle` 等)
- 消息边界追踪: 通过 `_pre_existing_msg_ids` 防止处理历史消息
- 自动回答 question/permission 工具调用
- 降级: SSE 失败 → 轮询模式

提供 `run_async(coro)` 工具函数, 供同步代码安全调用异步协程。

### SessionStateStore (会话状态机)

```
IDLE ──→ STARTING ──→ RUNNING ──→ STOPPING ──→ IDLE
              │           │
              └──→ ERROR ←┘
                    │
                    └──→ STARTING (auto-restart) / IDLE
```

- 线程安全 (threading.Lock)
- 状态转移验证 (拒绝非法跳转)
- 钩子机制: 状态变化触发通知 (如 ERROR → 发送告警卡片)
- 持久化到 `data/bot/state/sessions.json`

### FeishuMessagingClient (消息收发)

封装所有飞书 API 调用:

- `send_text` / `reply_text` / `send_card` / `reply_card` / `update_card`
- 令牌桶速率限制 (20 calls/s, 防止平台限流)
- 卡片发送失败自动降级为纯文本
- CardMessageTracker 追踪已发送卡片用于后续更新

---

## 稳定性机制

| 机制 | 实现位置 | 说明 |
|------|----------|------|
| 消息去重 | `message_handler._MessageDeduplicator` | TTL 缓存, 防止 SDK 重连重复投递 |
| 线程池 | `message_handler._executor` | 8 worker, 替代无限制线程创建 |
| API 速率限制 | `messaging.client._RateLimiter` | 令牌桶 20/s |
| 健康检查 | `SessionHealthMonitor` | 每 30s 检查, 3 次失败触发 ERROR |
| 状态持久化 | `SessionStateStore` + `ConversationContext` | 磁盘持久化, 重启恢复 |
| 进程清理 | `LifecycleManager.cleanup_previous_instances()` | 启动时清理僵尸进程 |
| LLM 降级 | `BotBrain` 三级策略 | LLM 失败回退到关键词匹配 |
| 确认机制 | `ConfirmationManager` + `RiskLevel` | 破坏性操作需要用户确认 |
| 自更新 | `SelfUpdateOrchestrator` + `bot_watcher.py` | exit(42) 触发 watcher 拉取更新并重启 |
| 管理员通知 | `LifecycleManager._notify_startup/shutdown` | 启停事件通知管理员 |

---

## 可扩展性

### 添加新 Action

1. 创建 Handler 类 (继承 `BaseHandler`):

```python
class MyHandler(BaseHandler):
    def handle(self, chat_id, message_id, ctx, **kwargs):
        ...
```

2. 在 `PlanExecutor.__init__()` 中注册:

```python
self._my_handler = MyHandler(ctx)
self._registry["my_action"] = (self._exec_my, "执行了 my_action")
```

3. 在 `BotBrain` 中添加识别:
   - `_BRAIN_FALLBACK_ACTIONS` 中添加关键词
   - 或在 LLM system prompt 中添加新 action 类型

### 添加新 Card 类型

在 `card_renderer.py` 中添加 `@staticmethod` 方法, 返回飞书卡片 JSON dict。

---

## 文件结构

```
sail_bot/
├── agent.py                  # FeishuBotAgent 入口协调器
├── config.py                 # AgentConfig (含验证)
├── brain.py                  # BotBrain 意图识别
├── context.py                # ActionPlan, ConversationContext
├── session_state.py          # 状态机, 健康监控, 风险分级, 确认管理
├── session_manager.py        # OpenCode 进程管理
├── async_task_manager.py     # SSE 异步任务 + run_async 工具
├── card_renderer.py          # 飞书卡片模板
├── log_formatter.py          # 日志格式化
├── long_output_handler.py    # 长文本分片
├── self_update_orchestrator.py  # 自更新编排
├── bot_state_manager.py      # 全局状态备份/恢复
├── opencode_client.py        # OpenCode HTTP/SSE 客户端
├── opencode_message_logger.py
├── task_logger.py
├── paths.py                  # 路径常量
├── messaging/
│   ├── __init__.py
│   └── client.py             # FeishuMessagingClient (速率限制)
└── handlers/
    ├── __init__.py
    ├── base.py               # HandlerContext 依赖注入
    ├── message_handler.py    # 消息入口 (去重 + 线程池)
    ├── card_action.py        # 卡片按钮处理
    ├── plan_executor.py      # Action 注册表路由
    ├── command_handlers.py   # help, status
    ├── workspace_handlers.py # start, stop, switch
    ├── task_handler.py       # 任务提交与进度追踪
    ├── self_update_handler.py
    ├── welcome_handler.py
    └── lifecycle_manager.py  # 启停清理
```

---

## 配置

配置文件: `bot/opencode.bot.yaml`

```yaml
app_id: "cli_xxx"
app_secret: "xxx"
base_port: 4096
max_sessions: 10
auto_restart: false
admin_chat_id: "oc_xxx"
projects:
  - slug: "sailzen"
    path: "~/repos/SailZen"
    label: "SailZen"
```

启动验证: `AgentConfig.validate()` 在加载时检查端口范围、路径存在性、LLM provider 有效性等。

---

## 运行方式

```bash
# 直接运行
uv run bot.py -c bot/opencode.bot.yaml

# 带自更新 watcher 运行 (推荐生产环境)
uv run bot_watcher.py -c bot/opencode.bot.yaml
```

---

## 与 SailZen 3.0 路线图的关系

当前 sail_bot/ 是 **Phase 0 Feishu Dev Loop MVP** 的核心实现。后续演进方向:

| 阶段 | 计划 |
|------|------|
| Phase 0 (当前) | 飞书长连接 Bot, OpenCode 进程管理 |
| Phase 1 | 结构化开发任务层, 与 control_plane 集成 |
| Phase 2 | 统一工具层, edge_runtime 双向通信 |
| Phase 3+ | 主动式助手, 笔记/数据桥接 |

`sail_server/control_plane/` 和 `sail_server/edge_runtime/` 已有基础实现, 等待与 sail_bot 集成。


好，让我系统性地检查 handlers 层的所有文件，查找残余引用和完整流程断点。----

现在让我搜索旧模块的残余引用：-

**发现了关键问题！** `brain.py` 第 429 行和 457 行调用了 `agent._reply_card` 和 `agent._update_card`，这两个是旧 API——在 v3.0 重构后 agent 不再直接暴露这些方法，消息操作已全部迁移到 `FeishuMessagingClient`。

让我确认 agent 中是否还存在这些方法：-

确认了！`agent._reply_card` 和 `agent._update_card` 已经不存在了（搜索返回 0 结果）。这是 **运行时必崩的断裂点**。

再检查 `plan_executor.py` 中 `request_self_update` 的签名问题：-

现在我已经完成了完整的审计。让我来修复发现的问题。

---

## 审计报告

### 🔴 严重问题（运行时必崩）

**`brain.py:429` 和 `brain.py:457`** — 调用了已删除的 `agent._reply_card()` 和 `agent._update_card()`

```python
# brain.py line 429 — 已不存在的方法
thinking_mid = agent._reply_card(message_id, thinking_card, ...)

# brain.py line 457 — 已不存在的方法  
agent._update_card(thinking_mid, fallback_card)
```

v3.0 重构后 agent 不再直接暴露消息方法，所有消息操作应通过 `agent.messaging`（即 `FeishuMessagingClient`）。

### 🟡 中等问题（签名不匹配）

**`plan_executor.py:147-151`** — `request_self_update()` 传入了 `trigger_source` 和 `initiated_by` 参数，但 `HandlerContext.request_self_update()` 只接受 `reason` 参数：

```python
# plan_executor.py line 147-151
result = self.ctx.request_self_update(
    trigger_source=trigger_source,
    reason=reason,
    initiated_by=chat_id,
)
```

但 `HandlerContext.request_self_update` 签名是 `(self, reason: str)`，而底层 `SelfUpdateOrchestrator.request_update` 签名是 `(self, reason: str, perform_git_pull: bool)`。

### 🟢 无问题（仅注释中的引用）

`agent.py:11`, `handlers/base.py:10,44`, `task_handler.py:10`, `lifecycle_manager.py:10` — 这些都是注释/docstring 中解释重构历史的文字，不影响运行。

---

现在修复。先修复 `brain.py` 中的残余旧 API 调用：-

现在修复 `plan_executor.py` 中 `request_self_update` 的签名不匹配问题：-

现在让我再做一轮检查，看还有没有遗漏：--

这两个是正常的——`HandlerContext` 对 agent 的引用，调用的 `_get_context` 和 `_save_contexts` 都确认存在于 `agent.py` 中。

现在来检查 `self_update_handler.py` 的 `handle` 方法签名与 `plan_executor.py` 的调用是否一致：

`plan_executor.py:132-138`:
```python
self._update.handle(
    chat_id, mid, ctx,
    plan.params.get("trigger_source", "manual"),
    plan.params.get("reason", "User requested update"),
)
```

但 `self_update_handler.py:23-28`:
```python
def handle(self, chat_id, message_id, ctx, reason="用户手动触发"):
```

`handle` 只接受 4 个参数（chat_id, message_id, ctx, reason），但调用方传了 5 个（多了一个 `trigger_source`）。这又是一个签名不匹配！-

现在做最后一轮搜索，确认没有其他残余问题：-

所有 import 都正确。注意到 `card_action.py` 导入了 `asyncio` 但实际上没有使用它（在之前的取消重构后，旧的异步取消逻辑已移除）。不过这只是一个 lint 警告，不会影响运行。

最后做一个完整的 `unused import` 检查：-

`card_action.py` 中有几个 unused imports：`asyncio`, `PendingConfirmation`, `PendingAction`, `RiskLevel`。让我确认它们在代码体中是否被使用：只出现在 import 行，确认全是 unused imports。清理掉：-

所有修复完成。下面给你完整的审计总结和流程验证。

---

## 完整审计总结

### 一、handlers 层残余引用检查

| 文件 | 问题 | 严重度 | 状态 |
|------|------|--------|------|
| `brain.py:429` | `agent._reply_card()` — 调用已删除方法 | 🔴 运行时必崩 | ✅ 已修复 → `messaging.reply_card()` |
| `brain.py:457` | `agent._update_card()` — 调用已删除方法 | 🔴 运行时必崩 | ✅ 已修复 → `messaging.update_card()` |
| `plan_executor.py:147` | `request_self_update(trigger_source=..., initiated_by=...)` — 签名不匹配 | 🟡 运行时 TypeError | ✅ 已修复 → 合并到 `reason` 参数 |
| `plan_executor.py:132` | `self._update.handle()` 传 5 个参数，签名只接受 4 个 | 🟡 运行时 TypeError | ✅ 已修复 → 合并 trigger+reason |
| `card_action.py` | `asyncio`, `PendingConfirmation`, `PendingAction`, `RiskLevel` unused imports | 🟢 lint 警告 | ✅ 已清理 |
| 其余注释引用 | `agent.py:11`, `base.py:10,44`, `task_handler.py:10`, `lifecycle_manager.py:10` 仅为历史说明 | ⚪ 无影响 | — |

### 二、完整流程验证：message → brain → task_handler → session_runner → card_update

```
1. 用户发送飞书消息 "帮我重构这段代码"
   ↓
2. MessageHandler.handle(data)
   ├── 解析 text, chat_id, message_id
   ├── 去重检查 (_MessageDeduplicator)
   └── _executor.submit(_process_message)
       ↓
3. _process_message(text, chat_id, message_id)
   ├── ctx = self.ctx.get_or_create_context(chat_id)  ✅ 正确调用 agent._get_context()
   └── plan, thinking_mid = _dispatch_message()
       ↓
4. _dispatch_message()
   ├── Level 1: brain._think_deterministic(text, ctx)
   │   └── mode=="coding" + no "!" → ActionPlan(action="send_task")  ✅
   │
   ├── Level 2: brain.think_with_feedback(text, ctx, chat_id, msg_id, agent)
   │   ├── messaging = agent.messaging  ✅ 修复后正确获取
   │   ├── thinking_mid = messaging.reply_card(...)  ✅ 修复后正确调用
   │   └── _think_llm() → ActionPlan  ✅
   │
   └── risk check (classify_risk) → confirmation if needed  ✅
       ↓
5. PlanExecutor.execute(plan, chat_id, message_id, ctx)
   └── _exec_task(plan, chat_id, mid, ctx)
       └── TaskHandler.handle(chat_id, mid, ctx, task_text, path)
           ↓
6. TaskHandler.handle()
   ├── op_id = op_tracker.start(path, desc, timeout=14400)  ✅
   ├── progress_card = CardRenderer.progress(show_cancel_button=True,
   │     cancel_action_data={"action":"cancel_task","task_id":op_id})  ✅
   ├── prog_mid = messaging.reply_card(message_id, progress_card)  ✅
   └── Thread → do_async_task → _execute_task()
       ↓
7. _execute_task() (async, 后台线程)
   ├── process_mgr.ensure_running_async(path)  ✅
   ├── process_mgr.get_or_create_api_session(path)  ✅
   ├── runner = SessionRunner(port=proc.port, callbacks=...)  ✅
   ├── op_tracker.register_cancel_callback(op_id, runner.cancel)  ✅ 新增关键注册
   ├── result = await runner.run(prompt, session_id, timeout)  ✅
   │   ├── SSE 流中实时回调 on_tool → CardRenderer.progress → messaging.update_card  ✅
   │   └── 检测 _cancel_event → result.was_cancelled=True  ✅
   ├── op_tracker.finish(op_id)  ✅ 清理 op + callback
   └── 结果处理:
       ├── success → _handle_success → LongOutputHandler → messaging.update_card  ✅
       ├── was_cancelled → CardRenderer.result("任务已取消") → messaging.update_card  ✅
       └── error → _handle_error → messaging.update_card  ✅
```

### 三、取消流程验证

```
用户点击 "❌ 取消任务" 按钮
  ↓
CardActionHandler._handle_cancel_task(value, chat_id)
  ├── task_id = value["task_id"]  ✅
  └── cancelled = op_tracker.cancel(task_id)  ✅
      ├── op.cancelled = True  ✅
      └── callback() → runner.cancel() → _cancel_event.set()  ✅
          ↓
SessionRunner.run() 的 SSE 循环:
  if self._cancel_event.is_set():
      result.was_cancelled = True
      return result  ✅
          ↓
TaskHandler._execute_task():
  ├── op_tracker.finish(op_id)  ✅ 清理资源
  └── result.was_cancelled → messaging.update_card(prog_mid, "任务已取消")  ✅
```

**整条链路端到端闭环，没有断裂点。** 你可以开始进行端到端验证了。
