# SailZen API 文档中心

> **版本**: v1.0 | **更新**: 2026-03-01 | **状态**: 已完成

---

## 📚 API 概览

SailZen 提供 RESTful API 供前端调用，所有 API 都以 `/api/v1` 为前缀。

### 基础信息

| 项目 | 说明 |
|------|------|
| 基础 URL | `http://<server>:<port>/api/v1` |
| 数据格式 | JSON |
| 认证方式 | 暂无需认证（内部使用） |
| 时间格式 | Unix 时间戳（秒） |

### 模块列表

| 模块 | 路径前缀 | 说明 | 文档 |
|------|----------|------|------|
| 财务管理 | `/finance` | 账户、交易、预算 | [finance.md](./finance.md) |
| 健康管理 | `/health` | 体重、运动、计划 | [health.md](./health.md) |
| 文本管理 | `/text` | 作品、版本、章节 | [text.md](./text.md) |
| AI 分析 | `/analysis` | 大纲提取、人物识别、设定提取 | [analysis.md](./analysis.md) |
| 项目管理 | `/project` | 任务、看板 | [project.md](./project.md) |
| 物资管理 | `/necessity` | 库存、住所、行程 | [necessity.md](./necessity.md) |

---

## 🔧 通用规范

### 请求格式

```json
{
  "field_name": "value"
}
```

### 响应格式

**成功响应:**
```json
{
  "id": 1,
  "name": "示例",
  "created_at": 1700000000
}
```

**错误响应:**
```json
{
  "detail": "错误描述信息"
}
```

### HTTP 状态码

| 状态码 | 含义 |
|--------|------|
| 200 | 请求成功 |
| 201 | 创建成功 |
| 400 | 请求参数错误 |
| 404 | 资源不存在 |
| 500 | 服务器内部错误 |

### 分页参数

支持分页的列表接口通用参数：

| 参数 | 类型 | 说明 |
|------|------|------|
| `skip` | int | 跳过记录数（默认 0） |
| `limit` | int | 返回记录数（默认 -1 表示无限制） |
| `page` | int | 页码（1-based，分页查询用） |
| `page_size` | int | 每页大小（默认 20，最大 100） |

---

## 📦 前端 API 客户端

前端使用 TypeScript 封装了 API 调用，位于 `packages/site/src/lib/api/` 目录。

### 使用示例

```typescript
import { api_get_accounts, api_create_transaction } from '@lib/api/money'
import { api_get_weights, api_create_weight } from '@lib/api/health'
import { api_get_works, api_import_text } from '@lib/api/text'

// 获取账户列表
const accounts = await api_get_accounts()

// 创建交易
const transaction = await api_create_transaction({
  from_acc_id: 1,
  to_acc_id: -1,  // -1 表示支出
  value: '100.00',
  description: '超市购物'
})
```

### API 客户端列表

| 文件 | 模块 | 主要功能 |
|------|------|----------|
| `money.ts` | 财务管理 | 账户、交易、预算操作 |
| `health.ts` | 健康管理 | 体重记录、运动记录、计划管理 |
| `text.ts` | 文本管理 | 作品管理、章节导入、内容获取 |
| `analysis.ts` | AI 分析 | 分析任务、人物、设定、大纲 |
| `project.ts` | 项目管理 | 任务、看板操作 |
| `necessity.ts` | 物资管理 | 库存、住所、行程 |

---

## 🔌 配置

API 配置位于 `packages/site/src/lib/api/config.ts`：

```typescript
export const SERVER_URL = process.env.SERVER_URL  // 后端服务器地址
export const API_BASE = 'api/v1'                   // API 版本前缀
```

开发环境下，可通过 `.env` 文件配置：

```
SERVER_URL=http://localhost:8000
```

---

## 📖 详细文档

- [财务管理 API](./finance.md)
- [健康管理 API](./health.md)
- [文本管理 API](./text.md)
- [AI 分析 API](./analysis.md)
- [项目管理 API](./project.md)
- [物资管理 API](./necessity.md)

---

*本文档由 AI Agent 维护，如有疑问请参考源代码或联系开发团队。*
