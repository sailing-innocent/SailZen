# AI Agent 系统集成指南

## 概述

本文档描述了如何将 AI Agent 系统集成到现有的 SailServer 中。

## 文件结构

创建以下文件：

```
sail_server/
├── data/
│   └── agent.py              # 数据模型和 DTOs（已创建）
├── model/
│   └── agent/
│       ├── __init__.py       # 包初始化
│       ├── scheduler.py      # 调度器核心逻辑
│       └── runner.py         # Agent 运行器
├── router/
│   └── agent.py              # API 路由（已创建）
└── migration/
    └── create_agent_tables.sql  # 数据库迁移（已创建）
```

## 集成步骤

### 1. 运行数据库迁移

```bash
# 使用 psql 执行迁移
psql -d your_database -f sail_server/migration/create_agent_tables.sql
```

### 2. 更新 db.py

在 `sail_server/db.py` 中导入 agent 数据模型：

```python
# sail_server/db.py

# import all ORM models
# ... existing imports ...
import sail_server.data.agent  # 添加这一行
```

### 3. 创建调度器和运行器

创建 `sail_server/model/agent/__init__.py`：

```python
# sail_server/model/agent/__init__.py
from .scheduler import AgentScheduler, get_agent_scheduler, set_agent_scheduler

__all__ = [
    'AgentScheduler',
    'get_agent_scheduler',
    'set_agent_scheduler',
]
```

创建 `sail_server/model/agent/scheduler.py`（核心代码见设计文档）

创建 `sail_server/model/agent/runner.py`（核心代码见设计文档）

### 4. 更新 server.py

修改 `server.py` 集成 Agent 系统：

```python
# server.py

class SailServer:
    def init(self):
        # ... existing code ...
        
        from sail_server.router.agent import router as agent_router
        
        self.api_router = Router(
            path=self.api_endpoint,
            route_handlers=[
                # ... existing routers ...
                agent_router,  # 添加 Agent 路由
            ],
        )
        # ...
    
    async def on_startup(self):
        logger.info("Server starting up...")
        
        # 启动 Agent 调度器
        from sail_server.model.agent import get_agent_scheduler
        scheduler = get_agent_scheduler()
        await scheduler.start()
        logger.info("Agent scheduler started")
    
    async def on_shutdown(self):
        logger.info("Server shutting down...")
        
        # 停止 Agent 调度器
        from sail_server.model.agent import get_agent_scheduler
        scheduler = get_agent_scheduler()
        await scheduler.stop()
        logger.info("Agent scheduler stopped")
```

### 5. 配置环境变量（可选）

在 `.env` 文件中添加：

```bash
# Agent Scheduler 配置
AGENT_POLL_INTERVAL=5.0        # 轮询间隔（秒）
AGENT_MAX_CONCURRENT=3         # 最大并发 Agent 数量
AGENT_TIMEOUT_SECONDS=3600     # Agent 默认超时时间
```

## API 端点

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
| POST | `/api/v1/agent/scheduler/config` | 更新调度器配置 |

## 使用示例

### 1. 提交用户提示

```bash
curl -X POST http://localhost:4399/api/v1/agent/prompt \
  -H "Content-Type: application/json" \
  -d '{
    "content": "请帮我分析这段代码的性能问题",
    "prompt_type": "code",
    "priority": 3,
    "context": {"language": "python", "file_path": "/path/to/file.py"}
  }'
```

响应：
```json
{
  "id": 1,
  "content": "请帮我分析这段代码的性能问题",
  "prompt_type": "code",
  "priority": 3,
  "status": "pending",
  "created_at": "2025-02-24T10:00:00"
}
```

### 2. 查询任务状态

```bash
curl http://localhost:4399/api/v1/agent/task/1
```

响应：
```json
{
  "task": {
    "id": 1,
    "prompt_id": 1,
    "agent_type": "coder",
    "status": "running",
    "progress": 45,
    "step_count": 5
  },
  "steps": [
    {
      "id": 1,
      "step_number": 1,
      "step_type": "thought",
      "title": "分析代码结构",
      "content": "正在分析代码的整体结构..."
    }
  ],
  "outputs": [],
  "prompt": {
    "id": 1,
    "content": "请帮我分析这段代码的性能问题"
  }
}
```

### 3. 获取调度器状态

```bash
curl http://localhost:4399/api/v1/agent/scheduler/status
```

响应：
```json
{
  "is_running": true,
  "active_agent_count": 2,
  "max_concurrent_agents": 3,
  "total_processed": 10,
  "total_failed": 1,
  "last_poll_at": "2025-02-24T10:05:00"
}
```

## 前端集成

### 1. API 客户端

```typescript
// api/agent.ts

export interface UserPrompt {
  id: number;
  content: string;
  prompt_type: string;
  priority: number;
  status: string;
  created_at: string;
}

export interface AgentTask {
  id: number;
  prompt_id: number;
  agent_type: string;
  status: string;
  progress: number;
  step_count: number;
}

export class AgentAPI {
  async createPrompt(content: string, options?: Partial<UserPrompt>): Promise<UserPrompt> {
    const res = await fetch('/api/v1/agent/prompt', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ content, ...options }),
    });
    return res.json();
  }
  
  async getTask(id: number): Promise<{ task: AgentTask; steps: AgentStep[]; outputs: AgentOutput[] }> {
    const res = await fetch(`/api/v1/agent/task/${id}`);
    return res.json();
  }
  
  async getSchedulerStatus(): Promise<SchedulerState> {
    const res = await fetch('/api/v1/agent/scheduler/status');
    return res.json();
  }
}
```

### 2. WebSocket 实时更新

```typescript
// hooks/useAgentWebSocket.ts

export function useAgentWebSocket(onEvent: (event: AgentStreamEvent) => void) {
  useEffect(() => {
    const ws = new WebSocket('ws://localhost:4399/api/v1/agent/ws/events');
    
    ws.onmessage = (event) => {
      const data = JSON.parse(event.data);
      onEvent(data);
    };
    
    return () => ws.close();
  }, [onEvent]);
}
```

### 3. React 组件示例

```tsx
// components/AgentMonitor.tsx

export function AgentMonitor() {
  const [tasks, setTasks] = useState<AgentTask[]>([]);
  const [schedulerState, setSchedulerState] = useState<SchedulerState | null>(null);
  
  useAgentWebSocket((event) => {
    switch (event.event_type) {
      case 'task_scheduled':
      case 'task_started':
        // 刷新任务列表
        loadTasks();
        break;
      case 'progress_update':
        // 更新特定任务的进度
        updateTaskProgress(event.task_id, event.data.progress);
        break;
      case 'task_completed':
        // 任务完成，显示通知
        showNotification(`Task ${event.task_id} completed!`);
        break;
    }
  });
  
  return (
    <div>
      <SchedulerStatus state={schedulerState} />
      <TaskList tasks={tasks} />
    </div>
  );
}
```

## 扩展指南

### 添加新的 Agent 类型

1. 在 `sail_server/model/agent/agents/` 目录下创建新的 Agent 实现
2. 继承 `BaseAgent` 类
3. 在调度器中注册新的 Agent 类型映射

```python
# sail_server/model/agent/agents/coder.py

class CoderAgent(BaseAgent):
    """代码分析 Agent"""
    
    async def run(self):
        # 1. 解析代码
        await self.add_step('thought', '解析代码结构')
        
        # 2. 分析性能
        await self.add_step('action', '执行性能分析')
        
        # 3. 生成报告
        await self.add_step('completion', '生成分析报告')
```

### 自定义调度策略

修改 `AgentScheduler._determine_agent_type()` 方法实现智能路由：

```python
def _determine_agent_type(self, prompt: UserPrompt) -> str:
    # 基于内容分析的智能路由
    content = prompt.content.lower()
    
    if any(kw in content for kw in ['代码', 'code', '函数', 'bug']):
        return 'coder'
    elif any(kw in content for kw in ['分析', '统计', '数据']):
        return 'analyst'
    elif any(kw in content for kw in ['写作', '写作', '文章']):
        return 'writer'
    
    return 'general'
```

## 注意事项

1. **并发控制**：调度器使用 `max_concurrent_agents` 限制并发数，避免资源耗尽
2. **超时处理**：每个任务有 `timeout_seconds` 限制，超时后自动标记为失败
3. **错误处理**：Agent 执行过程中的错误会被捕获并记录到 `error_message` 字段
4. **状态同步**：数据库状态是权威状态，调度器内存中的状态仅用于运行时管理
