# SailZen Feishu Dev Bot - Phase 0 MVP

飞书 Bot 实现自更新能力的第一阶段 MVP。

## 功能特性

### 核心功能 (已完成)

1. **Bot 状态管理** (`bot_state_manager.py`)
   - 会话状态序列化与持久化
   - 自动备份创建 (更新前)
   - 状态恢复 (更新后)
   - 过期备份清理

2. **自更新编排** (`self_update_orchestrator.py`)
   - 检测更新触发 (从 OpenCode Session)
   - 备份当前状态
   - 断开飞书连接
   - 启动新 uv run session
   - 优雅清理旧进程

3. **长连接客户端** (`bot_runtime.py`)
   - 基于 lark-oapi 的 WebSocket 长连接
   - 消息接收与处理
   - 状态持久化心跳

4. **Control Plane 整合** (`bot_control_integration.py`)
   - 工作区会话管理
   - 会话状态监控
   - Edge Runtime 同步
   - 交互卡片渲染

## 快速开始

### 1. 配置环境

创建 `.env.feishu` 文件：

```bash
# 从飞书开放平台获取
# https://open.feishu.cn/app
FEISHU_APP_ID=cli_xxxxxxxxxxxxxxxx
FEISHU_APP_SECRET=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

### 2. 启动 Bot

```bash
# 正常启动
uv run python scripts/feishu_dev_bot.py

# Mock 模式 (无真实飞书连接)
uv run python scripts/feishu_dev_bot.py --mock

# 从备份恢复
uv run python scripts/feishu_dev_bot.py --restore
```

### 3. 触发自更新

从 OpenCode session 中：

```bash
# 启动并触发更新
uv run python scripts/feishu_dev_bot.py --from-opencode --update-trigger
```

## 自更新流程

```
┌─────────────────┐
│  OpenCode通知    │
│  可以更新        │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  1. 备份状态     │
│  (pickle + json) │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  2. 断开连接     │
│  (WebSocket)     │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  3. 启动新进程   │
│  (uv run)        │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  4. 恢复状态     │
│  (handover file) │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  5. 清理退出     │
│  (旧进程优雅关闭) │
└─────────────────┘
```

## 文件结构

```
sail_server/feishu_gateway/
├── __init__.py                  # 模块导出
├── bot_runtime.py              # 主运行时
├── bot_state_manager.py        # 状态管理
├── self_update_orchestrator.py # 自更新编排
├── bot_control_integration.py  # Control Plane 整合
├── cards.py                    # 卡片渲染
├── session_orchestrator.py     # 会话编排
├── delivery.py                 # 消息投递
├── intent_router.py            # 意图路由
└── policy.py                   # 安全策略

scripts/
└── feishu_dev_bot.py           # 启动脚本
```

## 使用示例

### 查看状态

在飞书中发送：
```
状态
```

返回：
```
🤖 **SailZen Bot 状态**

会话ID: bot_20260329...
启动时间: 2026-03-29T...
上次心跳: 2026-03-29T...

活跃会话: 0
工作区状态: 1
待确认操作: 0

飞书连接: ✅ 已连接
自更新就绪: ✅ 是
```

### 触发自更新

在飞书中发送：
```
更新
```

Bot 将：
1. 回复确认消息
2. 备份当前状态
3. 断开飞书连接
4. 启动新进程
5. 新进程恢复状态并重新连接
6. 旧进程优雅退出

### 会话控制

```
启动会话 sailzen
停止会话 sailzen
重启会话 sailzen
```

## 技术细节

### 状态备份格式

```python
@dataclass
class BotSessionState:
    session_id: str           # 会话唯一ID
    created_at: str          # 创建时间
    backup_at: str           # 备份时间
    
    # 飞书连接状态
    chat_contexts: Dict      # 聊天上下文
    active_threads: Dict     # 活跃线程
    pending_confirmations: Dict  # 待确认操作
    
    # 工作区状态
    active_sessions: Dict    # 活跃会话
    workspace_states: Dict   # 工作区状态
    
    # 更新追踪
    update_reason: str       # 更新原因
    update_initiated_by: str # 更新发起者
```

### 进程间通信

使用临时文件进行进程间握手：

```
/tmp/sailzen_bot_handover/
├── handover_YYYYMMDD_HHMMSS_PID.json    # 握手数据
├── handover_YYYYMMDD_HHMMSS_PID.ready   # 新进程就绪信号
└── handover_YYYYMMDD_HHMMSS_PID.complete # 完成信号
```

### 锁机制

- **Windows**: 使用 `msvcrt.locking`
- **Unix**: 使用 `fcntl.flock`

确保同一时间只有一个 Bot 实例运行。

## 配置选项

### 环境变量

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `FEISHU_APP_ID` | 飞书 App ID | - |
| `FEISHU_APP_SECRET` | 飞书 App Secret | - |
| `SAILZEN_WORKSPACE_ROOT` | 工作区根目录 | `D:/ws/repos/SailZen` |
| `LOG_LEVEL` | 日志级别 | `INFO` |

### 启动参数

| 参数 | 说明 |
|------|------|
| `--mock` | Mock 模式 |
| `--restore` | 从备份恢复 |
| `--from-opencode` | 从 OpenCode 启动 |
| `--update-trigger` | 触发自更新 |
| `--status` | 显示状态 |

## 后续开发

### Phase 0.1 (计划中)

- [ ] 完整的 Feishu API 集成
- [ ] 交互式卡片响应
- [ ] 会话状态实时推送
- [ ] 错误恢复机制

### Phase 0.2 (计划中)

- [ ] 多工作区支持
- [ ] 开发任务追踪
- [ ] 代码变更通知
- [ ] 与 OpenCode 深度集成

## 故障排除

### Bot 无法启动

```bash
# 检查环境配置
cat .env.feishu

# 检查状态
uv run python scripts/feishu_dev_bot.py --status

# 清理锁文件
rm ~/.sailzen/bot_backups/*.lock
```

### 自更新失败

1. 检查 uv 是否可用
2. 检查备份文件是否存在
3. 查看 handover 文件状态
4. 手动恢复：`--restore`

### 飞书连接断开

1. 检查网络连接
2. 验证 App ID/Secret
3. 查看飞书开发者控制台
4. 检查 IP 白名单

## 贡献

本项目是 SailZen 3.0 的一部分。

## 许可证

MIT License
