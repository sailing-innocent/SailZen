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
