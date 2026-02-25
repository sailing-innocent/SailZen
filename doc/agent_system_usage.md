# Agent 系统使用指南

## 概述

这是一个基础版本的 AI Agent 系统，用于调试前后端 UI 状态。当前实现使用 Mock 数据（随机延时和随机失败），不实际接入 LLM。

## 功能特性

1. **用户提示队列 (UserPrompt)**
   - 提交用户请求
   - 优先级调度（1-10，1为最高）
   - 状态跟踪：pending → scheduled → processing → completed/failed/cancelled

2. **Agent 任务 (AgentTask)**
   - 自动调度执行
   - 实时进度跟踪（0-100%）
   - 步骤记录（thought/action/observation/error/completion）
   - 支持取消操作

3. **调度器 (Scheduler)**
   - 可配置最大并发数（默认3个）
   - 自动轮询待处理任务
   - 基于优先级的调度策略

4. **实时更新**
   - WebSocket 推送状态变更
   - 前端自动刷新任务列表和详情

## 后端 API

### User Prompt API

| 方法 | 路径 | 描述 |
|------|------|------|
| POST | `/api/v1/agent/prompt` | 提交新的用户提示 |
| GET | `/api/v1/agent/prompt` | 获取提示列表 |
| GET | `/api/v1/agent/prompt/{id}` | 获取提示详情 |
| POST | `/api/v1/agent/prompt/{id}/cancel` | 取消待处理提示 |
| DELETE | `/api/v1/agent/prompt/{id}` | 删除提示 |

### Agent Task API

| 方法 | 路径 | 描述 |
|------|------|------|
| GET | `/api/v1/agent/task` | 获取任务列表 |
| GET | `/api/v1/agent/task/{id}` | 获取任务详情（含步骤和输出） |
| GET | `/api/v1/agent/task/{id}/steps` | 获取任务步骤 |
| POST | `/api/v1/agent/task/{id}/cancel` | 取消任务 |

### Scheduler API

| 方法 | 路径 | 描述 |
|------|------|------|
| GET | `/api/v1/agent/scheduler/status` | 获取调度器状态 |
| POST | `/api/v1/agent/scheduler/start` | 启动调度器 |
| POST | `/api/v1/agent/scheduler/stop` | 停止调度器 |
| POST | `/api/v1/agent/scheduler/config` | 更新配置 |

### WebSocket

| 路径 | 描述 |
|------|------|
| `ws://host:port/api/v1/agent/ws/events` | 实时事件流 |

事件类型：
- `task_scheduled` - 任务已调度
- `task_started` - 任务开始执行
- `step_update` - 新步骤更新
- `progress_update` - 进度更新
- `task_completed` - 任务完成
- `task_failed` - 任务失败
- `task_cancelled` - 任务取消

## 快速开始

### 1. 数据库迁移

```bash
# 使用 psql 执行迁移
psql -d your_database -f sail_server/migration/create_agent_tables.sql
```

### 2. 启动服务器

```bash
# 开发模式
uv run server.py --dev

# 生产模式
uv run server.py
```

服务器启动时会自动：
- 导入 Agent 数据模型
- 注册 Agent 路由
- 启动 Agent 调度器

### 3. 使用前端界面

访问前端页面，使用 AgentMonitor 组件调试：

```tsx
import { AgentMonitor } from '@/components/agent_monitor';

function AgentPage() {
  return <AgentMonitor />;
}
```

## Mock 行为配置

在 `sail_server/model/agent/runner.py` 中可以调整 Mock 行为：

```python
class AgentRunner:
    MOCK_MIN_DELAY = 0.5      # 最小步骤延时（秒）
    MOCK_MAX_DELAY = 2.0      # 最大步骤延时（秒）
    MOCK_FAILURE_RATE = 0.2   # 失败率（20%）
    MOCK_MIN_STEPS = 3        # 最小步骤数
    MOCK_MAX_STEPS = 6        # 最大步骤数
```

## 测试 API

### 提交提示

```bash
curl -X POST http://localhost:4399/api/v1/agent/prompt \
  -H "Content-Type: application/json" \
  -d '{
    "content": "请帮我分析这段代码",
    "prompt_type": "code",
    "priority": 3
  }'
```

### 查看调度器状态

```bash
curl http://localhost:4399/api/v1/agent/scheduler/status
```

### 查看任务列表

```bash
curl http://localhost:4399/api/v1/agent/task
```

### 查看任务详情

```bash
curl http://localhost:4399/api/v1/agent/task/1
```

## 前端状态管理

使用 Zustand store 管理 Agent 状态：

```tsx
import { useAgentStore } from '@/lib/store/agentStore';

function MyComponent() {
  const { 
    tasks, 
    currentTask, 
    schedulerState,
    submitPrompt,
    loadTasks,
    connectRealtimeUpdates 
  } = useAgentStore();

  useEffect(() => {
    connectRealtimeUpdates();
  }, []);

  // ...
}
```

## 后续扩展

1. **接入真实 LLM**
   - 修改 `AgentRunner._run_agent_logic()` 方法
   - 集成 OpenAI/Google/Moonshot API

2. **添加更多 Agent 类型**
   - 在 `sail_server/model/agent/agents/` 目录下创建新的 Agent 实现
   - 继承 BaseAgent 类（待实现）

3. **任务重试机制**
   - 添加失败任务自动重试
   - 配置重试次数和间隔

4. **优先级策略增强**
   - 支持权重调度
   - 支持截止时间优先级

5. **Agent 间协作**
   - 支持多 Agent 协作完成任务
   - 添加 Agent 间通信机制
