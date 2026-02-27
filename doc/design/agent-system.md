# Agent 系统设计

## 概述

Agent 系统提供统一的 LLM 任务管理和执行框架。

## 架构

```
Frontend (Agent Workbench)
    ↓
Unified Agent API
    ↓
Agent Router
    ↓
UnifiedScheduler
    ↓
BaseAgent → NovelAnalysisAgent / GeneralAgent
    ↓
LLM Gateway
    ↓
Providers (Google/OpenAI/Moonshot)
```

## 核心组件

| 组件 | 文件 | 职责 |
|------|------|------|
| UnifiedScheduler | model/unified_scheduler.py | 任务调度与队列管理 |
| LLM Gateway | utils/llm/gateway.py | 多提供商 LLM 调用 |
| BaseAgent | agent/base.py | Agent 抽象基类 |
| NovelAnalysisAgent | agent/novel_analysis.py | 小说分析专用 Agent |
| GeneralAgent | agent/general.py | 通用对话 Agent |

## 任务模型

```python
class UnifiedAgentTask:
    task_type: str      # 'novel_analysis' | 'code' | 'writing' | 'general'
    sub_type: str       # 'outline_extraction' | 'character_detection' etc.
    status: str         # pending | running | completed | failed
    progress: int       # 0-100
    actual_tokens: int
    actual_cost: float
```

## API 概览

```
POST /api/v1/agent/tasks              # 创建任务
GET  /api/v1/agent/tasks/{id}         # 获取任务
GET  /api/v1/agent/tasks/{id}/progress # 获取进度
POST /api/v1/agent/tasks/{id}/cancel  # 取消任务
WS   /api/v1/agent/events             # 实时事件流
```
