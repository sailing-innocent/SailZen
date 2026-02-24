# AI Agent 系统设计总结

## 核心概念

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│  User Prompt    │────▶│  Agent Task     │────▶│  Agent Steps    │
│  (用户提示队列)  │     │  (Agent实例)    │     │  (执行步骤记录) │
└─────────────────┘     └─────────────────┘     └─────────────────┘
        │                                              │
        │                       ┌─────────────────┐    │
        └──────────────────────▶│  Agent Output   │◀───┘
                                │  (输出结果)     │
                                └─────────────────┘
```

## 数据模型（4个核心表）

### 1. user_prompts - 用户提示队列
| 字段 | 说明 |
|------|------|
| content | 用户请求内容 |
| prompt_type | 类型: general/code/analysis/writing |
| priority | 优先级 1-10 (1最高) |
| status | pending → scheduled → processing → completed/failed |

### 2. agent_tasks - Agent 任务
| 字段 | 说明 |
|------|------|
| prompt_id | 关联的提示 |
| agent_type | Agent类型: general/coder/analyst/writer |
| status | created → running → completed/failed |
| progress | 进度 0-100% |

### 3. agent_steps - 执行步骤
| 字段 | 说明 |
|------|------|
| task_id | 关联的任务 |
| step_number | 步骤序号 |
| step_type | thought/action/observation/error/completion |
| content | 步骤内容 |

### 4. agent_scheduler_state - 调度器状态（单例）
| 字段 | 说明 |
|------|------|
| is_running | 调度器是否运行 |
| active_agent_count | 当前活跃 Agent 数 |
| max_concurrent_agents | 最大并发数 |

## 工作流程

```
1. 用户提交 Prompt (POST /api/v1/agent/prompt)
        ↓
2. Prompt 状态 = pending，存入 user_prompts
        ↓
3. 调度器轮询 (每5秒)
        ↓
4. 选取最紧急的 pending Prompt
   (按 priority ASC, created_at ASC 排序)
        ↓
5. 创建 AgentTask，状态 = created
   Prompt 状态 = scheduled
        ↓
6. Spawn AgentRunner 异步执行
   Task 状态 = running
   Prompt 状态 = processing
        ↓
7. AgentRunner 记录 Steps，更新 Progress
        ↓
8. 完成后创建 AgentOutput
   Task 状态 = completed
   Prompt 状态 = completed
        ↓
9. 通过 WebSocket 实时推送事件给前端
```

## 调度策略

```python
# 优先级算法：priority 升序 -> created_at 升序
pending_prompts = db.query(UserPrompt).filter(
    UserPrompt.status == 'pending'
).order_by(
    UserPrompt.priority.asc(),      # 数字小优先
    UserPrompt.created_at.asc()     # 先创建先处理
).limit(available_slots).all()
```

## 并发控制

```python
max_concurrent_agents = 3  # 可配置

available_slots = max_concurrent_agents - len(active_runners)
if available_slots <= 0:
    return  # 等待下次轮询
```

## 前端状态反馈

### REST API 查询
- `GET /api/v1/agent/prompt` - 提示列表
- `GET /api/v1/agent/task/{id}` - 任务详情（含步骤）
- `GET /api/v1/agent/scheduler/status` - 调度器状态

### WebSocket 实时推送
```javascript
ws://localhost:4399/api/v1/agent/ws/events

// 事件类型:
- task_scheduled   // 任务已调度
- task_started     // 任务开始执行
- step_update      // 新步骤产生
- progress_update  // 进度更新
- task_completed   // 任务完成
- task_failed      // 任务失败
```

## 关键代码文件

| 文件 | 说明 |
|------|------|
| `sail_server/data/agent.py` | 数据模型和DTOs |
| `sail_server/model/agent/scheduler.py` | 调度器核心 |
| `sail_server/model/agent/runner.py` | Agent 运行器 |
| `sail_server/router/agent.py` | API 路由 |
| `sail_server/migration/create_agent_tables.sql` | 数据库迁移 |

## 扩展性

1. **新 Agent 类型**：添加 `agent_type` 和对应的 Agent 类
2. **自定义调度**：修改 `_determine_agent_type()` 实现智能路由
3. **优先级策略**：扩展 `priority` 字段或使用更复杂的排序逻辑

## 安全考虑

1. **并发限制**：防止资源耗尽
2. **超时机制**：`timeout_seconds` 防止无限执行
3. **最大迭代**：`max_iterations` 防止无限循环
4. **状态校验**：状态转换时的有效性检查
