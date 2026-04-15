# 大纲提取功能 V2 - Task State Checkpoint Resume 体系

## 概述

大纲提取功能 V2 是 V1 的升级版，引入了完整的 **Task State - Checkpoint - Resume** 体系，解决了 V1 中任务状态无法持久化、服务器重启后任务丢失的问题。

## 与 V1 的主要区别

| 特性 | V1 (旧版) | V2 (新版) |
|------|-----------|-----------|
| **任务存储** | 内存 + JSON 文件 | PostgreSQL 数据库 |
| **进度获取** | HTTP 轮询 (2秒间隔) | WebSocket 实时推送 |
| **服务器重启** | 任务丢失 | 自动恢复为暂停状态 |
| **检查点** | 仅文件系统 | 文件系统 + 数据库双写 |
| **任务恢复** | 部分支持 | 完整的恢复对话框 |
| **API 路径** | `/outline-extraction/` | `/outline-extraction-v2/` |

## 无缝升级指南

### 用户视角

作为用户，您**无需任何操作**即可享受升级：

1. **前端界面保持不变** - 同样的操作流程
2. **自动检测可恢复任务** - 页面加载时自动提示
3. **一键恢复** - 点击即可从上次进度继续

### 开发者视角

#### 1. 执行数据库迁移

```bash
# 方式一：使用 psql
psql -U postgres -d your_database -f sail_server/migration/add_outline_extraction_checkpoints.sql

# 方式二：使用项目脚本
uv run python -c "
from sail_server.db import get_db_session
from sail_server.utils.db_utils import run_migration
with get_db_session() as db:
    run_migration(db, 'add_outline_extraction_checkpoints.sql')
"
```

#### 2. 重启服务器

```bash
# 开发模式
uv run server.py --dev

# 生产模式
uv run server.py
```

服务器启动时会自动：
- 扫描运行中的任务
- 将它们标记为暂停状态
- 记录恢复事件

#### 3. 前端自动适配

前端代码已经更新，会自动：
- 检测可恢复任务
- 显示恢复对话框
- 使用新的 API 端点

## 架构设计

### 数据流

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              用户操作流程                                     │
└─────────────────────────────────────────────────────────────────────────────┘

1. 创建提取任务
   ┌─────────┐    POST /outline-extraction-v2/    ┌─────────────────────────┐
   │  用户   │ ──────────────────────────────────► │  Unified Agent Task     │
   │  点击   │                                     │  (unified_agent_tasks)  │
   │ "开始"  │ ◄────────────────────────────────── │  状态: pending          │
   └─────────┘    返回 task_id                     └─────────────────────────┘
                            │
                            ▼ 异步执行
                     ┌─────────────────┐
                     │ OutlineExtractor │
                     │  分批处理文本    │
                     └─────────────────┘

2. 实时进度 (WebSocket)
   ┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
   │   WebSocket     │────►│  前端进度条      │────►│  检查点可视化    │
   │  task_progress  │     │  实时更新        │     │  批次/节点统计   │
   └─────────────────┘     └─────────────────┘     └─────────────────┘

3. 页面刷新/服务器重启
   ┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
   │  localStorage   │────►│  查询数据库      │────►│  显示恢复对话框  │
   │  读取 task_id   │     │  获取检查点      │     │  用户一键恢复    │
   └─────────────────┘     └─────────────────┘     └─────────────────┘
```

### 存储架构

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              双写存储架构                                     │
└─────────────────────────────────────────────────────────────────────────────┘

                    ┌─────────────────────────┐
                    │   大纲提取任务状态        │
                    └───────────┬─────────────┘
                                │
            ┌───────────────────┼───────────────────┐
            │                   │                   │
            ▼                   ▼                   ▼
   ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐
   │  PostgreSQL     │  │  PostgreSQL     │  │  File System    │
   │  unified_agent_ │  │  outline_       │  │  .cache/        │
   │  tasks          │  │  extraction_    │  │  extraction/    │
   │                 │  │  checkpoints    │  │  {task_id}.json │
   │  - 任务元数据    │  │                 │  │                 │
   │  - 状态/进度     │  │  - 检查点元数据  │  │  - 完整批次结果  │
   │  - 配置信息      │  │  - 批次进度     │  │  - 节点详细数据  │
   │  - 结果摘要      │  │  - 文件路径引用  │  │  - 证据/转折点   │
   └─────────────────┘  └─────────────────┘  └─────────────────┘
            │                   │                   │
            └───────────────────┴───────────────────┘
                                │
                                ▼
                    ┌─────────────────────────┐
                    │   PersistentCheckpoint  │
                    │   Manager               │
                    │   (统一访问接口)         │
                    └─────────────────────────┘
```

## API 参考

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
    "extract_characters": true,
    "max_nodes": 50,
    "temperature": 0.3
  },
  "work_title": "作品标题",
  "known_characters": ["主角", "反派"]
}
```

**响应**:
```json
{
  "task_id": 456,
  "status": "pending",
  "message": "大纲提取任务已创建",
  "created_at": "2026-03-01T14:30:00"
}
```

### 获取任务进度

```http
GET /api/v1/outline-extraction-v2/task/456
```

**响应**:
```json
{
  "task_id": 456,
  "status": "running",
  "progress": 45,
  "current_phase": "processing_batch_3",
  "message": "正在分析第 3/5 批次",
  "checkpoint": {
    "phase": "batch_started",
    "progress_percent": 45,
    "total_batches": 5,
    "completed_batches": [0, 1],
    "failed_batches": [],
    "current_batch": 2,
    "total_nodes": 15,
    "total_turning_points": 3
  }
}
```

### 获取可恢复任务列表

```http
GET /api/v1/outline-extraction-v2/tasks/edition/123
```

**响应**:
```json
[
  {
    "task_id": "456",
    "edition_id": 123,
    "status": "paused",
    "progress": 60,
    "current_phase": "paused_by_shutdown",
    "checkpoint": {
      "phase": "batch_started",
      "progress_percent": 60,
      "total_batches": 5,
      "completed_batches": [0, 1, 2],
      "current_batch": 3,
      "total_nodes": 20
    },
    "is_recoverable": true,
    "recovery_suggestion": "任务已暂停，可从检查点恢复",
    "created_at": "2026-03-01T14:30:00"
  }
]
```

### 恢复任务

```http
POST /api/v1/outline-extraction-v2/task/456/resume
```

**响应**:
```json
{
  "success": true,
  "task_id": 456,
  "message": "任务已恢复",
  "resumed_from_batch": 3,
  "total_batches": 5
}
```

### WebSocket 连接

```javascript
const ws = new WebSocket('ws://localhost:1974/api/v1/agent-unified/ws/tasks');

// 订阅任务事件
ws.onopen = () => {
  ws.send(JSON.stringify({
    type: 'subscribe_task',
    taskId: 456
  }));
};

// 接收事件
ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  console.log('Event:', data.event_type, data.data);
};
```

**事件类型**:
- `task_created` - 任务创建
- `task_started` - 任务开始
- `task_progress` - 进度更新 `{progress, current_phase, batch_index, total_batches}`
- `task_step` - 步骤完成（包含检查点信息）
- `task_completed` - 任务完成
- `task_failed` - 任务失败
- `task_paused` - 任务暂停

## 数据库表结构

### unified_agent_tasks

| 字段 | 类型 | 说明 |
|------|------|------|
| id | SERIAL PK | 任务ID |
| task_type | VARCHAR(50) | `novel_analysis` |
| sub_type | VARCHAR(50) | `outline_extraction` |
| edition_id | INTEGER FK | 关联版本 |
| status | VARCHAR(50) | pending/running/paused/completed/failed/cancelled |
| progress | INTEGER | 0-100 |
| current_phase | VARCHAR(100) | 当前阶段描述 |
| result_data | JSONB | 提取结果 |
| config | JSONB | 配置信息 |
| created_at | TIMESTAMP | 创建时间 |
| updated_at | TIMESTAMP | 更新时间 |

### outline_extraction_checkpoints

| 字段 | 类型 | 说明 |
|------|------|------|
| id | SERIAL PK | 检查点ID |
| task_id | INTEGER FK | 关联任务 |
| phase | VARCHAR(50) | 提取阶段 |
| progress_percent | INTEGER | 进度百分比 |
| total_batches | INTEGER | 总批次数 |
| completed_batches | INTEGER[] | 已完成批次数组 |
| failed_batches | INTEGER[] | 失败批次数组 |
| current_batch | INTEGER | 当前批次 |
| total_nodes | INTEGER | 已提取节点数 |
| total_turning_points | INTEGER | 已提取转折点数 |
| checkpoint_file_path | VARCHAR(500) | 文件系统路径 |
| updated_at | TIMESTAMP | 更新时间 |

## 前端组件

### OutlineExtractionPanel

新的提取面板组件，特性：
- WebSocket 实时进度更新
- 检查点可视化（批次进度、节点统计）
- 自动检测可恢复任务
- 任务恢复对话框

### 使用方式

```tsx
import OutlineExtractionPanel from '@components/analysis/outline_extraction_panel';

function AnalysisPage() {
  return (
    <OutlineExtractionPanel
      editionId={123}
      workTitle="作品标题"
    />
  );
}
```

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

检查服务器日志中的 WebSocket 相关错误，确保防火墙允许 WebSocket 连接。

## 回滚方案

如果需要回滚到 V1：

```sql
-- 删除新表（可选）
DROP TABLE IF EXISTS outline_extraction_checkpoints;

-- 前端继续使用旧的 API 端点
-- 修改前端代码使用 /outline-extraction/ 而不是 /outline-extraction-v2/
```

## 性能优化建议

1. **定期清理检查点**
   ```sql
   SELECT cleanup_old_outline_checkpoints(168); -- 清理 7 天前的检查点
   ```

2. **监控存储空间**
   ```bash
   du -sh .cache/extraction/
   ```

3. **数据库索引优化**
   - 已为常用查询字段创建索引
   - 如需额外索引，参考迁移脚本

## 相关文档

- [原大纲提取设计文档](./outline-extraction.md) - V1 版本文档
- [Unified Agent 系统设计](../dev/text-analysis-agent-system.md)
- [数据库迁移指南](../../sail_server/migration/README_outline_checkpoint.md)
