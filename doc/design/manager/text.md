# 文本管理设计

## 核心模型

| 模型 | 说明 | 关键字段 |
|------|------|----------|
| Work | 作品 | title, author |
| Edition | 版本 | work_id, name |
| DocumentNode | 章节 | edition_id, title, level, parent_id, word_count |
| NoteItem | 笔记索引 | category, setting_file, work_id, edition_id, title, slug |

## 设计原则

**Notes are notes. Databases are databases.**

- `DocumentNode` 保留为文本的结构化骨架（作品 > 版本 > 章节）。
- 人物、设定、地理、大纲、剧情片段、历史事件、人物档案等**非结构化创作素材**统一作为 Markdown 笔记管理。
- 数据库中只保留轻量级 `note_items` 索引，实际内容由 `workspace/notes/text/<category>/<slug>.md` 承载。
- LLM 负责生成、解析、关联 Markdown 内容；CLI / 后端负责文件与索引的同步。

## 层级结构

### 文本层级

支持无限层级：卷 > 部 > 章 > 节

### 笔记目录约定

```
workspace/
├── notes/
│   └── text/                    # 文本/创作相关笔记
│       ├── characters/          # 人物
│       ├── settings/            # 设定
│       ├── geography/           # 地理
│       ├── outlines/            # 大纲
│       ├── plots/               # 剧情片段
│       ├── history/             # 历史事件
│       └── persons/             # 人物档案（现实/历史）
```

## API 概览

### 文本

```
GET  /api/v1/text/work/              # 作品列表
GET  /api/v1/text/edition/           # 版本列表
GET  /api/v1/text/node/              # 章节列表
GET  /api/v1/text/node/{id}/content  # 获取内容
POST /api/v1/text/import             # 文本导入
```

### 笔记 (NoteItem)

```
GET    /api/v1/text/note/                  # 列表（支持 ?category=&work_id=&edition_id=）
POST   /api/v1/text/note/                  # 创建
GET    /api/v1/text/note/{id}              # 获取索引
PUT    /api/v1/text/note/{id}              # 更新索引
DELETE /api/v1/text/note/{id}              # 删除索引
GET    /api/v1/text/note/{id}/content      # 获取 Markdown 原始内容
PUT    /api/v1/text/note/{id}/content      # 更新 Markdown 原始内容
GET    /api/v1/text/note/links             # 获取双向链接图谱
```

## AI 分析

### DAG 节点

```
GET  /api/v1/analysis/task/          # 分析任务列表
POST /api/v1/analysis/task/          # 创建分析任务
POST /api/v1/analysis/execute/{id}   # 执行任务
```

### 分析产物

AI 分析完成后，结果不再存入结构化 `Character` / `Setting` / `Outline` 表，而是通过 `note_sync` DAG 节点保存为 Markdown 笔记：

```
workspace/notes/text/characters/<slug>.md
workspace/notes/text/settings/<slug>.md
workspace/notes/text/geography/<slug>.md
workspace/notes/text/outlines/<slug>.md
workspace/notes/text/plots/<slug>.md
```

每个笔记的 frontmatter 中包含 `work` / `edition` / `tags` / `related` 等字段，正文中保留指向原文 `DocumentNode` 的 `[[...]]` 双向链接作为证据。

### 任务类型

- outline_extraction: 大纲提取 → `notes/text/outlines/*.md`
- character_detection: 人物识别 → `notes/text/characters/*.md`
- setting_extraction: 设定提取 → `notes/text/settings/*.md`
- geography_extraction: 地理识别 → `notes/text/geography/*.md`
- plot_extraction: 剧情片段 → `notes/text/plots/*.md`

## CLI

```bash
sailzen note list --category character
sailzen note pull --id 42 --workspace ./workspace
sailzen note push notes/text/ --workspace ./workspace
sailzen note create --category character --title "Alice" --work 1
sailzen note sync --workspace ./workspace
sailzen note links --json
```

## 历史/人物迁移

旧 `HistoryEvent` / `Person` 结构化表已废弃，数据迁移到：

- `HistoryEvent` → `note_items` (category='history') + `notes/text/history/*.md`
- `Person` → `note_items` (category='person') + `notes/text/persons/*.md`

迁移脚本：`scripts/migrate_history_to_notes.py`
