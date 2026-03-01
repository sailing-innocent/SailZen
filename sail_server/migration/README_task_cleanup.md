# 任务表清理指南

## 概述

在调试过程中，可能会出现任务状态异常（如中断导致的运行中任务、失败任务等）。本指南提供安全清理这些异常数据的方法。

## 清理脚本

### 1. 完全重置（谨慎使用）

**文件**: `reset_task_tables.sql`

**作用**: 清空所有任务相关表，重置序列

**适用场景**: 
- 需要完全重新开始测试
- 数据库状态严重混乱

**使用方法**:
```bash
# 使用 psql 直接执行
psql -d your_database -f sail_server/migration/reset_task_tables.sql

# 或使用 PowerShell 脚本
.\scripts\reset_tasks.ps1 -Mode full
```

**警告**: 此操作会删除所有任务数据，不可恢复！

---

### 2. 清理异常任务（推荐）

**文件**: `cleanup_abnormal_tasks.sql`

**作用**: 只清理状态异常的任务，保留正常任务

**清理范围**:
- `failed` - 失败的任务
- `cancelled` - 已取消的任务
- `running` 但超过 30 分钟未更新 - 可能已中断的任务
- 状态值异常的任务

**保留的任务**:
- `pending` - 等待中的任务
- `scheduled` - 已调度的任务
- `running` 且活跃的任务
- `paused` - 已暂停的任务
- `completed` - 已完成的任务

**使用方法**:
```bash
# 使用 psql 直接执行
psql -d your_database -f sail_server/migration/cleanup_abnormal_tasks.sql

# 或使用 PowerShell 脚本（推荐）
.\scripts\reset_tasks.ps1 -Mode cleanup
```

---

### 3. 预览模式（Dry Run）

**作用**: 查看将要清理的内容，不实际执行清理

**使用方法**:
```powershell
.\scripts\reset_tasks.ps1 -Mode dryrun
```

---

## PowerShell 脚本使用

### 前置要求

1. 安装 PostgreSQL 客户端 (`psql`)
2. 配置 `.env.dev` 文件中的 `POSTGRE_URI`

### 使用示例

```powershell
# 进入脚本目录
cd scripts

# 预览将要清理的内容
.\reset_tasks.ps1 -Mode dryrun

# 清理异常任务（推荐）
.\reset_tasks.ps1 -Mode cleanup

# 完全重置（谨慎！）
.\reset_tasks.ps1 -Mode full
```

---

## 手动执行 SQL

### 查看当前任务状态

```sql
SELECT 
    status, 
    COUNT(*) AS task_count,
    MAX(updated_at) AS last_update
FROM unified_agent_tasks
WHERE task_type = 'novel_analysis'
  AND sub_type = 'outline_extraction'
GROUP BY status
ORDER BY task_count DESC;
```

### 查看运行中但可能中断的任务

```sql
SELECT 
    id,
    status,
    current_phase,
    updated_at,
    EXTRACT(EPOCH FROM (CURRENT_TIMESTAMP - updated_at))/60 AS idle_minutes
FROM unified_agent_tasks
WHERE status = 'running'
  AND updated_at < CURRENT_TIMESTAMP - INTERVAL '30 minutes';
```

### 手动重置单个任务

```sql
-- 将卡住的运行中任务标记为失败
UPDATE unified_agent_tasks 
SET status = 'failed',
    error_message = 'Manually marked as failed due to stuck state',
    updated_at = CURRENT_TIMESTAMP
WHERE id = YOUR_TASK_ID;
```

---

## 清理文件系统检查点

数据库清理后，还需要手动删除文件系统上的检查点文件：

```powershell
# 删除检查点文件
Remove-Item -Path ".cache\extraction\*.json" -Force

# 或保留最近 7 天的文件
Get-ChildItem -Path ".cache\extraction" -Filter "*.json" | 
    Where-Object { $_.LastWriteTime -lt (Get-Date).AddDays(-7) } |
    Remove-Item -Force
```

---

## 注意事项

1. **备份重要数据**: 在执行清理前，确保已完成的任务结果已保存
2. **先预览再清理**: 使用 `dryrun` 模式预览将要清理的内容
3. **检查文件系统**: 数据库清理后，记得清理 `.cache/extraction/` 目录
4. **重启服务**: 清理后建议重启后端服务，确保状态一致

---

## 常见问题

### Q: 清理后任务 ID 会从 1 开始吗？
A: `full` 模式会重置序列，`cleanup` 模式不会。

### Q: 可以恢复已清理的任务吗？
A: 不可以，清理操作是不可逆的。重要数据请先备份。

### Q: 为什么需要清理文件系统检查点？
A: 检查点文件存储在 `.cache/extraction/` 目录，数据库清理后这些文件成为孤儿文件，需要手动清理。
