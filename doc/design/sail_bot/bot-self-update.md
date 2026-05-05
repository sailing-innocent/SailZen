# Bot 自更新功能

## 概述

Bot 自更新功能允许你在修改代码后，通过飞书指令重启 bot 应用最新修改，无需手动停止和启动。

## 架构

```
┌─────────────┐      ┌──────────────┐      ┌─────────────┐
│   User      │──────▶│    Bot       │──────▶│  Watcher    │
│  (Feishu)   │       │   (bot.py)   │      │(bot_watcher)│
└─────────────┘      └──────────────┘      └─────────────┘
                            │                       │
                            │ exit(42)              │ git pull
                            ▼                       ▼
                     ┌──────────────┐      ┌─────────────┐
                     │  State       │      │  Restart    │
                     │  Backup      │      │  Bot        │
                     └──────────────┘      └─────────────┘
```

## 使用方式

### 1. 使用 Watcher（推荐）

启动时使用 `bot_watcher.py`：

```bash
uv run bot_watcher.py -c bot/opencode.bot.yaml
```

### 2. 触发更新

在飞书中发送：
```
更新bot
```

或

```
重启bot
```

### 3. 更新流程

1. Bot 收到更新指令
2. 创建会话状态备份
3. 断开飞书连接
4. 执行 `git pull`
5. 以退出码 42 退出
6. Watcher 检测到退出码 42
7. Watcher 执行 `git pull`（确认）
8. Watcher 重新启动 bot
9. 新 bot 从备份恢复状态

## 退出码说明

| 退出码 | 含义 | Watcher 行为 |
|--------|------|-------------|
| 0 | 正常退出 | 不再重启 |
| 42 | 请求更新重启 | git pull + 重启 |
| 其他 | 异常退出 | 指数退避后重启 |

## 状态文件

Watcher 维护重启状态：
- 路径：`~/.sailzen/bot_restart_state.json`
- 包含：重启次数、上次退出码、git pull 状态等
- 超过 1 小时自动重置重启计数

## 直接运行（无自更新）

如果不使用 watcher，可以直接运行 bot：

```bash
uv run bot.py -c bot/opencode.bot.yaml
```

但此时 `更新bot` 指令不会生效。

## 注意事项

1. **Watcher 必须在 Bot 之前启动**，Watcher 负责管理 Bot 进程
2. **不要在 Bot 运行时直接修改代码**，通过 git 提交和拉取
3. **重启期间会有短暂离线**（5-10 秒），Bot 会自动重连
4. **状态备份包括**：会话状态、待处理操作、聊天记录上下文

## 故障排除

### Bot 无限重启

检查 `~/.sailzen/bot_restart_state.json`，如果 `consecutive_crashes` 持续增加：
- 查看 bot 日志找出崩溃原因
- 手动删除状态文件重置计数

### 更新后代码未生效

1. 确认代码已提交到 git
2. 检查 watcher 日志中的 git pull 输出
3. 手动执行 `git pull` 验证

### 状态未恢复

检查备份文件：
```bash
ls -la ~/.sailzen/bot_backups/
```

如果备份不存在，可能是状态管理器初始化失败。
