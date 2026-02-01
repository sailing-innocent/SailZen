# LLM 辅助小说分析功能使用指南

## 概述

本模块提供了使用大语言模型（LLM）辅助分析小说内容的功能，支持：
- **大纲提取**：自动识别情节结构和关键事件
- **人物识别**：自动检测人物及其别名、角色类型
- **设定提取**：提取世界观设定（物品、地点、组织等）

系统支持两种工作模式：
1. **LLM 直接调用**：系统直接调用 LLM API 完成分析
2. **Prompt 导出**：生成 Prompt 供用户在外部工具（如 ChatGPT、Claude）中使用，然后导入结果

---

## 快速开始

### 1. 环境准备

确保已运行数据库迁移：

```bash
psql -U your_user -d your_database -f sail_server/migration/add_llm_analysis_tables.sql
```

### 2. 安装依赖（可选）

如果需要直接调用 LLM API：

```bash
pip install openai anthropic aiohttp pyyaml
```

如果只使用 Prompt 导出模式，无需安装额外依赖。

---

## API 使用指南

### 基础 URL

所有 API 端点位于 `/api/v1/analysis/` 路径下。

### 完整工作流程

```
1. 创建分析任务
   POST /api/v1/analysis/task
   
2. 获取执行计划（预览）
   POST /api/v1/analysis/task-execution/{task_id}/plan
   
3. 执行任务
   POST /api/v1/analysis/task-execution/{task_id}/execute
   
4. 监控进度
   GET /api/v1/analysis/task-execution/{task_id}/progress
   
5. 查看结果
   GET /api/v1/analysis/task/{task_id}/results
   
6. 审核结果
   POST /api/v1/analysis/task/result/{result_id}/approve
   
7. 应用到主表
   POST /api/v1/analysis/task/{task_id}/apply-all
```

---

## 场景一：使用 LLM 直接调用

### 步骤 1：创建分析任务

```http
POST /api/v1/analysis/task
Content-Type: application/json

{
    "edition_id": 1,
    "task_type": "character_detection",
    "target_scope": "full",
    "target_node_ids": [],
    "parameters": {},
    "llm_model": "gpt-4",
    "llm_prompt_template": "character_detection_v1",
    "priority": 0
}
```

响应：
```json
{
    "id": 1,
    "edition_id": 1,
    "task_type": "character_detection",
    "status": "pending",
    ...
}
```

### 步骤 2：获取执行计划

```http
POST /api/v1/analysis/task-execution/1/plan
Content-Type: application/json

{
    "mode": "llm_direct"
}
```

响应：
```json
{
    "success": true,
    "plan": {
        "task_id": 1,
        "mode": "llm_direct",
        "chunks": [
            {
                "index": 0,
                "node_ids": [1, 2, 3],
                "chapter_range": "第1章 - 第3章",
                "token_estimate": 5000
            },
            {
                "index": 1,
                "node_ids": [4, 5],
                "chapter_range": "第4章 - 第5章",
                "token_estimate": 3500
            }
        ],
        "total_estimated_tokens": 8500,
        "estimated_cost_usd": 0.34,
        "prompt_template_id": "character_detection_v1"
    }
}
```

### 步骤 3：执行任务

```http
POST /api/v1/analysis/task-execution/1/execute
Content-Type: application/json

{
    "mode": "llm_direct",
    "llm_provider": "openai",
    "llm_model": "gpt-4",
    "llm_api_key": "sk-your-api-key",
    "temperature": 0.3
}
```

响应：
```json
{
    "success": true,
    "result": {
        "task_id": 1,
        "success": true,
        "results_count": 15,
        "execution_time_seconds": 45.2
    }
}
```

### 步骤 4：查看结果

```http
GET /api/v1/analysis/task/1/results
```

响应：
```json
[
    {
        "id": 1,
        "task_id": 1,
        "result_type": "character",
        "result_data": {
            "canonical_name": "李明",
            "aliases": ["小李"],
            "role_type": "protagonist",
            "description": "28岁的普通上班族..."
        },
        "confidence": 0.85,
        "review_status": "pending"
    },
    ...
]
```

### 步骤 5：审核并应用

```http
# 批准单个结果
POST /api/v1/analysis/task/result/1/approve?reviewer=admin

# 批量应用所有已批准的结果
POST /api/v1/analysis/task/1/apply-all
```

---

## 场景二：使用 Prompt 导出模式

适用于没有 API Key 或希望使用外部工具的用户。

### 步骤 1：创建任务并执行（Prompt Only 模式）

```http
POST /api/v1/analysis/task
Content-Type: application/json

{
    "edition_id": 1,
    "task_type": "outline_extraction",
    "target_scope": "range",
    "target_node_ids": [1, 2, 3, 4, 5]
}
```

```http
POST /api/v1/analysis/task-execution/1/execute
Content-Type: application/json

{
    "mode": "prompt_only"
}
```

### 步骤 2：获取生成的 Prompt

```http
GET /api/v1/analysis/export/task/1/prompts?format=markdown
```

响应：
```json
{
    "success": true,
    "task_id": 1,
    "format": "markdown",
    "prompts": [
        {
            "result_id": 101,
            "chunk_index": 0,
            "chunk_range": "第1章 - 第3章",
            "awaiting_result": true,
            "content": "# Chunk 1\n\n## System Prompt\n\n你是一位专业的文学分析师..."
        }
    ]
}
```

### 步骤 3：下载 Prompt 文件

```http
GET /api/v1/analysis/export/task/1/download?format=markdown
```

响应包含可直接保存的 Markdown 文件内容。

### 步骤 4：在外部工具中使用 Prompt

1. 打开 ChatGPT / Claude / 其他 LLM 工具
2. 粘贴 System Prompt（如果工具支持）
3. 粘贴 User Prompt
4. 获取分析结果

### 步骤 5：导入外部结果

```http
POST /api/v1/analysis/task-execution/1/import-result
Content-Type: application/json

{
    "chunk_index": 0,
    "result_text": "{\"plot_points\": [...], \"overall_summary\": \"...\"}"
}
```

响应：
```json
{
    "success": true,
    "result": {
        "id": 102,
        "result_type": "outline_extraction_imported",
        "review_status": "pending"
    }
}
```

### 步骤 6：审核并应用

与直接调用模式相同。

---

## 提示词模板管理

### 获取可用模板

```http
GET /api/v1/analysis/prompts?task_type=character_detection
```

响应：
```json
{
    "success": true,
    "templates": [
        {
            "id": "character_detection_v1",
            "name": "人物识别 - 基础版",
            "description": "从章节内容中识别人物...",
            "task_type": "character_detection",
            "version": "1.0"
        }
    ]
}
```

### 获取模板详情

```http
GET /api/v1/analysis/prompts/character_detection_v1
```

### 预览渲染后的 Prompt

```http
POST /api/v1/analysis/prompts/character_detection_v1/preview
Content-Type: application/json

{
    "variables": {
        "work_title": "测试小说",
        "chapter_range": "第1章",
        "chapter_contents": "这是测试内容..."
    }
}
```

---

## LLM 配置

### 获取支持的提供商

```http
GET /api/v1/analysis/llm/providers
```

响应：
```json
{
    "success": true,
    "providers": [
        {
            "id": "openai",
            "name": "OpenAI",
            "models": [
                {"id": "gpt-4", "name": "GPT-4", "context_length": 8192},
                {"id": "gpt-4-turbo", "name": "GPT-4 Turbo", "context_length": 128000}
            ]
        },
        {
            "id": "anthropic",
            "name": "Anthropic",
            "models": [
                {"id": "claude-3-opus-20240229", "name": "Claude 3 Opus", "context_length": 200000}
            ]
        },
        {
            "id": "external",
            "name": "External (Prompt Export Only)",
            "models": [
                {"id": "any", "name": "Any Model", "context_length": 0}
            ]
        }
    ]
}
```

### 测试 LLM 连接

```http
POST /api/v1/analysis/llm/test?provider=openai&api_key=sk-xxx&model=gpt-4
```

---

## 任务类型说明

| 任务类型 | 模板 ID | 说明 |
|---------|---------|------|
| `outline_extraction` | `outline_extraction_v1` | 大纲提取 - 识别情节结构 |
| `character_detection` | `character_detection_v1` | 人物识别 - 检测人物信息 |
| `setting_extraction` | `setting_extraction_v1` | 设定提取 - 提取世界观设定 |

---

## 最佳实践

### 1. 分块策略

系统会自动将长文本分块处理，每块约 8000 tokens。对于超长章节：
- 建议先按卷/部分创建多个任务
- 使用 `target_node_ids` 指定具体章节范围

### 2. 成本控制

- 使用 `plan` API 预估成本后再执行
- 考虑使用 Prompt 导出模式配合免费额度的 LLM 服务
- 对于试验性分析，先用小范围测试

### 3. 结果审核

- LLM 生成的结果可能有误，建议人工审核
- 利用 `confidence` 字段筛选低置信度结果重点审核
- 可以在审核时修改结果数据

### 4. 提示词优化

- 在 `parameters` 中传入 `known_characters` 可提高人物识别准确性
- 可以创建自定义 YAML 模板放在 `sail_server/prompts/` 目录

---

## 文件结构

```
sail_server/
├── utils/llm/
│   ├── __init__.py          # 模块导出
│   ├── client.py             # LLM 客户端封装
│   └── prompts.py            # 提示词模板管理
├── prompts/
│   ├── outline_extraction/
│   │   └── v1.yaml           # 大纲提取模板
│   └── character_detection/
│       └── v1.yaml           # 人物识别模板
├── model/analysis/
│   └── task_scheduler.py     # 任务调度器和执行器
├── controller/
│   ├── analysis.py           # 基础分析 API
│   └── analysis_llm.py       # LLM 分析 API
└── migration/
    └── add_llm_analysis_tables.sql  # 数据库迁移
```

---

## 常见问题

### Q: 为什么选择 Prompt 导出模式？

A: Prompt 导出模式适合以下场景：
- 没有 OpenAI/Anthropic API Key
- 希望使用其他 LLM 服务（如本地部署的模型）
- 希望手动控制调用过程
- 使用有免费额度的 LLM 服务

### Q: 如何处理分析失败的情况？

A: 
1. 检查任务状态：`GET /api/v1/analysis/task/{task_id}`
2. 查看错误信息：任务的 `error_message` 字段
3. 可以重试：先取消任务，然后创建新任务

### Q: 如何自定义提示词模板？

A:
1. 在 `sail_server/prompts/` 下创建 YAML 文件
2. 遵循现有模板的格式
3. 重启服务后自动加载

### Q: 支持哪些 LLM 提供商？

A: 目前支持：
- OpenAI (GPT-4, GPT-3.5)
- Anthropic (Claude 3)
- Local (Ollama)
- External (仅导出 Prompt)

---

## 版本历史

- **v1.0** (2025-02-01): 初始版本，支持大纲提取、人物识别、设定提取
