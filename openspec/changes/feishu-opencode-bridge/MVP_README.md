# Feishu-OpenCode Bridge - MVP 版本

## 已实现功能

✅ **基础架构**
- 飞书Webhook接收端点 (`/api/v1/feishu/webhook`)
- 消息解析和指令路由
- 本地Agent进程管理
- Git命令自动化（status/pull/commit/push）

✅ **支持指令**
- `/start-opencode [path]` - 提示启动OpenCode命令
- `/status` - 查看系统状态
- `/code <描述>` - 代码生成请求
- `/git-status` - Git状态
- `/git-pull` - 拉取代码
- `/git-commit "message"` - 提交代码
- `/git-push` - 推送代码

## 快速开始

### 1. 安装依赖

```bash
# 在项目根目录执行
uv sync
```

### 2. 启动后端服务

```bash
# 开发模式
uv run server.py --dev
```

服务器将运行在 `http://localhost:1974`

### 3. 启动本地Agent

```bash
# 在另一个终端窗口
python scripts/opencode_agent.py --project D:/ws/repos/SailZen
```

Agent启动后，你可以输入命令测试：
```
Agent> status    # 查看状态
Agent> start     # 启动OpenCode
Agent> commit    # 执行git commit
Agent> quit      # 退出
```

### 4. 测试Webhook

```bash
# 运行测试脚本
python scripts/test_feishu_bridge.py
```

## 手动测试飞书Webhook

使用curl模拟飞书消息：

```bash
curl -X POST http://localhost:1974/api/v1/feishu/webhook \
  -H "Content-Type: application/json" \
  -d '{
    "schema": "2.0",
    "header": {
      "event_id": "test-001",
      "event_type": "im.message.receive_v1",
      "app_id": "cli_test"
    },
    "event": {
      "sender": {"sender_id": {"open_id": "ou_test"}, "sender_type": "user"},
      "message": {
        "message_id": "om_test",
        "chat_type": "p2p",
        "message_type": "text",
        "content": "{\"text\": \"/status\"}"
      }
    }
  }'
```

## 飞书Bot配置（生产环境）

详见 [FEISHU_SETUP.md](./FEISHU_SETUP.md)

## 架构说明

### 当前MVP架构

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   飞书APP    │────▶│  SailServer │────▶│  本地Agent  │
│  (通过Webhook)│     │  /feishu/webhook │  │  (手动启动)  │
└─────────────┘     └─────────────┘     └──────┬──────┘
                                                 │
                         ┌───────────────────────┘
                         │
                         ▼
                  ┌─────────────┐
                  │   OpenCode  │
                  │  (手动启动)  │
                  └─────────────┘
```

### 完整版架构（后续实现）

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   飞书APP    │────▶│  SailServer │◄───▶│  本地Agent  │
│             │     │  + WebSocket │     │  (自动管理)  │
└─────────────┘     └──────┬──────┘     └──────┬──────┘
                           │                    │
                           │ 期望状态同步        │ 自动启动
                           │                    │
                    ┌──────▼──────┐     ┌──────▼──────┐
                    │    Redis    │     │   OpenCode  │
                    │ (desired_state)│  │  (自动管理)  │
                    └─────────────┘     └─────────────┘
```

## 下一步计划

### 短期（1-2周）
1. 实现WebSocket连接云端和本地Agent
2. 实现期望状态自动同步
3. 飞书消息自动回复
4. 添加交互式卡片支持

### 中期（1个月）
1. 完整的多会话管理
2. OpenCode Session自动创建
3. 代码diff展示
4. 多项目支持

### 长期
1. 多Agent并行
2. 自动代码审查
3. 集成测试执行
4. 团队协作功能

## 文件说明

```
openspec/changes/feishu-opencode-bridge/
├── proposal.md          # 项目提案
├── design.md           # 技术设计
├── tasks.md            # 任务列表
├── FEISHU_SETUP.md     # 飞书配置指南
└── MVP_README.md       # 本文件

sail_server/feishu_gateway/
├── __init__.py         # Gateway模块
├── webhook.py          # Webhook处理器
└── message_handler.py  # 消息处理器

scripts/
├── opencode_agent.py   # 本地Agent
└── test_feishu_bridge.py # 测试脚本
```

## 已知限制

1. **无WebSocket连接**：当前为单机模式，需要手动启动Agent
2. **飞书消息回复**：未接入飞书API，仅打印到控制台
3. **OpenCode自动启动**：仅提供命令提示，需手动执行
4. **无Redis存储**：配置存储在内存中
5. **单用户模式**：不支持多用户同时使用

## 贡献

如需扩展功能，请参阅完整设计文档：
- `design.md` - 架构设计
- `tasks.md` - 任务列表
- `specs/` - 详细规格说明
