# 大纲提取功能修复总结

## 问题描述

在使用 Moonshot (Kimi) API 进行大纲提取时，遇到 429 速率限制错误：

```
Error code: 429 - {'error': {'message': 'Your account ... request reached organization TPD rate limit, current: 1543253, limit: 1500000', 'type': 'rate_limit_reached_error'}}
```

这是一个每日 Token 配额超限错误（TPD = Tokens Per Day）。

## 修复方案

### 1. 分阶段缓存机制

**文件**: `sail_server/service/extraction_cache.py`

实现了完整的检查点系统：

- **ExtractionCheckpoint**: 主检查点类，包含：
  - 任务元数据（task_id, edition_id, 配置等）
  - 当前状态和进度
  - 批次处理状态（completed_batches, failed_batches）
  - 累积结果（accumulated_nodes, accumulated_turning_points）
  - 批次级别的详细检查点（batch_checkpoints）

- **BatchCheckpoint**: 单个批次的结果存储
  - 批次索引和章节范围
  - 提取的节点和转折点
  - 完成时间戳

- **ExtractionCacheManager**: 缓存管理器
  - 自动保存检查点到磁盘（JSON格式）
  - 支持从检查点恢复
  - 内存缓存 + 磁盘持久化
  - 过期检查点清理

**使用场景**:
- 长文本分批次处理时，每个批次完成后自动保存
- 任务失败后可以从上次成功的批次继续
- 支持查询任务详细状态和恢复进度

### 2. LLM 调用重试机制

**文件**: `sail_server/utils/llm/retry_handler.py`

实现了智能重试系统：

- **RetryConfig**: 可配置的重试策略
  - 最大重试次数（默认3次）
  - 重试策略：固定间隔、指数退避、线性增长
  - 抖动（jitter）避免惊群效应
  - 针对速率限制的特殊处理

- **RateLimitInfo**: 速率限制信息解析
  - 自动识别 TPD、RPM 等限制类型
  - 解析当前使用量和限制值
  - 提取 retry_after 时间

- **LLMRetryHandler**: 重试执行器
  - 自动检测可重试错误（429、超时、服务器错误）
  - 智能计算等待时间
  - 提供重试回调接口
  - 详细的重试统计信息

**重试策略**:
- 速率限制：使用更长的基础延迟（默认5秒起）
- 指数退避：delay = base * (2 ^ attempt)
- 抖动：添加 0.8-1.2 倍的随机因子

### 3. 增强的错误反馈

**文件**: `sail_server/service/outline_extractor.py`（更新）

- **ExtractionErrorInfo**: 详细的错误信息
  - 错误类型和消息
  - 是否可重试
  - 重试次数
  - 速率限制详情
  - 用户建议（如切换到其他LLM提供商）

- **ExtractionProgress**: 增强的进度信息
  - 重试状态（is_retrying, retry_attempt, retry_delay）
  - 速率限制信息

**文件**: `sail_server/controller/outline_extraction.py`（更新）

新增 API 端点：
- `GET /task/{task_id}/detailed`: 获取详细状态（包含检查点信息）
- `POST /task/{task_id}/resume`: 恢复失败/暂停的任务
- `GET /checkpoints`: 列出所有可用的检查点
- `POST /checkpoints/cleanup`: 清理过期检查点

**文件**: `packages/site/src/lib/data/analysis.ts`（更新）

新增类型定义：
- `RateLimitInfo`: 速率限制信息
- `ExtractionErrorInfo`: 错误详情
- `OutlineExtractionDetailedStatus`: 详细状态
- `ResumeTaskResponse`: 恢复任务响应

**文件**: `packages/site/src/lib/api/analysis.ts`（更新）

新增 API 函数：
- `api_get_outline_extraction_detailed_status()`: 获取详细状态
- `api_resume_outline_extraction_task()`: 恢复任务

## 使用示例

### 后端使用

```python
from sail_server.service.outline_extractor import OutlineExtractor

# 创建提取器（自动启用重试和缓存）
extractor = OutlineExtractor(db)

# 执行提取（自动处理重试和检查点）
result = await extractor.extract(
    edition_id=1,
    range_selection=range_selection,
    config=config,
    task_id="unique-task-id",  # 启用缓存
    resume_from_checkpoint=True,  # 支持恢复
)
```

### 前端使用

```typescript
// 创建任务
const task = await api_create_outline_extraction_task(request)

// 轮询进度（包含重试信息）
const progress = await api_get_outline_extraction_progress(task.task_id)
if (progress.is_retrying) {
  console.log(`正在重试 (${progress.retry_attempt})，等待 ${progress.retry_delay} 秒...`)
}

// 获取详细状态
const status = await api_get_outline_extraction_detailed_status(task.task_id)
console.log(`已完成批次: ${status.completed_batches.length}/${status.total_batches}`)

// 任务失败后恢复
if (status.status === 'failed') {
  const resumeResult = await api_resume_outline_extraction_task(task.task_id)
  console.log(resumeResult.message)
}
```

## 错误处理建议

当遇到 TPD 速率限制时，系统会返回以下建议：

1. **等待配额重置**：通常次日自动重置
2. **切换 LLM 提供商**：如从 Moonshot 切换到 OpenAI 或 Google
3. **减少处理范围**：减少单次处理的章节数量

## 文件变更列表

### 新增文件
1. `sail_server/utils/llm/retry_handler.py` - LLM 重试处理器
2. `sail_server/service/extraction_cache.py` - 提取缓存管理器

### 修改文件
1. `sail_server/service/outline_extractor.py` - 集成缓存和重试机制
2. `sail_server/controller/outline_extraction.py` - 新增 API 端点
3. `packages/site/src/lib/data/analysis.ts` - 新增类型定义
4. `packages/site/src/lib/api/analysis.ts` - 新增 API 函数

## 后续优化建议

1. **持久化任务队列**：使用 Redis 或数据库替代内存存储
2. **多提供商自动切换**：当一个提供商达到限制时自动切换到备用
3. **预估 Token 消耗**：在处理前预估 Token 消耗，避免超限
4. **智能批处理**：根据剩余配额动态调整批次大小
