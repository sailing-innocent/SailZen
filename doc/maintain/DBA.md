# SailZen 数据库维护文档

> 本文档记录 SailZen 项目的数据库表结构信息，方便 DBA 维护。
> 
> 生成日期: 2026-02-27
> 总计表数量: 48

---

## 目录

1. [Agent 系统](#1-agent-系统)
2. [小说分析系统](#2-小说分析系统)
3. [财务系统](#3-财务系统)
4. [健康系统](#4-健康系统)
5. [历史事件系统](#5-历史事件系统)
6. [生活服务](#6-生活服务)
7. [物资管理系统](#7-物资管理系统)
8. [项目管理系统](#8-项目管理系统)
9. [文本内容管理](#9-文本内容管理)
10. [统一 Agent 系统](#10-统一-agent-系统)

---

## 1. Agent 系统

**文件**: `sail_server/data/agent.py`

### 1.1 user_prompts - 用户提示表
存储用户提交的待处理请求

| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER | 主键 |
| content | TEXT | 提示内容 |
| prompt_type | VARCHAR | 提示类型 |
| context | JSONB | 上下文信息 |
| priority | INTEGER | 优先级 |
| status | VARCHAR | 状态 |
| created_by | VARCHAR | 创建者 |
| session_id | VARCHAR | 会话ID |
| parent_prompt_id | INTEGER | 父提示ID |
| created_at | TIMESTAMP | 创建时间 |
| scheduled_at | TIMESTAMP | 调度时间 |
| started_at | TIMESTAMP | 开始时间 |
| completed_at | TIMESTAMP | 完成时间 |

### 1.2 agent_tasks - Agent 任务表
记录每个 Agent 执行实例

| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER | 主键 |
| prompt_id | INTEGER | 提示ID |
| agent_type | VARCHAR | Agent类型 |
| agent_config | JSONB | Agent配置 |
| status | VARCHAR | 状态 |
| progress | INTEGER | 进度 |
| created_at | TIMESTAMP | 创建时间 |
| started_at | TIMESTAMP | 开始时间 |
| updated_at | TIMESTAMP | 更新时间 |
| completed_at | TIMESTAMP | 完成时间 |
| error_message | TEXT | 错误信息 |
| error_code | VARCHAR | 错误码 |
| max_iterations | INTEGER | 最大迭代次数 |
| timeout_seconds | INTEGER | 超时时间 |

### 1.3 agent_steps - Agent 执行步骤表
记录 Agent 的每一步操作

| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER | 主键 |
| task_id | INTEGER | 任务ID |
| step_number | INTEGER | 步骤序号 |
| step_type | VARCHAR | 步骤类型 |
| title | VARCHAR | 标题 |
| content | TEXT | 内容 |
| content_summary | VARCHAR | 内容摘要 |
| meta_data | JSONB | 元数据 |
| created_at | TIMESTAMP | 创建时间 |
| duration_ms | INTEGER | 耗时(毫秒) |

### 1.4 agent_outputs - Agent 输出结果表
存储 Agent 的最终产出

| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER | 主键 |
| task_id | INTEGER | 任务ID |
| output_type | VARCHAR | 输出类型 |
| content | TEXT | 内容 |
| file_path | VARCHAR | 文件路径 |
| meta_data | JSONB | 元数据 |
| review_status | VARCHAR | 审核状态 |
| reviewed_by | VARCHAR | 审核人 |
| reviewed_at | TIMESTAMP | 审核时间 |
| review_notes | TEXT | 审核备注 |
| created_at | TIMESTAMP | 创建时间 |

### 1.5 agent_scheduler_state - Agent 调度器状态表
单例表，记录调度器运行状态

| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER | 主键 |
| is_running | BOOLEAN | 是否运行中 |
| last_poll_at | TIMESTAMP | 最后轮询时间 |
| active_agent_count | INTEGER | 活跃Agent数 |
| max_concurrent_agents | INTEGER | 最大并发数 |
| total_processed | INTEGER | 总处理数 |
| total_failed | INTEGER | 总失败数 |
| updated_at | TIMESTAMP | 更新时间 |

---

## 2. 小说分析系统

**文件**: `sail_server/data/analysis.py`

### 2.1 outlines - 大纲表
存储作品的各类大纲结构

| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER | 主键 |
| edition_id | INTEGER | 版本ID |
| outline_type | VARCHAR | 大纲类型 |
| title | VARCHAR | 标题 |
| description | TEXT | 描述 |
| status | VARCHAR | 状态 |
| source | VARCHAR | 来源 |
| meta_data | JSONB | 元数据 |
| created_by | VARCHAR | 创建者 |
| created_at | TIMESTAMP | 创建时间 |
| updated_at | TIMESTAMP | 更新时间 |

### 2.2 outline_nodes - 大纲节点表
树形结构表示情节层级

| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER | 主键 |
| outline_id | INTEGER | 大纲ID |
| parent_id | INTEGER | 父节点ID |
| node_type | VARCHAR | 节点类型 |
| sort_index | INTEGER | 排序索引 |
| depth | INTEGER | 深度 |
| title | VARCHAR | 标题 |
| summary | TEXT | 摘要 |
| significance | VARCHAR | 重要程度 |
| chapter_start_id | INTEGER | 开始章节ID |
| chapter_end_id | INTEGER | 结束章节ID |
| path | VARCHAR | 物化路径 |
| status | VARCHAR | 状态 |
| meta_data | JSONB | 元数据 |
| created_at | TIMESTAMP | 创建时间 |
| updated_at | TIMESTAMP | 更新时间 |

### 2.3 outline_events - 大纲事件表
记录情节中的关键事件

| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER | 主键 |
| outline_node_id | INTEGER | 大纲节点ID |
| event_type | VARCHAR | 事件类型 |
| title | VARCHAR | 标题 |
| description | TEXT | 描述 |
| chronology_order | NUMERIC | 时间线顺序 |
| narrative_order | INTEGER | 叙事顺序 |
| importance | VARCHAR | 重要程度 |
| meta_data | JSONB | 元数据 |
| created_at | TIMESTAMP | 创建时间 |

### 2.4 characters - 人物表
存储作品中的人物信息

| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER | 主键 |
| edition_id | INTEGER | 版本ID |
| canonical_name | VARCHAR | 标准名称 |
| role_type | VARCHAR | 角色类型 |
| description | TEXT | 描述 |
| first_appearance_node_id | INTEGER | 首次出现节点ID |
| status | VARCHAR | 状态 |
| source | VARCHAR | 来源 |
| importance_score | FLOAT | 重要度评分 |
| meta_data | JSONB | 元数据 |
| created_at | TIMESTAMP | 创建时间 |
| updated_at | TIMESTAMP | 更新时间 |

### 2.5 character_aliases - 人物别名表
存储人物的各种称呼

| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER | 主键 |
| character_id | INTEGER | 人物ID |
| alias | VARCHAR | 别名 |
| alias_type | VARCHAR | 别名类型 |
| usage_context | VARCHAR | 使用场景 |
| is_preferred | BOOLEAN | 是否首选 |
| source | VARCHAR | 来源 |
| created_at | TIMESTAMP | 创建时间 |

### 2.6 character_attributes - 人物属性表
存储人物的各类属性

| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER | 主键 |
| character_id | INTEGER | 人物ID |
| category | VARCHAR | 类别 |
| attr_key | VARCHAR | 属性键 |
| attr_value | TEXT | 属性值 |
| confidence | FLOAT | 置信度 |
| source | VARCHAR | 来源 |
| source_node_id | INTEGER | 来源节点ID |
| status | VARCHAR | 状态 |
| created_at | TIMESTAMP | 创建时间 |
| updated_at | TIMESTAMP | 更新时间 |

### 2.7 character_arcs - 人物弧线表
记录人物的成长变化轨迹

| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER | 主键 |
| character_id | INTEGER | 人物ID |
| arc_type | VARCHAR | 弧线类型 |
| title | VARCHAR | 标题 |
| description | TEXT | 描述 |
| start_node_id | INTEGER | 开始节点ID |
| end_node_id | INTEGER | 结束节点ID |
| status | VARCHAR | 状态 |
| meta_data | JSONB | 元数据 |
| created_at | TIMESTAMP | 创建时间 |

### 2.8 character_relations - 人物关系表
存储人物之间的关系

| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER | 主键 |
| edition_id | INTEGER | 版本ID |
| source_character_id | INTEGER | 源人物ID |
| target_character_id | INTEGER | 目标人物ID |
| relation_type | VARCHAR | 关系类型 |
| relation_subtype | VARCHAR | 关系子类型 |
| description | TEXT | 描述 |
| strength | FLOAT | 关系强度 |
| is_mutual | BOOLEAN | 是否双向 |
| start_node_id | INTEGER | 开始节点ID |
| end_node_id | INTEGER | 结束节点ID |
| status | VARCHAR | 状态 |
| meta_data | JSONB | 元数据 |
| created_at | TIMESTAMP | 创建时间 |
| updated_at | TIMESTAMP | 更新时间 |

### 2.9 novel_settings - 设定表
存储世界观设定元素

| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER | 主键 |
| edition_id | INTEGER | 版本ID |
| setting_type | VARCHAR | 设定类型 |
| canonical_name | VARCHAR | 标准名称 |
| category | VARCHAR | 类别 |
| description | TEXT | 描述 |
| first_appearance_node_id | INTEGER | 首次出现节点ID |
| importance | VARCHAR | 重要程度 |
| status | VARCHAR | 状态 |
| source | VARCHAR | 来源 |
| meta_data | JSONB | 元数据 |
| created_at | TIMESTAMP | 创建时间 |
| updated_at | TIMESTAMP | 更新时间 |

### 2.10 setting_attributes - 设定属性表
存储设定的详细属性

| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER | 主键 |
| setting_id | INTEGER | 设定ID |
| attr_key | VARCHAR | 属性键 |
| attr_value | TEXT | 属性值 |
| source | VARCHAR | 来源 |
| source_node_id | INTEGER | 来源节点ID |
| status | VARCHAR | 状态 |
| created_at | TIMESTAMP | 创建时间 |

### 2.11 setting_relations - 设定关系表
存储设定之间的关系

| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER | 主键 |
| edition_id | INTEGER | 版本ID |
| source_setting_id | INTEGER | 源设定ID |
| target_setting_id | INTEGER | 目标设定ID |
| relation_type | VARCHAR | 关系类型 |
| description | TEXT | 描述 |
| meta_data | JSONB | 元数据 |
| created_at | TIMESTAMP | 创建时间 |

### 2.12 character_setting_links - 人物-设定关联表
记录人物与设定的关系

| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER | 主键 |
| character_id | INTEGER | 人物ID |
| setting_id | INTEGER | 设定ID |
| link_type | VARCHAR | 关联类型 |
| description | TEXT | 描述 |
| start_node_id | INTEGER | 开始节点ID |
| end_node_id | INTEGER | 结束节点ID |
| meta_data | JSONB | 元数据 |
| created_at | TIMESTAMP | 创建时间 |

### 2.13 text_evidence - 文本证据表
存储分析结果的原文依据

| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER | 主键 |
| edition_id | INTEGER | 版本ID |
| node_id | INTEGER | 节点ID |
| target_type | VARCHAR | 目标类型 |
| target_id | INTEGER | 目标ID |
| start_char | INTEGER | 开始字符位置 |
| end_char | INTEGER | 结束字符位置 |
| text_snippet | TEXT | 文本片段 |
| context_before | TEXT | 前文上下文 |
| context_after | TEXT | 后文上下文 |
| evidence_type | VARCHAR | 证据类型 |
| confidence | FLOAT | 置信度 |
| source | VARCHAR | 来源 |
| created_at | TIMESTAMP | 创建时间 |

### 2.14 analysis_tasks - 分析任务表
管理AI分析和人工标注任务

| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER | 主键 |
| edition_id | INTEGER | 版本ID |
| task_type | VARCHAR | 任务类型 |
| target_scope | VARCHAR | 目标范围 |
| target_node_ids | INTEGER[] | 目标节点ID列表 |
| parameters | JSONB | 参数 |
| llm_model | VARCHAR | LLM模型 |
| llm_prompt_template | VARCHAR | 提示模板 |
| status | VARCHAR | 状态 |
| priority | INTEGER | 优先级 |
| scheduled_at | TIMESTAMP | 调度时间 |
| started_at | TIMESTAMP | 开始时间 |
| completed_at | TIMESTAMP | 完成时间 |
| error_message | TEXT | 错误信息 |
| result_summary | JSONB | 结果摘要 |
| created_by | VARCHAR | 创建者 |
| created_at | TIMESTAMP | 创建时间 |

### 2.15 analysis_results - 分析结果表
存储待审核的分析结果

| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER | 主键 |
| task_id | INTEGER | 任务ID |
| result_type | VARCHAR | 结果类型 |
| result_data | JSONB | 结果数据 |
| confidence | FLOAT | 置信度 |
| review_status | VARCHAR | 审核状态 |
| reviewer | VARCHAR | 审核人 |
| reviewed_at | TIMESTAMP | 审核时间 |
| review_notes | TEXT | 审核备注 |
| applied | BOOLEAN | 是否已应用 |
| applied_at | TIMESTAMP | 应用时间 |
| created_at | TIMESTAMP | 创建时间 |

---

## 3. 财务系统

**文件**: `sail_server/data/finance.py`

### 3.1 accounts - 账户表

| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER | 主键 |
| name | VARCHAR | 账户名称 |
| description | VARCHAR | 描述 |
| balance | NUMERIC | 余额 |
| state | VARCHAR | 状态 |
| ctime | TIMESTAMP | 创建时间 |
| mtime | TIMESTAMP | 修改时间 |

### 3.2 transactions - 交易表

| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER | 主键 |
| from_acc_id | INTEGER | 转出账户ID |
| to_acc_id | INTEGER | 转入账户ID |
| budget_id | INTEGER | 预算ID |
| value | NUMERIC | 金额 |
| prev_value | NUMERIC | 变更前金额 |
| description | VARCHAR | 描述 |
| tags | VARCHAR[] | 标签 |
| state | VARCHAR | 状态 |
| htime | TIMESTAMP | 发生时间 |
| ctime | TIMESTAMP | 创建时间 |
| mtime | TIMESTAMP | 修改时间 |

### 3.3 budgets - 预算主体表
通用预算模型

| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER | 主键 |
| name | VARCHAR | 名称 |
| description | VARCHAR | 描述 |
| tags | VARCHAR[] | 标签 |
| start_date | DATE | 开始日期 |
| end_date | DATE | 结束日期 |
| total_amount | NUMERIC | 总金额 |
| direction | VARCHAR | 方向(收入/支出) |
| htime | TIMESTAMP | 发生时间 |
| ctime | TIMESTAMP | 创建时间 |
| mtime | TIMESTAMP | 修改时间 |

### 3.4 budget_items - 预算子项表
通用预算项模型

| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER | 主键 |
| budget_id | INTEGER | 预算ID |
| name | VARCHAR | 名称 |
| description | VARCHAR | 描述 |
| direction | VARCHAR | 方向 |
| item_type | VARCHAR | 项目类型 |
| amount | NUMERIC | 金额 |
| period_count | INTEGER | 期数 |
| is_refundable | BOOLEAN | 是否可退还 |
| refund_amount | NUMERIC | 退还金额 |
| current_period | INTEGER | 当前期数 |
| status | VARCHAR | 状态 |
| due_date | DATE | 到期日期 |
| ctime | TIMESTAMP | 创建时间 |
| mtime | TIMESTAMP | 修改时间 |

---

## 4. 健康系统

**文件**: `sail_server/data/health.py`

### 4.1 weights - 体重数据表

| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER | 主键 |
| value | FLOAT | 体重值 |
| htime | TIMESTAMP | 记录时间 |
| tag | VARCHAR | 标签 |
| description | VARCHAR | 描述 |

### 4.2 body_size - 身体尺寸表

| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER | 主键 |
| waist | FLOAT | 腰围 |
| hip | FLOAT | 臀围 |
| chest | FLOAT | 胸围 |
| tag | VARCHAR | 标签 |
| htime | TIMESTAMP | 记录时间 |

### 4.3 exercises - 运动记录表

| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER | 主键 |
| htime | TIMESTAMP | 运动时间 |
| description | VARCHAR | 运动描述 |

### 4.4 weight_plans - 体重计划表

| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER | 主键 |
| target_weight | FLOAT | 目标体重 |
| start_time | TIMESTAMP | 开始时间 |
| target_time | TIMESTAMP | 目标时间 |
| description | VARCHAR | 描述 |
| created_at | TIMESTAMP | 创建时间 |

---

## 5. 历史事件系统

**文件**: `sail_server/data/history.py`

### 5.1 history_events - 历史事件表
用于记录和组织历史事件，支持嵌套结构和关联检索

| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER | 主键 |
| receive_time | TIMESTAMP | 接收时间 |
| title | VARCHAR | 标题 |
| description | TEXT | 描述 |
| rar_tags | VARCHAR[] | RAR标签 |
| tags | VARCHAR[] | 标签 |
| start_time | TIMESTAMP | 开始时间 |
| end_time | TIMESTAMP | 结束时间 |
| related_events | INTEGER[] | 关联事件ID列表 |
| parent_event | INTEGER | 父事件ID |
| details | JSONB | 详细信息 |

---

## 6. 生活服务

**文件**: `sail_server/data/life.py`

### 6.1 service_account - 服务资产表
存在有效期限的服务账户

| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER | 主键 |
| name | VARCHAR | 服务名称 |
| entry | VARCHAR | 入口地址 |
| username | VARCHAR | 用户名 |
| password | VARCHAR | 密码 |
| desp | VARCHAR | 描述 |
| expire_time | TIMESTAMP | 过期时间 |

---

## 7. 物资管理系统

**文件**: `sail_server/data/necessity.py`

### 7.1 residences - 住所表

| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER | 主键 |
| name | VARCHAR | 名称 |
| code | VARCHAR | 代码 |
| type | VARCHAR | 类型 |
| address | VARCHAR | 地址 |
| description | VARCHAR | 描述 |
| is_portable | BOOLEAN | 是否便携 |
| priority | INTEGER | 优先级 |
| ctime | TIMESTAMP | 创建时间 |
| mtime | TIMESTAMP | 修改时间 |

### 7.2 containers - 容器/存储位置表

| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER | 主键 |
| residence_id | INTEGER | 住所ID |
| parent_id | INTEGER | 父容器ID |
| name | VARCHAR | 名称 |
| type | VARCHAR | 类型 |
| description | VARCHAR | 描述 |
| capacity | VARCHAR | 容量 |
| ctime | TIMESTAMP | 创建时间 |
| mtime | TIMESTAMP | 修改时间 |

### 7.3 item_categories - 物资类别表

| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER | 主键 |
| parent_id | INTEGER | 父类别ID |
| name | VARCHAR | 名称 |
| code | VARCHAR | 代码 |
| icon | VARCHAR | 图标 |
| is_consumable | BOOLEAN | 是否消耗品 |
| default_unit | VARCHAR | 默认单位 |
| description | VARCHAR | 描述 |
| ctime | TIMESTAMP | 创建时间 |
| mtime | TIMESTAMP | 修改时间 |

### 7.4 items - 物资表

| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER | 主键 |
| name | VARCHAR | 名称 |
| category_id | INTEGER | 类别ID |
| type | VARCHAR | 类型 |
| brand | VARCHAR | 品牌 |
| model | VARCHAR | 型号 |
| serial_number | VARCHAR | 序列号 |
| description | VARCHAR | 描述 |
| purchase_date | DATE | 购买日期 |
| purchase_price | NUMERIC | 购买价格 |
| warranty_until | DATE | 保修到期日 |
| expire_date | DATE | 过期日期 |
| importance | INTEGER | 重要程度 |
| portability | VARCHAR | 便携性 |
| tags | VARCHAR[] | 标签 |
| image_url | VARCHAR | 图片URL |
| state | VARCHAR | 状态 |
| ctime | TIMESTAMP | 创建时间 |
| mtime | TIMESTAMP | 修改时间 |

### 7.5 inventories - 库存记录表

| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER | 主键 |
| item_id | INTEGER | 物资ID |
| residence_id | INTEGER | 住所ID |
| container_id | INTEGER | 容器ID |
| quantity | NUMERIC | 数量 |
| unit | VARCHAR | 单位 |
| min_quantity | NUMERIC | 最小数量 |
| max_quantity | NUMERIC | 最大数量 |
| last_check_time | TIMESTAMP | 最后检查时间 |
| notes | VARCHAR | 备注 |
| ctime | TIMESTAMP | 创建时间 |
| mtime | TIMESTAMP | 修改时间 |

### 7.6 journeys - 旅程表

| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER | 主键 |
| from_residence_id | INTEGER | 出发住所ID |
| to_residence_id | INTEGER | 目的住所ID |
| depart_time | TIMESTAMP | 出发时间 |
| arrive_time | TIMESTAMP | 到达时间 |
| status | VARCHAR | 状态 |
| transport_mode | VARCHAR | 交通方式 |
| notes | VARCHAR | 备注 |
| ctime | TIMESTAMP | 创建时间 |
| mtime | TIMESTAMP | 修改时间 |

### 7.7 journey_items - 旅程物资表

| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER | 主键 |
| journey_id | INTEGER | 旅程ID |
| item_id | INTEGER | 物资ID |
| quantity | NUMERIC | 数量 |
| is_return | BOOLEAN | 是否返程 |
| from_container_id | INTEGER | 源容器ID |
| to_container_id | INTEGER | 目标容器ID |
| status | VARCHAR | 状态 |
| notes | VARCHAR | 备注 |
| ctime | TIMESTAMP | 创建时间 |
| mtime | TIMESTAMP | 修改时间 |

### 7.8 consumptions - 消耗记录表

| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER | 主键 |
| inventory_id | INTEGER | 库存ID |
| quantity | NUMERIC | 数量 |
| htime | TIMESTAMP | 发生时间 |
| reason | VARCHAR | 原因 |
| ctime | TIMESTAMP | 创建时间 |

### 7.9 replenishments - 补货记录表

| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER | 主键 |
| inventory_id | INTEGER | 库存ID |
| quantity | NUMERIC | 数量 |
| source | VARCHAR | 来源 |
| source_residence_id | INTEGER | 来源住所ID |
| cost | NUMERIC | 成本 |
| transaction_id | INTEGER | 交易ID |
| htime | TIMESTAMP | 发生时间 |
| notes | VARCHAR | 备注 |
| ctime | TIMESTAMP | 创建时间 |

---

## 8. 项目管理系统

**文件**: `sail_server/data/project.py`

### 8.1 projects - 长期项目管理表

| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER | 主键 |
| name | VARCHAR | 名称 |
| description | VARCHAR | 描述 |
| state | VARCHAR | 状态 |
| start_time_qbw | INTEGER | 开始时间( quarter-based week ) |
| end_time_qbw | INTEGER | 结束时间 |
| ctime | TIMESTAMP | 创建时间 |
| mtime | TIMESTAMP | 修改时间 |

### 8.2 missions - 任务管理表
树形结构（左右值结构）

| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER | 主键 |
| name | VARCHAR | 名称 |
| description | VARCHAR | 描述 |
| parent_id | INTEGER | 父任务ID |
| state | VARCHAR | 状态 |
| ddl | TIMESTAMP | 截止日期 |
| project_id | INTEGER | 项目ID |
| lft | INTEGER | 左值(树形结构) |
| rgt | INTEGER | 右值(树形结构) |
| tree_id | INTEGER | 树ID |
| ctime | TIMESTAMP | 创建时间 |
| mtime | TIMESTAMP | 修改时间 |

---

## 9. 文本内容管理

**文件**: `sail_server/data/text.py`

### 9.1 works - 作品表
代表一本书或小说

| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER | 主键 |
| slug | VARCHAR | 唯一标识符 |
| title | VARCHAR | 标题 |
| original_title | VARCHAR | 原标题 |
| author | VARCHAR | 作者 |
| language_primary | VARCHAR | 主要语言 |
| work_type | VARCHAR | 作品类型 |
| status | VARCHAR | 状态 |
| synopsis | TEXT | 简介 |
| meta_data | JSONB | 元数据 |
| created_at | TIMESTAMP | 创建时间 |
| updated_at | TIMESTAMP | 更新时间 |

### 9.2 editions - 版本表
代表作品的一个具体版本/译本

| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER | 主键 |
| work_id | INTEGER | 作品ID |
| edition_name | VARCHAR | 版本名称 |
| language | VARCHAR | 语言 |
| source_format | VARCHAR | 源格式 |
| canonical | BOOLEAN | 是否标准版本 |
| source_path | VARCHAR | 源文件路径 |
| source_checksum | VARCHAR | 源文件校验和 |
| ingest_version | INTEGER | 导入版本 |
| word_count | INTEGER | 字数 |
| char_count | INTEGER | 字符数 |
| description | TEXT | 描述 |
| status | VARCHAR | 状态 |
| meta_data | JSONB | 元数据 |
| created_at | TIMESTAMP | 创建时间 |
| updated_at | TIMESTAMP | 更新时间 |

### 9.3 document_nodes - 文档节点表
树形结构存储文本内容

| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER | 主键 |
| edition_id | INTEGER | 版本ID |
| parent_id | INTEGER | 父节点ID |
| node_type | VARCHAR | 节点类型 |
| sort_index | INTEGER | 排序索引 |
| depth | INTEGER | 深度 |
| label | VARCHAR | 标签 |
| title | VARCHAR | 标题 |
| raw_text | TEXT | 原始文本 |
| word_count | INTEGER | 字数 |
| char_count | INTEGER | 字符数 |
| path | VARCHAR | 物化路径 |
| status | VARCHAR | 状态 |
| meta_data | JSONB | 元数据 |
| created_at | TIMESTAMP | 创建时间 |
| updated_at | TIMESTAMP | 更新时间 |

### 9.4 ingest_jobs - 导入作业表
跟踪文本导入任务

| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER | 主键 |
| edition_id | INTEGER | 版本ID |
| job_type | VARCHAR | 作业类型 |
| status | VARCHAR | 状态 |
| payload | JSONB | 载荷数据 |
| started_at | TIMESTAMP | 开始时间 |
| finished_at | TIMESTAMP | 完成时间 |
| error_message | TEXT | 错误信息 |
| progress | INTEGER | 进度 |
| total_items | INTEGER | 总项目数 |
| processed_items | INTEGER | 已处理项目数 |

---

## 10. 统一 Agent 系统

**文件**: `sail_server/data/unified_agent.py`

### 10.1 unified_agent_tasks - 统一 Agent 任务表
整合 AgentTask 和 AnalysisTask 的功能

| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER | 主键 |
| task_type | VARCHAR | 任务类型 |
| sub_type | VARCHAR | 子类型 |
| edition_id | INTEGER | 版本ID |
| target_node_ids | INTEGER[] | 目标节点ID列表 |
| target_scope | VARCHAR | 目标范围 |
| llm_provider | VARCHAR | LLM提供商 |
| llm_model | VARCHAR | LLM模型 |
| prompt_template_id | VARCHAR | 提示模板ID |
| status | VARCHAR | 状态 |
| progress | INTEGER | 进度 |
| current_phase | VARCHAR | 当前阶段 |
| priority | INTEGER | 优先级 |
| error_message | TEXT | 错误信息 |
| error_code | VARCHAR | 错误码 |
| estimated_tokens | INTEGER | 预估Token数 |
| actual_tokens | INTEGER | 实际Token数 |
| estimated_cost | NUMERIC | 预估成本 |
| actual_cost | NUMERIC | 实际成本 |
| result_data | JSONB | 结果数据 |
| review_status | VARCHAR | 审核状态 |
| config | JSONB | 配置 |
| created_at | TIMESTAMP | 创建时间 |
| started_at | TIMESTAMP | 开始时间 |
| completed_at | TIMESTAMP | 完成时间 |
| cancelled_at | TIMESTAMP | 取消时间 |
| updated_at | TIMESTAMP | 更新时间 |

### 10.2 unified_agent_steps - 统一 Agent 任务步骤表
整合 AgentStep 功能，增强 LLM 调用追踪

| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER | 主键 |
| task_id | INTEGER | 任务ID |
| step_number | INTEGER | 步骤序号 |
| step_type | VARCHAR | 步骤类型 |
| title | VARCHAR | 标题 |
| content | TEXT | 内容 |
| content_summary | VARCHAR | 内容摘要 |
| llm_provider | VARCHAR | LLM提供商 |
| llm_model | VARCHAR | LLM模型 |
| prompt_tokens | INTEGER | Prompt Token数 |
| completion_tokens | INTEGER | 补全Token数 |
| cost | NUMERIC | 成本 |
| meta_data | JSONB | 元数据 |
| created_at | TIMESTAMP | 创建时间 |
| duration_ms | INTEGER | 耗时(毫秒) |

### 10.3 unified_agent_events - 统一 Agent 事件日志表
用于记录任务执行过程中的关键事件，便于审计和调试

| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER | 主键 |
| task_id | INTEGER | 任务ID |
| event_type | VARCHAR | 事件类型 |
| event_data | JSONB | 事件数据 |
| created_at | TIMESTAMP | 创建时间 |

---

## 附录

### 表数量统计

| 模块 | 表数量 |
|------|--------|
| Agent 系统 | 5 |
| 小说分析系统 | 15 |
| 财务系统 | 4 |
| 健康系统 | 4 |
| 历史事件系统 | 1 |
| 生活服务 | 1 |
| 物资管理系统 | 9 |
| 项目管理系统 | 2 |
| 文本内容管理 | 4 |
| 统一 Agent 系统 | 3 |
| **总计** | **48** |

### 常用维护命令

```bash
# 备份数据库
pg_dump $POSTGRE_URI > backup_$(date +%Y%m%d_%H%M%S).sql

# 恢复数据库
psql $POSTGRE_URI < backup_file.sql

# 查看表大小
psql $POSTGRE_URI -c "SELECT schemaname, tablename, pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) FROM pg_tables WHERE schemaname='public' ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;"

# 查看连接数
psql $POSTGRE_URI -c "SELECT count(*) FROM pg_stat_activity;"
```

### 相关文件

- ORM 基类: `sail_server/data/orm.py`
- 数据库连接: `sail_server/db.py`
- 迁移脚本目录: `sail_server/migration/`
