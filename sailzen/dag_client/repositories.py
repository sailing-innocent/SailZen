# -*- coding: utf-8 -*-
# @file repositories.py
# @brief 通用 DAG 数据访问层
# @author sailing-innocent
# @date 2025-06-02
# @version 3.0
# ---------------------------------
"""SailZen DAG Client Repository 层。

所有数据库操作通过 Repository 类封装，对外暴露 dict 接口。
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from sqlalchemy import select, update, delete
from sqlalchemy.ext.asyncio import AsyncSession

from sailzen.dag_client.database import Database
from sailzen.dag_client.models import (
    DBDAGDefinition, DBDAGRun, DBDAGNode, DBDAGEdge, DBNodeRun,
    DBAgent, DBEventLog, DBRequiredSkill,
    orm_to_dict, dict_to_orm, _json_encode, _json_decode, _JSON_FIELDS,
    _now_iso, NodeStatus, RunStatus,
    status_rank, is_terminal,
)

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════
#  BaseRepository
# ═══════════════════════════════════════════════════════════════════════

class BaseRepository:
    def __init__(self, db: Database):
        self._db = db

    def _session(self) -> AsyncSession:
        return self._db.session()


# ═══════════════════════════════════════════════════════════════════════
#  DAGDefinitionRepository
# ═══════════════════════════════════════════════════════════════════════

class DAGDefinitionRepository(BaseRepository):
    async def upsert(self, data: dict) -> dict:
        async with self._session() as session:
            obj = dict_to_orm(DBDAGDefinition, data)
            merged = await session.merge(obj)
            await session.commit()
            return orm_to_dict(merged)

    async def get(self, def_id: str) -> Optional[dict]:
        async with self._session() as session:
            result = await session.get(DBDAGDefinition, def_id)
            return orm_to_dict(result) if result else None

    async def get_all(self) -> List[dict]:
        async with self._session() as session:
            result = await session.execute(
                select(DBDAGDefinition).order_by(DBDAGDefinition.created_at)
            )
            return [orm_to_dict(r) for r in result.scalars().all()]

    async def delete(self, def_id: str) -> bool:
        async with self._session() as session:
            obj = await session.get(DBDAGDefinition, def_id)
            if not obj:
                return False
            await session.delete(obj)
            await session.commit()
            return True


# ═══════════════════════════════════════════════════════════════════════
#  DAGRunRepository
# ═══════════════════════════════════════════════════════════════════════

class DAGRunRepository(BaseRepository):
    async def create(self, data: dict) -> dict:
        async with self._session() as session:
            obj = dict_to_orm(DBDAGRun, data)
            session.add(obj)
            await session.commit()
            await session.refresh(obj)
            return orm_to_dict(obj)

    async def get(self, run_id: str) -> Optional[dict]:
        async with self._session() as session:
            result = await session.get(DBDAGRun, run_id)
            return orm_to_dict(result) if result else None

    async def get_all(
        self,
        definition_id: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 100,
    ) -> List[dict]:
        async with self._session() as session:
            stmt = select(DBDAGRun)
            if definition_id:
                stmt = stmt.where(DBDAGRun.definition_id == definition_id)
            if status:
                stmt = stmt.where(DBDAGRun.status == status)
            stmt = stmt.order_by(DBDAGRun.created_at.desc()).limit(limit)
            result = await session.execute(stmt)
            return [orm_to_dict(r) for r in result.scalars().all()]

    async def update_status(self, run_id: str, status: str, **kwargs: Any) -> bool:
        async with self._session() as session:
            obj = await session.get(DBDAGRun, run_id)
            if not obj:
                return False
            obj.status = status
            for key, value in kwargs.items():
                if key in _JSON_FIELDS:
                    value = _json_encode(value)
                attr_name = "metadata_" if key == "metadata" else key
                setattr(obj, attr_name, value)
            obj.updated_at = _now_iso()
            await session.commit()
            return True


# ═══════════════════════════════════════════════════════════════════════
#  DAGNodeRepository
# ═══════════════════════════════════════════════════════════════════════

class DAGNodeRepository(BaseRepository):
    async def create(self, data: dict) -> dict:
        async with self._session() as session:
            obj = dict_to_orm(DBDAGNode, data)
            session.add(obj)
            await session.commit()
            await session.refresh(obj)
            return orm_to_dict(obj)

    async def upsert(self, data: dict) -> dict:
        async with self._session() as session:
            existing = None
            if data.get("id"):
                existing = await session.get(DBDAGNode, data["id"])
            if existing:
                for col in DBDAGNode.__table__.columns:
                    key = col.key
                    if key in data:
                        val = data[key]
                        if key in _JSON_FIELDS:
                            val = _json_encode(val)
                        attr_name = "metadata_" if key == "metadata" else key
                        setattr(existing, attr_name, val)
                await session.commit()
                await session.refresh(existing)
                return orm_to_dict(existing)
            else:
                return await self.create(data)

    async def get(self, node_db_id: str) -> Optional[dict]:
        async with self._session() as session:
            result = await session.get(DBDAGNode, node_db_id)
            return orm_to_dict(result) if result else None

    async def get_by_run(self, run_id: str, status: Optional[str] = None) -> List[dict]:
        async with self._session() as session:
            stmt = select(DBDAGNode).where(DBDAGNode.run_id == run_id)
            if status:
                stmt = stmt.where(DBDAGNode.status == status)
            stmt = stmt.order_by(DBDAGNode.priority.asc(), DBDAGNode.created_at.asc())
            result = await session.execute(stmt)
            return [orm_to_dict(r) for r in result.scalars().all()]

    async def get_by_node_id(self, run_id: str, node_id: str) -> Optional[dict]:
        async with self._session() as session:
            result = await session.execute(
                select(DBDAGNode)
                .where(DBDAGNode.run_id == run_id, DBDAGNode.node_id == node_id)
            )
            obj = result.scalar_one_or_none()
            return orm_to_dict(obj) if obj else None

    async def update_status(
        self,
        node_db_id: str,
        status: str,
        *,
        expected_statuses: Optional[List[str]] = None,
        force: bool = False,
        **kwargs: Any,
    ) -> bool:
        async with self._session() as session:
            obj = await session.get(DBDAGNode, node_db_id)
            if not obj:
                return False
            if expected_statuses is not None and obj.status not in expected_statuses:
                return False
            if not force:
                current_rank = status_rank(obj.status, "node")
                target_rank = status_rank(status, "node")
                if obj.status in _NODE_TERMINAL_STATUSES and obj.status != status:
                    logger.warning(
                        "Refuse node terminal-state overwrite: %s current=%s target=%s",
                        node_db_id[:8], obj.status, status,
                    )
                    return False
                if target_rank < current_rank:
                    logger.warning(
                        "Refuse node status regression: %s current=%s target=%s",
                        node_db_id[:8], obj.status, status,
                    )
                    return False
            obj.status = status
            for k, v in kwargs.items():
                if k in _JSON_FIELDS:
                    v = _json_encode(v)
                attr_name = "metadata_" if k == "metadata" else k
                setattr(obj, attr_name, v)
            await session.commit()
            return True


# ═══════════════════════════════════════════════════════════════════════
#  DAGEdgeRepository
# ═══════════════════════════════════════════════════════════════════════

class DAGEdgeRepository(BaseRepository):
    async def create(self, data: dict) -> dict:
        async with self._session() as session:
            obj = dict_to_orm(DBDAGEdge, data)
            session.add(obj)
            await session.commit()
            await session.refresh(obj)
            return orm_to_dict(obj)

    async def get_by_run(self, run_id: str) -> List[dict]:
        async with self._session() as session:
            result = await session.execute(
                select(DBDAGEdge)
                .where(DBDAGEdge.run_id == run_id)
                .order_by(DBDAGEdge.created_at)
            )
            return [orm_to_dict(r) for r in result.scalars().all()]


# ═══════════════════════════════════════════════════════════════════════
#  NodeRunRepository
# ═══════════════════════════════════════════════════════════════════════

class NodeRunRepository(BaseRepository):
    async def create(self, data: dict) -> dict:
        async with self._session() as session:
            obj = dict_to_orm(DBNodeRun, data)
            session.add(obj)
            await session.commit()
            await session.refresh(obj)
            return orm_to_dict(obj)

    async def get(self, run_id: str) -> Optional[dict]:
        async with self._session() as session:
            result = await session.get(DBNodeRun, run_id)
            return orm_to_dict(result) if result else None

    async def get_by_node(self, node_db_id: str) -> List[dict]:
        async with self._session() as session:
            result = await session.execute(
                select(DBNodeRun)
                .where(DBNodeRun.node_id == node_db_id)
                .order_by(DBNodeRun.attempt.asc(), DBNodeRun.started_at.asc())
            )
            return [orm_to_dict(r) for r in result.scalars().all()]

    async def next_attempt(self, node_db_id: str) -> int:
        async with self._session() as session:
            result = await session.execute(
                select(DBNodeRun.attempt)
                .where(DBNodeRun.node_id == node_db_id)
                .order_by(DBNodeRun.attempt.desc())
                .limit(1)
            )
            latest = result.scalar_one_or_none()
            return int(latest or 0) + 1

    async def update(self, run_id: str, **kwargs: Any) -> bool:
        async with self._session() as session:
            obj = await session.get(DBNodeRun, run_id)
            if not obj:
                return False
            for k, v in kwargs.items():
                if k in _JSON_FIELDS:
                    v = _json_encode(v)
                attr_name = "metadata_" if k == "metadata" else k
                setattr(obj, attr_name, v)
            await session.commit()
            return True

    async def complete(self, run_id: str, success: bool, result: Any = None, error: Any = None) -> bool:
        status = NodeStatus.SUCCESS.value if success else NodeStatus.FAILED.value
        return await self.update(
            run_id,
            status=status,
            result=result,
            error=error,
            completed_at=_now_iso(),
        )


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
#  RequiredSkillRepository
# ═══════════════════════════════════════════════════════════════════════

class RequiredSkillRepository(BaseRepository):
    async def upsert(self, data: dict) -> dict:
        async with self._session() as session:
            obj = dict_to_orm(DBRequiredSkill, data)
            merged = await session.merge(obj)
            await session.commit()
            return orm_to_dict(merged)

    async def get_all(self) -> List[dict]:
        async with self._session() as session:
            result = await session.execute(select(DBRequiredSkill))
            return [orm_to_dict(r) for r in result.scalars().all()]

    async def update_status(self, skill_name: str, status: str) -> None:
        async with self._session() as session:
            result = await session.execute(
                select(DBRequiredSkill).where(DBRequiredSkill.skill_name == skill_name)
            )
            obj = result.scalar_one_or_none()
            if obj:
                obj.status = status
                obj.checked_at = _now_iso()
                await session.commit()


# ═══════════════════════════════════════════════════════════════════════
#  Repositories — 统一入口
# ═══════════════════════════════════════════════════════════════════════

class Repositories:
    """所有 Repository 的聚合入口。"""

    def __init__(self, db: Database):
        self.definition = DAGDefinitionRepository(db)
        self.run = DAGRunRepository(db)
        self.node = DAGNodeRepository(db)
        self.edge = DAGEdgeRepository(db)
        self.node_run = NodeRunRepository(db)
        self.agent = AgentRepository(db)
        self.event_log = EventLogRepository(db)
        self.required_skill = RequiredSkillRepository(db)


# ═══════════════════════════════════════════════════════════════════════
#  DatabaseCompat — 向后兼容接口
# ═══════════════════════════════════════════════════════════════════════

class DatabaseCompat:
    """向后兼容的 Database 接口。"""

    def __init__(self, db: Database):
        self._db = db
        self._repos = Repositories(db)

    @property
    def repos(self) -> Repositories:
        return self._repos

    async def connect(self) -> None:
        await self._db.connect()

    async def close(self) -> None:
        await self._db.close()

    async def check_integrity(self) -> bool:
        return await self._db.check_integrity()

    async def get_stats(self) -> dict:
        return await self._db.get_stats()

    # DAGDefinition
    async def upsert_definition(self, data: dict) -> dict:
        return await self._repos.definition.upsert(data)

    async def get_definition(self, def_id: str) -> Optional[dict]:
        return await self._repos.definition.get(def_id)

    async def get_definitions(self) -> List[dict]:
        return await self._repos.definition.get_all()

    # DAGRun
    async def create_run(self, data: dict) -> dict:
        return await self._repos.run.create(data)

    async def get_run(self, run_id: str) -> Optional[dict]:
        return await self._repos.run.get(run_id)

    async def get_runs(self, definition_id: Optional[str] = None, status: Optional[str] = None) -> List[dict]:
        return await self._repos.run.get_all(definition_id, status)

    async def update_run_status(self, run_id: str, status: str, **kwargs: Any) -> bool:
        return await self._repos.run.update_status(run_id, status, **kwargs)

    # DAGNode
    async def create_node(self, data: dict) -> dict:
        return await self._repos.node.create(data)

    async def upsert_node(self, data: dict) -> dict:
        return await self._repos.node.upsert(data)

    async def get_node(self, node_db_id: str) -> Optional[dict]:
        return await self._repos.node.get(node_db_id)

    async def get_nodes(self, run_id: str, status: Optional[str] = None) -> List[dict]:
        return await self._repos.node.get_by_run(run_id, status)

    async def get_node_by_template_id(self, run_id: str, node_id: str) -> Optional[dict]:
        return await self._repos.node.get_by_node_id(run_id, node_id)

    async def update_node_status(self, node_db_id: str, status: str, **kwargs: Any) -> bool:
        return await self._repos.node.update_status(node_db_id, status, **kwargs)

    # DAGEdge
    async def create_edge(self, data: dict) -> dict:
        return await self._repos.edge.create(data)

    async def get_edges(self, run_id: str) -> List[dict]:
        return await self._repos.edge.get_by_run(run_id)

    # NodeRun
    async def create_node_run(self, data: dict) -> dict:
        return await self._repos.node_run.create(data)

    async def get_node_runs(self, node_db_id: str) -> List[dict]:
        return await self._repos.node_run.get_by_node(node_db_id)

    async def next_node_run_attempt(self, node_db_id: str) -> int:
        return await self._repos.node_run.next_attempt(node_db_id)

    async def complete_node_run(self, run_id: str, success: bool, **kwargs: Any) -> bool:
        return await self._repos.node_run.complete(run_id, success, **kwargs)

    # Agent
    async def upsert_agent(self, data: dict) -> dict:
        return await self._repos.agent.upsert(data)

    async def get_agent(self, agent_id: str) -> Optional[dict]:
        return await self._repos.agent.get(agent_id)

    async def get_agents(self, status: Optional[str] = None) -> List[dict]:
        return await self._repos.agent.get_all(status)

    async def update_agent_status(self, agent_id: str, status: str, **kwargs: Any) -> None:
        await self._repos.agent.update_status(agent_id, status, **kwargs)

    # EventLog
    async def log_event(self, event: dict) -> int:
        return await self._repos.event_log.log(event)

    async def get_event_logs(self, entity_type: Optional[str] = None,
                             entity_id: Optional[str] = None, limit: int = 100) -> List[dict]:
        return await self._repos.event_log.get_all(entity_type, entity_id, limit)

    # RequiredSkill
    async def upsert_required_skill(self, data: dict) -> dict:
        return await self._repos.required_skill.upsert(data)

    async def get_required_skills(self) -> List[dict]:
        return await self._repos.required_skill.get_all()

    async def update_required_skill_status(self, skill_name: str, status: str) -> None:
        await self._repos.required_skill.update_status(skill_name, status)
