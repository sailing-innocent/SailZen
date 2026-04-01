# Feishu Bot 入口合并说明

## 问题背景

之前项目中存在两个 Feishu Bot 入口文件，功能重叠但各有侧重：

### 1. `scripts/feishu_dev_bot.py` (Phase 0 MVP Launcher)
- **定位**: 轻量级启动器
- **特点**: 使用 `SailZenBotRuntime` 架构，支持自更新、状态恢复
- **不足**: 功能简单，缺少丰富的用户交互（卡片、LLM意图识别等）

### 2. `bot/feishu_agent.py` (Legacy Full Implementation)
- **定位**: 完整的老版本实现
- **特点**: 包含 LLM意图识别、卡片系统、OpenCode会话管理、对话上下文
- **不足**: 独立运行，未使用新的 gateway 架构

## 合并方案

创建统一的 `./bot.py` 入口文件，整合两个文件的优点：

### 新入口特性

| 特性 | 来源 | 说明 |
|------|------|------|
| **SailZenBotRuntime 架构** | `scripts/feishu_dev_bot.py` | 长连接 Feishu 客户端、状态管理、自更新 |
| **OpenCode 会话管理** | `bot/feishu_agent.py` | 启动/停止工作区、发送任务、状态追踪 |
| **LLM 意图识别** | `bot/feishu_agent.py` | 支持多 provider 的意图理解 |
| **对话上下文** | `bot/feishu_agent.py` | 多轮对话、工作区切换 |
| **简化版卡片系统** | `bot/feishu_agent.py` | 文本回复（可扩展为富文本卡片） |
| **统一配置** | 两者整合 | 支持 `.env.feishu` 配置文件 |

## 迁移指南

### 之前的使用方式

```bash
# 方式1: 使用 scripts/feishu_dev_bot.py
uv run python scripts/feishu_dev_bot.py

# 方式2: 使用 bot/feishu_agent.py
uv run python bot/feishu_agent.py -c bot/opencode.bot.yaml
```

### 新的使用方式

```bash
# 启动 Bot（推荐）
uv run python bot.py

# 使用特定配置
uv run python bot.py --config .env.feishu

# Mock 模式（测试用）
uv run python bot.py --mock

# 查看状态
uv run python bot.py --status

# 从 OpenCode 触发自更新
uv run python bot.py --from-opencode --update-trigger
```

## 配置文件

创建 `.env.feishu` 文件（如果还不存在）：

```bash
# Feishu Bot Configuration
FEISHU_APP_ID=cli_xxxxxxxxxxxxxxxx
FEISHU_APP_SECRET=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx

# Optional: Override workspace root
SAILZEN_WORKSPACE_ROOT=D:/ws/repos/SailZen

# Optional: LLM Configuration
LLM_PROVIDER=moonshot
LLM_API_KEY=your_api_key_here
```

## 架构对比

### 旧架构（两个独立入口）

```
┌─────────────────────┐     ┌─────────────────────┐
│ scripts/feishu_dev  │     │ bot/feishu_agent.py │
│    _bot.py          │     │                     │
├─────────────────────┤     ├─────────────────────┤
│ • SailZenBotRuntime │     │ • FeishuBotAgent    │
│ • Self-update       │     │ • OpenCodeSessionMgr│
│ • State management  │     │ • BotBrain (LLM)    │
│ • Basic commands    │     │ • Card system       │
└─────────────────────┘     │ • Rich interaction  │
                            └─────────────────────┘
```

### 新架构（统一入口）

```
┌─────────────────────────────┐
│         ./bot.py            │
├─────────────────────────────┤
│  SailZenFeishuBot           │
├─────────────────────────────┤
│  • FeishuClient (长连接)     │
│  • OpenCodeSessionManager   │
│  • BotBrain (LLM意图)        │
│  • Self-update orchestrator │
│  • State manager            │
└─────────────────────────────┘
```

## 保留的旧文件

以下文件暂时保留用于参考和向后兼容：

- `scripts/feishu_dev_bot.py` - 原始 Phase 0 启动器
- `bot/feishu_agent.py` - 完整的老版本实现（包含卡片渲染等）

**注意**: 新开发请使用 `./bot.py`，旧文件可能会在未来版本中移除。

## 功能差异

### 新入口 `./bot.py` 相对旧入口的改进

1. **统一架构**: 基于 `SailZenBotRuntime` 设计，与 gateway 模块集成更好
2. **简化的依赖**: 不需要 `card_renderer.py` 和 `session_state.py` 等辅助文件
3. **更清晰的代码结构**: 单一文件包含所有核心功能
4. **更好的错误处理**: 统一的异常处理和日志

### 暂时缺少的功能（可后续添加）

1. **富文本卡片**: 当前使用纯文本回复，可以后续添加卡片支持
2. **操作确认卡片**: 当前使用文本确认，可以添加交互式确认卡片
3. **进度卡片**: 当前使用文本进度，可以添加动态进度卡片
4. **项目快捷方式**: 需要在配置中添加 `projects` 列表支持

## 使用示例

### 启动工作区

```
用户: 启动 sailzen
Bot: 正在启动工作区: sailzen...
Bot: 工作区已启动！
路径: D:\ws\repos\SailZen
端口: 4096
PID: 12345
```

### 发送开发任务

```
用户: 帮我修复 health API 的 bug
Bot: 正在向 sailzen 发送任务...
Bot: **任务完成**

[OpenCode 的回复内容...]
```

### 查看状态

```
用户: 状态
Bot: ```
Session Status
========================================
[running] D:\ws\repos\SailZen
  Port: 4096  PID: 12345
  OpenCode session: sess_abc123
```
```

### 停止工作区

```
用户: 停止 sailzen
Bot: 已停止: sailzen
```

## 后续计划

1. **Phase 0 完成**: 稳定基础功能，确保日常可用
2. **卡片系统增强**: 添加富文本卡片支持
3. **Control Plane 集成**: 与 `control_plane/` 模块深度集成
4. **移除旧文件**: 在 `./bot.py` 稳定后，移除旧入口文件

## 故障排除

### 问题: `lark-oapi` 未安装

**解决**: `uv add lark-oapi`

### 问题: `httpx` 未安装

**解决**: `uv add httpx`

### 问题: Feishu 凭证无效

**解决**: 编辑 `.env.feishu` 文件，从 https://open.feishu.cn/app 获取正确的 App ID 和 Secret

### 问题: OpenCode 命令未找到

**解决**: 确保 `opencode` 已安装并在 PATH 中

---

**创建日期**: 2026-03-30
**版本**: 1.0
