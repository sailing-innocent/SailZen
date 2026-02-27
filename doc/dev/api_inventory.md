# API 接口清单

> Agent 系统和小说分析系统的完整 API 接口列表

---

## 1. Agent API (`/api/v1/agent`)

### 1.1 User Prompt 接口

| # | 方法 | 路径 | 请求参数 | 响应 | 实现状态 | 兼容策略 |
|---|-----|------|---------|------|---------|---------|
| 1 | POST | `/prompt` | `CreatePromptRequest` | `UserPrompt` | ✅ 已实现 | 转发到新 API |
| 2 | GET | `/prompt` | `?status=&skip=&limit=` | `UserPrompt[]` | ✅ 已实现 | 转发到新 API |
| 3 | GET | `/prompt/{id}` | - | `UserPrompt` | ✅ 已实现 | 转发到新 API |
| 4 | POST | `/prompt/{id}/cancel` | - | `UserPrompt` | ✅ 已实现 | 转发到新 API |
| 5 | DELETE | `/prompt/{id}` | - | `UserPrompt` | ✅ 已实现 | 转发到新 API |

#### CreatePromptRequest
```typescript
{
  content: string;           // 用户请求内容
  prompt_type?: string;      // general | code | analysis | writing | data
  context?: Record<string, any>;
  priority?: number;         // 1-10, 1为最高
  session_id?: string;
  parent_prompt_id?: number;
}
```

#### UserPrompt
```typescript
{
  id: number;
  content: string;
  prompt_type: string;
  context: Record<string, any>;
  priority: number;
  status: 'pending' | 'scheduled' | 'processing' | 'completed' | 'failed' | 'cancelled';
  created_by?: string;
  session_id?: string;
  parent_prompt_id?: number;
  created_at: string;
  scheduled_at?: string;
  started_at?: string;
  completed_at?: string;
}
```

### 1.2 Agent Task 接口

| # | 方法 | 路径 | 请求参数 | 响应 | 实现状态 | 兼容策略 |
|---|-----|------|---------|------|---------|---------|
| 6 | GET | `/task` | `?status=&skip=&limit=` | `AgentTask[]` | ✅ 已实现 | 转发到新 API |
| 7 | GET | `/task/{id}` | - | `AgentTaskDetailResponse` | ✅ 已实现 | 转发到新 API |
| 8 | GET | `/task/{id}/steps` | `?skip=&limit=` | `AgentStep[]` | ✅ 已实现 | 转发到新 API |
| 9 | POST | `/task/{id}/cancel` | - | `AgentTask` | ✅ 已实现 | 转发到新 API |

#### AgentTask
```typescript
{
  id: number;
  prompt_id: number;
  agent_type: string;        // general | coder | analyst | writer
  agent_config: Record<string, any>;
  status: 'created' | 'preparing' | 'running' | 'paused' | 'completed' | 'failed' | 'cancelled';
  progress: number;          // 0-100
  created_at: string;
  started_at?: string;
  updated_at?: string;
  completed_at?: string;
  error_message?: string;
  error_code?: string;
  step_count: number;
}
```

#### AgentStep
```typescript
{
  id: number;
  task_id: number;
  step_number: number;
  step_type: 'thought' | 'action' | 'observation' | 'error' | 'completion';
  title?: string;
  content?: string;
  content_summary?: string;
  meta_data: Record<string, any>;
  created_at: string;
  duration_ms?: number;
}
```

#### AgentOutput
```typescript
{
  id: number;
  task_id: number;
  output_type: 'text' | 'code' | 'file' | 'json' | 'error';
  content?: string;
  file_path?: string;
  meta_data: Record<string, any>;
  review_status: 'pending' | 'approved' | 'rejected';
  reviewed_by?: string;
  reviewed_at?: string;
  review_notes?: string;
  created_at: string;
}
```

#### AgentTaskDetailResponse
```typescript
{
  task: AgentTask;
  steps: AgentStep[];
  outputs: AgentOutput[];
  prompt: UserPrompt;
}
```

### 1.3 Scheduler 接口

| # | 方法 | 路径 | 请求参数 | 响应 | 实现状态 | 兼容策略 |
|---|-----|------|---------|------|---------|---------|
| 10 | GET | `/scheduler/status` | - | `SchedulerState` | ✅ 已实现 | 保留 |
| 11 | POST | `/scheduler/start` | - | `SchedulerState` | ✅ 已实现 | 转发到新调度器 |
| 12 | POST | `/scheduler/stop` | - | `SchedulerState` | ✅ 已实现 | 转发到新调度器 |
| 13 | POST | `/scheduler/config` | `?max_concurrent_agents=` | `SchedulerState` | ✅ 已实现 | 保留 |

#### SchedulerState
```typescript
{
  is_running: boolean;
  last_poll_at?: string;
  active_agent_count: number;
  max_concurrent_agents: number;
  total_processed: number;
  total_failed: number;
  updated_at?: string;
}
```

### 1.4 WebSocket 接口

| # | 方法 | 路径 | 方向 | 消息格式 | 实现状态 | 兼容策略 |
|---|-----|------|------|---------|---------|---------|
| 14 | WS | `/ws/events` | 服务端→客户端 | `AgentStreamEvent` | ✅ 已实现 | 保留，统一事件格式 |

#### AgentStreamEvent
```typescript
{
  event_type: 'task_scheduled' | 'task_started' | 'step_update' | 
              'progress_update' | 'task_completed' | 'task_failed' | 
              'task_cancelled' | 'output_ready';
  task_id: number;
  timestamp: string;
  data: Record<string, any>;
}
```

---

## 2. Analysis API (`/api/v1/analysis`)

### 2.1 任务管理接口

| # | 方法 | 路径 | 请求参数 | 响应 | 实现状态 | 兼容策略 |
|---|-----|------|---------|------|---------|---------|
| 15 | POST | `/task/` | `CreateTaskRequest` | `AnalysisTask` | ✅ 已实现 | 转发到新 API |
| 16 | GET | `/task/{id}` | - | `AnalysisTask` | ✅ 已实现 | 转发到新 API |
| 17 | GET | `/task/edition/{id}` | `?status=&task_type=&skip=&limit=` | `AnalysisTask[]` | ✅ 已实现 | 保留 |
| 18 | POST | `/task/{id}/cancel` | - | `{success: boolean}` | ✅ 已实现 | 转发到新 API |
| 19 | GET | `/task/{id}/results` | `?review_status=` | `AnalysisResult[]` | ✅ 已实现 | 保留 |
| 20 | POST | `/task/result/{id}/approve` | `?reviewer=` | `{success: boolean}` | ✅ 已实现 | 保留 |
| 21 | POST | `/task/result/{id}/reject` | `?reviewer=&notes=` | `{success: boolean}` | ✅ 已实现 | 保留 |
| 22 | POST | `/task/result/{id}/modify` | `{result_data}` | `AnalysisResult` | ✅ 已实现 | 保留 |
| 23 | POST | `/task/{id}/apply-all` | - | `{applied, failed, total}` | ✅ 已实现 | 保留 |
| 24 | GET | `/task/stats/{id}` | - | `AnalysisStats` | ✅ 已实现 | 保留 |

#### CreateTaskRequest
```typescript
{
  edition_id: number;
  task_type: 'outline_extraction' | 'character_detection' | 
             'setting_extraction' | 'relation_analysis';
  target_scope: 'full' | 'range' | 'chapter';
  target_node_ids?: number[];
  parameters?: Record<string, any>;
  llm_model?: string;
  llm_prompt_template?: string;
  priority?: number;
}
```

#### AnalysisTask
```typescript
{
  id: number;
  edition_id: number;
  task_type: string;
  target_scope: string;
  target_node_ids: number[];
  parameters: Record<string, any>;
  llm_model?: string;
  llm_prompt_template?: string;
  status: 'pending' | 'running' | 'completed' | 'failed' | 'cancelled';
  priority: number;
  scheduled_at?: string;
  started_at?: string;
  completed_at?: string;
  error_message?: string;
  result_summary?: Record<string, any>;
  created_by?: string;
  created_at: string;
  result_count: number;
}
```

#### AnalysisResult
```typescript
{
  id: number;
  task_id: number;
  result_type: string;
  result_data: Record<string, any>;
  confidence?: number;
  review_status: 'pending' | 'approved' | 'rejected' | 'modified';
  reviewer?: string;
  reviewed_at?: string;
  review_notes?: string;
  applied: boolean;
  applied_at?: string;
  created_at: string;
}
```

### 2.2 任务执行接口

| # | 方法 | 路径 | 请求参数 | 响应 | 实现状态 | 兼容策略 |
|---|-----|------|---------|------|---------|---------|
| 25 | POST | `/task-execution/{id}/plan` | `{mode: 'llm_direct' | 'prompt_only'}` | `{success, plan?, error?}` | ✅ 已实现 | 保留 |
| 26 | POST | `/task-execution/{id}/execute` | `TaskExecuteRequest` | `{success, result?, error?}` | ✅ 已实现 | 转发到新执行器 |
| 27 | POST | `/task-execution/{id}/execute-async` | `TaskExecuteRequest` | `{success, message?, task_id?}` | ✅ 已实现 | 转发到新执行器 |
| 28 | GET | `/task-execution/{id}/progress` | - | `{success, is_running?, completed?, progress?, result?, error?}` | ✅ 已实现 | 转发到新执行器 |
| 29 | POST | `/task-execution/{id}/cancel` | - | `{success, message?, error?}` | ✅ 已实现 | 转发到新执行器 |
| 30 | GET | `/llm/providers` | - | `{success, providers: LLMProvider[]}` | ✅ 已实现 | 保留 |
| 31 | GET | `/export/task/{id}/prompts` | `?format=` | `{success, task_id, format, prompts[]}` | ✅ 已实现 | 保留 |

#### TaskExecuteRequest
```typescript
{
  mode: 'llm_direct' | 'prompt_only';
  llm_provider?: string;
  llm_model?: string;
  llm_api_key?: string;
  temperature?: number;
}
```

#### TaskProgress
```typescript
{
  task_id: number;
  status: string;
  current_step: string;
  total_chunks: number;
  completed_chunks: number;
  current_chunk_info?: string;
  started_at?: string;
  estimated_remaining_seconds?: number;
  error?: string;
}
```

#### LLMProvider
```typescript
{
  id: string;
  name: string;
  description?: string;
  requires_api_key: boolean;
  models: {
    id: string;
    name: string;
    context_length: number;
  }[];
}
```

### 2.3 业务实体接口 (保持不变)

以下接口与任务调度无关，在整合中保持不变：

#### Character API
- `POST /character/` - 创建人物
- `GET /character/{id}` - 获取人物
- `GET /character/edition/{id}` - 按版本获取
- `PUT /character/{id}` - 更新人物
- `DELETE /character/{id}` - 删除人物
- `GET /character/search` - 搜索人物
- `GET /character/{id}/profile` - 获取完整档案
- `POST /character/{id}/alias` - 添加别名
- `GET /character/{id}/aliases` - 获取别名列表
- `DELETE /character/alias/{id}` - 删除别名
- `POST /character/{id}/attribute` - 添加属性
- `GET /character/{id}/attributes` - 获取属性列表
- `DELETE /character/attribute/{id}` - 删除属性
- `POST /character/{id}/arc` - 添加人物弧线
- `GET /character/{id}/arcs` - 获取弧线列表
- `DELETE /character/arc/{id}` - 删除弧线

#### Relation API
- `POST /relation/` - 创建关系
- `GET /relation/edition/{id}` - 按版本获取
- `GET /relation/character/{id}` - 获取人物关系
- `GET /relation/graph/{id}` - 获取关系图数据
- `DELETE /relation/{id}` - 删除关系

#### Setting API
- `POST /setting/` - 创建设定
- `GET /setting/{id}` - 获取设定
- `GET /setting/edition/{id}` - 按版本获取
- `PUT /setting/{id}` - 更新设定
- `DELETE /setting/{id}` - 删除设定
- `GET /setting/{id}/detail` - 获取详情
- `GET /setting/types/{id}` - 获取类型统计
- `POST /setting/{id}/attribute` - 添加属性
- `GET /setting/{id}/attributes` - 获取属性列表
- `DELETE /setting/attribute/{id}` - 删除属性

#### Setting Relation API
- `POST /setting-relation/` - 创建设定关系
- `GET /setting-relation/{id}` - 获取设定关系

#### Character-Setting Link API
- `POST /character-setting-link/` - 创建关联
- `GET /character-setting-link/character/{id}` - 获取人物的设定
- `GET /character-setting-link/setting/{id}` - 获取设定的人物

#### Outline API
- `POST /outline/` - 创建大纲
- `GET /outline/{id}` - 获取大纲
- `GET /outline/edition/{id}` - 按版本获取
- `DELETE /outline/{id}` - 删除大纲
- `GET /outline/{id}/tree` - 获取树形结构
- `POST /outline/{id}/node` - 添加节点
- `GET /outline/node/{id}` - 获取节点
- `PUT /outline/node/{id}` - 更新节点
- `DELETE /outline/node/{id}` - 删除节点
- `POST /outline/node/{id}/event` - 添加事件
- `GET /outline/node/{id}/events` - 获取事件列表
- `DELETE /outline/event/{id}` - 删除事件

#### Evidence API
- `POST /evidence/` - 添加证据
- `GET /evidence/target/{type}/{id}` - 获取目标证据
- `GET /evidence/chapter/{id}` - 获取章节标注
- `DELETE /evidence/{id}` - 删除证据

---

## 3. 统一 API 设计 (`/api/v2/agent`)

### 3.1 任务管理 (新)

| # | 方法 | 路径 | 描述 |
|---|-----|------|------|
| 1 | POST | `/tasks` | 创建任务 (统一入口) |
| 2 | GET | `/tasks` | 任务列表查询 |
| 3 | GET | `/tasks/{id}` | 获取任务详情 |
| 4 | POST | `/tasks/{id}/cancel` | 取消任务 |
| 5 | DELETE | `/tasks/{id}` | 删除任务 |
| 6 | GET | `/tasks/{id}/steps` | 获取任务步骤 |
| 7 | GET | `/tasks/{id}/progress` | 获取任务进度 |

### 3.2 模板管理 (新)

| # | 方法 | 路径 | 描述 |
|---|-----|------|------|
| 8 | GET | `/templates` | 模板列表 |
| 9 | GET | `/templates/{id}` | 模板详情 |
| 10 | POST | `/templates/{id}/test` | 测试模板 |

### 3.3 成本统计 (新)

| # | 方法 | 路径 | 描述 |
|---|-----|------|------|
| 11 | GET | `/cost/summary` | 成本摘要 |
| 12 | GET | `/cost/tasks` | 任务成本明细 |
| 13 | GET | `/cost/providers` | 按提供商统计 |

### 3.4 实时事件 (WebSocket)

| # | 方法 | 路径 | 描述 |
|---|-----|------|------|
| 14 | WS | `/events` | 实时任务事件流 |

---

## 4. 兼容性策略总结

### 4.1 完全保留的接口

以下接口无需修改，直接保留：
- 所有 Character/Setting/Outline/Evidence CRUD 接口
- 任务执行计划接口 (`/task-execution/*/plan`)
- Prompt 导出接口 (`/export/task/*/prompts`)
- LLM 提供商列表 (`/llm/providers`)

### 4.2 需要适配器转发的接口

以下接口保持路径不变，内部转发到新实现：
- `/api/v1/agent/*` 所有接口 → 新 UnifiedAgentScheduler
- `/api/v1/analysis/task/*` → 新 UnifiedAgentScheduler
- `/api/v1/analysis/task-execution/*/execute*` → 新 Agent 执行器

### 4.3 废弃的接口

以下接口在整合后可废弃：
- Agent 系统的 UserPrompt 相关接口 (可合并到 Task)
- Analysis 系统的独立结果审核接口 (合并到 Task)

---

## 5. 前端影响分析

### 5.1 无需修改的页面

- 小说分析管理页面 (character/setting/outline)
- 任务结果审核页面 (继续使用旧 API)

### 5.2 需要调整的页面

- Agent 监控页面 → 适配新的统一事件格式
- 任务创建页面 → 可选使用新的 `/api/v2/agent/tasks` 接口

### 5.3 新增的页面

- Agent 工作台 (统一入口)
- Prompt 模板管理
- 成本仪表盘

---

**文档版本**: 1.0  
**更新日期**: 2026-02-26  
**状态**: Phase 0 完成
