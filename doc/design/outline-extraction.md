# 大纲提取功能设计文档

## 概述

大纲提取功能使用 AI 自动分析文本内容，提取结构化的大纲信息，包括故事结构、情节节点、转折点等。该功能集成在 SailZen 的分析模块中。

## 功能特性

### 1. 文本范围选择

支持多种文本选择模式：

- **单章选择**: 选择单个章节进行分析
- **章节范围**: 选择连续的章节范围
- **多章选择**: 选择多个不连续的章节
- **整部作品**: 分析整个版本的所有内容
- **从当前到结尾**: 从指定章节到作品结尾
- **自定义范围**: 通过节点 ID 指定具体范围

### 2. 提取配置

#### 粒度级别 (Granularity)

| 级别 | 说明 | 适用场景 |
|------|------|----------|
| `act` | 幕/卷级别 | 长篇小说的宏观结构 |
| `arc` | 故事弧级别 | 中篇结构，包含多个章节的故事线 |
| `scene` | 场景级别 | 具体场景和段落 |
| `beat` | 节拍级别 | 最细粒度，适合详细分析 |

#### 大纲类型 (Outline Type)

| 类型 | 说明 |
|------|------|
| `main` | 主线大纲 |
| `subplot` | 支线大纲 |
| `character_arc` | 人物弧光大纲 |
| `theme` | 主题大纲 |

#### 附加选项

- **提取转折点**: 识别关键情节点（触发事件、高潮、结局等）
- **关联人物**: 自动识别涉及的人物角色

### 3. AI 提取流程

```
┌─────────────────┐
│  创建提取任务    │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  异步执行提取    │
│  - 文本分块     │
│  - LLM 分析     │
│  - 结果合并     │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  查询任务进度    │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  获取提取结果    │
│  - 预览确认     │
│  - 保存到数据库 │
└─────────────────┘
```

## API 接口

### 大纲管理 API

#### 获取版本的大纲列表
```http
GET /api/v1/analysis/outline/edition/{edition_id}?outline_type={type}
```

#### 创建大纲
```http
POST /api/v1/analysis/outline/
Content-Type: application/json

{
  "edition_id": 1,
  "name": "主线大纲",
  "outline_type": "main",
  "description": "故事主线结构"
}
```

#### 删除大纲
```http
DELETE /api/v1/analysis/outline/{outline_id}
```

#### 获取大纲树结构
```http
GET /api/v1/analysis/outline/{outline_id}/tree
```

#### 添加大纲节点
```http
POST /api/v1/analysis/outline/node
Content-Type: application/json

{
  "outline_id": "uuid",
  "parent_id": "parent-uuid",
  "node_type": "chapter",
  "title": "第一章",
  "summary": "章节概要",
  "sort_index": 0
}
```

#### 删除大纲节点
```http
DELETE /api/v1/analysis/outline/node/{node_id}
```

#### 添加大纲事件
```http
POST /api/v1/analysis/outline/event
Content-Type: application/json

{
  "node_id": "node-uuid",
  "event_type": "turning_point",
  "description": "关键转折点",
  "significance": "high"
}
```

### 大纲提取 API

#### 创建提取任务
```http
POST /api/v1/analysis/outline-extraction/
Content-Type: application/json

{
  "edition_id": 1,
  "range_selection": {
    "edition_id": 1,
    "mode": "chapter_range",
    "start_index": 0,
    "end_index": 10
  },
  "config": {
    "granularity": "scene",
    "outline_type": "main",
    "extract_turning_points": true,
    "extract_characters": true
  },
  "work_title": "作品标题",
  "known_characters": ["主角", "反派"]
}
```

**响应**:
```json
{
  "task_id": "uuid",
  "status": "pending",
  "message": "大纲提取任务已创建",
  "created_at": "2025-02-28T12:00:00"
}
```

#### 获取任务进度
```http
GET /api/v1/analysis/outline-extraction/task/{task_id}
```

**响应**:
```json
{
  "task_id": "uuid",
  "current_step": "extracting",
  "progress_percent": 45,
  "message": "正在分析第 3/10 章",
  "chunk_index": 3,
  "total_chunks": 10
}
```

#### 获取任务结果
```http
GET /api/v1/analysis/outline-extraction/task/{task_id}/result
```

**响应**:
```json
{
  "success": true,
  "task_id": "uuid",
  "result": {
    "nodes": [
      {
        "id": "node-uuid",
        "node_type": "act",
        "title": "第一幕：启程",
        "summary": "故事开端，主角踏上旅程",
        "significance": "high",
        "sort_index": 0,
        "parent_id": null,
        "characters": ["主角"],
        "evidence": {"text": "原文引用", "chapter": 1}
      }
    ],
    "turning_points": [
      {
        "node_id": "node-uuid",
        "turning_point_type": "inciting_incident",
        "description": "触发事件描述"
      }
    ],
    "metadata": {
      "total_nodes": 15,
      "estimated_tokens": 5000
    }
  },
  "message": "大纲提取完成"
}
```

#### 保存提取结果
```http
POST /api/v1/analysis/outline-extraction/task/{task_id}/save
```

**响应**:
```json
{
  "success": true,
  "message": "大纲已保存到数据库",
  "outline_id": "uuid",
  "nodes_created": 15,
  "events_created": 5
}
```

#### 预览提取效果
```http
POST /api/v1/analysis/outline-extraction/preview
Content-Type: application/json

{
  "edition_id": 1,
  "range_selection": {...},
  "config": {...}
}
```

预览模式只返回前 10 个节点，用于快速验证提取效果。

## 前端使用流程

### 1. 打开分析工作台

导航到 `分析 > 大纲分析`，选择要分析的版本。

### 2. 配置提取参数

在右侧面板配置：
- **文本范围**: 选择要分析的章节范围
- **粒度**: 选择提取的详细程度
- **大纲类型**: 选择大纲的用途类型
- **附加选项**: 勾选是否需要提取转折点和关联人物

### 3. 预览与提取

点击 **预览** 按钮查看前 10 个节点的提取效果，确认后点击 **开始提取** 创建任务。

### 4. 查看进度

任务创建后显示进度条，可以实时查看：
- 当前处理步骤
- 完成百分比
- 处理章节进度

### 5. 审查与保存

提取完成后：
- 查看完整的节点树
- 检查每个节点的标题、摘要、重要性
- 查看识别的转折点
- 确认无误后点击 **保存到数据库**

### 6. 手动编辑

保存后可以在大纲树编辑器中：
- 添加/删除节点
- 修改节点内容
- 调整节点层级
- 添加事件标记

## 数据库模型

### Outline (大纲)

| 字段 | 类型 | 说明 |
|------|------|------|
| id | Integer (PK) | 主键 |
| edition_id | Integer (FK) | 关联版本 |
| title | String | 大纲标题 |
| outline_type | String | 大纲类型: main(主线), subplot(支线), character_arc(人物弧) |
| description | Text | 描述 |
| status | String | 状态: draft(草稿), analyzing(分析中), reviewed(已审核), finalized(已定稿) |
| source | String | 来源: manual(手动), ai_generated(AI生成), hybrid(混合) |
| meta_data | JSONB | 元数据 |
| created_by | String | 创建者 |
| created_at | TIMESTAMP | 创建时间 |
| updated_at | TIMESTAMP | 更新时间 |

### OutlineNode (大纲节点)

| 字段 | 类型 | 说明 |
|------|------|------|
| id | Integer (PK) | 主键 |
| outline_id | Integer (FK) | 关联大纲 |
| parent_id | Integer (FK) | 父节点 |
| node_type | String | 节点类型: act(幕), arc(弧), beat(节拍), scene(场景), turning_point(转折点) |
| sort_index | Integer | 排序索引 |
| depth | Integer | 层级深度 |
| path | String | 物化路径，如 "0001.0003" |
| title | String | 节点标题 |
| summary | Text | 内容摘要 |
| significance | String | 重要程度: critical(关键), major(主要), normal(普通), minor(次要) |
| chapter_start_id | Integer (FK) | 起始章节 |
| chapter_end_id | Integer (FK) | 结束章节 |
| status | String | 状态: draft(草稿) |
| meta_data | JSONB | 元数据 |
| created_at | TIMESTAMP | 创建时间 |
| updated_at | TIMESTAMP | 更新时间 |

### OutlineEvent (大纲事件)

| 字段 | 类型 | 说明 |
|------|------|------|
| id | Integer (PK) | 主键 |
| outline_node_id | Integer (FK) | 关联节点 |
| event_type | String | 事件类型: plot(情节), conflict(冲突), revelation(揭示), resolution(解决), climax(高潮) |
| title | String | 事件标题 |
| description | Text | 描述 |
| chronology_order | Float | 故事内时间线顺序 |
| narrative_order | Integer | 叙事顺序 |
| importance | String | 重要性 |
| meta_data | JSONB | 元数据 |
| created_at | TIMESTAMP | 创建时间 |

## 技术实现

### 后端组件

- **OutlineController**: 大纲管理 API
- **OutlineExtractionController**: 大纲提取 API
- **OutlineExtractor**: LLM 提取服务
- **Outline ORM Models**: 数据库模型

### 前端组件

- **OutlinePanel**: 大纲列表面板
- **OutlineTreeEditor**: 大纲树编辑器
- **OutlineExtractionConfigPanel**: 提取配置面板
- **OutlineReviewPanel**: 结果审查面板

### LLM 提示词

提示词模板位于 `sail_server/prompts/outline_extraction/v2.yaml`，包含：
- 系统角色定义
- 输出格式规范 (JSON Schema)
- 示例输入输出
- 特殊章节处理说明

## 注意事项

1. **长文本处理**: 长文本会自动分块处理，每块独立调用 LLM，最后合并结果
2. **Token 限制**: 预览模式限制节点数，避免超出 LLM 上下文限制
3. **任务存储**: 任务状态暂时存储在内存中，重启服务器会丢失未保存的任务
4. **数据库关系**: 大纲与版本关联，删除版本会级联删除相关大纲
