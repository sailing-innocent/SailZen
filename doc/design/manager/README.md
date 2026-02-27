# 模块设计文档

## 模块概览

| 模块 | 文档 | 状态 | 说明 |
|------|------|------|------|
| 财务管理 | [life_budget.md](./life_budget.md) | ✅ | 账户、交易、预算 |
| 项目管理 | [project.md](./project.md) | ✅ | 项目、任务管理 |
| 健康管理 | [health.md](./health.md) | 🔶 | 体重、健身追踪 |
| 物资管理 | [necessity.md](./necessity.md) | ✅ | 库存、住所管理 |
| 文本管理 | [text.md](./text.md) | ✅ | 作品、章节管理 |

## 状态说明

- ✅ 已实现：核心功能可用
- 🔶 部分实现：基础功能完成
- 📋 设计阶段

## 通用架构

所有模块遵循相同的分层架构：

```
Frontend (React + Zustand)
    ↓
API Client (TypeScript)
    ↓
Backend Router (Litestar)
    ↓
Controller (业务逻辑)
    ↓
Data/Model (SQLAlchemy)
    ↓
PostgreSQL
```
