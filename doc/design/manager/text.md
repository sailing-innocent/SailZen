# 文本管理设计

## 核心模型

| 模型 | 说明 | 关键字段 |
|------|------|----------|
| Work | 作品 | title, author |
| Edition | 版本 | work_id, name |
| DocumentNode | 章节 | edition_id, title, level, parent_id, word_count |

## 层级结构

支持无限层级：卷 > 部 > 章 > 节

## API 概览

```
GET  /api/v1/text/work/              # 作品列表
GET  /api/v1/text/edition/           # 版本列表
GET  /api/v1/text/node/              # 章节列表
GET  /api/v1/text/node/{id}/content  # 获取内容
POST /api/v1/text/import             # 文本导入
```

## AI 分析

```
GET  /api/v1/analysis/task/          # 分析任务列表
POST /api/v1/analysis/task/          # 创建分析任务
POST /api/v1/analysis/execute/{id}   # 执行任务
GET  /api/v1/analysis/character/     # 人物列表
GET  /api/v1/analysis/setting/       # 设定列表
GET  /api/v1/analysis/outline/       # 大纲列表
```

## 任务类型

- outline_extraction: 大纲提取
- character_detection: 人物识别
- setting_extraction: 设定提取
