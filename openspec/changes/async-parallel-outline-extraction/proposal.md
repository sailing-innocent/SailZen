## Why

当前的大纲提取服务采用串行处理模式，将文本切分为 chunks 后逐个调用 LLM API，导致处理速度慢且资源利用率低。随着文本量和复杂度增加，串行模式已成为性能瓶颈。利用 LLM 服务商提供的高并发能力（并发100，RPM 500，TPM 3000000），可以通过并行化显著加速大纲提取过程，提升用户体验和系统吞吐量。

## What Changes

- **重构大纲提取架构**：从简单的 chunk 级串行处理升级为多层级的异步并行任务图架构
- **引入任务层级**：在 chunk 之上增加文本段(segment)和章节(chapter)层级，形成树状任务依赖图
- **实现发布-重连-执行模式**：任务按依赖关系发布，完成后触发下游任务，最终合并结果
- **添加并发控制和速率限制**：实现基于 LLM 服务商限制的动态限流和任务调度
- **保证结果顺序**：并行处理的同时确保最终大纲结构按原文顺序组织
- **提供进度反馈**：实现实时进度追踪，包括层级完成度和预估时间

## Capabilities

### New Capabilities
- `task-graph-engine`: 异步任务图执行引擎，支持依赖发布和结果重连
- `hierarchical-outline-extraction`: 多层级大纲提取，支持 chunk/segment/chapter 三级并行
- `concurrency-control`: 基于 LLM API 限制的并发控制和速率限制
- `progress-tracking`: 实时进度追踪和状态报告系统

### Modified Capabilities
- `outline-extraction`: 重构现有大纲提取流程，改为并行架构，保持 API 兼容

## Impact

### 代码影响
- `sail_server/controller/analysis/outline_extraction.py` - 完全重写核心逻辑
- `sail_server/utils/llm/` - 新增并发控制和队列管理模块
- `sail_server/model/analysis/` - 可能新增任务状态存储模型

### API 影响
- `/api/v1/analysis/outline` - 接口保持不变，但内部实现改为异步
- 可能新增 `/api/v1/analysis/outline/status/{task_id}` - 用于查询进度

### 性能影响
- 预期处理速度提升 5-10 倍（取决于文本长度和层级深度）
- 内存使用增加（需要存储更多中间状态）
- 网络并发增加，需要更好的错误重试机制

### 依赖影响
- 新增 `asyncio` 和 `aiohttp` 或 `httpx` 用于异步 HTTP 请求
- 可能需要任务队列（如 Celery）处理长时间运行任务
