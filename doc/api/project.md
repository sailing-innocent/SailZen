# 项目管理 API

> **版本**: v1.0 | **更新**: 2026-03-01 | **状态**: 已完成

---

## 📋 功能概述

项目管理模块提供项目和任务管理功能，支持看板式任务状态流转。

### 核心概念

| 概念 | 说明 |
|------|------|
| **项目 (Project)** | 一个独立的工程或目标 |
| **任务 (Mission)** | 项目下的具体可执行任务 |

### 任务状态流转

```
PENDING (待处理) → READY (就绪) → DOING (进行中) → DONE (已完成)
                      ↓
                   CANCELED (已取消)
```

| 状态 | 说明 |
|------|------|
| `PENDING` | 待处理，尚未准备就绪 |
| `READY` | 就绪，可以开始执行 |
| `DOING` | 进行中 |
| `DONE` | 已完成 |
| `CANCELED` | 已取消 |

---

## 📁 项目 API

### 获取项目列表

```http
GET /api/v1/project/project
```

**参数:**
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| skip | int | 否 | 跳过记录数（默认 0） |
| limit | int | 否 | 返回记录数（默认 -1） |

**响应:**
```json
[
  {
    "id": 1,
    "name": "项目A",
    "description": "项目描述",
    "deadline": 1700000000,
    "state": "active",
    "created_at": 1700000000
  }
]
```

---

### 获取单个项目

```http
GET /api/v1/project/project/{project_id}
```

---

### 创建项目

```http
POST /api/v1/project/project/
```

**请求体:**
```json
{
  "name": "新项目",
  "description": "项目描述",
  "deadline": 1700000000  // 截止时间（可选）
}
```

---

### 更新项目

```http
PUT /api/v1/project/project/{project_id}
```

**请求体:** 同创建

---

### 删除项目

```http
DELETE /api/v1/project/project/{project_id}
```

**响应:**
```json
{
  "id": 1,
  "status": "success",
  "message": "Project deleted"
}
```

---

## ✅ 任务 API

### 获取任务列表

```http
GET /api/v1/project/mission
```

**参数:**
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| skip | int | 否 | 跳过记录数 |
| limit | int | 否 | 返回记录数 |
| project_id | int | 否 | 按项目筛选 |
| parent_id | int | 否 | 按父任务筛选（子任务） |

**响应:**
```json
[
  {
    "id": 1,
    "project_id": 1,
    "parent_id": null,
    "name": "任务1",
    "description": "任务描述",
    "deadline": 1700000000,
    "state": "DOING",
    "priority": 1,
    "created_at": 1700000000
  }
]
```

---

### 获取单个任务

```http
GET /api/v1/project/mission/{mission_id}
```

---

### 创建任务

```http
POST /api/v1/project/mission/
```

**请求体:**
```json
{
  "project_id": 1,
  "parent_id": null,        // 父任务ID（可选，用于子任务）
  "name": "新任务",
  "description": "任务描述",
  "deadline": 1700000000,   // 截止时间（可选）
  "priority": 1             // 优先级（1-5，1最高）
}
```

---

### 更新任务

```http
PUT /api/v1/project/mission/{mission_id}
```

---

### 删除任务

```http
DELETE /api/v1/project/mission/{mission_id}
```

---

## 🔄 任务状态流转 API

### 设为待处理

```http
POST /api/v1/project/mission/{mission_id}/pending
```

---

### 设为就绪

```http
POST /api/v1/project/mission/{mission_id}/ready
```

---

### 设为进行中

```http
POST /api/v1/project/mission/{mission_id}/doing
```

---

### 设为已完成

```http
POST /api/v1/project/mission/{mission_id}/done
```

---

### 设为已取消

```http
POST /api/v1/project/mission/{mission_id}/cancel
```

---

### 延期任务

```http
POST /api/v1/project/mission/{mission_id}/postpone?days=7
```

**参数:**
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| days | int | 否 | 延期天数（默认 7） |

---

## ⏰ 提醒 API

### 获取即将到期的任务

```http
GET /api/v1/project/mission/upcoming?hours=24
```

**参数:**
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| hours | int | 否 | 时间范围（默认 24 小时） |

---

### 获取已逾期的任务

```http
GET /api/v1/project/mission/overdue
```

返回已过期但未完成/未取消的任务。

---

## 🖥️ 前端 API 客户端

### 导入

```typescript
import {
  // 项目
  api_get_projects,
  api_get_project,
  api_create_project,
  api_update_project,
  api_delete_project,
  
  // 任务
  api_get_missions,
  api_get_mission,
  api_create_mission,
  api_update_mission,
  api_delete_mission,
  
  // 状态流转
  api_pending_mission,
  api_ready_mission,
  api_doing_mission,
  api_done_mission,
  api_cancel_mission,
  api_postpone_mission,
  
  // 提醒
  api_get_upcoming_missions,
  api_get_overdue_missions,
} from '@lib/api/project'
```

### 使用示例

```typescript
// 创建项目
const project = await api_create_project({
  name: '开发新功能',
  description: '开发用户反馈的新功能',
  deadline: Date.now() / 1000 + 30 * 24 * 3600  // 30天后
})

// 获取所有项目
const projects = await api_get_projects()

// 创建任务
const mission = await api_create_mission({
  project_id: project.id,
  name: '需求分析',
  description: '分析用户需求',
  deadline: Date.now() / 1000 + 7 * 24 * 3600,  // 7天后
  priority: 1
})

// 任务状态流转
await api_ready_mission(mission.id)   // 设为就绪
await api_doing_mission(mission.id)   // 开始执行
await api_done_mission(mission.id)    // 完成

// 获取项目的所有任务
const missions = await api_get_missions(project.id)

// 创建子任务
const subMission = await api_create_mission({
  project_id: project.id,
  parent_id: mission.id,  // 父任务ID
  name: '子任务',
  priority: 2
})

// 延期任务
await api_postpone_mission(mission.id, 3)  // 延期3天

// 获取即将到期的任务（24小时内）
const upcoming = await api_get_upcoming_missions(24)

// 获取已逾期的任务
const overdue = await api_get_overdue_missions()
```

---

## 📦 数据类型

### ProjectData

```typescript
interface ProjectData {
  id: number
  name: string
  description?: string
  deadline?: number    // Unix 时间戳
  state: string        // active, archived
  created_at: number
}

type ProjectCreateProps = Omit<ProjectData, 'id' | 'created_at'>
```

### MissionData

```typescript
interface MissionData {
  id: number
  project_id: number
  parent_id?: number   // 父任务ID（子任务）
  name: string
  description?: string
  deadline?: number
  state: 'PENDING' | 'READY' | 'DOING' | 'DONE' | 'CANCELED'
  priority: number     // 1-5
  created_at: number
}

type MissionCreateProps = Omit<MissionData, 'id' | 'created_at'>
```

---

*本文档由 AI Agent 维护，如有疑问请参考源代码或联系开发团队。*
