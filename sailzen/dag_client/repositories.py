"""Repository 层 — 各实体的异步 CRUD 操作。

所有数据库操作通过 Repository 类封装，对外暴露 dict 接口（兼容旧代码），
内部使用 SQLAlchemy ORM 进行类型安全的查询。

Repository 统一入口:
  repos = Repositories(db)
  project = await repos.project.upsert(data)
  tasks = await repos.task.get_by_batch(batch_id)

向后兼容:
  为了让 scheduler.py / app.py 的迁移代价最小，
  提供了 DatabaseCompat 类，保持 db.upsert_project() 等老接口签名，
  内部委托给 Repository 实现。
"""

from __future__ import annotations

import logging
import os
from typing import Any, Dict, List, Optional

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from bot_server.database import Database
from bot_server.models import (
    # ORM models
    DBProject, DBWorkspace, DBBatch, DBSubBatch, DBTask, DBTaskRun,
    DBAgent, DBSession, DBEventLog, DBMessage, DBSnapshot,
    # Conversion helpers
    orm_to_dict, dict_to_orm, _json_encode, _json_decode, _JSON_FIELDS,
    # Helpers
    now_iso, TaskStatus, TaskRunStatus,
)

logger = logging.getLogger(__name__)


# Task runtime transitions must be monotonic.  A smaller rank must never be
# written over a larger rank by a stale runner snapshot.
_TASK_STATUS_RANK = {
    TaskStatus.PENDING.value: 0,
    TaskStatus.QUEUED.value: 1,
    TaskStatus.ASSIGNED.value: 2,
    TaskStatus.RUNNING.value: 3,
    TaskStatus.SUCCESS.value: 4,
    TaskStatus.FAILED.value: 4,
    TaskStatus.BLOCKED.value: 4,
    TaskStatus.CANCELLED.value: 4,
    TaskStatus.SUPERSEDED.value: 4,
}
_TASK_TERMINAL_STATUSES = {
    TaskStatus.SUCCESS.value,
    TaskStatus.FAILED.value,
    TaskStatus.BLOCKED.value,
    TaskStatus.CANCELLED.value,
    TaskStatus.SUPERSEDED.value,
}


# ═══════════════════════════════════════════════════════════════════════


class BaseRepository:
    """Repository 基类，持有 Database 引用。"""

    def __init__(self, db: Database):
        self._db = db

    def _session(self) -> AsyncSession:
        return self._db.session()


# ═══════════════════════════════════════════════════════════════════════
#  ProjectRepository
# ═══════════════════════════════════════════════════════════════════════


class ProjectRepository(BaseRepository):

    async def upsert(self, data: dict) -> dict:
        async with self._session() as session:
            obj = dict_to_orm(DBProject, data)
            merged = await session.merge(obj)
            await session.commit()
            return orm_to_dict(merged)

    async def get(self, project_id: str) -> Optional[dict]:
        async with self._session() as session:
            result = await session.get(DBProject, project_id)
            return orm_to_dict(result) if result else None

    async def get_all(self) -> List[dict]:
        async with self._session() as session:
            result = await session.execute(
                select(DBProject).order_by(DBProject.created_at)
            )
            return [orm_to_dict(r) for r in result.scalars().all()]


# ═══════════════════════════════════════════════════════════════════════
#  WorkspaceRepository
# ═══════════════════════════════════════════════════════════════════════


class WorkspaceRepository(BaseRepository):

    async def upsert(self, data: dict) -> dict:
        async with self._session() as session:
            obj = dict_to_orm(DBWorkspace, data)
            merged = await session.merge(obj)
            await session.commit()
            return orm_to_dict(merged)

    async def get(self, ws_id: str) -> Optional[dict]:
        async with self._session() as session:
            result = await session.get(DBWorkspace, ws_id)
            return orm_to_dict(result) if result else None

    async def get_by_project(self, project_id: str) -> List[dict]:
        async with self._session() as session:
            result = await session.execute(
                select(DBWorkspace)
                .where(DBWorkspace.project_id == project_id)
                .order_by(DBWorkspace.created_at)
            )
            return [orm_to_dict(r) for r in result.scalars().all()]


# ═══════════════════════════════════════════════════════════════════════
#  BatchRepository
# ═══════════════════════════════════════════════════════════════════════


class BatchRepository(BaseRepository):

    async def upsert(self, data: dict) -> dict:
        async with self._session() as session:
            obj = dict_to_orm(DBBatch, data)
            merged = await session.merge(obj)
            await session.commit()
            return orm_to_dict(merged)

    async def get(self, batch_id: str) -> Optional[dict]:
        async with self._session() as session:
            result = await session.get(DBBatch, batch_id)
            return orm_to_dict(result) if result else None

    async def get_all(
        self,
        workspace_id: Optional[str] = None,
        status: Optional[str] = None,
        lifecycle: Optional[str] = None,
    ) -> List[dict]:
        async with self._session() as session:
            stmt = select(DBBatch)
            if workspace_id:
                stmt = stmt.where(DBBatch.workspace_id == workspace_id)
            if status:
                stmt = stmt.where(DBBatch.status == status)
            if lifecycle:
                stmt = stmt.where(DBBatch.lifecycle == lifecycle)
            stmt = stmt.order_by(DBBatch.created_at.desc())
            result = await session.execute(stmt)
            return [orm_to_dict(r) for r in result.scalars().all()]

    async def update_status(self, batch_id: str, status: str, **kwargs: Any) -> None:
        async with self._session() as session:
            obj = await session.get(DBBatch, batch_id)
            if not obj:
                return
            obj.status = status
            for key, value in kwargs.items():
                if key in _JSON_FIELDS:
                    value = _json_encode(value)
                attr_name = "metadata_" if key == "metadata" else key
                setattr(obj, attr_name, value)
            await session.commit()


# ═══════════════════════════════════════════════════════════════════════
#  SubBatchRepository
# ═══════════════════════════════════════════════════════════════════════


class SubBatchRepository(BaseRepository):

    async def upsert(self, data: dict) -> dict:
        async with self._session() as session:
            obj = dict_to_orm(DBSubBatch, data)
            merged = await session.merge(obj)
            await session.commit()
            return orm_to_dict(merged)

    async def get(self, sb_id: str) -> Optional[dict]:
        async with self._session() as session:
            result = await session.get(DBSubBatch, sb_id)
            return orm_to_dict(result) if result else None

    async def get_by_batch(self, batch_id: str) -> List[dict]:
        async with self._session() as session:
            result = await session.execute(
                select(DBSubBatch)
                .where(DBSubBatch.batch_id == batch_id)
                .order_by(DBSubBatch.index_num)
            )
            return [orm_to_dict(r) for r in result.scalars().all()]

    async def update_status(self, sb_id: str, status: str) -> None:
        async with self._session() as session:
            obj = await session.get(DBSubBatch, sb_id)
            if not obj:
                return
            obj.status = status
            obj.updated_at = now_iso()
            await session.commit()


# ═══════════════════════════════════════════════════════════════════════
#  TaskRepository
# ═══════════════════════════════════════════════════════════════════════


class TaskRepository(BaseRepository):

    def _merge_runtime_safe_task(self, existing: dict, incoming: dict) -> dict:
        """Merge task rows without letting stale snapshots move runtime state backwards.

        `upsert_task` is used while building the DAG and by some legacy/debug paths.
        During execution it must not be able to overwrite a newer runtime state such
        as success/running with an older detached dict such as pending/queued.
        """
        if not existing:
            return dict(incoming)

        merged = dict(incoming)
        existing_status = existing.get("status")
        incoming_status = incoming.get("status")
        existing_rank = _TASK_STATUS_RANK.get(existing_status, -1)
        incoming_rank = _TASK_STATUS_RANK.get(incoming_status, -1)
        if existing_status and (incoming_status is None or incoming_rank < existing_rank):
            merged["status"] = existing_status

        for key in ("created_at", "queued_at", "started_at", "completed_at"):
            value = existing.get(key) or incoming.get(key)
            if value is not None:
                merged[key] = value
        for key in ("result", "error"):
            if existing.get(key) is not None:
                merged[key] = existing.get(key)
            elif incoming.get(key) is not None:
                merged[key] = incoming.get(key)
        return merged

    async def upsert(self, data: dict) -> dict:
        async with self._session() as session:
            existing_obj = None
            existing_data: Optional[dict] = None
            if data.get("id"):
                existing_obj = await session.get(DBTask, data["id"])
                if existing_obj:
                    existing_data = orm_to_dict(existing_obj)
            data_to_write = self._merge_runtime_safe_task(existing_data or {}, data)

            values: Dict[str, Any] = {}
            for col in DBTask.__table__.columns:
                key = col.key
                if key not in data_to_write:
                    continue
                val = data_to_write[key]
                if key in _JSON_FIELDS:
                    val = _json_encode(val)
                attr_name = "metadata_" if key == "metadata" else key
                values[attr_name] = val

            if existing_obj:
                for attr_name, value in values.items():
                    setattr(existing_obj, attr_name, value)
                await session.commit()
                await session.refresh(existing_obj)
                return orm_to_dict(existing_obj)

            obj = dict_to_orm(DBTask, data_to_write)
            session.add(obj)
            await session.commit()
            await session.refresh(obj)
            return orm_to_dict(obj)

    async def get(self, task_id: str) -> Optional[dict]:
        async with self._session() as session:
            result = await session.get(DBTask, task_id)
            return orm_to_dict(result) if result else None

    async def get_all(
        self,
        sub_batch_id: Optional[str] = None,
        status: Optional[str] = None,
        task_type: Optional[str] = None,
    ) -> List[dict]:
        async with self._session() as session:
            stmt = select(DBTask)
            if sub_batch_id:
                stmt = stmt.where(DBTask.sub_batch_id == sub_batch_id)
            if status:
                stmt = stmt.where(DBTask.status == status)
            if task_type:
                stmt = stmt.where(DBTask.type == task_type)
            stmt = stmt.order_by(DBTask.priority.asc(), DBTask.created_at.asc())
            result = await session.execute(stmt)
            return [orm_to_dict(r) for r in result.scalars().all()]

    async def get_by_batch(self, batch_id: str) -> List[dict]:
        async with self._session() as session:
            result = await session.execute(
                select(DBTask)
                .join(DBSubBatch, DBTask.sub_batch_id == DBSubBatch.id)
                .where(DBSubBatch.batch_id == batch_id)
                .order_by(DBTask.priority.asc(), DBTask.created_at.asc())
            )
            return [orm_to_dict(r) for r in result.scalars().all()]

    async def update_status(
        self,
        task_id: str,
        status: str,
        *,
        expected_statuses: Optional[List[str]] = None,
        force: bool = False,
        **kwargs: Any,
    ) -> bool:
        async with self._session() as session:
            existing = await session.get(DBTask, task_id)
            if not existing:
                return False
            if expected_statuses is not None and existing.status not in expected_statuses:
                return False
            if not force:
                current_rank = _TASK_STATUS_RANK.get(existing.status, -1)
                target_rank = _TASK_STATUS_RANK.get(status, -1)
                if existing.status in _TASK_TERMINAL_STATUSES and existing.status != status:
                    logger.warning(
                        "Refuse task terminal-state overwrite: task=%s current=%s target=%s",
                        task_id[:8], existing.status, status,
                    )
                    return False
                if target_rank < current_rank:
                    logger.warning(
                        "Refuse task status regression: task=%s current=%s target=%s",
                        task_id[:8], existing.status, status,
                    )
                    return False
            elif existing.status != status:
                logger.info(
                    "[update_status] forced override: task=%s current=%s target=%s",
                    task_id[:8], existing.status, status,
                )
            existing.status = status
            for k, v in kwargs.items():
                if k in _JSON_FIELDS:
                    v = _json_encode(v)
                attr_name = "metadata_" if k == "metadata" else k
                setattr(existing, attr_name, v)
            await session.commit()
            logger.info("[update_status] task=%s commit ok status=%s kwargs=%s",task_id[:8], status, list(kwargs.keys()))
            return True

    async def transition_status(
        self,
        task_id: str,
        from_statuses: List[str],
        to_status: str,
        **kwargs: Any,
    ) -> bool:
        return await self.update_status(
            task_id,
            to_status,
            expected_statuses=from_statuses,
            **kwargs,
        )

    async def queue_pending(self, task_id: str, **kwargs: Any) -> bool:
        return await self.transition_status(
            task_id,
            [TaskStatus.PENDING.value],
            TaskStatus.QUEUED.value,
            **kwargs,
        )

    async def complete_running(self, task_id: str, success: bool, **kwargs: Any) -> bool:
        target = TaskStatus.SUCCESS.value if success else kwargs.pop("failure_status", TaskStatus.BLOCKED.value)
        return await self.transition_status(
            task_id,
            [TaskStatus.RUNNING.value, TaskStatus.ASSIGNED.value],
            target,
            **kwargs,
        )

    async def claim_queued(self, task_id: str, **kwargs: Any) -> bool:
        async with self._session() as session:
            existing = await session.get(DBTask, task_id)
            if not existing or existing.status != TaskStatus.QUEUED.value:
                return False
            existing.status = TaskStatus.RUNNING.value
            for k, v in kwargs.items():
                if k in _JSON_FIELDS:
                    v = _json_encode(v)
                attr_name = "metadata_" if k == "metadata" else k
                setattr(existing, attr_name, v)
            await session.commit()
            return True


# ═══════════════════════════════════════════════════════════════════════
#  AgentRepository
# ═══════════════════════════════════════════════════════════════════════


class AgentRepository(BaseRepository):

    async def upsert(self, data: dict) -> dict:
        async with self._session() as session:
            obj = dict_to_orm(DBAgent, data)
            merged = await session.merge(obj)
            await session.commit()
            return orm_to_dict(merged)

    async def get(self, agent_id: str) -> Optional[dict]:
        async with self._session() as session:
            result = await session.get(DBAgent, agent_id)
            return orm_to_dict(result) if result else None

    async def get_all(self, status: Optional[str] = None) -> List[dict]:
        async with self._session() as session:
            stmt = select(DBAgent)
            if status:
                stmt = stmt.where(DBAgent.status == status)
            stmt = stmt.order_by(DBAgent.registered_at)
            result = await session.execute(stmt)
            return [orm_to_dict(r) for r in result.scalars().all()]

    async def update_status(self, agent_id: str, status: str, **kwargs: Any) -> None:
        async with self._session() as session:
            obj = await session.get(DBAgent, agent_id)
            if not obj:
                return
            obj.status = status
            for key, value in kwargs.items():
                if key in _JSON_FIELDS:
                    value = _json_encode(value)
                attr_name = "metadata_" if key == "metadata" else key
                setattr(obj, attr_name, value)
            await session.commit()


# ═══════════════════════════════════════════════════════════════════════
#  SessionRepository
# ═══════════════════════════════════════════════════════════════════════


class SessionRepository(BaseRepository):

    async def upsert(self, data: dict) -> dict:
        async with self._session() as session:
            obj = dict_to_orm(DBSession, data)
            merged = await session.merge(obj)
            await session.commit()
            return orm_to_dict(merged)

    async def get_all(self, task_id: Optional[str] = None) -> List[dict]:
        async with self._session() as session:
            stmt = select(DBSession)
            if task_id:
                stmt = stmt.where(DBSession.task_id == task_id).order_by(DBSession.started_at)
            else:
                stmt = stmt.order_by(DBSession.started_at.desc()).limit(100)
            result = await session.execute(stmt)
            return [orm_to_dict(r) for r in result.scalars().all()]


# ═══════════════════════════════════════════════════════════════════════
#  TaskRunRepository
# ═══════════════════════════════════════════════════════════════════════

class TaskRunRepository(BaseRepository):

    async def create(self, data: dict) -> dict:
        async with self._session() as session:
            obj = dict_to_orm(DBTaskRun, data)
            session.add(obj)
            await session.commit()
            await session.refresh(obj)
            return orm_to_dict(obj)

    async def get(self, run_id: str) -> Optional[dict]:
        async with self._session() as session:
            result = await session.get(DBTaskRun, run_id)
            return orm_to_dict(result) if result else None

    async def get_all(self, task_id: Optional[str] = None) -> List[dict]:
        async with self._session() as session:
            stmt = select(DBTaskRun)
            if task_id:
                stmt = stmt.where(DBTaskRun.task_id == task_id).order_by(DBTaskRun.attempt.asc(), DBTaskRun.started_at.asc())
            else:
                stmt = stmt.order_by(DBTaskRun.started_at.desc()).limit(100)
            result = await session.execute(stmt)
            return [orm_to_dict(r) for r in result.scalars().all()]

    async def get_latest(self, task_id: str) -> Optional[dict]:
        runs = await self.get_all(task_id)
        return runs[-1] if runs else None

    async def next_attempt(self, task_id: str) -> int:
        async with self._session() as session:
            result = await session.execute(
                select(DBTaskRun.attempt)
                .where(DBTaskRun.task_id == task_id)
                .order_by(DBTaskRun.attempt.desc())
                .limit(1)
            )
            latest = result.scalar_one_or_none()
            return int(latest or 0) + 1

    async def update(self, run_id: str, **kwargs: Any) -> bool:
        async with self._session() as session:
            obj = await session.get(DBTaskRun, run_id)
            if not obj:
                return False
            for k, v in kwargs.items():
                if k in _JSON_FIELDS:
                    v = _json_encode(v)
                attr_name = "metadata_" if k == "metadata" else k
                setattr(obj, attr_name, v)
            await session.commit()
            return True

    async def complete(self, run_id: str, success: bool, result: Any = None, error: Any = None, **kwargs: Any) -> bool:
        status = TaskRunStatus.SUCCESS.value if success else TaskRunStatus.FAILED.value
        return await self.update(
            run_id,
            status=status,
            result=result,
            error=error,
            completed_at=now_iso(),
            last_activity_at=now_iso(),
            **kwargs,
        )


# ═══════════════════════════════════════════════════════════════════════
#  EventLogRepository
# ═══════════════════════════════════════════════════════════════════════


class EventLogRepository(BaseRepository):

    async def log(self, data: dict) -> int:
        async with self._session() as session:
            obj = dict_to_orm(DBEventLog, data)
            session.add(obj)
            await session.commit()
            return obj.id or 0

    async def get_all(
        self,
        entity_type: Optional[str] = None,
        entity_id: Optional[str] = None,
        limit: int = 100,
    ) -> List[dict]:
        async with self._session() as session:
            stmt = select(DBEventLog)
            if entity_type:
                stmt = stmt.where(DBEventLog.entity_type == entity_type)
            if entity_id:
                stmt = stmt.where(DBEventLog.entity_id == entity_id)
            stmt = stmt.order_by(DBEventLog.id.desc()).limit(limit)
            result = await session.execute(stmt)
            return [orm_to_dict(r) for r in result.scalars().all()]


# ═══════════════════════════════════════════════════════════════════════
#  Repositories — 统一入口
# ═══════════════════════════════════════════════════════════════════════


class Repositories:
    """所有 Repository 的聚合入口。

    Usage::
        repos = Repositories(db)
        await repos.project.upsert(data)
        await repos.task.get_by_batch(batch_id)
    """

    def __init__(self, db: Database):
        self.project = ProjectRepository(db)
        self.workspace = WorkspaceRepository(db)
        self.batch = BatchRepository(db)
        self.sub_batch = SubBatchRepository(db)
        self.task = TaskRepository(db)
        self.task_run = TaskRunRepository(db)
        self.agent = AgentRepository(db)
        self.session = SessionRepository(db)
        self.event_log = EventLogRepository(db)


# ═══════════════════════════════════════════════════════════════════════
#  DatabaseCompat — 向后兼容层
# ═══════════════════════════════════════════════════════════════════════


class DatabaseCompat:
    """向后兼容的 Database 接口。

    保持 scheduler.py / app.py 现有调用签名不变，
    内部委托给 Repositories + Database。

    Usage::
        db = Database("cubeclaw.db")
        await db.connect()
        compat = DatabaseCompat(db)
        await compat.upsert_project(data)  # 兼容旧接口
    """

    def __init__(self, db: Database):
        self._db = db
        self._repos = Repositories(db)

    @property
    def repos(self) -> Repositories:
        return self._repos

    # ── 直接代理 Database 方法 ────────────────────────────────────────

    async def connect(self) -> None:
        await self._db.connect()

    async def close(self) -> None:
        await self._db.close()

    async def check_integrity(self) -> bool:
        return await self._db.check_integrity()

    async def get_stats(self) -> dict:
        return await self._db.get_stats()

    # ── Projects ───────────────────────────────────────────────────────

    async def upsert_project(self, project: dict) -> dict:
        return await self._repos.project.upsert(project)

    async def get_project(self, project_id: str) -> Optional[dict]:
        return await self._repos.project.get(project_id)

    async def get_projects(self) -> List[dict]:
        return await self._repos.project.get_all()

    # ── Workspaces ─────────────────────────────────────────────────────

    async def upsert_workspace(self, ws: dict) -> dict:
        return await self._repos.workspace.upsert(ws)

    async def get_workspace(self, ws_id: str) -> Optional[dict]:
        return await self._repos.workspace.get(ws_id)

    async def get_workspaces(self, project_id: str) -> List[dict]:
        return await self._repos.workspace.get_by_project(project_id)

    # ── Batches ────────────────────────────────────────────────────────

    async def upsert_batch(self, b: dict) -> dict:
        return await self._repos.batch.upsert(b)

    async def get_batch(self, batch_id: str) -> Optional[dict]:
        return await self._repos.batch.get(batch_id)

    async def get_batches(
        self,
        workspace_id: Optional[str] = None,
        status: Optional[str] = None,
        lifecycle: Optional[str] = None,
    ) -> List[dict]:
        return await self._repos.batch.get_all(workspace_id, status, lifecycle)

    async def update_batch_status(self, batch_id: str, status: str, **kwargs: Any) -> None:
        await self._repos.batch.update_status(batch_id, status, **kwargs)

    # ── SubBatches ─────────────────────────────────────────────────────

    async def upsert_sub_batch(self, sb: dict) -> dict:
        return await self._repos.sub_batch.upsert(sb)

    async def get_sub_batch(self, sb_id: str) -> Optional[dict]:
        return await self._repos.sub_batch.get(sb_id)

    async def get_sub_batches(self, batch_id: str) -> List[dict]:
        return await self._repos.sub_batch.get_by_batch(batch_id)

    async def update_sub_batch_status(self, sb_id: str, status: str) -> None:
        await self._repos.sub_batch.update_status(sb_id, status)

    # ── Tasks ──────────────────────────────────────────────────────────

    async def upsert_task(self, t: dict) -> dict:
        return await self._repos.task.upsert(t)

    async def get_task(self, task_id: str) -> Optional[dict]:
        return await self._repos.task.get(task_id)

    async def get_tasks(
        self,
        sub_batch_id: Optional[str] = None,
        status: Optional[str] = None,
        task_type: Optional[str] = None,
    ) -> List[dict]:
        return await self._repos.task.get_all(sub_batch_id, status, task_type)

    async def get_tasks_by_batch(self, batch_id: str) -> List[dict]:
        return await self._repos.task.get_by_batch(batch_id)

    async def update_task_status(
        self,
        task_id: str,
        status: str,
        *,
        expected_statuses: Optional[List[str]] = None,
        force: bool = False,
        **kwargs: Any,
    ) -> bool:
        return await self._repos.task.update_status(
            task_id,
            status,
            expected_statuses=expected_statuses,
            force=force,
            **kwargs,
        )

    async def transition_task_status(
        self,
        task_id: str,
        from_statuses: List[str],
        to_status: str,
        **kwargs: Any,
    ) -> bool:
        return await self._repos.task.transition_status(task_id, from_statuses, to_status, **kwargs)

    async def queue_pending_task(self, task_id: str, **kwargs: Any) -> bool:
        return await self._repos.task.queue_pending(task_id, **kwargs)

    async def complete_running_task(self, task_id: str, success: bool, **kwargs: Any) -> bool:
        return await self._repos.task.complete_running(task_id, success, **kwargs)

    async def claim_queued_task(self, task_id: str, **kwargs: Any) -> bool:
        return await self._repos.task.claim_queued(task_id, **kwargs)

    # ── TaskRuns ────────────────────────────────────────────────────────

    async def create_task_run(self, run: dict) -> dict:
        return await self._repos.task_run.create(run)

    async def get_task_run(self, run_id: str) -> Optional[dict]:
        return await self._repos.task_run.get(run_id)

    async def get_task_runs(self, task_id: Optional[str] = None) -> List[dict]:
        return await self._repos.task_run.get_all(task_id)

    async def get_latest_task_run(self, task_id: str) -> Optional[dict]:
        return await self._repos.task_run.get_latest(task_id)

    async def next_task_run_attempt(self, task_id: str) -> int:
        return await self._repos.task_run.next_attempt(task_id)

    async def update_task_run(self, run_id: str, **kwargs: Any) -> bool:
        return await self._repos.task_run.update(run_id, **kwargs)

    async def complete_task_run(self, run_id: str, success: bool, result: Any = None, error: Any = None, **kwargs: Any) -> bool:
        return await self._repos.task_run.complete(run_id, success, result, error, **kwargs)

    # ── Agents ─────────────────────────────────────────────────────────

    async def upsert_agent(self, a: dict) -> dict:
        return await self._repos.agent.upsert(a)

    async def get_agent(self, agent_id: str) -> Optional[dict]:
        return await self._repos.agent.get(agent_id)

    async def get_agents(self, status: Optional[str] = None) -> List[dict]:
        return await self._repos.agent.get_all(status)

    async def update_agent_status(self, agent_id: str, status: str, **kwargs: Any) -> None:
        await self._repos.agent.update_status(agent_id, status, **kwargs)

    # ── Sessions ───────────────────────────────────────────────────────

    async def upsert_session(self, s: dict) -> dict:
        return await self._repos.session.upsert(s)

    async def get_sessions(self, task_id: Optional[str] = None) -> List[dict]:
        return await self._repos.session.get_all(task_id)

    # ── Event Logs ─────────────────────────────────────────────────────

    async def log_event(self, event: dict) -> int:
        return await self._repos.event_log.log(event)

    async def get_event_logs(
        self,
        entity_type: Optional[str] = None,
        entity_id: Optional[str] = None,
        limit: int = 100,
    ) -> List[dict]:
        return await self._repos.event_log.get_all(entity_type, entity_id, limit)
