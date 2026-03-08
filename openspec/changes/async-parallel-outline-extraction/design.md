## Context

### 当前架构
现有大纲提取服务采用简单的串行处理模式：
1. 将长文本切分为固定大小的 chunks
2. 逐个 chunk 调用 LLM API 提取大纲节点
3. 合并所有 chunk 的结果生成最终大纲

这种模式存在以下问题：
- **性能瓶颈**：串行调用导致处理时间与文本长度线性增长
- **资源浪费**：LLM API 支持高并发（100并发，RPM 500），但当前只使用单线程
- **无进度反馈**：用户无法知道处理进度，长文本处理时体验差
- **缺乏层级**：简单 chunk 合并无法捕获文本的深层结构关系

### LLM API 限制
- 最大并发数：100
- TPM（每分钟Token数）：3,000,000
- RPM（每分钟请求数）：500
- TPD：无限制

## Goals / Non-Goals

**Goals:**
- 实现异步并行的大纲提取架构，充分利用 LLM API 并发能力
- 建立多级任务层级（chunk/segment/chapter），形成树状依赖图
- 实现发布-重连-执行模式，确保依赖任务正确执行
- 保证最终结果按原文顺序组织，与串行模式结果一致
- 提供实时进度追踪和预估时间
- 实现基于 LLM API 限制的动态限流

**Non-Goals:**
- 不改变现有 API 接口契约（保持向后兼容）
- 不修改前端 UI（仅后端重构）
- 不引入外部消息队列（使用 Python asyncio）
- 不支持分布式部署（单机并行即可）

## Decisions

### 1. 使用 Python asyncio + httpx 实现异步
**选择**：使用 Python 原生 asyncio 和 httpx 库实现异步 HTTP 请求

**理由**：
- 无需引入额外依赖（如 Celery/RabbitMQ）
- httpx 支持 HTTP/2 和连接池复用
- 与现有 Python 后端技术栈一致

**替代方案**：
- Celery + Redis：太重，需要额外基础设施
- aiohttp：功能类似但社区活跃度不如 httpx

### 2. 三层任务层级架构
**选择**：实现 chunk → segment → chapter 三级并行

**理由**：
- chunk（约1000-2000 tokens）：最细粒度并行，最大化并发
- segment（约5-10 chunks）：中级并行，捕获段落内关系
- chapter（多个 segments）：高级并行，捕获章节结构

**树状依赖关系**：
```
Chapter Tasks (Level 2)
    ├── Segment Task 1 (Level 1)
    │   ├── Chunk Task 1 (Level 0)
    │   ├── Chunk Task 2 (Level 0)
    │   └── Chunk Task 3 (Level 0)
    ├── Segment Task 2 (Level 1)
    │   └── ...
    └── Segment Task 3 (Level 1)
        └── ...
```

**合并策略**：
- Level 0 (Chunk)：提取基础大纲节点
- Level 1 (Segment)：合并 chunk 结果，识别段落结构
- Level 2 (Chapter)：合并 segment 结果，形成最终大纲树

### 3. 令牌桶算法实现速率限制
**选择**：使用令牌桶算法控制并发和速率

**配置**：
```python
RATE_LIMITS = {
    "max_concurrent": 100,      # 最大并发请求
    "rpm": 500,                 # 每分钟请求数
    "tpm": 3_000_000,          # 每分钟Token数
}
```

**理由**：
- 平滑突发流量，避免触发 API 限流
- 动态调整，根据当前负载自适应
- 支持优先级队列，确保高层级任务优先

### 4. 任务图执行引擎设计
**组件**：
1. **TaskGraphBuilder**：将文本切分为任务图
2. **TaskScheduler**：调度可执行任务（依赖满足且有空闲槽位）
3. **TaskExecutor**：执行 LLM API 调用
4. **ResultMerger**：合并下级任务结果到上级

**状态流转**：
```
PENDING → READY → RUNNING → COMPLETED
                    ↓
                FAILED → RETRY → RUNNING
```

**重连机制**：
- 任务完成后触发下游依赖任务的 READY 检查
- 使用 asyncio.Event 进行任务间同步

### 5. 内存存储任务状态
**选择**：使用内存字典存储任务状态，而非数据库

**理由**：
- 大纲提取是短时任务（通常 < 5分钟）
- 内存操作更快，减少 I/O 开销
- 任务完成后立即清理，避免内存泄漏

**注意**：如需要持久化进度，可额外写入 Redis

## Risks / Trade-offs

| 风险 | 缓解措施 |
|------|----------|
| **内存使用激增** | 限制并发数，任务完成后立即释放资源；监控内存使用，超过阈值时降低并发 |
| **API 限流触发** | 实现指数退避重试；预留 20% 缓冲（实际使用 80 RPM 而非 500） |
| **结果顺序错乱** | 每个任务记录原始位置索引；合并时按索引排序 |
| **网络超时/失败** | 每个任务最多 3 次重试；失败任务标记并记录错误 |
| **调试困难** | 完善日志记录（任务 ID、依赖关系、执行时间）；保留原始串行模式作为 fallback |

## Migration Plan

### 阶段 1：新架构并行开发（不替换现有代码）
- 创建新的 `async_outline_extraction.py` 模块
- 保持现有 `outline_extraction.py` 不变
- 通过 feature flag 控制使用哪个版本

### 阶段 2：A/B 测试
- 5% 流量使用新架构
- 监控性能指标（处理时间、成功率、API 调用次数）
- 对比结果一致性

### 阶段 3：灰度发布
- 50% → 100% 逐步切换
- 保留旧代码 1 个版本作为 fallback

### 阶段 4：清理
- 移除旧串行代码
- 删除 feature flag

### 回滚策略
- 发现严重问题时立即切回旧代码（修改配置即可）
- 无需数据迁移（无持久化状态）

## Open Questions

1. **任务粒度如何确定？**
   - chunk 大小：1000 tokens？2000 tokens？
   - segment 应该包含多少 chunks？
   - 需要实验验证最优参数

2. **错误处理策略？**
   - 单个 chunk 失败是否影响整个任务？
   - 使用 best-effort 合并还是整体失败？

3. **缓存策略？**
   - 是否需要缓存 LLM 响应？
   - 缓存键如何设计？

4. **监控指标？**
   - 需要记录哪些指标？（p99 延迟、并发数、重试次数）
   - 使用 Prometheus 还是简单日志？
