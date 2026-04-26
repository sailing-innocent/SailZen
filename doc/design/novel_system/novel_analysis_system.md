# AI-Driven Novel Analysis & Creation System

> **版本**: 1.0 Draft  
> **作者**: sailing-innocent  
> **日期**: 2026-04-14  
> **状态**: 设计阶段

## 1. 系统愿景

构建一个**小说整理 → 清理 → 分析 → 创作**的全链路 AI 工作流系统。

核心设计原则：
- **DAG Pipeline 驱动**: 所有工作流建模为 DAG，天然支持并行化
- **AI 深度赋能**: 每个分析节点都可以调度 LLM，支持批量并发
- **渐进式精炼**: 分析结果从粗到细，每一层都可人工校验
- **前后端一体**: 服务端执行 + Web 实时可视化 + 飞书快捷操作

## 2. 现有组件盘点

| 组件 | 路径 | 能力 | 成熟度 |
|------|------|------|--------|
| DAG Pipeline ORM | `infrastructure/orm/dag_pipeline.py` | PipelineRun / NodeRun 持久化，状态机 | ✅ 可用 |
| DAG Executor | `service/dag_executor.py` | 依赖解析、并行执行、动态生成节点、失败传播 | ✅ 可用 |
| Pipeline Loader | `service/dag_pipeline_loader.py` | JSON 定义加载、模板变量解析 | ✅ 可用 |
| Text ORM | `infrastructure/orm/text.py` | Work / Edition / DocumentNode / IngestJob | ✅ 可用 |
| Text DAO | `data/dao/text.py` | CRUD + 查询方法 | ✅ 可用 |
| Analysis ORM | `infrastructure/orm/analysis/` | Character / Outline / Setting / Evidence | ✅ 可用 |
| Analysis Router | `router/analysis.py` | 大纲提取、人物检测、设定提取 Controller | ✅ 可用 |
| AI Text Import Skill | `.opencode/skills/sailzen-ai-text-import/` | 编码检测、采样分析、章节切分、批量上传 | ✅ 可用 |
| OpenCode Client | `sail_bot/opencode_client.py` | Session CRUD、SSE 流、异步执行 | ✅ 可用 |
| DAG Pipeline 前端 | `packages/site/src/pages/dag_pipeline.tsx` | DAG 画布、节点详情、运行历史 | ✅ 可用 |
| Text 前端 | `packages/site/src/pages/text.tsx` | 作品列表、章节阅读器 | ✅ 可用 |

## 3. 系统架构总览

```
┌─────────────────────────────────────────────────────────────────┐
│                        触发层 (Trigger)                         │
│  ┌──────────┐  ┌──────────────┐  ┌───────────┐  ┌───────────┐ │
│  │ Web UI   │  │ Feishu Bot   │  │ CLI       │  │ Cron/Hook │ │
│  └────┬─────┘  └──────┬───────┘  └─────┬─────┘  └─────┬─────┘ │
└───────┼───────────────┼────────────────┼──────────────┼────────┘
        │               │                │              │
        ▼               ▼                ▼              ▼
┌─────────────────────────────────────────────────────────────────┐
│                     控制平面 (Control Plane)                     │
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │              Novel Pipeline Orchestrator                 │   │
│  │  - 接收触发请求，实例化 Pipeline                         │   │
│  │  - 管理 Pipeline 生命周期                                │   │
│  │  - 协调 Human-in-the-Loop 审批                          │   │
│  └───────────────────────┬─────────────────────────────────┘   │
│                           │                                     │
│  ┌───────────────────────▼─────────────────────────────────┐   │
│  │              DAG Executor (已有)                          │   │
│  │  - 拓扑排序 + 并行调度                                   │   │
│  │  - 动态节点生成 (dynamic_spawn)                          │   │
│  │  - 失败传播 + 重试                                       │   │
│  └───────────────────────┬─────────────────────────────────┘   │
│                           │                                     │
└───────────────────────────┼─────────────────────────────────────┘
                            │
        ┌───────────────────┼───────────────────┐
        ▼                   ▼                   ▼
┌──────────────┐  ┌──────────────┐  ┌──────────────────┐
│  Node Workers │  │  LLM Agents  │  │  OpenCode Session│
│  (内置逻辑)   │  │  (AI 分析)   │  │  (代码生成/执行)  │
└──────┬───────┘  └──────┬───────┘  └────────┬─────────┘
       │                 │                    │
       ▼                 ▼                    ▼
┌─────────────────────────────────────────────────────────────────┐
│                      数据层 (Data Layer)                         │
│                                                                 │
│  ┌──────────┐  ┌───────────┐  ┌──────────┐  ┌──────────────┐  │
│  │ Text     │  │ Analysis  │  │ Pipeline │  │ Artifact     │  │
│  │ (Work,   │  │ (Character│  │ (Run,    │  │ (生成物,     │  │
│  │ Edition, │  │  Outline, │  │  Node,   │  │  中间结果)   │  │
│  │ DocNode) │  │  Setting, │  │  Status) │  │              │  │
│  │          │  │  Evidence) │  │          │  │              │  │
│  └──────────┘  └───────────┘  └──────────┘  └──────────────┘  │
│                                                                 │
│                    PostgreSQL / SQLite                           │
└─────────────────────────────────────────────────────────────────┘
```

## 4. 核心工作流 Pipeline 定义

### 4.1 Pipeline 总览

系统定义 **4 条主 Pipeline**，每条可独立运行，也可串联：

```
Pipeline 1: Ingest        Pipeline 2: Analyze       Pipeline 3: Enrich
(导入整理)                 (深度分析)                (知识增强)
                                                     
 ┌─────────┐              ┌──────────┐              ┌───────────┐
 │ 文件探查 │              │ 人物检测  │              │ 关系图谱   │
 └────┬────┘              └────┬─────┘              └─────┬─────┘
      │                        │                          │
 ┌────▼────┐              ┌────▼─────┐              ┌─────▼─────┐
 │ 编码检测 │              │ 大纲提取  │              │ 时间线构建 │
 └────┬────┘              └────┬─────┘              └─────┬─────┘
      │                        │                          │
 ┌────▼────┐              ┌────▼─────┐              ┌─────▼─────┐
 │ 采样分析 │              │ 设定提取  │              │ 世界观图谱 │
 └────┬────┘              └────┬─────┘              └─────┬─────┘
      │                        │                          │
 ┌────▼────┐              ┌────▼─────┐              ┌─────▼─────┐
 │ 章节切分 │              │ 证据关联  │              │ 一致性检查 │
 └────┬────┘              └──────────┘              └───────────┘
      │
 ┌────▼────┐              Pipeline 4: Create
 │ 内容清洗 │              (辅助创作)
 └────┬────┘
      │                    ┌───────────┐
 ┌────▼────┐              │ 大纲生成   │
 │ 异常检测 │              └─────┬─────┘
 └────┬────┘                    │
      │                    ┌─────▼─────┐
 ┌────▼──────┐            │ 章节草稿   │
 │ 批量上传   │            └─────┬─────┘
 └────┬──────┘                  │
      │                    ┌─────▼─────┐
 ┌────▼──────┐            │ 风格校验   │
 │ 校验确认   │            └─────┬─────┘
 └───────────┘                  │
                           ┌─────▼─────┐
                           │ 人工审校   │
                           └───────────┘
```

### 4.2 Pipeline 1: Ingest (小说导入整理)

**触发**: 用户上传 txt 文件 / 飞书发送文件 / CLI 指定路径

```jsonc
{
  "id": "novel-ingest",
  "name": "小说导入: {title}",
  "description": "从原始 txt 文件导入、清洗、切分、上传小说",
  "params_schema": {
    "file_path": { "type": "string", "required": true },
    "title": { "type": "string", "required": true },
    "author": { "type": "string", "required": true },
    "encoding": { "type": "string", "default": "auto" }
  },
  "nodes": [
    {
      "id": "probe",
      "name": "文件探查",
      "type": "builtin",
      "handler": "novel.ingest.probe_file",
      "description": "检测文件大小、编码、总字符数",
      "depends_on": []
    },
    {
      "id": "sample",
      "name": "采样分析",
      "type": "llm",
      "handler": "novel.ingest.sample_analyze",
      "description": "从头/中/尾采样，AI 识别章节边界模式",
      "depends_on": ["probe"],
      "llm_config": {
        "provider": "default",
        "temperature": 0.3,
        "max_tokens": 4000
      }
    },
    {
      "id": "split",
      "name": "章节切分",
      "type": "builtin",
      "handler": "novel.ingest.split_chapters",
      "description": "根据采样结果选择策略切分章节",
      "depends_on": ["sample"]
    },
    {
      "id": "clean",
      "name": "内容清洗",
      "type": "builtin",
      "handler": "novel.ingest.clean_content",
      "description": "去广告、去乱码、去重复空行",
      "depends_on": ["split"]
    },
    {
      "id": "anomaly",
      "name": "异常检测",
      "type": "builtin",
      "handler": "novel.ingest.detect_anomalies",
      "description": "检测超长/超短/编号跳跃章节",
      "depends_on": ["clean"]
    },
    {
      "id": "review_gate",
      "name": "人工审核",
      "type": "human_gate",
      "handler": "novel.ingest.await_review",
      "description": "展示分析报告，等待用户确认",
      "depends_on": ["anomaly"],
      "gate_config": {
        "auto_approve_if": "anomaly.warnings_count == 0",
        "timeout_hours": 72
      }
    },
    {
      "id": "upload",
      "name": "批量上传",
      "type": "builtin",
      "handler": "novel.ingest.batch_upload",
      "description": "分批上传到服务端 Text API",
      "depends_on": ["review_gate"]
    },
    {
      "id": "verify",
      "name": "校验确认",
      "type": "builtin",
      "handler": "novel.ingest.verify_upload",
      "description": "比对服务端章节数与本地预期",
      "depends_on": ["upload"]
    }
  ]
}
```

## 5. 核心技术设计

### 5.1 DAG Executor 扩展：从 Mock 到真实执行

现有 `dag_executor.py` 的 `_execute_node` 是 mock 实现（`asyncio.sleep` + `random.random`）。
需要替换为**可插拔的 Handler 注册机制**。

```python
# sail_server/service/novel_node_handlers.py

from typing import Any, Callable, Coroutine

# Handler 签名: (run_id, node_def, params, context) -> result_dict
NodeHandler = Callable[[int, dict, dict, dict], Coroutine[Any, Any, dict]]

_handler_registry: dict[str, NodeHandler] = {}

def register_handler(handler_path: str, fn: NodeHandler):
    """注册节点处理器，handler_path 如 'novel.ingest.probe_file'"""
    _handler_registry[handler_path] = fn

def get_handler(handler_path: str) -> NodeHandler | None:
    return _handler_registry.get(handler_path)
```

修改后的 `_execute_node`:

```python
async def _execute_node(run_id: int, node_def: dict, params: dict, context: dict) -> bool:
    node_id = node_def["id"]
    handler_path = node_def.get("handler")
    node_type = node_def.get("type", "builtin")
    
    handler = get_handler(handler_path)
    if not handler:
        # 回退到 mock 行为（兼容旧 pipeline）
        return await _execute_node_mock(run_id, node_def, params)
    
    await _db_update_node_sync(run_id, node_id, status=RunStatus.running, started_at=now())
    
    try:
        if node_type == "human_gate":
            result = await _execute_human_gate(run_id, node_def, params, context)
        elif node_type == "llm_batch":
            result = await _execute_llm_batch(run_id, node_def, params, context)
        else:
            result = await handler(run_id, node_def, params, context)
        
        context[node_id] = result  # 存入上下文供下游节点使用
        await _db_update_node_sync(run_id, node_id, status=RunStatus.success, ...)
        return True
    except Exception as e:
        await _db_update_node_sync(run_id, node_id, status=RunStatus.failed, ...)
        return False
```

### 5.2 节点类型体系

| 类型 | 说明 | 执行方式 |
|------|------|----------|
| `builtin` | 纯 Python 逻辑，无外部调用 | 直接 `await handler(...)` |
| `llm` | 单次 LLM 调用 | Semaphore 控制 + 结构化输出解析 |
| `llm_batch` | 批量 LLM 调用（分片并发） | `asyncio.gather` + 信号量 + 结果合并 |
| `human_gate` | 人工审核门控 | 暂停 Pipeline，等待 API 回调 approve/reject |
| `opencode` | 委托 OpenCode Session 执行 | 通过 SSE 流监听结果 |

### 5.3 Human Gate（人工审核门控）

```python
async def _execute_human_gate(run_id: int, node_def: dict, params: dict, context: dict):
    gate_config = node_def.get("gate_config", {})
    
    # 检查自动放行条件
    auto_approve_expr = gate_config.get("auto_approve_if")
    if auto_approve_expr and evaluate_condition(auto_approve_expr, context):
        return {"auto_approved": True, "reason": auto_approve_expr}
    
    # 暂停 Pipeline，设置节点为 waiting 状态
    await _db_update_node_sync(run_id, node_def["id"], status=RunStatus.waiting)
    
    # 发送通知（WebSocket / Feishu）
    await notify_review_needed(run_id, node_def, context)
    
    # 创建一个 Future，等待外部 API 回调
    future = asyncio.get_event_loop().create_future()
    _waiting_gates[f"{run_id}:{node_def['id']}"] = future
    
    # 等待（带超时）
    timeout_hours = gate_config.get("timeout_hours", 72)
    result = await asyncio.wait_for(future, timeout=timeout_hours * 3600)
    
    return result
```

**审核 API**:

```
POST /api/v1/novel/pipeline/{run_id}/gate/{node_id}/approve
POST /api/v1/novel/pipeline/{run_id}/gate/{node_id}/reject
```

### 5.4 LLM Batch 调度器

针对长篇小说（1000+ 章节），需要精细控制 LLM 并发：

```python
class LLMBatchScheduler:
    """分批调度 LLM 请求，控制并发和速率"""
    
    def __init__(self, max_concurrency: int = 5, rate_limit_rpm: int = 60):
        self.semaphore = asyncio.Semaphore(max_concurrency)
        self.rate_limiter = TokenBucketRateLimiter(rate_limit_rpm)
    
    async def process_batch(
        self,
        chunks: list[dict],
        handler: Callable,
        on_progress: Callable[[int, int], None] | None = None,
        retry_count: int = 2,
    ) -> list[dict]:
        results = [None] * len(chunks)
        
        async def process_one(idx: int, chunk: dict):
            async with self.semaphore:
                await self.rate_limiter.acquire()
                for attempt in range(retry_count + 1):
                    try:
                        results[idx] = await handler(chunk)
                        if on_progress:
                            on_progress(idx, len(chunks))
                        return
                    except RateLimitError:
                        await asyncio.sleep(2 ** attempt * 10)
                    except Exception as e:
                        if attempt == retry_count:
                            results[idx] = {"error": str(e), "chunk_idx": idx}
                            return
        
        await asyncio.gather(*[process_one(i, c) for i, c in enumerate(chunks)])
        return results
```

### 5.5 Pipeline 上下文与 Artifact 传递

节点间通过 **Pipeline Context** 传递中间结果：

```python
@dataclass
class PipelineContext:
    """Pipeline 执行上下文，节点间共享数据"""
    run_id: int
    params: dict                          # Pipeline 参数
    node_outputs: dict[str, Any] = field(default_factory=dict)  # node_id -> output
    artifacts: dict[str, str] = field(default_factory=dict)     # key -> artifact_path
    
    def get_node_output(self, node_id: str) -> Any:
        return self.node_outputs.get(node_id)
    
    def set_node_output(self, node_id: str, output: Any):
        self.node_outputs[node_id] = output
```

**大型中间结果的处理**:
- 小结果 (<1MB): 直接存入 `node_outputs`（内存）
- 大结果 (>1MB): 序列化到磁盘 `data/artifacts/{run_id}/{node_id}.json`，context 中只存路径
- 这样即使服务重启，也能从 artifact 文件恢复上下文实现断点续传

### 5.6 Checkpoint 与断点续传

```python
class CheckpointManager:
    """Pipeline 断点续传管理"""
    
    async def save_checkpoint(self, run_id: int, context: PipelineContext):
        """保存当前进度到磁盘"""
        checkpoint = {
            "run_id": run_id,
            "params": context.params,
            "completed_nodes": [
                nid for nid, out in context.node_outputs.items()
                if out is not None
            ],
            "artifacts": context.artifacts,
            "timestamp": datetime.utcnow().isoformat(),
        }
        path = f"data/checkpoints/{run_id}.json"
        async with aiofiles.open(path, "w") as f:
            await f.write(json.dumps(checkpoint, ensure_ascii=False))
    
    async def resume_from_checkpoint(self, run_id: int) -> PipelineContext | None:
        """从断点恢复"""
        path = f"data/checkpoints/{run_id}.json"
        if not os.path.exists(path):
            return None
        # 加载 checkpoint，跳过已完成节点
        ...
```

## 6. 新增数据模型

### 6.1 PipelineArtifact（流水线产物）

用于持久化中间和最终结果，支持跨 Pipeline 引用。

```python
class PipelineArtifact(ORMBase):
    __tablename__ = "pipeline_artifacts"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    pipeline_run_id = Column(Integer, ForeignKey("dag_pipeline_runs.id"), nullable=False)
    node_id = Column(String(64), nullable=False)
    artifact_type = Column(String(32), nullable=False)  # json | text | file
    artifact_key = Column(String(128), nullable=False)   # 如 "chapter_chunks", "character_list"
    content = Column(Text, nullable=True)                 # 小型 artifact 直接存储
    file_path = Column(String(256), nullable=True)        # 大型 artifact 的文件路径
    size_bytes = Column(Integer, nullable=True)
    meta_data = Column(JSONB, default={})
    created_at = Column(DateTime, default=datetime.utcnow)
```

### 6.2 HumanReview（人工审核记录）

```python
class HumanReview(ORMBase):
    __tablename__ = "human_reviews"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    pipeline_run_id = Column(Integer, ForeignKey("dag_pipeline_runs.id"), nullable=False)
    node_id = Column(String(64), nullable=False)
    review_type = Column(String(32), nullable=False)    # ingest_confirm | outline_review | final_review
    status = Column(String(16), default="pending")       # pending | approved | rejected | modified
    review_data = Column(JSONB, default={})              # 审核时的上下文数据
    reviewer_notes = Column(Text, nullable=True)          # 审核意见
    modifications = Column(JSONB, nullable=True)          # 修改内容
    reviewed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
```

### 6.3 AnalysisTask ORM 化

将现有的 dataclass 占位符升级为正式 ORM 模型：

```python
class NovelAnalysisTask(ORMBase):
    __tablename__ = "novel_analysis_tasks"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    edition_id = Column(Integer, ForeignKey("editions.id"), nullable=False)
    pipeline_run_id = Column(Integer, ForeignKey("dag_pipeline_runs.id"), nullable=True)
    task_type = Column(String(32), nullable=False)    # character_detect | outline_extract | setting_extract
    scope = Column(String(16), default="full")        # full | partial | incremental
    chunk_start = Column(Integer, nullable=True)       # 处理范围
    chunk_end = Column(Integer, nullable=True)
    status = Column(String(16), default="pending")
    llm_provider = Column(String(32), nullable=True)
    llm_model = Column(String(64), nullable=True)
    input_tokens = Column(Integer, default=0)
    output_tokens = Column(Integer, default=0)
    cost_usd = Column(Float, default=0.0)
    result_summary = Column(JSONB, default={})
    error_message = Column(Text, nullable=True)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
```

## 7. API 设计

### 7.1 Novel Workspace Router

```python
# sail_server/router/novel.py

novel_router = Router(
    path="/novel",
    route_handlers=[
        NovelPipelineController,    # Pipeline 管理
        NovelIngestController,      # 导入相关
        NovelAnalysisController,    # 分析结果 (代理到现有 analysis router)
        NovelCreationController,    # 创作任务
    ],
)
```

### 7.2 核心端点

| 方法 | 路径 | 说明 |
|------|------|------|
| **Pipeline 管理** | | |
| `GET` | `/novel/pipelines` | 列出可用的小说 Pipeline 模板 |
| `POST` | `/novel/pipeline/run` | 触发 Pipeline 运行 |
| `GET` | `/novel/pipeline/run/{id}` | 查询运行状态 |
| `GET` | `/novel/pipeline/run/{id}/sse` | SSE 实时订阅节点状态变化 |
| `POST` | `/novel/pipeline/run/{id}/cancel` | 取消运行 |
| `POST` | `/novel/pipeline/run/{id}/resume` | 从断点恢复 |
| **人工审核** | | |
| `GET` | `/novel/reviews/pending` | 获取待审核列表 |
| `GET` | `/novel/review/{id}` | 获取审核详情（含上下文数据） |
| `POST` | `/novel/review/{id}/approve` | 批准 |
| `POST` | `/novel/review/{id}/reject` | 驳回 |
| `POST` | `/novel/review/{id}/modify` | 修改后批准 |
| **导入** | | |
| `POST` | `/novel/ingest/upload` | 上传 txt 文件到暂存区 |
| `POST` | `/novel/ingest/start` | 触发 Ingest Pipeline |
| **作品概览** | | |
| `GET` | `/novel/work/{id}/dashboard` | 作品分析仪表板数据 |
| `GET` | `/novel/work/{id}/knowledge-graph` | 作品知识图谱数据 |
| **创作** | | |
| `POST` | `/novel/create/outline` | 触发大纲生成 Pipeline |
| `POST` | `/novel/create/draft` | 触发章节草稿生成 |
| `POST` | `/novel/create/rewrite` | 触发章节重写 |

## 8. 前端设计

### 8.1 统一工作台入口

新增页面 `/novel-workspace`，作为小说工作流的统一入口：

```
/novel-workspace
├─ 左侧边栏
│  ├─ 作品列表 (复用 WorksList)
│  ├─ 快捷操作
│  │  ├─ 📥 导入新作品
│  │  ├─ 🔍 分析作品
│  │  └─ ✍️ 创作模式
│  └─ 运行中 Pipeline (迷你状态卡片)
│
├─ 主工作区 (根据模式切换)
│  ├─ [阅读模式]   → ChapterReader (复用)
│  ├─ [分析模式]   → AnalysisDashboard (新)
│  ├─ [Pipeline]   → DAGCanvas (复用) + NodeDetail
│  └─ [创作模式]   → CreationEditor (新)
│
└─ 右侧面板 (上下文)
   ├─ 人物卡片
   ├─ 设定百科
   ├─ 大纲导航
   └─ AI 助手对话
```

### 8.2 Analysis Dashboard（分析仪表板）

展示作品的完整分析结果：

```
┌──────────────────────────────────────────┐
│ 📊 Analysis Dashboard: 诡秘之主          │
├──────────┬──────────┬────────────────────┤
│ 角色 287 │ 设定 156 │ 大纲节点 89        │
├──────────┴──────────┴────────────────────┤
│                                          │
│ [人物关系网络图]      [世界观层级图]      │
│                                          │
│ [大纲时间线]                             │
│                                          │
│ [分析覆盖率]  章节: 1411/1411 (100%)     │
│               人物覆盖: 89%              │
│               设定覆盖: 76%              │
│                                          │
│ [最近分析任务]                           │
│ ✅ 人物检测   2h ago   1411章 → 287人物  │
│ ✅ 大纲提取   3h ago   1411章 → 89节点   │
│ 🔄 设定提取   进行中   856/1411章        │
└──────────────────────────────────────────┘
```

### 8.3 复用策略

| 现有组件 | 在新系统中的角色 |
|----------|-----------------|
| `DAGCanvas` | Pipeline 执行可视化（完全复用） |
| `NodeDetailPanel` | 节点日志和结果查看（完全复用） |
| `RunConfigPanel` | Pipeline 参数配置（扩展 param_schema 渲染） |
| `WorksList` | 作品选择器（复用，添加分析状态标签） |
| `ChapterReader` | 阅读模式 + 证据高亮（扩展高亮功能） |
| `RunHistoryPanel` | 运行历史（完全复用） |

## 9. 文件结构规划

```
sail_server/
├── service/
│   ├── dag_executor.py              # [修改] 添加 handler 注册 + 真实执行
│   ├── dag_pipeline_loader.py       # [不变] Pipeline JSON 加载
│   └── novel/                       # [新增] 小说工作流服务层
│       ├── __init__.py
│       ├── node_registry.py         # 节点 Handler 注册表
│       ├── pipeline_context.py      # Pipeline 上下文管理
│       ├── checkpoint.py            # 断点续传
│       ├── llm_batch.py             # LLM 批量调度器
│       ├── human_gate.py            # 人工审核门控
│       ├── ingest/                  # Ingest Pipeline Handlers
│       │   ├── __init__.py
│       │   ├── probe.py             # 文件探查
│       │   ├── sample.py            # AI 采样分析
│       │   ├── split.py             # 章节切分
│       │   ├── clean.py             # 内容清洗
│       │   ├── anomaly.py           # 异常检测
│       │   └── upload.py            # 批量上传
│       ├── analyze/                 # Analyze Pipeline Handlers
│       │   ├── __init__.py
│       │   ├── prepare.py           # 上下文准备
│       │   ├── character.py         # 人物检测 + 合并
│       │   ├── outline.py           # 大纲提取 + 结构化
│       │   ├── setting.py           # 设定提取 + 合并
│       │   └── evidence.py          # 证据关联
│       ├── enrich/                  # Enrich Pipeline Handlers
│       │   ├── __init__.py
│       │   ├── relation_graph.py    # 关系图谱
│       │   ├── timeline.py          # 时间线
│       │   ├── worldview.py         # 世界观
│       │   └── consistency.py       # 一致性检查
│       └── create/                  # Create Pipeline Handlers
│           ├── __init__.py
│           ├── context_gather.py    # 上下文采集
│           ├── outline_gen.py       # 大纲生成
│           ├── draft_gen.py         # 草稿生成
│           └── style_check.py       # 风格校验
│
├── infrastructure/orm/
│   ├── dag_pipeline.py              # [不变]
│   ├── pipeline_artifact.py         # [新增] 流水线产物
│   ├── human_review.py              # [新增] 人工审核
│   └── novel_analysis_task.py       # [新增] 分析任务 ORM
│
├── controller/
│   └── novel/                       # [新增] 小说工作台 Controller
│       ├── __init__.py
│       ├── pipeline.py              # Pipeline 管理 API
│       ├── ingest.py                # 导入 API
│       ├── review.py                # 审核 API
│       ├── dashboard.py             # 仪表板 API
│       └── creation.py              # 创作 API
│
├── router/
│   └── novel.py                     # [新增] 小说路由汇总
│
└── data/
    ├── pipelines/                   # [新增] Pipeline JSON 定义
    │   ├── novel-ingest.json
    │   ├── novel-analyze.json
    │   ├── novel-enrich.json
    │   └── novel-create.json
    └── artifacts/                   # [新增] Pipeline 产物存储
        └── {run_id}/
            └── {node_id}.json

packages/site/src/
├── pages/
│   └── novel_workspace.tsx          # [新增] 统一工作台页面
├── components/
│   └── novel/                       # [新增] 小说工作台组件
│       ├── WorkSelector.tsx
│       ├── AnalysisDashboard.tsx
│       ├── CreationEditor.tsx
│       ├── ReviewPanel.tsx
│       ├── KnowledgeGraph.tsx
│       └── PipelineMiniCard.tsx
└── lib/
    ├── api/
    │   └── novel.ts                 # [新增] Novel API client
    ├── store/
    │   └── novel_workspace.ts       # [新增] Zustand store
    └── data/
        └── novel.ts                 # [新增] 数据类型定义
```

## 10. 实施路线

### Phase 1: 基础框架 (1-2 周)

**目标**: 打通 Pipeline 真实执行链路

- [ ] 实现 `NodeHandler` 注册机制，替换 mock executor
- [ ] 实现 `PipelineContext` 上下文传递
- [ ] 实现 `PipelineArtifact` ORM + 存储
- [ ] 编写 `novel-ingest.json` Pipeline 定义
- [ ] 迁移 AI Text Import Skill 逻辑到 `service/novel/ingest/` 下的各个 handler
- [ ] 端到端测试：通过 DAG Pipeline 页面触发一次完整的小说导入

### Phase 2: 分析 Pipeline (2-3 周)

**目标**: 三维并行分析跑通

- [ ] 实现 `llm_batch` 节点类型 + `LLMBatchScheduler`
- [ ] 实现人物检测 handler（复用现有 `CharacterDetectionController` 逻辑）
- [ ] 实现大纲提取 handler（复用现有 `OutlineExtractionController` 逻辑）
- [ ] 实现设定提取 handler（复用现有 `SettingExtractionController` 逻辑）
- [ ] 实现 `evidence_link` 和 `quality_report`
- [ ] 编写 `novel-analyze.json` Pipeline 定义
- [ ] 验证三路并行执行正确性

### Phase 3: 人工审核 + 前端 (2 周)

**目标**: Human-in-the-Loop 完善

- [ ] 实现 `HumanGate` + `HumanReview` ORM
- [ ] 实现审核 API 端点
- [ ] 新建 `/novel-workspace` 前端页面
- [ ] 实现 `AnalysisDashboard` 组件
- [ ] 实现 `ReviewPanel` 组件
- [ ] 集成飞书通知（审核提醒推送到飞书）

### Phase 4: 知识增强 + 创作 (3-4 周)

**目标**: 完成 Enrich + Create Pipeline

- [ ] 实现关系图谱构建
- [ ] 实现时间线提取
- [ ] 实现一致性检查
- [ ] 实现创作辅助 Pipeline（大纲生成、草稿、风格校验）
- [ ] 前端 `KnowledgeGraph` 可视化
- [ ] 前端 `CreationEditor` 编辑器

### Phase 5: 断点续传 + 优化 (1-2 周)

**目标**: 生产级稳定性

- [ ] 实现 `CheckpointManager` 断点续传
- [ ] LLM 调用成本追踪和预估
- [ ] Pipeline 运行统计和分析
- [ ] 性能优化：大文件分片上传、数据库查询优化
- [ ] 完善错误处理和日志

## 11. 设计决策记录

### Q: 为什么选择扩展现有 DAG Pipeline 而不是新建系统？

**A**: 
1. DAG Pipeline 已经实现了拓扑排序、并行执行、动态节点、状态持久化
2. 前端 DAG Canvas 可以直接复用，减少前端工作量
3. SSE 实时推送机制已经验证可用
4. 统一架构降低维护成本

### Q: 为什么需要 `llm_batch` 节点类型？

**A**: 
一本 1400 章的小说，如果 10 章一组，需要 140 次 LLM 调用。
串行执行需要 ~70 分钟（每次约 30 秒），5 路并发只需 ~14 分钟。
`llm_batch` 封装了信号量控制、速率限制、失败重试、进度汇报，
让业务代码只需关注单个 chunk 的处理逻辑。

### Q: 人工审核门控怎么避免阻塞 Pipeline 进程？

**A**:
使用 `asyncio.Future` 实现异步等待。Pipeline executor 的事件循环不会被阻塞，
其他 Pipeline 和节点可以继续运行。外部 API 调用 `approve`/`reject` 时，
resolve 对应的 Future。超时后自动 reject。

### Q: OpenCode Session 在创作阶段的角色是什么？

**A**:
创作阶段需要更灵活的 AI 交互（多轮对话、文件编辑、代码执行）。
OpenCode Session 提供了完整的 Agent 环境，可以：
1. 根据人物档案和设定约束生成创作指令
2. 通过 SSE 流实时获取生成进度
3. 让 AI Agent 直接在工作区内编辑和保存文件
Pipeline 的 `opencode` 节点类型会创建一个 Session，发送编排好的 prompt，
通过 SSE 监听完成信号。

**关键设计点**:

1. **`sample` 节点使用 LLM**: 自动识别文本的章节边界模式，替代手工编写正则
2. **`review_gate` 人工闸门**: 如果异常检测通过（0 warnings），自动放行；否则暂停等待人工确认
3. **复用现有 Skill**: `probe` / `split` / `clean` / `anomaly` 的逻辑直接从 `sailzen-ai-text-import` Skill 中提取

### 4.3 Pipeline 2: Analyze (深度分析)

**触发**: Ingest 完成后自动 / 用户手动对已有作品触发

**核心特性**: 三个分析维度（人物 / 大纲 / 设定）**完全并行**执行。

```jsonc
{
  "id": "novel-analyze",
  "name": "深度分析: {title}",
  "description": "对已导入作品进行人物、大纲、设定三维并行分析",
  "params_schema": {
    "edition_id": { "type": "integer", "required": true },
    "title": { "type": "string", "required": true },
    "chunk_size": { "type": "integer", "default": 10 },
    "llm_provider": { "type": "string", "default": "default" }
  },
  "nodes": [
    {
      "id": "prepare",
      "name": "准备分析上下文",
      "type": "builtin",
      "handler": "novel.analyze.prepare_context",
      "description": "加载章节列表，按 chunk_size 分组，生成分析计划",
      "depends_on": []
    },
    {
      "id": "char_detect",
      "name": "人物检测",
      "type": "llm_batch",
      "handler": "novel.analyze.detect_characters",
      "description": "分块扫描全文，提取人物出现及描述",
      "depends_on": ["prepare"],
      "batch_config": {
        "source": "prepare.chapter_chunks",
        "max_concurrency": 5,
        "retry_on_fail": 2
      }
    },
    {
      "id": "char_merge",
      "name": "人物去重合并",
      "type": "llm",
      "handler": "novel.analyze.merge_characters",
      "description": "AI 合并同一人物的不同称呼，建立别名表",
      "depends_on": ["char_detect"]
    },
    {
      "id": "outline_extract",
      "name": "大纲提取",
      "type": "llm_batch",
      "handler": "novel.analyze.extract_outline",
      "description": "分块提取情节摘要和关键事件",
      "depends_on": ["prepare"],
      "batch_config": {
        "source": "prepare.chapter_chunks",
        "max_concurrency": 5,
        "retry_on_fail": 2
      }
    },
    {
      "id": "outline_merge",
      "name": "大纲结构化",
      "type": "llm",
      "handler": "novel.analyze.structure_outline",
      "description": "将分块摘要合并为多层级大纲树",
      "depends_on": ["outline_extract"]
    },
    {
      "id": "setting_extract",
      "name": "设定提取",
      "type": "llm_batch",
      "handler": "novel.analyze.extract_settings",
      "description": "分块提取世界观、物品、地点、组织等设定",
      "depends_on": ["prepare"],
      "batch_config": {
        "source": "prepare.chapter_chunks",
        "max_concurrency": 5,
        "retry_on_fail": 2
      }
    },
    {
      "id": "setting_merge",
      "name": "设定去重合并",
      "type": "llm",
      "handler": "novel.analyze.merge_settings",
      "description": "合并重复设定，建立设定分类体系",
      "depends_on": ["setting_extract"]
    },
    {
      "id": "evidence_link",
      "name": "证据关联",
      "type": "builtin",
      "handler": "novel.analyze.link_evidence",
      "description": "将分析结果回链到原文段落（TextEvidence）",
      "depends_on": ["char_merge", "outline_merge", "setting_merge"]
    },
    {
      "id": "quality_report",
      "name": "分析质量报告",
      "type": "builtin",
      "handler": "novel.analyze.generate_report",
      "description": "统计覆盖率、置信度分布、异常项",
      "depends_on": ["evidence_link"]
    }
  ]
}
```

**并行化设计**:

```
                    prepare
                   /   |   \
                  /    |    \
    char_detect  outline_extract  setting_extract   ← 三路并行
         |            |                |
    char_merge   outline_merge    setting_merge     ← 三路并行
         \            |               /
          \           |              /
              evidence_link                         ← 汇聚
                   |
             quality_report
```

**`llm_batch` 节点类型**: 这是本系统引入的关键新节点类型。

```python
# 一个 llm_batch 节点实际上会动态生成 N 个子任务
# 每个子任务独立调用 LLM，互不依赖
# max_concurrency 控制同时进行的 LLM 调用数（避免 rate limit）

# 伪代码:
async def execute_llm_batch(node_def, context):
    chunks = context[node_def.batch_config.source]
    semaphore = asyncio.Semaphore(node_def.batch_config.max_concurrency)
    
    async def process_chunk(chunk):
        async with semaphore:
            return await call_llm(chunk, node_def.llm_config)
    
    results = await asyncio.gather(
        *[process_chunk(c) for c in chunks]
    )
    return merge_chunk_results(results)
```

### 4.4 Pipeline 3: Enrich (知识增强)

**触发**: Analyze 完成后 / 用户手动触发

```jsonc
{
  "id": "novel-enrich",
  "name": "知识增强: {title}",
  "params_schema": {
    "edition_id": { "type": "integer", "required": true },
    "title": { "type": "string", "required": true }
  },
  "nodes": [
    {
      "id": "relation_graph",
      "name": "关系图谱构建",
      "type": "llm",
      "handler": "novel.enrich.build_relation_graph",
      "description": "基于人物+设定，构建完整关系网络",
      "depends_on": []
    },
    {
      "id": "timeline",
      "name": "时间线构建",
      "type": "llm",
      "handler": "novel.enrich.build_timeline",
      "description": "从大纲事件中提取时间线，区分叙事序和时间序",
      "depends_on": []
    },
    {
      "id": "worldview",
      "name": "世界观图谱",
      "type": "llm",
      "handler": "novel.enrich.build_worldview",
      "description": "设定之间的层级关系和约束规则",
      "depends_on": []
    },
    {
      "id": "consistency",
      "name": "一致性检查",
      "type": "llm",
      "handler": "novel.enrich.check_consistency",
      "description": "跨章节检查人物/设定/时间线矛盾",
      "depends_on": ["relation_graph", "timeline", "worldview"]
    }
  ]
}
```

### 4.5 Pipeline 4: Create (辅助创作)

**触发**: 用户主动发起创作任务

```jsonc
{
  "id": "novel-create",
  "name": "辅助创作: {task_description}",
  "params_schema": {
    "edition_id": { "type": "integer", "required": true },
    "task_type": {
      "type": "string",
      "enum": ["continue", "branch", "rewrite", "expand"]
    },
    "target_chapters": { "type": "array", "items": "integer" },
    "instruction": { "type": "string", "required": true }
  },
  "nodes": [
    {
      "id": "context_gather",
      "name": "上下文采集",
      "type": "builtin",
      "handler": "novel.create.gather_context",
      "description": "收集相关人物档案、设定、前文摘要",
      "depends_on": []
    },
    {
      "id": "outline_gen",
      "name": "大纲生成",
      "type": "llm",
      "handler": "novel.create.generate_outline",
      "description": "基于上下文和指令生成章节大纲",
      "depends_on": ["context_gather"]
    },
    {
      "id": "outline_review",
      "name": "大纲审核",
      "type": "human_gate",
      "handler": "novel.create.review_outline",
      "description": "用户审核并修改大纲",
      "depends_on": ["outline_gen"]
    },
    {
      "id": "draft_gen",
      "name": "草稿生成",
      "type": "llm",
      "handler": "novel.create.generate_draft",
      "description": "按大纲逐段生成草稿",
      "depends_on": ["outline_review"],
      "llm_config": {
        "temperature": 0.8,
        "max_tokens": 8000
      }
    },
    {
      "id": "style_check",
      "name": "风格一致性校验",
      "type": "llm",
      "handler": "novel.create.check_style",
      "description": "对比原文风格，检查语言/节奏/用词一致性",
      "depends_on": ["draft_gen"]
    },
    {
      "id": "final_review",
      "name": "人工审校",
      "type": "human_gate",
      "handler": "novel.create.final_review",
      "description": "最终人工审校和修改",
      "depends_on": ["style_check"]
    }
  ]
}
```
