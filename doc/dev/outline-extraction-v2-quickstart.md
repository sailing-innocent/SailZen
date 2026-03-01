# 大纲提取 V2 快速参考

## 一键升级命令

```bash
# 1. 执行数据库迁移
psql -U postgres -d sailzen -f sail_server/migration/add_outline_extraction_checkpoints.sql

# 2. 重启服务器
uv run server.py

# 3. 构建前端
pnpm run build-site
```

## 用户操作

### 正常使用

1. 打开 **分析 > 大纲分析**
2. 点击 **AI 大纲提取**
3. 配置参数，点击 **开始提取**
4. 等待完成，查看结果

### 任务恢复

如果页面刷新或服务器重启：

1. 重新打开 **大纲分析**
2. 自动弹出 **恢复对话框**
3. 点击 **恢复** 继续之前的任务

## 开发者 API

### 创建任务

```bash
curl -X POST http://localhost:1974/api/v1/outline-extraction-v2/ \
  -H "Content-Type: application/json" \
  -d '{
    "edition_id": 123,
    "range_selection": {"edition_id": 123, "mode": "full_edition"},
    "config": {
      "granularity": "scene",
      "outline_type": "main",
      "extract_turning_points": true,
      "extract_characters": true
    }
  }'
```

### 获取进度

```bash
curl http://localhost:1974/api/v1/outline-extraction-v2/task/456
```

### 恢复任务

```bash
curl -X POST http://localhost:1974/api/v1/outline-extraction-v2/task/456/resume
```

## 数据库查询

### 查看可恢复任务

```sql
SELECT * FROM recoverable_outline_tasks 
WHERE edition_id = 123;
```

### 查看任务检查点

```sql
SELECT * FROM outline_extraction_checkpoints 
WHERE task_id = 456;
```

### 清理旧检查点

```sql
-- 清理 7 天前的已完成检查点
SELECT cleanup_old_outline_checkpoints(168);
```

## 故障排查

### 任务无法恢复

```sql
-- 检查任务状态
SELECT id, status, progress, current_phase 
FROM unified_agent_tasks 
WHERE id = 456;

-- 检查检查点
SELECT phase, progress_percent, checkpoint_file_path 
FROM outline_extraction_checkpoints 
WHERE task_id = 456;
```

### 检查点文件缺失

```bash
# 检查文件系统
ls -la .cache/extraction/

# 检查权限
touch .cache/extraction/test && rm .cache/extraction/test
```

### WebSocket 不工作

```bash
# 检查服务器日志
grep -i websocket logs/sailzen.log

# 测试 WebSocket 连接
wscat -c ws://localhost:1974/api/v1/agent-unified/ws/tasks
```

## 文件位置

| 组件 | 路径 |
|------|------|
| 数据库迁移 | `sail_server/migration/add_outline_extraction_checkpoints.sql` |
| 后端控制器 | `sail_server/controller/outline_extraction_unified.py` |
| 检查点管理器 | `sail_server/service/persistent_checkpoint.py` |
| 任务注册表 | `sail_server/service/outline_task_registry.py` |
| 前端 API | `packages/site/src/lib/api/outlineExtraction.ts` |
| 前端组件 | `packages/site/src/components/analysis/outline_extraction_panel.tsx` |
| 设计文档 | `doc/design/outline-extraction-v2.md` |

## 环境变量

```bash
# 检查点存储路径（可选，默认 .cache/extraction/）
export EXTRACTION_CACHE_DIR=/path/to/cache

# 清理间隔（小时，默认 168 = 7天）
export CHECKPOINT_CLEANUP_HOURS=168
```

## 相关文档

- [完整设计文档](../design/outline-extraction-v2.md)
- [数据库迁移指南](../../sail_server/migration/README_outline_checkpoint.md)
- [原 V1 文档](../design/outline-extraction.md)
