## 1. 基础设施与依赖

- [x] 1.1 添加 httpx 依赖到 pyproject.toml
- [x] 1.2 创建 async_outline_extraction 模块目录结构
- [x] 1.3 定义任务状态枚举和基础数据类
- [x] 1.4 创建异常处理基类（TaskTimeoutError, RateLimitError 等）

## 2. 任务图引擎核心

- [x] 2.1 实现 Task 数据类（id, level, dependencies, status, result）
- [x] 2.2 实现 TaskGraph 类管理任务依赖关系
- [x] 2.3 实现依赖检测算法（检测循环依赖）
- [x] 2.4 实现任务状态机（PENDING → READY → RUNNING → COMPLETED/FAILED）
- [x] 2.5 实现下游任务自动触发机制
- [x] 2.6 添加任务超时检测逻辑
- [x] 3.1 实现 TokenBucket 令牌桶算法
- [x] 3.2 实现 RateLimiter 类（支持 RPM/TPM/并发数限制）
- [x] 3.3 实现优先级队列（高层级任务优先）
- [x] 3.4 添加动态限流调整（根据 429 响应调整）
- [x] 3.5 实现并发槽位管理（max_concurrent=100）
- [x] 3.6 添加限流配置参数（可配置的 RPM/TPM/并发数）

## 4. 层级文本切分

- [x] 4.1 实现文本 Tokenizer（估算 Token 数）
- [x] 4.2 实现 Chunk 切分器（支持滑动窗口 overlap）
- [x] 4.3 实现 Segment 切分器（按 chunk 数量分组）
- [x] 4.4 实现 Chapter 切分器（单 chapter 或智能分章）
- [x] 4.5 实现 TaskGraphBuilder 整合切分逻辑
- [x] 4.6 添加切分参数配置（chunk_size, segment_size 等）
- [x] 5.1 实现 AsyncLLMClient 类（基于 httpx）
- [x] 5.2 实现连接池管理（HTTP/2 复用）
- [x] 5.3 实现 TaskExecutor 执行单个 LLM 任务
- [x] 5.4 实现错误重试逻辑（指数退避，最多 3 次）
- [x] 5.5 添加请求/响应日志记录
- [x] 5.6 实现任务取消机制
- [x] 6.1 实现 ChunkResultMerger（合并 chunks 到 segment）
- [x] 6.2 实现 SegmentResultMerger（合并 segments 到 chapter）
- [x] 6.3 实现去重逻辑（基于位置索引）
- [x] 6.4 添加顺序保持验证
- [x] 6.5 实现边界重叠内容处理
- [x] 6.6 创建合并结果缓存（可选）
- [x] 7.1 实现 ProgressTracker 类
- [x] 7.2 实现各级别进度计算（chunk/segment/chapter）
- [x] 7.3 实现 ETA 计算（基于历史执行速度）
- [x] 7.4 添加进度事件发布机制
- [x] 7.5 实现进度查询 API 端点
- [x] 7.6 生成执行报告（总耗时、任务数、Token 消耗等）
- [x] 8.1 实现 AsyncOutlineExtractionController
- [x] 8.2 整合 TaskGraphBuilder + TaskScheduler + TaskExecutor
- [x] 8.3 实现主事件循环（asyncio）
- [x] 8.4 添加配置参数支持（mode, max_concurrency 等）
- [x] 8.5 实现串行模式兼容（fallback）
- [x] 8.6 添加性能指标收集

## 9. API 接口更新

- [x] 9.1 更新 outline extraction 路由支持异步模式
- [x] 9.2 添加 /status/{task_id} 进度查询端点
- [x] 9.3 添加 /{task_id} DELETE 取消任务端点
- [x] 9.4 更新响应格式（包含 performance 字段）
- [x] 9.5 添加错误响应增强（详细错误信息）
- [ ] 9.6 实现 WebSocket 实时推送（可选）

## 10. 测试

- [ ] 10.1 编写单元测试（TaskGraph, RateLimiter, TokenBucket）
- [ ] 10.2 编写集成测试（完整并行提取流程）
- [ ] 10.3 编写性能测试（对比串行 vs 并行性能）
- [ ] 10.4 编写结果一致性测试（确保顺序和内容正确）
- [ ] 10.5 编写错误处理测试（超时、重试、部分失败）
- [ ] 10.6 编写限流测试（模拟 429 响应）

## 11. 监控与日志

- [ ] 11.1 添加结构化日志（任务执行、状态变更）
- [ ] 11.2 实现关键指标采集（p99 延迟、并发数、重试次数）
- [ ] 11.3 添加内存使用监控
- [ ] 11.4 配置日志级别和输出格式
- [ ] 11.5 创建性能基准测试脚本

## 12. 部署与迁移

- [x] 12.1 添加 feature flag 配置
- [ ] 12.2 创建 A/B 测试配置（5% 流量）
- [ ] 12.3 编写部署文档
- [ ] 12.4 创建回滚脚本
- [x] 12.5 更新环境变量模板（.env.template）
- [x] 12.6 编写使用说明文档
