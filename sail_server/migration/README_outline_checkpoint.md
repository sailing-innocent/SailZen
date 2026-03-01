# 大纲提取检查点系统迁移指南

## 概述

本文档描述了如何部署新的 Task State - Checkpoint - Resume 体系。

## 迁移步骤

### 1. 执行数据库迁移

```bash
# 连接到 PostgreSQL 数据库
psql -U postgres -d your_database

# 执行迁移脚本
\i sail_server/migration/add_outline_extraction_checkpoints.sql
```

### 2. 验证迁移结果

```sql
-- 检查表是否创建成功
SELECT * FROM information_schema.tables 
WHERE table_name = 'outline_extraction_checkpoints';

-- 检查视图是否创建成功
SELECT * FROM information_schema.views 
WHERE view_name = 'recoverable_outline_tasks';

-- 检查函数是否创建成功
SELECT * FROM information_schema.routines 
WHERE routine_name IN ('update_outline_checkpoint', 'cleanup_old_outline_checkpoints');
```

### 3. 重启服务器

服务器启动时会自动执行恢复逻辑：
- 扫描运行中的大纲提取任务
- 将它们标记为暂停状态
- 等待用户手动恢复

## 新 API 端点

### 创建任务
```http
POST /api/v1/outline-extraction-v2/
Content-Type: application/json

{
  "edition_id": 123,
  "range_selection": {
    "edition_id": 123,
    "mode": "full_edition"
  },
  "config": {
    "granularity": "scene",
    "outline_type": "main",
    "extract_turning_points": true,
    "extract_characters": true
  }
}
```

### 获取任务进度
```http
GET /api/v1/outline-extraction-v2/task/{task_id}
```

### 获取可恢复任务列表
```http
GET /api/v1/outline-extraction-v2/tasks/edition/{edition_id}
```

### 恢复任务
```http
POST /api/v1/outline-extraction-v2/task/{task_id}/resume
```

### 取消任务
```http
POST /api/v1/outline-extraction-v2/task/{task_id}/cancel
```

### 关闭任务
```http
POST /api/v1/outline-extraction-v2/task/{task_id}/dismiss
```

### 获取任务结果
```http
GET /api/v1/outline-extraction-v2/task/{task_id}/result
```

## WebSocket 事件

连接 WebSocket 以接收实时进度更新：

```javascript
const ws = new WebSocket('ws://localhost:1974/api/v1/agent-unified/ws/tasks');

ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  // 处理任务事件
};
```

事件类型：
- `task_created` - 任务创建
- `task_started` - 任务开始
- `task_progress` - 进度更新
- `task_step` - 步骤完成（包含检查点信息）
- `task_completed` - 任务完成
- `task_failed` - 任务失败
- `task_paused` - 任务暂停

## 数据流

```
1. 创建任务
   Client -> POST /outline-extraction-v2/
   Server -> 创建 unified_agent_tasks 记录
   Server -> 创建 outline_extraction_checkpoints 记录
   Server -> 异步执行提取任务

2. 进度更新
   Server -> 更新文件系统检查点
   Server -> 同步更新数据库检查点
   Server -> WebSocket 推送进度事件
   Client -> 接收并显示进度

3. 任务恢复
   Client -> GET /tasks/edition/{id} (获取可恢复任务)
   Client -> POST /task/{id}/resume
   Server -> 从检查点恢复任务
   Server -> 继续执行未完成的批次

4. 服务器重启
   Server -> 启动时扫描运行中任务
   Server -> 标记为暂停状态
   Client -> 页面加载时获取可恢复任务
   Client -> 用户选择恢复任务
```

## 回滚方案

如果需要回滚到旧版本：

```sql
-- 删除新表
DROP TABLE IF EXISTS outline_extraction_checkpoints;

-- 删除视图
DROP VIEW IF EXISTS recoverable_outline_tasks;

-- 删除函数
DROP FUNCTION IF EXISTS update_outline_checkpoint;
DROP FUNCTION IF EXISTS cleanup_old_outline_checkpoints;
```

前端继续使用旧的 API 端点 `/outline-extraction/`。

## 注意事项

1. **数据库兼容性**：新表使用 PostgreSQL 特有的数组类型 `INTEGER[]`
2. **文件系统权限**：确保服务器有权限写入 `.cache/extraction/` 目录
3. **存储空间**：检查点文件可能占用较多磁盘空间，建议定期清理
4. **并发控制**：同一任务同时只能有一个执行实例

## 故障排除

### 任务无法恢复

检查数据库中的任务状态：
```sql
SELECT * FROM recoverable_outline_tasks 
WHERE edition_id = 123;
```

### 检查点未保存

检查文件系统权限：
```bash
ls -la .cache/extraction/
```

### WebSocket 连接失败

检查服务器日志中的 WebSocket 相关错误。

## 性能优化

1. **定期清理**：使用 `cleanup_old_outline_checkpoints(168)` 清理 7 天前的检查点
2. **索引优化**：已为常用查询字段创建索引
3. **批量更新**：使用 `update_outline_checkpoint` 函数进行原子更新
