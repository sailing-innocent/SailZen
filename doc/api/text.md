# 文本管理 API

> **版本**: v1.0 | **更新**: 2026-03-01 | **状态**: 已完成

---

## 📋 功能概述

文本管理模块提供小说等文本内容的导入、章节管理、层级结构组织等功能。

### 核心概念

| 概念 | 说明 |
|------|------|
| **作品 (Work)** | 一部小说或文本作品 |
| **版本 (Edition)** | 作品的特定版本（如精校版、草稿版） |
| **章节节点 (DocumentNode)** | 文本的层级节点，支持无限层级 |

### 层级结构

支持无限层级组织，常见层级示例：

```
作品
└── 版本
    ├── 卷一：起
    │   ├── 第一章：开篇
    │   ├── 第二章：发展
    │   └── ...
    ├── 卷二：承
    │   └── ...
    └── 番外篇
        └── ...
```

---

## 📚 作品 API

### 获取作品列表

```http
GET /api/v1/text/work
```

**参数:**
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| skip | int | 否 | 跳过记录数（默认 0） |
| limit | int | 否 | 返回记录数（默认 20） |

**响应:**
```json
[
  {
    "id": 1,
    "title": "示例小说",
    "author": "作者名",
    "description": "作品简介",
    "htime": 1700000000
  }
]
```

---

### 搜索作品

```http
GET /api/v1/text/work/search?keyword=搜索词
```

**参数:**
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| keyword | string | 是 | 搜索关键词 |
| skip | int | 否 | 跳过记录数 |
| limit | int | 否 | 返回记录数 |

---

### 获取单个作品

```http
GET /api/v1/text/work/{work_id}
```

**响应:**
```json
{
  "id": 1,
  "title": "示例小说",
  "author": "作者名",
  "description": "作品简介",
  "htime": 1700000000
}
```

---

### 创建作品

```http
POST /api/v1/text/work/
```

**请求体:**
```json
{
  "title": "新作品",
  "author": "作者名",
  "description": "作品简介（可选）"
}
```

---

### 更新作品

```http
PUT /api/v1/text/work/{work_id}
```

**请求体:** 同创建

---

### 删除作品

```http
DELETE /api/v1/text/work/{work_id}
```

---

## 📖 版本 API

### 获取版本详情

```http
GET /api/v1/text/edition/{edition_id}
```

**响应:**
```json
{
  "id": 1,
  "work_id": 1,
  "name": "精校版",
  "description": "精校版本说明",
  "htime": 1700000000
}
```

---

### 获取作品的版本列表

```http
GET /api/v1/text/edition/work/{work_id}
```

---

### 创建版本

```http
POST /api/v1/text/edition/
```

**请求体:**
```json
{
  "work_id": 1,
  "name": "草稿版",
  "description": "初始草稿"
}
```

---

### 更新版本

```http
PUT /api/v1/text/edition/{edition_id}
```

---

### 删除版本

```http
DELETE /api/v1/text/edition/{edition_id}
```

---

### 获取章节列表

```http
GET /api/v1/text/edition/{edition_id}/chapters
```

**响应:**
```json
[
  {
    "id": 1,
    "title": "第一章",
    "level": 1,
    "parent_id": null,
    "index": 0,
    "word_count": 3000
  }
]
```

---

### 获取章节内容

```http
GET /api/v1/text/edition/{edition_id}/chapter/{chapter_index}
```

**响应:**
```json
{
  "id": 1,
  "title": "第一章",
  "content": "章节正文内容...",
  "level": 1,
  "parent_id": null,
  "index": 0,
  "word_count": 3000
}
```

---

### 搜索内容

```http
GET /api/v1/text/edition/{edition_id}/search?keyword=关键词
```

**参数:**
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| keyword | string | 是 | 搜索关键词 |
| skip | int | 否 | 跳过结果数 |
| limit | int | 否 | 返回结果数（默认 50） |

---

### 插入章节

```http
POST /api/v1/text/edition/{edition_id}/chapter/insert
```

在指定位置插入新章节。

**请求体:**
```json
{
  "title": "插入章节",
  "content": "章节内容",
  "level": 1,
  "parent_id": null,
  "insert_index": 5  // 插入位置
}
```

---

## 📝 章节节点 API

### 获取节点详情

```http
GET /api/v1/text/node/{node_id}?include_content=true
```

**参数:**
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| include_content | bool | 否 | 是否包含正文内容（默认 true） |

---

### 更新节点

```http
PUT /api/v1/text/node/{node_id}
```

**请求体:**
```json
{
  "title": "新标题",
  "content": "新内容",
  "level": 1,
  "parent_id": null
}
```

---

## 📥 导入 API

### 导入文本

```http
POST /api/v1/text/import/
```

导入新作品（创建作品+版本+章节）。

**请求体:**
```json
{
  "title": "作品标题",
  "author": "作者",
  "edition_name": "精校版",
  "content": "全文内容",
  "chapter_pattern": "第[一二三四五六七八九十百零\\d]+章"  // 章节匹配正则（可选）
}
```

**响应:**
```json
{
  "work_id": 1,
  "edition_id": 1,
  "nodes_created": 100,
  "message": "Successfully imported"
}
```

---

### 追加章节

```http
POST /api/v1/text/import/append/{edition_id}
```

向已有版本追加新章节。

**请求体:** (Content-Type: application/x-www-form-urlencoded)
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| content | string | 是 | 追加的文本内容 |
| chapter_pattern | string | 否 | 章节匹配正则 |

**响应:**
```json
{
  "nodes_created": 10,
  "total_nodes": 110
}
```

---

## 🖥️ 前端 API 客户端

### 导入

```typescript
import {
  // 作品
  api_get_works,
  api_search_works,
  api_get_work,
  api_create_work,
  api_update_work,
  api_delete_work,
  
  // 版本
  api_get_edition,
  api_get_editions_by_work,
  api_create_edition,
  api_update_edition,
  api_delete_edition,
  api_get_chapter_list,
  api_get_chapter_content,
  api_search_content,
  
  // 节点
  api_get_node,
  api_update_node,
  
  // 导入
  api_import_text,
  api_append_chapters,
  api_insert_chapter,
} from '@lib/api/text'
```

### 使用示例

```typescript
// 获取作品列表
const works = await api_get_works(0, 20)

// 搜索作品
const results = await api_search_works('修仙', 0, 10)

// 创建新作品
const work = await api_create_work({
  title: '我的修仙路',
  author: '作者名',
  description: '一本修仙小说'
})

// 创建版本
const edition = await api_create_edition({
  work_id: work.id,
  name: '精校版',
  description: '精校版本'
})

// 导入文本（AI自动分章）
const importResult = await api_import_text({
  title: '我的修仙路',
  author: '作者名',
  edition_name: '精校版',
  content: fullTextContent  // 完整文本
})
console.log(`导入了 ${importResult.nodes_created} 个章节`)

// 获取章节列表
const chapters = await api_get_chapter_list(edition.id)

// 获取特定章节内容
const chapter = await api_get_chapter_content(edition.id, 0)
console.log(chapter.title)
console.log(chapter.content)

// 搜索内容
const searchResults = await api_search_content(edition.id, '关键词', 0, 20)

// 追加新章节
const appendResult = await api_append_chapters(
  edition.id,
  newChaptersContent
)

// 在指定位置插入章节
const insertResult = await api_insert_chapter(edition.id, {
  title: '插章',
  content: '插章内容',
  level: 1,
  insert_index: 5
})

// 更新章节
await api_update_node(chapterId, {
  title: '新标题',
  content: '新内容'
})
```

---

## 📦 数据类型

### Work

```typescript
interface Work {
  id: number
  title: string
  author: string
  description?: string
  htime: number
}

type WorkCreate = Omit<Work, 'id' | 'htime'>
```

### Edition

```typescript
interface Edition {
  id: number
  work_id: number
  name: string
  description?: string
  htime: number
}

type EditionCreate = Omit<Edition, 'id' | 'htime'>
```

### DocumentNode

```typescript
interface DocumentNode {
  id: number
  edition_id: number
  title: string
  content?: string
  level: number       // 层级深度（1开始）
  parent_id?: number  // 父节点ID
  index: number       // 同级排序索引
  word_count: number
  htime: number
}

type DocumentNodeUpdate = Partial<Pick<DocumentNode, 'title' | 'content' | 'level' | 'parent_id'>>
```

### ChapterListItem

```typescript
interface ChapterListItem {
  id: number
  title: string
  level: number
  parent_id?: number
  index: number
  word_count: number
}
```

### TextImportRequest

```typescript
interface TextImportRequest {
  title: string
  author: string
  edition_name: string
  content: string
  chapter_pattern?: string  // 自定义章节匹配正则
}
```

### ImportResponse

```typescript
interface ImportResponse {
  work_id: number
  edition_id: number
  nodes_created: number
  message: string
}
```

### AppendResponse

```typescript
interface AppendResponse {
  nodes_created: number
  total_nodes: number
}
```

### ChapterInsertRequest

```typescript
interface ChapterInsertRequest {
  edition_id: number
  title: string
  content: string
  level: number
  parent_id?: number
  insert_index: number
}
```

### ChapterInsertResponse

```typescript
interface ChapterInsertResponse {
  node_id: number
  index: number
  message: string
}
```

---

## 🤖 AI 辅助导入

项目提供 AI 驱动的智能文本导入功能，位于 `.agents/skills/sailzen-ai-text-import/`。

### 功能特点

- 智能章节识别（支持各种格式）
- 自动识别特殊章节（楔子、番外等）
- 过滤广告噪音
- 异常章节检测
- 人机确认界面

### 使用方式

```bash
# AI 文本导入
uv run python .agents/skills/sailzen-ai-text-import/scripts/import_with_ai.py \
  novel.txt --title "作品标题" --author "作者名" --preview
```

---

*本文档由 AI Agent 维护，如有疑问请参考源代码或联系开发团队。*
