# 数据模型对比表

> 对比 Agent 系统和小说分析系统的数据模型

---

## 1. 任务主表对比

### AgentTask (agent_tasks) vs AnalysisTask (analysis_tasks)

| 字段名 | AgentTask | AnalysisTask | 类型 | 统一策略 | 备注 |
|-------|-----------|--------------|------|---------|------|
| **主键** | id | id | INTEGER | ✅ 保留 | |
| **任务类型** | agent_type | task_type | VARCHAR | 🔀 统一为 task_type | 值域需对齐 |
| **子类型** | - | - | VARCHAR | ➕ 新增 sub_type | 如 outline_extraction |
| **版本ID** | - | edition_id | INTEGER | ➕ 新增 | 小说分析专用 |
| **目标节点** | - | target_node_ids | INTEGER[] | ➕ 新增 | 小说分析专用 |
| **目标范围** | - | target_scope | VARCHAR | ➕ 新增 | full/range/chapter |
| **状态** | status | status | VARCHAR | 🔀 统一枚举 | |
| **进度** | progress | - | INTEGER | ➕ 保留 progress | 0-100 |
| **当前阶段** | - | - | VARCHAR | ➕ 新增 current_phase | |
| **优先级** | 在 UserPrompt | priority | INTEGER | ➕ 提升到任务层 | |
| **LLM提供商** | - | llm_model(部分) | VARCHAR | ➕ 新增 llm_provider | google/openai/moonshot |
| **LLM模型** | - | llm_model | VARCHAR | ➕ 保留 llm_model | |
| **Prompt模板** | - | llm_prompt_template | VARCHAR | ➕ 保留 prompt_template_id | |
| **配置参数** | agent_config | parameters | JSONB | 🔀 统一为 config | |
| **预估Token** | - | - | INTEGER | ➕ 新增 estimated_tokens | |
| **实际Token** | - | - | INTEGER | ➕ 新增 actual_tokens | |
| **预估成本** | - | - | FLOAT | ➕ 新增 estimated_cost | USD |
| **实际成本** | - | - | FLOAT | ➕ 新增 actual_cost | USD |
| **错误信息** | error_message | error_message | TEXT | ✅ 保留 | |
| **错误码** | error_code | - | VARCHAR | ➕ 保留 error_code | |
| **结果摘要** | - | result_summary | JSONB | 🔀 合并到 result_data | |
| **创建者** | - | created_by | VARCHAR | ➕ 新增 | |
| **创建时间** | created_at | created_at | TIMESTAMP | ✅ 保留 | |
| **开始时间** | started_at | started_at | TIMESTAMP | ✅ 保留 | |
| **完成时间** | completed_at | completed_at | TIMESTAMP | ✅ 保留 | |
| **取消时间** | - | - | TIMESTAMP | ➕ 新增 cancelled_at | |
| **更新时间** | updated_at | - | TIMESTAMP | ➕ 可选保留 | |

---

## 2. 任务步骤表对比

### AgentStep (agent_steps) - 现有

| 字段名 | 类型 | 说明 | 统一策略 |
|-------|------|------|---------|
| id | INTEGER PK | 主键 | ✅ 保留 |
| task_id | INTEGER FK | 关联任务 | ✅ 保留 |
| step_number | INTEGER | 步骤序号 | ✅ 保留 |
| step_type | VARCHAR | thought/action/observation/error/completion | 🔀 扩展枚举 |
| title | VARCHAR | 步骤标题 | ✅ 保留 |
| content | TEXT | 详细内容 | ✅ 保留 |
| content_summary | VARCHAR | 内容摘要 | ✅ 保留 |
| meta_data | JSONB | 附加信息 | ✅ 保留 |
| created_at | TIMESTAMP | 创建时间 | ✅ 保留 |
| duration_ms | INTEGER | 执行耗时 | ✅ 保留 |

### 新增字段建议

| 字段名 | 类型 | 说明 | 理由 |
|-------|------|------|------|
| llm_provider | VARCHAR | LLM提供商 | 追踪每步使用的提供商 |
| llm_model | VARCHAR | LLM模型 | 追踪具体模型 |
| prompt_tokens | INTEGER | Prompt Token数 | 成本分析 |
| completion_tokens | INTEGER | 补全 Token数 | 成本分析 |
| cost | FLOAT | 本步成本 | 成本分析 |

---

## 3. 结果/输出表对比

### AgentOutput (agent_outputs) vs AnalysisResult (analysis_results)

| 字段名 | AgentOutput | AnalysisResult | 类型 | 统一策略 | 备注 |
|-------|-------------|----------------|------|---------|------|
| **主键** | id | id | INTEGER | ✅ 保留 | |
| **任务ID** | task_id | task_id | INTEGER FK | ✅ 保留 | |
| **结果类型** | output_type | result_type | VARCHAR | 🔀 统一 | text/json/code/error |
| **内容** | content | result_data | TEXT/JSONB | 🔀 统一为 result_data JSONB | |
| **文件路径** | file_path | - | VARCHAR | ➕ 保留到 meta_data | |
| **置信度** | - | confidence | NUMERIC | ➕ 新增 | LLM 结果置信度 |
| **审核状态** | review_status | review_status | VARCHAR | ✅ 保留 | pending/approved/rejected |
| **审核人** | reviewed_by | reviewer | VARCHAR | 🔀 统一为 reviewer | |
| **审核时间** | reviewed_at | reviewed_at | TIMESTAMP | ✅ 保留 | |
| **审核备注** | review_notes | review_notes | TEXT | ✅ 保留 | |
| **已应用** | - | applied | BOOLEAN | ➕ 新增 | 结果是否已应用到业务表 |
| **应用时间** | - | applied_at | TIMESTAMP | ➕ 新增 | |
| **元数据** | meta_data | - | JSONB | ✅ 保留 | |
| **创建时间** | created_at | created_at | TIMESTAMP | ✅ 保留 | |

### 统一后结果表设计

建议将结果数据直接存储在任务表的 `result_data` JSONB 字段中，减少 JOIN 查询：

```sql
-- unified_agent_tasks.result_data 结构
{
  "outputs": [
    {
      "type": "outline|character|setting|text|code|error",
      "data": { ... },
      "confidence": 0.95,
      "evidence": [...]
    }
  ],
  "review_status": "pending|approved|rejected",
  "reviewer": "user",
  "reviewed_at": "2026-02-26T10:00:00Z",
  "review_notes": "...",
  "applied": true,
  "applied_at": "2026-02-26T10:05:00Z"
}
```

---

## 4. 状态枚举统一

### 当前状态枚举

**AgentTask.status**:
```python
'created' | 'preparing' | 'running' | 'paused' | 'completed' | 'failed' | 'cancelled'
```

**AnalysisTask.status**:
```python
'pending' | 'running' | 'completed' | 'failed' | 'cancelled'
```

**UserPrompt.status**:
```python
'pending' | 'scheduled' | 'processing' | 'completed' | 'failed' | 'cancelled'
```

### 统一后的状态枚举

```python
'pending'     # 等待调度
'scheduled'   # 已调度，等待执行
'running'     # 执行中
'paused'      # 已暂停（保留）
'completed'   # 完成
'failed'      # 失败
'cancelled'   # 已取消
```

---

## 5. 任务类型枚举

### 当前类型

**AgentTask.agent_type**:
```python
'general' | 'coder' | 'analyst' | 'writer'
```

**AnalysisTask.task_type**:
```python
'outline_extraction' | 'character_detection' | 'setting_extraction' | 'relation_analysis'
```

**UserPrompt.prompt_type**:
```python
'general' | 'code' | 'analysis' | 'writing' | 'data'
```

### 统一后的任务类型

```python
# 顶级分类 (task_type)
'novel_analysis'    # 小说分析
'code'              # 代码辅助
'writing'           # 写作辅助
'general'           # 通用对话
'data'              # 数据处理

# 子类型 (sub_type) - novel_analysis 下
'outline_extraction'     # 大纲提取
'character_detection'    # 人物识别
'setting_extraction'     # 设定提取
'relation_analysis'      # 关系分析
'plot_analysis'          # 情节分析
```

---

## 6. 外键关系图

### 当前关系

```
Agent 系统:
user_prompts (1) ───< (N) agent_tasks (1) ───< (N) agent_steps
                                      (1) ───< (N) agent_outputs

Analysis 系统:
editions (1) ───< (N) analysis_tasks (1) ───< (N) analysis_results
            (1) ───< (N) characters/settings/outlines
```

### 统一后关系

```
unified_agent_tasks (1) ───< (N) unified_agent_steps

-- 小说分析结果通过 edition_id 关联到业务表
unified_agent_tasks (task_type='novel_analysis') 
  └── result_data ──> characters/settings/outlines (通过审核流程)

-- Agent 输出直接存储在 result_data 中
unified_agent_tasks (task_type in ('code', 'writing', 'general'))
  └── result_data ──> 直接输出
```

---

## 7. 索引建议

### unified_agent_tasks 索引

```sql
-- 主键索引 (自动创建)
PRIMARY KEY (id)

-- 状态查询索引 (常用)
CREATE INDEX idx_uat_status ON unified_agent_tasks(status);

-- 任务类型查询索引
CREATE INDEX idx_uat_task_type ON unified_agent_tasks(task_type);

-- 子类型查询索引
CREATE INDEX idx_uat_sub_type ON unified_agent_tasks(sub_type);

-- 版本ID索引 (小说分析)
CREATE INDEX idx_uat_edition_id ON unified_agent_tasks(edition_id);

-- 创建时间倒序 (列表查询)
CREATE INDEX idx_uat_created_at ON unified_agent_tasks(created_at DESC);

-- 组合索引: 状态 + 优先级 + 创建时间 (调度器查询)
CREATE INDEX idx_uat_schedule ON unified_agent_tasks(status, priority, created_at);

-- 审核状态索引
CREATE INDEX idx_uat_review_status ON unified_agent_tasks(review_status) 
WHERE review_status IN ('pending', 'approved');
```

### unified_agent_steps 索引

```sql
-- 任务ID索引
CREATE INDEX idx_uas_task_id ON unified_agent_steps(task_id);

-- 步骤序号索引
CREATE INDEX idx_uas_step_number ON unified_agent_steps(task_id, step_number);
```

---

## 8. 数据迁移映射

### AgentTask → UnifiedAgentTask

| 源字段 | 目标字段 | 转换规则 |
|-------|---------|---------|
| id | id | 直接复制 |
| agent_type | task_type | general→general, coder→code, analyst→general, writer→writing |
| - | sub_type | NULL |
| - | edition_id | NULL |
| - | target_node_ids | NULL |
| - | target_scope | NULL |
| status | status | created→pending, preparing→scheduled, 其他不变 |
| progress | progress | 直接复制 |
| - | current_phase | NULL |
| - | priority | 5 (默认值) |
| - | llm_provider | NULL |
| - | llm_model | NULL |
| - | prompt_template_id | NULL |
| agent_config | config | 直接复制 |
| - | estimated_tokens | NULL |
| - | actual_tokens | 0 |
| - | estimated_cost | NULL |
| - | actual_cost | 0.0 |
| error_message | error_message | 直接复制 |
| error_code | error_code | 直接复制 |
| - | result_data | 关联 agent_outputs 数据聚合 |
| - | review_status | 'pending' |
| created_at | created_at | 直接复制 |
| started_at | started_at | 直接复制 |
| completed_at | completed_at | 直接复制 |
| - | cancelled_at | NULL |

### AnalysisTask → UnifiedAgentTask

| 源字段 | 目标字段 | 转换规则 |
|-------|---------|---------|
| id | id | 直接复制 |
| task_type | sub_type | 直接复制 |
| - | task_type | 'novel_analysis' |
| edition_id | edition_id | 直接复制 |
| target_node_ids | target_node_ids | 直接复制 |
| target_scope | target_scope | 直接复制 |
| status | status | 直接复制 |
| - | progress | CASE status: running→50, completed→100, 其他→0 |
| - | current_phase | NULL |
| priority | priority | 直接复制 |
| - | llm_provider | 从 llm_model 推断 |
| llm_model | llm_model | 直接复制 |
| llm_prompt_template | prompt_template_id | 直接复制 |
| parameters | config | 直接复制 |
| - | estimated_tokens | NULL (历史数据无法补全) |
| - | actual_tokens | 0 |
| - | estimated_cost | NULL |
| - | actual_cost | 0.0 |
| error_message | error_message | 直接复制 |
| - | error_code | NULL |
| result_summary | result_data | 包装为 JSON {summary: ...} |
| - | review_status | 从 analysis_results 聚合计算 |
| created_by | created_by | 直接复制 |
| created_at | created_at | 直接复制 |
| started_at | started_at | 直接复制 |
| completed_at | completed_at | 直接复制 |
| - | cancelled_at | NULL |

---

**文档版本**: 1.0  
**更新日期**: 2026-02-26  
**状态**: Phase 0 完成，待 Phase 2 使用
