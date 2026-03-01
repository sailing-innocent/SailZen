# AI 文本分析 API

> **版本**: v1.0 | **更新**: 2026-03-01 | **状态**: 已完成

---

## 📋 功能概述

AI 文本分析模块提供小说等文本的智能分析功能，包括大纲提取、人物识别、设定提取等。

### 核心功能

| 功能 | 说明 |
|------|------|
| **大纲提取** | 自动提取文本的大纲结构 |
| **人物识别** | 识别文本中的人物及其属性 |
| **设定提取** | 提取世界观、能力体系等设定 |
| **分析任务** | 异步执行分析任务，支持进度追踪 |
| **证据管理** | 管理分析结果的文本证据 |

### 分析任务类型

| 类型 | 说明 |
|------|------|
| `outline_extraction` | 大纲提取 |
| `character_detection` | 人物识别 |
| `setting_extraction` | 设定提取 |

---

## 🎯 分析任务 API

### 创建分析任务

```http
POST /api/v1/analysis/task/
```

**请求体:**
```json
{
  "edition_id": 1,
  "task_type": "outline_extraction",
  "name": "大纲分析任务",
  "description": "提取前10章大纲",
  "config": {
    "start_chapter": 0,
    "end_chapter": 10
  }
}
```

**响应:**
```json
{
  "id": 1,
  "edition_id": 1,
  "task_type": "outline_extraction",
  "name": "大纲分析任务",
  "status": "pending",
  "created_at": 1700000000
}
```

---

### 获取任务列表

```http
GET /api/v1/analysis/task/?edition_id=1
```

**参数:**
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| edition_id | int | 是 | 版本ID |

---

### 获取任务详情

```http
GET /api/v1/analysis/task/{task_id}
```

---

### 创建执行计划

```http
POST /api/v1/analysis/task/{task_id}/plan
```

**请求体:**
```json
{
  "mode": "auto"  // auto: 自动模式, manual: 手动模式
}
```

---

### 异步执行任务

```http
POST /api/v1/analysis/task/{task_id}/execute
```

**请求体:**
```json
{
  "mode": "auto",
  "llm_provider": "moonshot",  // LLM 提供商
  "temperature": 0.7
}
```

---

### 获取任务进度

```http
GET /api/v1/analysis/progress/{task_id}
```

**响应:**
```json
{
  "success": true,
  "progress": {
    "task_id": 1,
    "status": "running",
    "current_step": 5,
    "total_steps": 10,
    "percent": 50,
    "message": "正在分析第5章"
  }
}
```

---

### 取消任务

```http
POST /api/v1/analysis/task/{task_id}/cancel
```

---

### 获取任务结果

```http
GET /api/v1/analysis/result/{task_id}
```

---

### 批准结果

```http
POST /api/v1/analysis/result/{result_id}/verify
```

**请求体:**
```json
{
  "status": "approved"
}
```

---

### 拒绝结果

```http
POST /api/v1/analysis/result/{result_id}/verify
```

**请求体:**
```json
{
  "status": "rejected"
}
```

---

### 应用所有已批准结果

```http
POST /api/v1/analysis/task/{task_id}/apply
```

**响应:**
```json
{
  "applied": 5,
  "failed": 0
}
```

---

## 📖 大纲 API

### 获取版本的大纲列表

```http
GET /api/v1/analysis/outline/edition/{edition_id}
```

**参数:**
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| outline_type | string | 否 | 大纲类型筛选 |

**响应:**
```json
[
  {
    "id": "uuid",
    "edition_id": 1,
    "title": "主线大纲",
    "outline_type": "main",
    "description": "主线剧情大纲"
  }
]
```

---

### 创建大纲

```http
POST /api/v1/analysis/outline/
```

**请求体:**
```json
{
  "title": "大纲名称",
  "outline_type": "main",
  "description": "大纲描述",
  "edition_id": 1
}
```

---

### 删除大纲

```http
DELETE /api/v1/analysis/outline/{outline_id}
```

---

### 获取大纲树

```http
GET /api/v1/analysis/outline/{outline_id}/tree
```

**响应:**
```json
{
  "outline_id": "uuid",
  "nodes": [
    {
      "id": "node-uuid",
      "title": "节点标题",
      "node_type": "chapter",
      "summary": "内容摘要",
      "children": [...]
    }
  ]
}
```

---

### 添加大纲节点

```http
POST /api/v1/analysis/outline/node
```

**请求体:**
```json
{
  "outline_id": "uuid",
  "parent_id": "parent-uuid",  // 可选
  "node_type": "chapter",
  "title": "节点标题",
  "summary": "内容摘要",
  "sort_index": 0
}
```

---

### 删除大纲节点

```http
DELETE /api/v1/analysis/outline/node/{node_id}
```

---

### 添加大纲事件

```http
POST /api/v1/analysis/outline/event
```

**请求体:**
```json
{
  "node_id": "node-uuid",
  "event_type": "conflict",
  "description": "事件描述",
  "significance": "high"
}
```

---

## 👤 人物 API

### 获取版本的人物列表

```http
GET /api/v1/analysis/character/edition/{edition_id}
```

**参数:**
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| role_type | string | 否 | 角色类型筛选 |

**响应:**
```json
[
  {
    "id": "uuid",
    "edition_id": 1,
    "canonical_name": "主角名",
    "role_type": "protagonist",
    "description": "人物简介"
  }
]
```

---

### 创建人物

```http
POST /api/v1/analysis/character/
```

**请求体:**
```json
{
  "edition_id": 1,
  "canonical_name": "人物名",
  "role_type": "protagonist",  // protagonist, antagonist, supporting, minor
  "description": "人物简介"
}
```

---

### 删除人物

```http
DELETE /api/v1/analysis/character/{character_id}
```

---

### 获取人物详情

```http
GET /api/v1/analysis/character/{character_id}/profile
```

**响应:**
```json
{
  "character": { ... },
  "aliases": [...],
  "attributes": [
    {
      "id": "uuid",
      "category": "physical",
      "key": "age",
      "value": "20岁"
    }
  ],
  "evidence": [...]
}
```

---

### 添加人物别名

```http
POST /api/v1/analysis/character/{character_id}/alias
```

**请求体:**
```json
{
  "alias": "别名",
  "alias_type": "nickname"  // name, nickname, title, alias
}
```

---

### 删除人物别名

```http
DELETE /api/v1/analysis/character/alias/{alias_id}
```

---

### 添加人物属性

```http
POST /api/v1/analysis/character/{character_id}/attribute
```

**请求体:**
```json
{
  "category": "physical",  // physical, personality, background, ability, relationship
  "key": "age",
  "value": "20岁",
  "confidence": 0.9
}
```

---

### 删除人物属性

```http
DELETE /api/v1/analysis/character/attribute/{attribute_id}
```

---

### 获取关系图谱

```http
GET /api/v1/analysis/edition/{edition_id}/relation-graph
```

**响应:**
```json
{
  "nodes": [
    {
      "id": "uuid",
      "name": "人物名",
      "role_type": "protagonist"
    }
  ],
  "edges": [
    {
      "source": "uuid1",
      "target": "uuid2",
      "relation": "friend"
    }
  ]
}
```

---

## 🌍 设定 API

### 获取版本的设定列表

```http
GET /api/v1/analysis/setting/edition/{edition_id}
```

**参数:**
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| setting_type | string | 否 | 设定类型筛选 |

**响应:**
```json
[
  {
    "id": "uuid",
    "edition_id": 1,
    "canonical_name": "修仙体系",
    "setting_type": "power_system",
    "description": "修炼等级体系",
    "importance": "high"
  }
]
```

---

### 创建设定

```http
POST /api/v1/analysis/setting/
```

**请求体:**
```json
{
  "edition_id": 1,
  "canonical_name": "设定名",
  "setting_type": "worldview",  // worldview, power_system, organization, item, location, custom
  "description": "设定描述",
  "importance": "high"  // critical, high, medium, low
}
```

---

### 删除设定

```http
DELETE /api/v1/analysis/setting/{setting_id}
```

---

### 获取设定详情

```http
GET /api/v1/analysis/setting/{setting_id}/detail
```

**响应:**
```json
{
  "setting": { ... },
  "attributes": [...],
  "evidence": [...]
}
```

---

### 获取设定类型列表

```http
GET /api/v1/analysis/setting/types
```

**响应:**
```json
{
  "types": ["worldview", "power_system", "organization", "item", "location", "custom"],
  "labels": {
    "worldview": "世界观",
    "power_system": "力量体系",
    ...
  }
}
```

---

### 添加设定属性

```http
POST /api/v1/analysis/setting/{setting_id}/attribute
```

**请求体:**
```json
{
  "key": "等级划分",
  "value": "练气、筑基、金丹...",
  "description": "详细说明"
}
```

---

### 删除设定属性

```http
DELETE /api/v1/analysis/setting/attribute/{attribute_id}
```

---

## 📍 文本范围 API

### 预览文本范围

```http
POST /api/v1/analysis/range/preview
```

**请求体:**
```json
{
  "edition_id": 1,
  "mode": "chapter_range",  // chapter_range, node_range, text_range
  "start_chapter": 0,
  "end_chapter": 10
}
```

**响应:**
```json
{
  "word_count": 50000,
  "chapter_count": 10,
  "preview": "文本预览..."
}
```

---

### 获取范围内容

```http
POST /api/v1/analysis/range/content
```

**请求体:** 同预览

**响应:**
```json
{
  "content": "完整文本内容",
  "word_count": 50000
}
```

---

### 获取选择模式列表

```http
GET /api/v1/analysis/range/modes
```

---

## 📋 证据 API

### 创建证据

```http
POST /api/v1/analysis/evidence/
```

**请求体:**
```json
{
  "node_id": 1,
  "evidence_type": "character",
  "target_type": "character",
  "target_id": "uuid",
  "content": "证据文本",
  "position_start": 100,
  "position_end": 200
}
```

---

### 获取证据

```http
GET /api/v1/analysis/evidence/{evidence_id}
```

---

### 获取章节的证据

```http
GET /api/v1/analysis/evidence/chapter/{node_id}
```

**参数:**
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| evidence_type | string | 否 | 证据类型筛选 |

---

### 获取目标的证据

```http
GET /api/v1/analysis/evidence/target/{target_type}/{target_id}
```

---

### 更新证据

```http
POST /api/v1/analysis/evidence/{evidence_id}
```

---

### 删除证据

```http
DELETE /api/v1/analysis/evidence/{evidence_id}
```

---

## 🚀 大纲提取任务 API

### 创建大纲提取任务

```http
POST /api/v1/analysis/outline-extraction/
```

**请求体:**
```json
{
  "edition_id": 1,
  "name": "大纲提取",
  "start_chapter": 0,
  "end_chapter": 50,
  "config": {
    "extraction_depth": "detailed"
  }
}
```

---

### 获取提取任务进度

```http
GET /api/v1/analysis/outline-extraction/task/{task_id}
```

---

### 获取详细状态

```http
GET /api/v1/analysis/outline-extraction/task/{task_id}/detailed
```

---

### 恢复任务

```http
POST /api/v1/analysis/outline-extraction/task/{task_id}/resume
```

---

### 获取提取结果

```http
GET /api/v1/analysis/outline-extraction/task/{task_id}/result
```

---

### 保存提取结果

```http
POST /api/v1/analysis/outline-extraction/task/{task_id}/save
```

将提取的大纲保存为正式大纲。

---

### 预览提取效果

```http
POST /api/v1/analysis/outline-extraction/preview
```

**请求体:** 同创建任务

---

### 获取版本的所有提取任务

```http
GET /api/v1/analysis/outline-extraction/tasks/edition/{edition_id}
```

---

## ⚙️ LLM 配置 API

### 获取 LLM 提供商列表

```http
GET /api/v1/analysis/llm-providers
```

**响应:**
```json
{
  "providers": [
    {
      "name": "moonshot",
      "models": ["kimi-k2.5"],
      "default_model": "kimi-k2.5"
    }
  ],
  "default": "moonshot"
}
```

---

## 🖥️ 前端 API 客户端

### 导入

```typescript
import {
  // 任务管理
  api_create_analysis_task,
  api_get_tasks_by_edition,
  api_get_analysis_task,
  api_get_task_results,
  api_approve_result,
  api_reject_result,
  api_apply_all_results,
  api_create_task_plan,
  api_execute_task_async,
  api_get_task_progress,
  api_cancel_running_task,
  
  // 大纲
  api_get_outlines_by_edition,
  api_create_outline,
  api_delete_outline,
  api_get_outline_tree,
  api_add_outline_node,
  api_delete_outline_node,
  api_add_outline_event,
  
  // 人物
  api_get_characters_by_edition,
  api_create_character,
  api_delete_character,
  api_get_character_profile,
  api_add_character_alias,
  api_remove_character_alias,
  api_add_character_attribute,
  api_delete_character_attribute,
  api_get_relation_graph,
  
  // 设定
  api_get_settings_by_edition,
  api_create_setting,
  api_delete_setting,
  api_get_setting_detail,
  api_get_setting_types,
  api_add_setting_attribute,
  api_delete_setting_attribute,
  
  // 证据
  api_create_evidence,
  api_get_evidence,
  api_get_chapter_evidence,
  api_get_target_evidence,
  api_update_evidence,
  api_delete_evidence,
  
  // 文本范围
  api_preview_range,
  api_get_range_content,
  api_get_selection_modes,
  
  // 大纲提取
  api_create_outline_extraction_task,
  api_get_outline_extraction_progress,
  api_get_outline_extraction_result,
  api_save_outline_extraction_result,
  api_preview_outline_extraction,
  api_resume_outline_extraction_task,
} from '@lib/api/analysis'
```

### 使用示例

```typescript
// 创建大纲提取任务
const task = await api_create_outline_extraction_task({
  edition_id: 1,
  name: '前50章大纲提取',
  start_chapter: 0,
  end_chapter: 50
})

// 轮询获取进度
const checkProgress = async () => {
  const result = await api_get_outline_extraction_progress(task.task_id)
  console.log(`进度: ${result.progress_percent}%`)
  
  if (result.status === 'completed') {
    // 获取结果
    const extractionResult = await api_get_outline_extraction_result(task.task_id)
    console.log(extractionResult.outline)
    
    // 保存结果
    await api_save_outline_extraction_result(task.task_id)
  } else if (result.status === 'failed') {
    console.error('任务失败')
  } else {
    setTimeout(checkProgress, 2000)  // 2秒后再次检查
  }
}
checkProgress()

// 创建人物
const character = await api_create_character(1, {
  canonical_name: '主角',
  role_type: 'protagonist',
  description: '小说的主角'
})

// 添加人物属性
await api_add_character_attribute(character.id, {
  category: 'physical',
  key: '年龄',
  value: '20岁',
  confidence: 0.95
})

// 添加别名
await api_add_character_alias(character.id, '小名', 'nickname')

// 创建设定
const setting = await api_create_setting(1, {
  name: '修仙体系',
  setting_type: 'power_system',
  description: '修炼等级划分',
  importance: 'high'
})

// 获取关系图谱
const graph = await api_get_relation_graph(1)
console.log(graph.nodes)
console.log(graph.edges)

// 预览文本范围
const preview = await api_preview_range({
  edition_id: 1,
  mode: 'chapter_range',
  start_chapter: 0,
  end_chapter: 10
})
console.log(`字数: ${preview.word_count}`)
```

---

*本文档由 AI Agent 维护，如有疑问请参考源代码或联系开发团队。*
