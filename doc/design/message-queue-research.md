# SailZen 消息队列与任务调度技术调研报告

## 文档信息

- **版本**: 1.0
- **日期**: 2026-03-01
- **调研目标**: 评估 Redis/RabbitMQ 等消息队列在 SailZen 项目中的必要性
- **调研范围**: 后端任务调度、缓存、异步处理

---

## 1. 执行摘要

### 1.1 核心结论

| 技术 | 是否推荐 | 推荐场景 | 当前阶段建议 |
|------|----------|----------|--------------|
| **Redis** | ⚠️ 可选 | 缓存、分布式锁、高性能 KV | **暂不需要** |
| **RabbitMQ** | ❌ 不推荐 | 高可靠消息队列、企业级应用 | **不需要** |
| **SQLite/PostgreSQL 队列** | ✅ 推荐 | 轻量级任务队列、单机部署 | **当前首选** |
| **Python asyncio** | ✅ 已使用 | 单进程异步任务 | **继续使用** |
| **Huey/RQ** | ⚠️ 未来可选 | 需要持久化任务队列时 | **第二阶段考虑** |

### 1.2 一句话总结

> 对于当前个人使用的 SailZen 项目，**不建议**引入 Redis 或 RabbitMQ。现有 PostgreSQL + asyncio 架构完全满足需求，引入外部服务会增加不必要的运维复杂度。

---

## 2. 现状分析

### 2.1 当前架构

```
┌─────────────────────────────────────────────────────────────┐
│                    SailZen 当前架构                          │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌──────────────┐         ┌──────────────┐                 │
│  │  Web 前端    │◄────────►│  sail_server │                 │
│  │  (React)     │   HTTP   │  (Litestar)  │                 │
│  └──────────────┘         └──────┬───────┘                 │
│                                  │                          │
│                    ┌─────────────┴─────────────┐            │
│                    │    AsyncTaskManager       │            │
│                    │    (内存中的任务管理)       │            │
│                    │                           │            │
│                    │  • running_tasks: dict    │            │
│                    │  • task_progress: dict    │            │
│                    │  • asyncio.Task           │            │
│                    └─────────────┬─────────────┘            │
│                                  │                          │
│                         ┌────────▼────────┐                │
│                         │   PostgreSQL    │                │
│                         │   (持久化存储)   │                │
│                         └─────────────────┘                │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### 2.2 当前任务调度实现

从代码分析可知，当前使用 `AsyncTaskManager` 单例管理任务：

```python
class AsyncTaskManager:
    """异步任务管理器 - 管理后台运行的分析任务"""
    
    def __init__(self):
        self.running_tasks: Dict[int, asyncio.Task] = {}      # 内存中
        self.task_progress: Dict[int, TaskProgress] = {}      # 内存中
        self.task_results: Dict[int, TaskRunResult] = {}      # 内存中
```

**特点**:
- ✅ 基于 Python asyncio，无需外部依赖
- ✅ 适合 I/O 密集型任务（LLM API 调用）
- ⚠️ 进程重启后任务状态丢失
- ⚠️ 单进程限制，无法利用多核

### 2.3 实际负载评估

| 场景 | QPS/并发 | 处理时间 | 当前方案是否满足 |
|------|----------|----------|------------------|
| 创建分析任务 | < 1 req/s | 即时响应 | ✅ 完全满足 |
| 执行 LLM 分析 | 1-3 并发 | 5-30s/任务 | ✅ asyncio 满足 |
| 文本导入 | < 1 req/s | 1-10s | ✅ 完全满足 |
| 数据查询 | < 10 req/s | < 100ms | ✅ 完全满足 |

**结论**: 个人使用场景下，请求量极低，远未达到任何性能瓶颈。

---

## 3. 技术选项深度分析

### 3.1 Redis

#### 3.1.1 主要用途

| 用途 | 说明 | SailZen 需求程度 |
|------|------|------------------|
| **缓存** | 加速数据读取 | 低 - 数据量小 |
| **Session 存储** | 分布式会话 | 无 - 个人使用 |
| **任务队列** | 配合 Celery/RQ | 中 - 可考虑替代方案 |
| **实时排行榜** | 高频计数 | 无 |
| **分布式锁** | 防止重复执行 | 低 - 单机部署 |
| **Pub/Sub** | 实时消息推送 | 低 - 可用 WebSocket 替代 |

#### 3.1.2 成本分析

```
引入 Redis 的额外开销:

1. 基础设施成本
   ├── 内存占用: 最少 100MB-1GB
   ├── 额外进程: 需要维护 Redis 服务
   └── 备份策略: 持久化配置(RDB/AOF)

2. 开发成本
   ├── 学习成本: Redis 命令、Python 客户端
   ├── 代码复杂度: 增加缓存层、处理穿透/雪崩
   └── 调试成本: 多一个服务排错

3. 运维成本
   ├── 监控: Redis 健康检查
   ├── 扩容: 未来可能需要集群
   └── 故障恢复: 数据丢失风险
```

#### 3.1.3 许可证风险 (2024年后)

Redis 在 2024 年更改了许可证为 **SSPL/RSAL**:
- 对个人使用：✅ 无影响
- 对商业托管：❌ 受限制
- 长期风险：⚠️ 社区已分裂，Valkey/Garnet 等替代方案出现

**建议**: 即使未来需要缓存，也建议考虑 **Valkey** (AWS  fork) 或 **KeyDB** (多线程 Redis)。

### 3.2 RabbitMQ

#### 3.2.1 适用场景

RabbitMQ 适合以下场景，但 SailZen **均不符合**：

| 场景 | 企业级需求 | SailZen 现状 |
|------|-----------|--------------|
| 多服务间异步通信 | ✅ 微服务架构 | ❌ 单体应用 |
| 高可靠消息传递 | ✅ 金融级可靠 | ❌ 个人使用 |
| 复杂路由规则 | ✅ topic/headers exchange | ❌ 简单队列即可 |
| 多语言消费者 | ✅ Python/Java/Go 混合 | ❌ 纯 Python |

#### 3.2.2 复杂度评估

```
RabbitMQ 运维复杂度: ████████████████████ 高

所需知识:
- AMQP 协议理解
- Exchange/Queue/Binding 配置
- 集群与高可用配置
- 镜像队列策略
- 流控与背压处理
- 监控与告警 (Prometheus/Grafana)
```

### 3.3 轻量级替代方案

#### 3.3.1 方案对比表

| 方案 | 依赖 | 持久化 | 复杂度 | 适用规模 | 推荐度 |
|------|------|--------|--------|----------|--------|
| **asyncio (当前)** | 无 | 无 | 极低 | 单机 | ⭐⭐⭐⭐ |
| **PostgreSQL 队列** | PG | ✅ | 低 | 单机/小集群 | ⭐⭐⭐⭐⭐ |
| **Huey (SQLite)** | 无 | ✅ | 低 | 单机 | ⭐⭐⭐⭐⭐ |
| **Huey (Redis)** | Redis | ✅ | 中 | 单机/小集群 | ⭐⭐⭐ |
| **RQ** | Redis | ✅ | 中 | 单机/小集群 | ⭐⭐⭐ |
| **Celery** | Redis/RabbitMQ | ✅ | 高 | 大规模 | ⭐⭐ |

#### 3.3.2 推荐方案详解

**方案一: PostgreSQL 作为队列 (推荐)**

```python
# 使用 PostgreSQL 的 SKIP LOCKED 实现轻量级队列
# 无需任何外部依赖

class PostgresTaskQueue:
    """基于 PostgreSQL 的轻量级任务队列"""
    
    async def enqueue(self, task_type: str, payload: dict):
        """入队"""
        await self.db.execute(
            """
            INSERT INTO task_queue (task_type, payload, status, created_at)
            VALUES ($1, $2, 'pending', NOW())
            """,
            task_type, json.dumps(payload)
        )
    
    async def dequeue(self) -> Optional[Task]:
        """出队 - 使用 SKIP LOCKED 防止竞争"""
        async with self.db.transaction():
            row = await self.db.fetchrow(
                """
                SELECT id, task_type, payload 
                FROM task_queue 
                WHERE status = 'pending'
                ORDER BY created_at
                FOR UPDATE SKIP LOCKED
                LIMIT 1
                """
            )
            if row:
                await self.db.execute(
                    "UPDATE task_queue SET status = 'running' WHERE id = $1",
                    row['id']
                )
            return row
```

**优势**:
- ✅ 零额外依赖，已有 PostgreSQL
- ✅ ACID 保证，不丢消息
- ✅ 可查看队列状态（直接 SQL 查询）
- ✅ 支持多进程消费（多 worker）

**方案二: Huey + SQLite (极简方案)**

```python
# 如果希望更简单，使用 Huey + SQLite
# 甚至不需要 PostgreSQL

from huey import SqliteHuey

huey = SqliteHuey(filename='/data/sailzen_tasks.db')

@huey.task()
def run_analysis_task(task_id: int):
    """分析任务"""
    # 执行 LLM 分析
    pass

@huey.periodic_task(crontab(hour='2', minute='0'))
def nightly_cleanup():
    """夜间清理任务"""
    pass

# 启动消费者
# huey_consumer.py tasks.huey -k thread -w 2
```

**优势**:
- ✅ 极简配置，单文件存储
- ✅ 支持定时任务、重试、结果存储
- ✅ 可迁移到 Redis 后端（未来需要时）

---

## 4. 场景化建议

### 4.1 当前阶段 (个人使用)

**不推荐任何外部消息队列**

```
建议架构:
┌─────────────────────────────────────┐
│         sail_server                 │
│  ┌─────────────────────────────┐   │
│  │    AsyncTaskManager         │   │
│  │    (内存 + PostgreSQL)      │   │
│  │                             │   │
│  │  进程重启时从数据库恢复状态   │   │
│  └─────────────────────────────┘   │
└─────────────────┬───────────────────┘
                  │
         ┌────────▼────────┐
         │   PostgreSQL    │
         │  (任务状态表)    │
         └─────────────────┘
```

**改进建议** (不引入新服务):
1. 增强 `AsyncTaskManager` 持久化能力
2. 进程启动时从数据库恢复未完成任务
3. 使用 `pg_notify` 实现简单的事件通知

### 4.2 第二阶段 (多用户/小型团队)

当需求增长到以下程度时，考虑引入轻量级方案：

```
触发条件:
- 同时运行任务 > 10 个
- 需要多进程消费 CPU 密集型任务
- 需要任务历史/审计

推荐方案:
┌─────────────────────────────────────┐
│         sail_server                 │
│  ┌─────────────────────────────┐   │
│  │        Huey                 │   │
│  │   (SQLite 或 PostgreSQL)     │   │
│  │                             │   │
│  │  • 持久化任务队列            │   │
│  │  • 定时任务支持              │   │
│  │  • 多 worker 进程            │   │
│  └─────────────────────────────┘   │
└─────────────────────────────────────┘

# 无需 Redis，使用 PostgreSQL 作为后端
huey = Huey('postgres://localhost/sailzen', backend='postgres')
```

### 4.3 第三阶段 (大规模部署)

只有当出现以下需求时，才考虑 Redis/RabbitMQ：

```
触发条件:
- 多机部署，需要分布式协调
- QPS > 100/s
- 需要复杂的路由规则
- 团队有专人运维

推荐方案:
┌─────────────────────────────────────┐
│         sail_server                 │
│  ┌─────────────────────────────┐   │
│  │       Dramatiq/RQ           │   │
│  │         +                   │   │
│  │    Redis/Valkey (可选)       │   │
│  └─────────────────────────────┘   │
└─────────────────────────────────────┘
```

---

## 5. 具体实施建议

### 5.1 短期优化 (不引入新服务)

改进现有 `AsyncTaskManager` 的持久化：

```python
class ImprovedTaskManager(AsyncTaskManager):
    """改进版任务管理器，增强持久化"""
    
    async def recover_tasks(self):
        """进程启动时恢复未完成任务"""
        db = get_db_session()
        running_tasks = db.query(AnalysisTask).filter(
            AnalysisTask.status.in_(['running', 'pending'])
        ).all()
        
        for task in running_tasks:
            # 重置为 pending 状态
            task.status = 'pending'
            db.commit()
    
    async def persist_progress(self, task_id: int, progress: TaskProgress):
        """持久化进度到数据库"""
        db = get_db_session()
        task = db.query(AnalysisTask).get(task_id)
        if task:
            task.progress_data = progress.to_dict()
            task.updated_at = datetime.now()
            db.commit()
```

### 5.2 中期演进 (如需更可靠的任务队列)

使用 **Propan** 或 **FastStream** (基于 asyncio 的现代消息队列库)：

```python
# 使用 Propan 构建轻量级队列
# 可切换内存/SQLite/Redis/RabbitMQ 后端

from propan import PropanApp
from propan.brokers import RabbitBroker

# 开发/测试使用内存后端
broker = RabbitBroker("memory://")

# 生产环境可切换到 RabbitMQ
# broker = RabbitBroker("amqp://guest:guest@localhost:5672/")

app = PropanApp(broker)

@broker.handle("analysis_tasks")
async def process_analysis(task_id: int):
    await run_analysis(task_id)
```

### 5.3 长期演进

如确实需要 Redis 缓存，建议：

```
1. 优先尝试 PostgreSQL 优化:
   - 添加适当的索引
   - 使用物化视图
   - 查询优化

2. 考虑应用级缓存:
   - cachetools (内存 LRU 缓存)
   - diskcache (磁盘缓存)

3. 最后考虑 Redis 替代方案:
   - Valkey (AWS fork, BSD 许可证)
   - KeyDB (多线程 Redis)
   - Garnet (Microsoft 实现, C#)
```

---

## 6. 风险评估

### 6.1 不引入 Redis/RabbitMQ 的风险

| 风险 | 可能性 | 影响 | 缓解措施 |
|------|--------|------|----------|
| 进程崩溃导致任务丢失 | 中 | 中 | 增强持久化，定期 checkpoint |
| 单进程无法处理高并发 | 低 | 低 | 个人使用场景不会出现 |
| 无法水平扩展 | 低 | 低 | 当前单机部署足够 |

### 6.2 引入 Redis/RabbitMQ 的风险

| 风险 | 可能性 | 影响 | 说明 |
|------|--------|------|------|
| 增加运维负担 | 高 | 高 | 个人时间有限 |
| 环境配置复杂度 | 高 | 中 | Windows 开发环境更麻烦 |
| 调试困难 | 中 | 中 | 多一个服务排查 |
| 许可证风险 (Redis) | 中 | 低 | SSPL 对自用无影响 |

---

## 7. 结论与建议

### 7.1 最终建议

**现阶段 (个人使用):**
```
❌ 不引入 Redis
❌ 不引入 RabbitMQ
✅ 继续使用 asyncio + PostgreSQL
✅ 增强任务持久化
```

**未来演进路径:**
```
第一阶段: asyncio + PG (当前)
    ↓ (需要更可靠队列时)
第二阶段: Huey + SQLite/PG
    ↓ (需要分布式时)
第三阶段: Dramatiq/RQ + Valkey (Redis 替代)
```

### 7.2 决策树

```
是否需要消息队列?
│
├─ 是否是个人使用? 
│  └─ 是 → 不需要 Redis/RabbitMQ
│
├─ 是否需要跨机器通信?
│  ├─ 否 → 使用 PostgreSQL 队列
│  └─ 是 → 考虑 Valkey + Dramatiq
│
├─ QPS 是否 > 100?
│  ├─ 否 → 当前架构足够
│  └─ 是 → 考虑 Redis
│
└─ 是否有专人运维?
   ├─ 否 → 避免 RabbitMQ
   └─ 是 → 可选 RabbitMQ
```

### 7.3 一句话总结

> **保持简单，避免过度工程化。** 当前 PostgreSQL + asyncio 架构对个人项目完全足够。将精力放在功能开发上，而非基础设施。当且仅当遇到实际性能瓶颈时，再考虑引入外部服务。

---

## 8. 参考资源

- [Huey 文档](https://huey.readthedocs.io/)
- [Redis 许可证变更分析](https://news.ycombinator.com/item?id=39772562)
- [Valkey - Redis 替代](https://valkey.io/)
- [PostgreSQL SKIP LOCKED 队列](https://www.2ndquadrant.com/en/blog/what-is-select-skip-locked-for-in-postgresql-9-5/)
- [Dramatiq vs Celery](https://dramatiq.io/motivation.html)

---

*报告结束*
