# LLM驱动的世界观构造系统 - 后端开发设计（Python + FastAPI 方案）

## 0. 概述

本文档基于 `DATA_DESIGN.md` 的数据库方案，给出全部后端设计细节，选用 **Python + FastAPI + Pydantic + SQLAlchemy** 作为核心栈，重点支持“人类标注者 ⇄ LLM 自动化”交替编辑世界观数据的流程。系统目标：
- 为小说文本构建统一的多层结构、知识实体与版本追踪能力；
- 支撑 LLM 批量抽取、人工校验、审阅与回滚；
- 提供细粒度的协作接口，让人类和 LLM 可以在同一上下文中反复迭代；
- 保证审计溯源、权限控制与性能可扩展性。

---

## 1. 技术栈基线

### 1.1 后端核心
- **语言**：Python 3.12+
- **Web 框架**：FastAPI 0.115+，使用 `uvicorn[standard]` 作为 ASGI server；生产建议搭配 `gunicorn`/`uvicorn workers`。
- **数据建模**：SQLAlchemy 2.0（Async ORM 模式，类型提示友好），配合 Alembic 做迁移。
- **数据验证与序列化**：Pydantic v2（`BaseModel` + `pydantic-settings`），通过 `from_attributes=True` 支持 ORM 对象。
- **数据库驱动**：asyncpg（PostgreSQL 异步驱动）。
- **任务队列**：Celery 5.x + Redis（消息中间件），用于文本导入、LLM 调用、批次合并等长耗时操作。
- **认证授权**：PyJWT + OAuth2 Password/Bearer；拓展角色（管理员、审阅者、标注者、LLM 代理账号）。

### 1.2 数据与缓存
- **数据库**：PostgreSQL 15+，启用 `pgcrypto`、`pgvector`（可选）。
- **连接池**：SQLAlchemy async engine 设置 `pool_size=20 / max_overflow=40`，根据部署规模调优。
- **缓存**：Redis 7.x（Celery 共用），缓存热门查询结果与协作状态。
- **对象存储**：MinIO / S3 兼容（存放原始文本、导出文件）。

### 1.3 LLM & 服务
- **LLM 接口**：OpenAI-compatible API（可换成本地模型）；统一封装在 `llm_client.py`。
- **Prompt 管理**：自定义模板 + 版本；存储于数据库或文件（`prompts/*.yaml`）。
- **向量检索**（可选）：结合 `pgvector` 和外部嵌入服务，支撑章节/实体检索。

### 1.4 开发与质量
- **依赖管理**：uv / poetry。
- **代码质量**：ruff（lint），mypy（类型检查），pytest（含 asyncio 支持），coverage 统计。
- **CI/CD**：GitHub Actions / GitLab CI，同步运行 lint、测试、构建镜像。

---

## 2. 架构设计

### 2.1 总体拓扑
```
┌───────────────────────────────────────────────┐
│                    Client                     │
│  Web Console / 标注工具 / LLM Orchestrator    │
└───────────────────────────────────────────────┘
                       │ REST / WebSocket
┌───────────────────────────────────────────────┐
│                FastAPI Application            │
│                                               │
│  ┌─────────────┐  ┌──────────────────────┐    │
│  │ API Layer   │→ │ Collaboration Layer  │    │
│  │ (Routers)   │  │ (Sessions, Diffs,    │    │
│  │             │  │  Workflows)          │    │
│  └─────────────┘  └──────────────────────┘    │
│         │                    │                 │
│  ┌─────────────┐       ┌───────────────┐       │
│  │ Service     │       │ LLM Service   │       │
│  │ Layer       │←Task→ │ (Prompt,      │       │
│  │ (Work/Text/ │       │  Execution)   │       │
│  │ Entity/...) │       └───────────────┘       │
│  └─────────────┘                │              │
│         │                       ▼              │
│  ┌─────────────┐         ┌─────────────┐        │
│  │ Repository  │         │ Audit/Change│        │
│  │ Layer       │         │ Tracker     │        │
│  └─────────────┘         └─────────────┘        │
└───────────────────────────────────────────────┘
                       │ Async tasks
┌───────────────────────────────────────────────┐
│                 Celery Workers                │
│  - 文本导入 & 节点构建                         │
│  - LLM 抽取 & 回写批次                         │
│  - 差异比对、冲突检测                          │
└───────────────────────────────────────────────┘
                       │
┌───────────────────────────────────────────────┐
│                 PostgreSQL + Redis            │
└───────────────────────────────────────────────┘
```

### 2.2 模块职责（聚焦协同编辑）
1. **Collaboration Module**
   - 管理编辑 Session（关联 `annotation_batches`, `change_sets`）。
   - 维护 LLM 建议、人工草稿、冲突状态、时间线。
   - 提供差异计算（基于 `text_spans`、`entities` 的快照对比）。

2. **LLM Assistant Module**
   - 调度 Celery 任务，封装 Prompt、上下文打包、输出解析。
   - 支持“自动写入草稿”或“需要人工确认”两种模式。

3. **Audit & Versioning Module**
   - 对接 `change_sets`, `change_items`, `review_tasks`，确保溯源。
   - 人工通过后再投影到正式表（entities / relations / events）。

4. **Work/Text/Entity Services**
   - 负责基础 CRUD 与查询，支撑协同模块。

5. **Async Workers**
   - 长耗时的文本解析、批量 diff、嵌入生成。

### 2.3 关键数据流
- **LLM 建议流**：用户或系统创建 Session → 选择节点/实体 → 触发 LLM 任务 → 生成 `annotation_batch (batch_type='llm_suggestion')` → 前端展示 diff → 人工选择接受/拒绝 → 生成 `change_set`。
- **人工编辑流**：编辑器直接创建草稿 → `annotation_batch (batch_type='human_draft')` → 可请求 LLM 校对 → 组合成 `change_set` → 审核。
- **冲突解决**：同一资源存在多个草稿/建议 → Collaboration Module 聚合 → 需人工合并后才允许提交。
- **回滚/追溯**：任何变更都在 `change_sets` 中，允许创建逆向 change_set。

---

## 3. 协同编辑业务流程

### 3.1 Session 生命周期

1. **创建**：`POST /collab/sessions`，关联 edition / node / entity + 创建者角色。
2. **上下文准备**：读取目标文本、关联知识（entities, relations）。
3. **草稿阶段**：
   - 人工提交草稿：`POST /collab/sessions/{id}/drafts`
   - 请求 LLM 建议：`POST /collab/sessions/{id}/llm-suggestions`
4. **对比与讨论**：
   - 获取差异视图：`GET /collab/sessions/{id}/diff`
   - 留言讨论：`POST /collab/sessions/{id}/comments`
5. **合并**：选择草稿/建议生成 `change_set`（`POST /collab/sessions/{id}/commit`）。
6. **审核**：触发 `review_task`，通过/拒绝。
7. **发布/归档**：
   - 应用变更：`PUT /change-sets/{id}/apply`
   - 归档 session：`POST /collab/sessions/{id}/close`

### 3.2 人 ⇄ LLM 交互模式
- **模式 A：LLM 先行，人工审核**：LLM 生成建议 → 人类审核 → 接受或手动改写。
- **模式 B：人工起草，LLM 校对**：人类草稿 → LLM 自动校验规范性/补充引用 → 形成完整 change_set。
- **模式 C：协同对话**：以 Session 为中心多轮交互，通过评论流保存结论。

### 3.3 冲突检测与处理
- 同一 `target_id` 多个草稿 → Collaboration Module 将其标记为 `state='needs_merge'`。
- 通过 diff 对比（基于 `document_nodes.raw_text`、`entities` 属性）生成冲突列表。
- 提供 `/collab/sessions/{id}/conflicts` API 返回冲突详情，并支持选择保留版本。

### 3.4 权限与锁
- Session 级别锁：`lock_scope` 可选 `node/entity/span`。
- 行为约束：
  - 标注者可创建草稿、请求 LLM。
  - 审核者可生成 change_set / 提交 review。
  - 管理员可强制合并或关闭 session。
- Redis 实现乐观锁 + 过期时间，防止资源长期锁定。

---

## 4. REST API 设计

### 4.1 基础约定
- **Base URL**：`/api/v1`
- **认证**：OAuth2 Bearer；支持“LLM 代理”类型 token（只读 / 仅限草稿写入）。
- **分页**：`page/page_size`，默认每页 20。
- **响应包装**：
```json
{
  "data": {...},
  "meta_data": {"page":1,"page_size":20,"total":100},
  "trace_id": "req-uuid"
}
```
- **错误格式**：
```json
{
  "error": {
    "code": "COLLAB_CONFLICT",
    "message": "Session has conflicts",
    "details": {...}
  }
}
```

### 4.2 核心资源 API（概览）
> 详尽参数见附录 Swagger（自动生成）。

#### 4.2.1 世界观 / 作品 / 版本
```
GET    /universes
POST   /universes
GET    /works
POST   /works
GET    /works/{id}/editions
POST   /editions
POST   /editions/{id}/upload
POST   /editions/{id}/ingest
```

#### 4.2.2 文本节点 & 跨度
```
GET    /editions/{id}/nodes              # 支持 tree_flat/tree_full 模式
GET    /nodes/{node_id}
GET    /nodes/{node_id}/text
GET    /nodes/{node_id}/children
GET    /nodes/{node_id}/spans
POST   /nodes/{node_id}/spans            # 人工新增跨度
```

#### 4.2.3 实体 / 关系 / 事件
```
GET    /entities?edition_id=...&type=...
POST   /entities
GET    /entities/{id}/mentions
GET    /relations
POST   /relations
GET    /events
POST   /events
```

### 4.3 协同编辑 API（新增重点）

#### 4.3.1 Session 管理
```
POST   /collab/sessions
    body: {
      "target_type": "node|entity|relation|event",
      "target_id": "uuid",
      "edition_id": "uuid",
      "lock_scope": "node",
      "meta_data": {...}
    }
GET    /collab/sessions?target_id=...
GET    /collab/sessions/{id}
POST   /collab/sessions/{id}/close
```

#### 4.3.2 草稿与建议
```
POST   /collab/sessions/{id}/drafts
    body: {
      "source": "human",
      "payload": {...},           # 对应 annotation_items payload
      "span_ids": [...],
      "notes": "..."
    }
POST   /collab/sessions/{id}/llm-suggestions
    body: {
      "prompt_template": "entity_refine",
      "parameters": {...},
      "auto_commit": false
    }
GET    /collab/sessions/{id}/drafts
GET    /collab/sessions/{id}/llm-suggestions
POST   /collab/sessions/{session_id}/drafts/{draft_id}/promote
    → 生成新的 annotation_batch (status='ready_for_commit')
```

#### 4.3.3 Diff / 冲突 / 留言
```
GET    /collab/sessions/{id}/diff?baseline=latest_applied
POST   /collab/sessions/{id}/resolve-conflicts
POST   /collab/sessions/{id}/comments
GET    /collab/sessions/{id}/timeline
```

#### 4.3.4 Commit & 审核
```
POST   /collab/sessions/{id}/commit
    body: {
      "draft_ids": [...],
      "llm_suggestion_ids": [...],
      "commit_message": "..."
    }
GET    /change-sets?session_id=...
POST   /review-tasks/{id}/approve
POST   /review-tasks/{id}/reject
PUT    /change-sets/{id}/apply
PUT    /change-sets/{id}/rollback
```

### 4.4 示例：人类草稿 + LLM 辅助
1. **创建 Session**：
```http
POST /api/v1/collab/sessions
{
  "target_type": "entity",
  "target_id": "b3c...",
  "edition_id": "e12...",
  "lock_scope": "entity"
}
```
→ 返回 `session_id`

2. **人工草稿**：
```http
POST /api/v1/collab/sessions/{session}/drafts
{
  "source": "human",
  "payload": {
    "entity": {
      "canonical_name": "孙悟空",
      "entity_type": "character",
      "attributes": [
        {"key": "title", "value": "齐天大圣"}
      ]
    }
  }
}
```

3. **LLM 校对**：
```http
POST /api/v1/collab/sessions/{session}/llm-suggestions
{
  "prompt_template": "entity_consistency",
  "parameters": {
    "check_alias": true,
    "style": "formal"
  }
}
```

4. **查看 Diff 与合并**：
```http
GET /api/v1/collab/sessions/{session}/diff
POST /api/v1/collab/sessions/{session}/commit
```
→ 生成 change_set，进入审核流程。

---

## 5. 实现细节（Python + FastAPI + SQLAlchemy）

### 5.1 项目结构
```
sailzen/
├── src/
│   ├── api/
│   │   ├── main.py
│   │   ├── dependencies.py
│   │   ├── middleware.py
│   │   └── routes/
│   │       ├── works.py
│   │       ├── editions.py
│   │       ├── nodes.py
│   │       ├── entities.py
│   │       ├── collab_sessions.py   # 协同接口
│   │       ├── change_sets.py
│   │       └── search.py
│   ├── core/
│   │   ├── config.py
│   │   ├── database.py
│   │   ├── security.py
│   │   └── logging.py
│   ├── models/
│   │   ├── base.py                  # SQLAlchemy Base
│   │   ├── work.py
│   │   ├── edition.py
│   │   ├── document_node.py
│   │   ├── entity.py
│   │   ├── annotation.py
│   │   ├── change_set.py
│   │   └── collab_session.py        # SQLAlchemy 映射（可选视图/模型）
│   ├── schemas/
│   │   ├── work.py
│   │   ├── edition.py
│   │   ├── collab.py
│   │   └── common.py
│   ├── repositories/
│   │   ├── base.py
│   │   ├── works.py
│   │   ├── editions.py
│   │   ├── collab_sessions.py
│   │   └── change_sets.py
│   ├── services/
│   │   ├── works_service.py
│   │   ├── text_service.py
│   │   ├── entity_service.py
│   │   ├── collab_service.py
│   │   ├── llm_service.py
│   │   └── audit_service.py
│   ├── workers/
│   │   ├── celery_app.py
│   │   ├── ingest_worker.py
│   │   ├── llm_worker.py
│   │   └── diff_worker.py
│   └── utils/
│       ├── diff.py
│       ├── prompt.py
│       ├── pagination.py
│       └── permissions.py
├── alembic/
└── tests/
```

### 5.2 配置（core/config.py）
```python
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="SAILZEN_")

    app_name: str = "sailzen-api"
    debug: bool = False
    database_url: str
    redis_url: str
    jwt_secret: str
    jwt_algorithm: str = "HS256"
    llm_endpoint: str
    llm_api_key: str | None = None
    max_llm_concurrency: int = 4

settings = Settings()
```

### 5.3 数据访问层（示例）
```python
from typing import Sequence, Optional
from uuid import UUID
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from models.annotation import AnnotationBatch
from models.collab_session import CollaborationSession

class CollaborationRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_session(
        self,
        edition_id: UUID,
        target_type: str,
        target_id: UUID,
        created_by: UUID,
        lock_scope: str,
        meta_data: dict | None = None,
    ) -> CollaborationSession:
        obj = CollaborationSession(
            edition_id=edition_id,
            target_type=target_type,
            target_id=target_id,
            created_by=created_by,
            lock_scope=lock_scope,
            meta_data=meta_data or {},
        )
        self.session.add(obj)
        await self.session.flush()
        return obj

    async def list_session_batches(
        self,
        session_id: UUID,
        batch_type: str | None = None
    ) -> Sequence[AnnotationBatch]:
        stmt = select(AnnotationBatch).where(AnnotationBatch.session_id == session_id)
        if batch_type:
            stmt = stmt.where(AnnotationBatch.batch_type == batch_type)
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def mark_session_state(
        self,
        session_id: UUID,
        state: str,
        reason: str | None = None
    ) -> None:
        await self.session.execute(
            update(CollaborationSession)
            .where(CollaborationSession.id == session_id)
            .values(state=state, state_reason=reason)
        )
```

### 5.4 服务层（collab_service.py）
```python
from uuid import UUID
from typing import Sequence
from sqlalchemy.ext.asyncio import AsyncSession
from repositories.collab_sessions import CollaborationRepository
from repositories.annotation_batches import AnnotationBatchRepository
from schemas.collab import SessionCreate, SessionDetail, DraftCreate
from core.exceptions import ConflictError, NotFoundError

class CollaborationService:
    def __init__(self, session: AsyncSession):
        self.repo = CollaborationRepository(session)
        self.batch_repo = AnnotationBatchRepository(session)

    async def create_session(self, payload: SessionCreate) -> SessionDetail:
        # 检查是否已有活跃 Session 锁住资源
        exists = await self.repo.find_active_session(
            target_type=payload.target_type,
            target_id=payload.target_id
        )
        if exists:
            raise ConflictError("Resource already locked by session")

        session_obj = await self.repo.create_session(
            edition_id=payload.edition_id,
            target_type=payload.target_type,
            target_id=payload.target_id,
            created_by=payload.created_by,
            lock_scope=payload.lock_scope,
            meta_data=payload.meta_data,
        )
        return SessionDetail.model_validate(session_obj)

    async def create_draft(self, session_id: UUID, payload: DraftCreate):
        session_obj = await self.repo.get_session(session_id)
        if not session_obj:
            raise NotFoundError("Session not found")
        if session_obj.state != "active":
            raise ConflictError("Session is not active")

        batch = await self.batch_repo.create_annotation_batch(
            edition_id=session_obj.edition_id,
            session_id=session_id,
            batch_type="human_draft",
            source=payload.source,
            payload=payload.payload,
            created_by=payload.created_by,
        )
        return batch
```

### 5.5 LLM 任务（workers/llm_worker.py）
```python
from celery import shared_task
from uuid import UUID
from services.llm_service import LLMService
from services.collab_service import CollaborationService
from core.database import async_session

@shared_task(name="collab.generate_llm_suggestion")
def generate_llm_suggestion(session_id: str, batch_id: str):
    async def _run():
        async with async_session() as db:
            collab_service = CollaborationService(db)
            llm_service = LLMService(db)
            suggestion = await llm_service.generate_suggestion(
                session_id=UUID(session_id),
                batch_id=UUID(batch_id)
            )
            await db.commit()
            return suggestion

    import asyncio
    return asyncio.run(_run())
```

### 5.6 差异计算（utils/diff.py）
```python
import difflib
from typing import Sequence

def compute_text_diff(original: str, candidate: str) -> list[dict]:
    diff = difflib.unified_diff(
        original.splitlines(),
        candidate.splitlines(),
        lineterm=""
    )
    return [
        {"line": line, "type": line[:1]}  # -, +,  空格
        for line in diff
    ]

def compute_entity_diff(original: dict, candidate: dict) -> dict:
    return {
        "attributes_added": list(set(candidate.get("attributes", [])) - set(original.get("attributes", []))),
        "attributes_removed": list(set(original.get("attributes", [])) - set(candidate.get("attributes", []))),
    }
```

---

## 6. LLM 集成与提示管理

### 6.1 Prompt 模板
- 存储于 `prompts/*.yaml`，结构：
```yaml
name: entity_consistency
input_schema:
  target_entity_id: uuid
  context_spans: list
system: |
  你是世界观知识库助手，要检查实体字段一致性...
user: |
  实体信息：{{ entity_json }}
  相关文本：{{ context_text }}
output_schema:
  suggested_changes: list
  confidence: float
```
- 通过 Pydantic 验证 input/output，避免 LLM 输出不规范。

### 6.2 LLMService
```python
class LLMService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def generate_suggestion(self, session_id: UUID, batch_id: UUID):
        batch = await self.batch_repo.get(batch_id)
        context = await self.build_context(session_id)
        prompt = render_prompt(batch, context)
        response = await self.llm_client.complete(prompt)
        parsed = self.parser.parse(response)
        await self.batch_repo.attach_llm_output(batch_id, parsed)
        return parsed
```

### 6.3 并发与速率限制
- 使用 `asyncio.Semaphore` 控制同时调用数量（与配置 `max_llm_concurrency` 对应）。
- Celery 任务队列按 `llm` 队列分流，可动态扩容 worker。
- 记录每次调用耗时、成本，写入 `llm_invocations` 日志表（可选）。

---

## 7. 数据一致性与审核保障

### 7.1 Session ↔ Annotation ↔ ChangeSet 映射
- `collab_sessions`（业务视图/表）
  - `id`, `edition_id`, `target_type`, `target_id`, `state`, `lock_scope`, `meta_data`。
- `annotation_batches`
  - `session_id` 外键，`batch_type`：`human_draft` / `llm_suggestion` / `merged`。
- `annotation_items`
  - 附加 `source='human' | 'llm'`，保留原始 payload。
- `change_sets`
  - `session_id` 外键，`source='collaboration_commit'`。

### 7.2 审核流
1. `commit` 时生成 change_set（draft + suggestion 合并）。
2. 自动创建 `review_task`，通知审核者。
3. 审核通过后执行 `apply` → 更新真正实体/关系表。
4. 审核拒绝 → change_set 标记失败，session 回到 `active`，允许继续编辑。

### 7.3 并发保护
- Session 状态与锁写入 Redis，key 结构：`collab:lock:{target_type}:{target_id}`。
- `SETNX` + TTL，防止死锁。
- 事务级别采用 PostgreSQL `SERIALIZABLE` 或 `REPEATABLE READ` 以防止脏写。

### 7.4 追溯
- 每次 commit 记录 `change_items`。
- 提供 `/audit/logs?target_id=` API 聚合历史。
- 可导出 Session 时间线：草稿→建议→审阅→应用。

---

## 8. 异步任务与调度

### 8.1 Celery 队列划分
- `ingest`：文本导入与节点构建。
- `llm`：LLM 调用、批处理。
- `diff`：大规模 diff、冲突检测。

### 8.2 任务示例
```python
@celery_app.task(name="diff.compute")
def compute_diff_task(session_id: str):
    async def _run():
        async with async_session() as db:
            service = CollaborationService(db)
            await service.refresh_diff(UUID(session_id))
            await db.commit()
    import asyncio
    asyncio.run(_run())
```

### 8.3 定时任务
- `beat` 计划：
  - 每小时扫描 `annotation_batches`，对 `pending_review` 状态发通知。
  - 每日刷新 `node_rollups`, `span_rollups`。
  - 定期回收过期 Session（长时间未活动自动关闭）。

---

## 9. 测试策略与质量保障

### 9.1 单元测试
- 使用 pytest + pytest-asyncio。
- 对 Service 层 Mock Repository，验证业务逻辑（特别是合并/冲突场景）。

### 9.2 集成测试
- 利用 `httpx.AsyncClient` + FastAPI TestClient，覆盖 API。
- 启动临时 PostgreSQL + Redis（例如 `pytest-docker`）。
- 针对协同流程：创建 session → 草稿 → LLM 建议（Mock LLM）→ commit → 审核。

### 9.3 端到端测试
- 可选使用 Playwright 结合前端 UI 自动化。
- 验证锁机制、状态刷新、通知。

### 9.4 质量指标
- 变更回归测试：对 change_set 应用/回滚做快照比对。
- LLM 输出校验：正则 / JSON schema 检验。
- 性能基准：
  - 文本导入 1e6 字以内保持 < 5 分钟。
  - 协同接口 p95 < 200ms。

---

## 10. 部署与运维

### 10.1 环境
- **容器化**：Dockerfile（多阶段构建：依赖→代码→运行）。
- **编排**：Docker Compose / Kubernetes。
- **服务划分**：
  - `api`（FastAPI）
  - `worker`（Celery）
  - `beat`（Celery Beat）
  - `db`（PostgreSQL）
  - `redis`

### 10.2 配置示例（docker-compose.yml 片段）
```yaml
services:
  api:
    build: .
    environment:
      SAILZEN_DATABASE_URL: postgresql+asyncpg://...
      SAILZEN_REDIS_URL: redis://redis:6379/0
      SAILZEN_LLM_ENDPOINT: https://...
    depends_on:
      - db
      - redis
  worker:
    build: .
    command: celery -A src.workers.celery_app worker -Q ingest,llm,diff
    depends_on:
      - api
      - redis
  beat:
    build: .
    command: celery -A src.workers.celery_app beat
```

### 10.3 监控
- **Metrics**：Prometheus + FastAPI Instrumentation，关注请求耗时、任务队列长度。
- **Tracing**：OpenTelemetry（OTLP → Jaeger）。
- **日志**：结构化 JSON 日志，包含 `session_id / change_set_id / request_id`。
- **告警**：ChangeSet 审核超时、Session 长时间锁定、LLM 调用失败率上升。

---

## 12. 总结

- 体系采用 Python + FastAPI + Pydantic + SQLAlchemy，结合 Celery/Redis 与 PostgreSQL。
- 核心亮点在于 **协同编辑 Session 模型**：LLM 建议与人工草稿统一在 `annotation_batches` / `change_sets` 框架下，保持数据一致性。
- 完整封装了 Session 生命周期、差异/冲突处理、审核发布的 API。
- LLM 集成可替换为自托管模型，同时保留并发控制、输出约束机制。
- 路线图循序渐进，先上线基础管理与 Session MVP，再增强 LLM 协作与审计能力。

系统在保证溯源和审核的前提下，让人类与 LLM 能够高效协同，持续构建高质量的世界观知识库。

