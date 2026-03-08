# Async Outline Extraction 模块文档

## 概述

异步并行大纲提取模块，利用 asyncio 和 httpx 实现高并发 LLM API 调用，大幅提升大纲提取速度。

## 架构

```
Text
  ├── Chunks (Level 0) - 并行提取
  │     └── 多个 chunk 任务并发执行
  ├── Segments (Level 1) - 依赖 chunks 完成
  │     └── 合并 chunks 结果后执行
  └── Chapters (Level 2) - 依赖 segments 完成
        └── 合并 segments 结果生成最终大纲
```

## 核心组件

### 1. TaskGraph (任务图引擎)
- 管理任务依赖关系
- 检测循环依赖
- 自动触发下游任务

### 2. RateLimiter (速率限制器)
- 令牌桶算法控制 RPM
- TPM 滑动窗口限制
- 动态限流调整

### 3. AsyncLLMClient (异步 LLM 客户端)
- HTTP/2 连接池
- 指数退避重试
- 自动错误处理

### 4. ResultMerger (结果合并器)
- Chunk 结果合并
- Segment 结果合并
- 去重和顺序保持

### 5. ProgressTracker (进度追踪器)
- 实时进度计算
- ETA 预估
- 性能指标收集

## 使用方法

### 基本使用

```python
from sail_server.service.async_outline_extraction import (
    AsyncOutlineExtractor,
    ExtractionConfig,
)
from sail_server.service.async_outline_extraction.async_llm_client import AsyncLLMClient

# 创建 LLM 客户端
llm_client = AsyncLLMClient(
    base_url="https://api.moonshot.cn/v1",
    api_key="your-api-key",
    model="kimi-k2.5",
)

# 创建配置
config = ExtractionConfig(
    chunk_size=1500,
    max_concurrent=100,
)

# 创建提取器
extractor = AsyncOutlineExtractor(
    llm_client=llm_client,
    config=config,
)

# 执行提取
result = await extractor.extract(
    text="要提取大纲的文本...",
    work_id="work-123",
    chapter_id="chapter-456",
)

print(result.outline)
```

### API 调用

```bash
# 提取大纲
curl -X POST http://localhost:4399/api/v1/analysis/async-outline/extract \
  -H "Content-Type: application/json" \
  -d '{
    "text": "要提取大纲的文本...",
    "work_id": "work-123",
    "chunk_size": 1500,
    "max_concurrent": 100
  }'

# 查询进度
curl http://localhost:4399/api/v1/analysis/async-outline/status/{task_id}

# 取消任务
curl -X DELETE http://localhost:4399/api/v1/analysis/async-outline/{task_id}
```

## 配置参数

### 环境变量

| 变量名 | 默认值 | 说明 |
|--------|--------|------|
| USE_ASYNC_OUTLINE_EXTRACTION | false | 是否启用异步提取 |
| ASYNC_EXTRACTION_MAX_CONCURRENT | 100 | 最大并发数 |
| ASYNC_EXTRACTION_RPM_LIMIT | 400 | RPM 限制 |
| ASYNC_EXTRACTION_TPM_LIMIT | 2400000 | TPM 限制 |

### 代码配置

```python
ExtractionConfig(
    chunk_size=1500,           # 每个 chunk 的 token 数
    chunk_overlap=200,         # chunk 重叠数
    chunks_per_segment=5,      # 每个 segment 的 chunk 数
    max_concurrent=100,        # 最大并发
    rpm_limit=400,            # RPM 限制
    tpm_limit=2400000,        # TPM 限制
    timeout_seconds=30,       # 任务超时
    max_retries=3,            # 最大重试次数
)
```

## 性能优化建议

1. **调整并发数**: 根据 LLM API 限制调整 `max_concurrent`
2. **预留缓冲**: RPM 和 TPM 设置建议预留 20% 缓冲
3. **监控指标**: 关注重试率、平均延迟、p99 延迟
4. **内存管理**: 长时间运行注意内存使用，任务完成后自动清理

## 故障排除

### 429 Rate Limit 错误
- 检查 RPM/TPM 配置是否合理
- 查看 `adaptive_factor` 是否自动降低
- 增加缓冲比例

### 任务超时
- 增加 `timeout_seconds` 配置
- 减小 `chunk_size` 减少单个任务负载
- 检查网络连接

### 结果不一致
- 检查 `chunk_overlap` 设置
- 验证去重逻辑
- 对比串行模式结果
