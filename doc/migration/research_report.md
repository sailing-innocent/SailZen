# SailZen LLM/Agent 系统代码调研报告

> 调研日期: 2026-02-26  
> 调研范围: Agent 系统与小说分析系统  
> 状态: Phase 0 完成

---

## 1. 执行摘要

本次调研深入分析了 SailZen 项目中两个并行的 LLM/Agent 系统：
- **Agent 系统** (`sail_server/data/agent.py`, `sail_server/router/agent.py`): 通用任务调度框架（当前为 Mock 实现）
- **小说分析系统** (`sail_server/data/analysis.py`, `sail_server/router/analysis.py`): 专用小说分析工作流（功能完整）

**核心发现**:
1. 两个系统独立运行，存在功能重复
2. Agent 系统的 Runner 是 Mock，未实际调用 LLM
3. 小说分析系统具有完整的 LLM 调用、成本追踪、审核流程
4. 两套数据模型可合并为统一的任务模型

---

## 2. 系统架构对比

### 2.1 Agent 系统架构

```
sail_server/
├── data/agent.py           # 数据模型: UserPrompt, AgentTask, AgentStep, AgentOutput
├── router/agent.py         # API 路由: /api/v1/agent/*
├── model/agent/
│   ├── scheduler.py        # AgentScheduler - 轮询调度逻辑
│   └── runner.py           # AgentRunner - Mock 执行器 ⚠️
└── utils/llm/
    ├── client.py           # LLMClient - 多提供商支持 ✅
    └── prompts.py          # PromptTemplateManager - YAML 模板 ✅
```

**数据流**:
```
UserPrompt → AgentScheduler → AgentTask → AgentRunner (Mock) → AgentOutput
                ↓
         WebSocket 推送事件
```

**关键特点**:
- 基于轮询的调度 (`poll_interval=5.0`)
- WebSocket 实时推送 (`/api/v1/agent/ws/events`)
- 优先级队列 (1-10, 1为最高)
- 并发控制 (`max_concurrent_agents`)

### 2.2 小说分析系统架构

```
sail_server/
├── data/analysis.py        # 数据模型: AnalysisTask, AnalysisResult, Character, Setting, Outline...
├── router/analysis.py      # API 路由: /api/v1/analysis/*
├── controller/
│   ├── analysis.py         # CRUD 控制器
│   └── analysis_llm.py     # LLM 分析控制器 (AsyncTaskManager)
└── model/analysis/
    └── task_scheduler.py   # AnalysisTaskRunner - 实际 LLM 调用 ✅
```

**数据流**:
```
AnalysisTask → AsyncTaskManager → AnalysisTaskRunner → LLMClient → AnalysisResult
                      ↓
               SSE/轮询进度查询
```

**关键特点**:
- 异步任务管理 (`AsyncTaskManager`)
- 分块处理 (`MAX_CHUNK_TOKENS = 8000`)
- Token 成本估算 (`estimate_cost`)
- 结果审核流程 (`review_status: pending/approved/rejected`)
- Prompt 模板系统 (`PromptTemplateManager`)

---

## 3. 数据模型详细对比

### 3.1 任务模型对比

| 字段 | AgentTask | AnalysisTask | 统一建议 |
|-----|-----------|--------------|---------|
| **ID** | `id: int` | `id: int` | ✅ 相同 |
| **任务类型** | `agent_type: str` | `task_type: str` | 🔀 合并为 `task_type` |
| **子类型** | 无 | 无 | ➕ 新增 `sub_type` |
| **状态** | `status: str` | `status: str` | 🔀 统一状态枚举 |
| **进度** | `progress: int` | 无 | ➕ 添加到统一模型 |
| **优先级** | 在 UserPrompt | `priority: int` | ➕ 提升到任务层 |
| **目标范围** | 无 | `target_scope, target_node_ids` | ➕ 保留 |
| **LLM 配置** | 无 | `llm_model, llm_prompt_template` | ➕ 统一 LLM 配置 |
| **Token 追踪** | 无 | 无 | ➕ 新增成本字段 |
| **结果数据** | 关联 AgentOutput | 关联 AnalysisResult | 🔀 统一 result_data JSON |
| **错误信息** | `error_message, error_code` | `error_message` | ✅ 兼容 |
| **时间戳** | created/started/updated/completed | created/started/completed | ✅ 兼容 |

### 3.2 现有表结构分析

#### user_prompts 表
```sql
-- Agent 系统的入口表
id SERIAL PRIMARY KEY
content TEXT NOT NULL              -- 用户原始请求
prompt_type VARCHAR DEFAULT 'general'  -- general | code | analysis | writing | data
context JSONB DEFAULT '{}'
priority INTEGER DEFAULT 5         -- 1-10
status VARCHAR DEFAULT 'pending'   -- pending | scheduled | processing | completed | failed | cancelled
created_by VARCHAR NULL
session_id VARCHAR NULL
parent_prompt_id INTEGER NULL
created_at TIMESTAMP DEFAULT now()
scheduled_at TIMESTAMP NULL
started_at TIMESTAMP NULL
completed_at TIMESTAMP NULL
```

#### agent_tasks 表
```sql
-- Agent 执行实例
id SERIAL PRIMARY KEY
prompt_id INTEGER NOT NULL REFERENCES user_prompts(id)
agent_type VARCHAR DEFAULT 'general'  -- general | coder | analyst | writer
agent_config JSONB DEFAULT '{}'
status VARCHAR DEFAULT 'created'   -- created | preparing | running | paused | completed | failed | cancelled
progress INTEGER DEFAULT 0         -- 0-100
created_at TIMESTAMP DEFAULT now()
started_at TIMESTAMP NULL
updated_at TIMESTAMP DEFAULT now()
completed_at TIMESTAMP NULL
error_message TEXT NULL
error_code VARCHAR NULL
max_iterations INTEGER DEFAULT 100
timeout_seconds INTEGER DEFAULT 3600
```

#### agent_steps 表
```sql
-- Agent 执行步骤
id SERIAL PRIMARY KEY
task_id INTEGER NOT NULL REFERENCES agent_tasks(id)
step_number INTEGER NOT NULL
step_type VARCHAR NOT NULL         -- thought | action | observation | error | completion
title VARCHAR NULL
content TEXT NULL
content_summary VARCHAR NULL
meta_data JSONB DEFAULT '{}'
created_at TIMESTAMP DEFAULT now()
duration_ms INTEGER NULL
```

#### agent_outputs 表
```sql
-- Agent 输出结果
id SERIAL PRIMARY KEY
task_id INTEGER NOT NULL REFERENCES agent_tasks(id)
output_type VARCHAR NOT NULL       -- text | code | file | json | error
content TEXT NULL
file_path VARCHAR NULL
meta_data JSONB DEFAULT '{}'
review_status VARCHAR DEFAULT 'pending'  -- pending | approved | rejected
reviewed_by VARCHAR NULL
reviewed_at TIMESTAMP NULL
review_notes TEXT NULL
created_at TIMESTAMP DEFAULT now()
```

#### analysis_tasks 表
```sql
-- 分析任务表
id SERIAL PRIMARY KEY
edition_id INTEGER NOT NULL REFERENCES editions(id)
task_type VARCHAR NOT NULL         -- outline_extraction | character_detection | setting_extraction | relation_analysis
target_scope VARCHAR NOT NULL      -- full | range | chapter
target_node_ids INTEGER[] DEFAULT '{}'
parameters JSONB DEFAULT '{}'
llm_model VARCHAR NULL
llm_prompt_template VARCHAR NULL
status VARCHAR DEFAULT 'pending'   -- pending | running | completed | failed | cancelled
priority INTEGER DEFAULT 0
scheduled_at TIMESTAMP NULL
started_at TIMESTAMP NULL
completed_at TIMESTAMP NULL
error_message TEXT NULL
result_summary JSONB NULL
created_by VARCHAR NULL
created_at TIMESTAMP DEFAULT now()
```

#### analysis_results 表
```sql
-- 分析结果表
id SERIAL PRIMARY KEY
task_id INTEGER NOT NULL REFERENCES analysis_tasks(id)
result_type VARCHAR NOT NULL
result_data JSONB NOT NULL
confidence NUMERIC(5,4) NULL
review_status VARCHAR DEFAULT 'pending'  -- pending | approved | rejected | modified
reviewer VARCHAR NULL
reviewed_at TIMESTAMP NULL
review_notes TEXT NULL
applied BOOLEAN DEFAULT FALSE
applied_at TIMESTAMP NULL
created_at TIMESTAMP DEFAULT now()
```

---
## 4. API 接口清单

### 4.1 Agent API (`/api/v1/agent`)

| 方法 | 路径 | 描述 | 状态 |
|-----|------|------|------|
| POST | `/prompt` | 创建用户提示 | ✅ 保留 |
| GET | `/prompt` | 列表查询 | ✅ 保留 |
| GET | `/prompt/{id}` | 获取详情 | ✅ 保留 |
| POST | `/prompt/{id}/cancel` | 取消提示 | ✅ 保留 |
| DELETE | `/prompt/{id}` | 删除提示 | ✅ 保留 |
| GET | `/task` | 任务列表 | ✅ 保留 |
| GET | `/task/{id}` | 任务详情 | ✅ 保留 |
| GET | `/task/{id}/steps` | 任务步骤 | ✅ 保留 |
| POST | `/task/{id}/cancel` | 取消任务 | ✅ 保留 |
| GET | `/scheduler/status` | 调度器状态 | ✅ 保留 |
| POST | `/scheduler/start` | 启动调度器 | ✅ 保留 |
| POST | `/scheduler/stop` | 停止调度器 | ✅ 保留 |
| POST | `/scheduler/config` | 更新配置 | ✅ 保留 |
| WS | `/ws/events` | WebSocket 实时事件 | ✅ 保留 |

### 4.2 Analysis API (`/api/v1/analysis`)

#### 任务管理
| 方法 | 路径 | 描述 | 状态 |
|-----|------|------|------|
| POST | `/task/` | 创建分析任务 | ✅ 保留（兼容） |
| GET | `/task/{id}` | 获取任务 | ✅ 保留（兼容） |
| GET | `/task/edition/{id}` | 按版本查询 | ✅ 保留 |
| POST | `/task/{id}/cancel` | 取消任务 | ✅ 保留（兼容） |
| GET | `/task/{id}/results` | 获取结果 | ✅ 保留 |
| POST | `/task/result/{id}/approve` | 审核通过 | ✅ 保留 |
| POST | `/task/result/{id}/reject` | 审核拒绝 | ✅ 保留 |
| POST | `/task/result/{id}/modify` | 修改结果 | ✅ 保留 |
| POST | `/task/{id}/apply-all` | 应用所有结果 | ✅ 保留 |
| GET | `/task/stats/{id}` | 统计信息 | ✅ 保留 |

#### 任务执行
| 方法 | 路径 | 描述 | 状态 |
|-----|------|------|------|
| POST | `/task-execution/{id}/plan` | 创建执行计划 | ✅ 保留 |
| POST | `/task-execution/{id}/execute` | 执行任务 | ✅ 保留 |
| POST | `/task-execution/{id}/execute-async` | 异步执行 | ✅ 保留 |
| GET | `/task-execution/{id}/progress` | 查询进度 | ✅ 保留 |
| POST | `/task-execution/{id}/cancel` | 取消执行 | ✅ 保留 |
| GET | `/llm/providers` | LLM 提供商列表 | ✅ 保留 |
| GET | `/export/task/{id}/prompts` | 导出 Prompts | ✅ 保留 |

#### 业务实体 CRUD（保持独立）
- Character, Setting, Outline, Relation, Evidence 等接口保持不变

---

## 5. 技术债务清单

### 5.1 高优先级

| # | 问题 | 影响 | 解决方案 |
|---|-----|------|---------|
| 1 | AgentRunner 是 Mock 实现 | Agent 系统无法实际调用 LLM | 整合 LLMClient 到 AgentRunner |
| 2 | 两套任务调度器 | 维护成本高，功能重复 | 统一为 UnifiedAgentScheduler |
| 3 | 两套数据模型 | 数据分散，无法关联 | 迁移到 unified_agent_tasks 表 |
| 4 | Agent 系统无 Token 成本控制 | 可能产生意外费用 | 复用 AnalysisTaskRunner 的成本估算 |

### 5.2 中优先级

| # | 问题 | 影响 | 解决方案 |
|---|-----|------|---------|
| 5 | Agent 系统无 Prompt 模板 | 难以管理 Prompt | 集成 PromptTemplateManager |
| 6 | 进度通知机制不一致 | 前端需要两套代码 | 统一使用 WebSocket |
| 7 | Agent 输出无审核流程 | 结果质量不可控 | 复用 AnalysisResult 审核机制 |

### 5.3 低优先级

| # | 问题 | 影响 | 解决方案 |
|---|-----|------|---------|
| 8 | LLMClient 无可降级机制 | 单点故障 | 实现 LLMGateway 自动切换 Provider |
| 9 | 无请求缓存 | 重复调用浪费 Token | 添加 LLM 请求缓存层 |

---

## 6. 整合可行性分析

### 6.1 技术可行性

| 组件 | 可行性 | 说明 |
|-----|-------|------|
| 数据模型合并 | ✅ 高 | 字段高度兼容，可无损迁移 |
| API 兼容层 | ✅ 高 | 旧 API 可通过适配器转发 |
| LLM 调用整合 | ✅ 高 | 两套系统都使用 LLMClient |
| 调度器统一 | ⚠️ 中 | 需要整合轮询和异步两种模式 |
| 前端兼容 | ✅ 高 | 保持 API 不变，前端无需修改 |

### 6.2 风险评估

| 风险 | 概率 | 影响 | 缓解措施 |
|-----|------|------|---------|
| 数据迁移失败 | 低 | 高 | 完整备份；灰度迁移；回滚脚本 |
| API 不兼容 | 低 | 中 | 保留旧 API；渐进式切换 |
| 性能下降 | 中 | 中 | 性能测试；索引优化 |
| 功能回归 | 中 | 高 | 完整回归测试；功能标记 |

---

## 7. 建议的整合策略

### 7.1 数据模型整合方案

建议创建新的 `unified_agent_tasks` 表，同时保留旧表作为视图：

```sql
-- 新表: unified_agent_tasks
CREATE TABLE unified_agent_tasks (
    id SERIAL PRIMARY KEY,
    
    -- 任务分类
    task_type VARCHAR(50) NOT NULL,     -- 'novel_analysis' | 'code' | 'writing' | 'general'
    sub_type VARCHAR(50),                -- 如 'outline_extraction'
    
    -- 关联信息
    edition_id INTEGER NULL,             -- 小说分析用
    target_node_ids INTEGER[] NULL,      -- 目标章节
    
    -- LLM 配置
    llm_provider VARCHAR(50) NULL,
    llm_model VARCHAR(100) NULL,
    prompt_template_id VARCHAR(100) NULL,
    
    -- 执行状态
    status VARCHAR(50) NOT NULL,         -- pending | running | completed | failed | cancelled
    progress INTEGER DEFAULT 0,          -- 0-100
    current_phase VARCHAR(100) NULL,
    error_message TEXT NULL,
    
    -- 成本追踪
    estimated_tokens INTEGER NULL,
    actual_tokens INTEGER DEFAULT 0,
    estimated_cost FLOAT NULL,
    actual_cost FLOAT DEFAULT 0.0,
    
    -- 结果数据 (替代 AgentOutput 和 AnalysisResult)
    result_data JSONB NULL,
    review_status VARCHAR(50) DEFAULT 'pending',
    
    -- 时间戳
    created_at TIMESTAMP DEFAULT now(),
    started_at TIMESTAMP NULL,
    completed_at TIMESTAMP NULL,
    cancelled_at TIMESTAMP NULL
);

-- 兼容视图
CREATE VIEW agent_tasks_v AS 
SELECT * FROM unified_agent_tasks 
WHERE task_type IN ('code', 'writing', 'general');

CREATE VIEW analysis_tasks_v AS 
SELECT * FROM unified_agent_tasks 
WHERE task_type = 'novel_analysis';
```

### 7.2 后端架构整合

```
sail_server/
├── model/unified_agent.py      # UnifiedAgentTask, UnifiedAgentStep
├── model/unified_scheduler.py  # UnifiedAgentScheduler
├── agent/
│   ├── base.py                 # BaseAgent 抽象类
│   ├── novel_analysis.py       # NovelAnalysisAgent (整合 AnalysisTaskRunner)
│   └── general.py              # GeneralAgent (整合 AgentRunner + LLM)
├── utils/llm/
│   └── gateway.py              # LLMGateway (增强版 LLMClient)
└── router/
    ├── agent_compat.py         # 旧 Agent API 兼容层
    └── analysis_compat.py      # 旧 Analysis API 兼容层
```

### 7.3 迁移顺序建议

1. **Phase 0** (当前): 代码调研完成 ✅
2. **Phase 1**: 统一数据模型设计
3. **Phase 2**: 数据库迁移 (⚠️ 高风险，单独阶段)
4. **Phase 3**: LLM Gateway 封装
5. **Phase 4**: 统一调度器实现
6. **Phase 5**: Agent 抽象与 NovelAnalysisAgent
7. **Phase 6**: GeneralAgent 实现
8. **Phase 7**: 旧 API 兼容层
9. **Phase 8**: 前端统一 API 层
10. **Phase 9**: Agent 工作台页面

---

## 8. 附录

### 8.1 调研范围

**已审查文件**:
- `sail_server/data/agent.py` (394 lines)
- `sail_server/data/analysis.py` (1450 lines)
- `sail_server/router/agent.py` (377 lines)
- `sail_server/router/analysis.py` (44 lines)
- `sail_server/model/agent/scheduler.py` (200+ lines)
- `sail_server/model/analysis/task_scheduler.py` (200+ lines)
- `sail_server/controller/analysis_llm.py` (200+ lines)
- `sail_server/utils/llm/client.py` (780 lines)
- `sail_server/utils/llm/prompts.py` (483 lines)
- `packages/site/src/lib/api/agent.ts` (267 lines)
- `packages/site/src/lib/api/analysis.ts` (1000+ lines)

### 8.2 功能特性对比

| 特性 | Agent 系统 | 小说分析系统 | 整合后支持 |
|-----|-----------|-------------|-----------|
| 多提供商 LLM | ❌ Mock | ✅ LLMClient | ✅ 统一 |
| Token 成本控制 | ❌ | ✅ | ✅ 统一 |
| Prompt 模板 | ❌ 内置字符串 | ✅ YAML 模板 | ✅ 统一 |
| 分块处理 | ❌ | ✅ | ✅ 统一 |
| 结果审核 | ❌ | ✅ | ✅ 统一 |
| WebSocket 实时通知 | ✅ | ❌ SSE/轮询 | ✅ 统一 WebSocket |
| 任务优先级 | ✅ | ✅ (字段存在) | ✅ 统一 |
| 并发控制 | ✅ | ✅ | ✅ 统一 |
| 进度追踪 | ✅ | ✅ | ✅ 统一 |

---

**报告完成**  
下一步: Phase 1 - 统一数据模型设计
