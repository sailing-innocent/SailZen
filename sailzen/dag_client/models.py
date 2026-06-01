# -*- coding: utf-8 -*-
# @file models.py
# @brief 通用 DAG 数据模型
# @author sailing-innocent
# @date 2025-06-02
# @version 3.0
# ---------------------------------
"""SailZen DAG Client 通用数据模型。

架构:
  Layer 1: Enums          — 业务状态枚举
  Layer 2: SQLAlchemy ORM — 数据库表定义
  Layer 3: Pydantic       — API 输入/输出验证
"""

from __future__ import annotations

import json as _json
import uuid
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field
from sqlalchemy import (
    Column, Integer, String, Text, DateTime, ForeignKey, CheckConstraint,
    UniqueConstraint, Index, func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


# ═══════════════════════════════════════════════════════════════════════
#  Enums
# ═══════════════════════════════════════════════════════════════════════


class RunStatus(str, Enum):
    PENDING = "pending"
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    BLOCKED = "blocked"
    CANCELLED = "cancelled"


class NodeStatus(str, Enum):
    PENDING = "pending"
    QUEUED = "queued"
    ASSIGNED = "assigned"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    BLOCKED = "blocked"
    CANCELLED = "cancelled"
    SKIPPED = "skipped"


class AgentStatus(str, Enum):
    ONLINE = "online"
    OFFLINE = "offline"
    BUSY = "busy"
    MAINTENANCE = "maintenance"


# ── 状态机 Rank（防止运行时回退）─────────────────────────────────────

_RUN_STATUS_RANK = {
    RunStatus.PENDING.value: 0,
    RunStatus.QUEUED.value: 1,
    RunStatus.RUNNING.value: 2,
    RunStatus.COMPLETED.value: 3,
    RunStatus.FAILED.value: 3,
    RunStatus.BLOCKED.value: 3,
    RunStatus.CANCELLED.value: 3,
}

_NODE_STATUS_RANK = {
    NodeStatus.PENDING.value: 0,
    NodeStatus.QUEUED.value: 1,
    NodeStatus.ASSIGNED.value: 2,
    NodeStatus.RUNNING.value: 3,
    NodeStatus.SUCCESS.value: 4,
    NodeStatus.FAILED.value: 4,
    NodeStatus.BLOCKED.value: 4,
    NodeStatus.CANCELLED.value: 4,
    NodeStatus.SKIPPED.value: 4,
}

_NODE_TERMINAL_STATUSES = {
    NodeStatus.SUCCESS.value,
    NodeStatus.FAILED.value,
    NodeStatus.BLOCKED.value,
    NodeStatus.CANCELLED.value,
    NodeStatus.SKIPPED.value,
}


# ═══════════════════════════════════════════════════════════════════════
#  SQLAlchemy ORM
# ═══════════════════════════════════════════════════════════════════════


class Base(DeclarativeBase):
    pass


# ── ORM: DAGDefinition ────────────────────────────────────────────────

class DBDAGDefinition(Base):
    __tablename__ = "dag_definitions"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str] = mapped_column(Text, default="")
    # JSON 存储 DAG 模板（节点列表和边列表）
    template: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[str] = mapped_column(String, default=lambda: _now_iso())
    updated_at: Mapped[str] = mapped_column(String, default=lambda: _now_iso())

    runs: Mapped[List["DBDAGRun"]] = relationship(back_populates="definition", lazy="selectin")


# ── ORM: DAGRun ───────────────────────────────────────────────────────

class DBDAGRun(Base):
    __tablename__ = "dag_runs"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    definition_id: Mapped[str] = mapped_column(String, ForeignKey("dag_definitions.id"), nullable=False)
    name: Mapped[str] = mapped_column(String, nullable=False, default="")
    status: Mapped[str] = mapped_column(String, nullable=False, default=RunStatus.PENDING.value)
    params: Mapped[str] = mapped_column(Text, default="{}")  # 运行时参数
    result: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[str] = mapped_column(String, default=lambda: _now_iso())
    started_at: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    completed_at: Mapped[Optional[str]] = mapped_column(String, nullable=True)

    definition: Mapped["DBDAGDefinition"] = relationship(back_populates="runs")
    nodes: Mapped[List["DBDAGNode"]] = relationship(back_populates="run", lazy="selectin")
    edges: Mapped[List["DBDAGEdge"]] = relationship(back_populates="run", lazy="selectin")


# ── ORM: DAGNode ──────────────────────────────────────────────────────

class DBDAGNode(Base):
    __tablename__ = "dag_nodes"
    __table_args__ = (
        UniqueConstraint("run_id", "node_id", name="uq_node_run_nodeid"),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True)
    run_id: Mapped[str] = mapped_column(String, ForeignKey("dag_runs.id"), nullable=False)
    node_id: Mapped[str] = mapped_column(String, nullable=False)  # 模板中的节点 id
    node_type: Mapped[str] = mapped_column(String, nullable=False)
    name: Mapped[str] = mapped_column(String, nullable=False, default="")
    status: Mapped[str] = mapped_column(String, nullable=False, default=NodeStatus.PENDING.value)
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=100)
    params: Mapped[str] = mapped_column(Text, default="{}")
    result: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    max_retries: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    timeout_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=3600)
    created_at: Mapped[str] = mapped_column(String, default=lambda: _now_iso())
    queued_at: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    started_at: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    completed_at: Mapped[Optional[str]] = mapped_column(String, nullable=True)

    run: Mapped["DBDAGRun"] = relationship(back_populates="nodes")
    node_runs: Mapped[List["DBNodeRun"]] = relationship(back_populates="node", lazy="selectin")


# ── ORM: DAGEdge ──────────────────────────────────────────────────────

class DBDAGEdge(Base):
    __tablename__ = "dag_edges"
    __table_args__ = (
        UniqueConstraint("run_id", "from_node", "to_node", name="uq_edge_run_from_to"),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True)
    run_id: Mapped[str] = mapped_column(String, ForeignKey("dag_runs.id"), nullable=False)
    from_node: Mapped[str] = mapped_column(String, nullable=False)
    to_node: Mapped[str] = mapped_column(String, nullable=False)
    edge_type: Mapped[str] = mapped_column(String, default="dependency")  # dependency / trigger
    condition: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # 条件表达式
    created_at: Mapped[str] = mapped_column(String, default=lambda: _now_iso())

    run: Mapped["DBDAGRun"] = relationship(back_populates="edges")


# ── ORM: NodeRun ──────────────────────────────────────────────────────

class DBNodeRun(Base):
    __tablename__ = "node_runs"
    __table_args__ = (
        UniqueConstraint("node_id", "attempt", name="uq_node_run_node_attempt"),
        Index("idx_node_runs_node_started", "node_id", "started_at"),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True)
    node_id: Mapped[str] = mapped_column(String, ForeignKey("dag_nodes.id"), nullable=False)
    attempt: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    status: Mapped[str] = mapped_column(String, nullable=False, default=NodeStatus.PENDING.value)
    runner: Mapped[str] = mapped_column(String, nullable=False, default="")
    prompt: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    context: Mapped[str] = mapped_column(Text, default="{}")
    result: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    started_at: Mapped[str] = mapped_column(String, default=lambda: _now_iso())
    completed_at: Mapped[Optional[str]] = mapped_column(String, nullable=True)

    node: Mapped["DBDAGNode"] = relationship(back_populates="node_runs")


# ── ORM: Agent ────────────────────────────────────────────────────────

class DBAgent(Base):
    __tablename__ = "agents"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    host: Mapped[str] = mapped_column(String, nullable=False)
    port: Mapped[int] = mapped_column(Integer, nullable=False, default=9000)
    capabilities: Mapped[str] = mapped_column(Text, default="[]")
    status: Mapped[str] = mapped_column(String, default=AgentStatus.OFFLINE.value)
    current_node_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    max_concurrent: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    heartbeat_at: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    registered_at: Mapped[str] = mapped_column(String, default=lambda: _now_iso())
    config: Mapped[str] = mapped_column(Text, default="{}")


# ── ORM: EventLog ─────────────────────────────────────────────────────

class DBEventLog(Base):
    __tablename__ = "event_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    event_type: Mapped[str] = mapped_column(String, nullable=False)
    entity_type: Mapped[str] = mapped_column(String, nullable=False)
    entity_id: Mapped[str] = mapped_column(String, nullable=False)
    old_state: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    new_state: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    metadata_: Mapped[Optional[str]] = mapped_column("metadata", Text, nullable=True)
    actor: Mapped[str] = mapped_column(String, default="system")
    created_at: Mapped[str] = mapped_column(String, default=lambda: _now_iso())


# ── ORM: RequiredSkill ────────────────────────────────────────────────

class DBRequiredSkill(Base):
    __tablename__ = "required_skills"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    skill_name: Mapped[str] = mapped_column(String, nullable=False)
    node_type: Mapped[str] = mapped_column(String, default="*")  # * 表示全局必需
    version_constraint: Mapped[str] = mapped_column(String, default="*")
    status: Mapped[str] = mapped_column(String, default="pending")  # pending / ok / missing
    checked_at: Mapped[Optional[str]] = mapped_column(String, nullable=True)


# ═══════════════════════════════════════════════════════════════════════
#  JSON 工具
# ═══════════════════════════════════════════════════════════════════════

_JSON_FIELDS = frozenset([
    "template", "params", "result", "error", "context",
    "capabilities", "config", "metadata", "old_state", "new_state",
])


def _json_encode(val: Any) -> Optional[str]:
    if val is None:
        return None
    if isinstance(val, str):
        return val
    return _json.dumps(val, ensure_ascii=False, default=str)


def _json_decode(val: Any) -> Any:
    if val is None:
        return None
    if isinstance(val, str):
        try:
            return _json.loads(val)
        except (_json.JSONDecodeError, TypeError):
            return val
    return val


def orm_to_dict(obj: Base) -> dict:
    d = {}
    for col in obj.__table__.columns:
        key = col.key
        val = getattr(obj, key if key != "metadata" else "metadata_")
        if key in _JSON_FIELDS:
            val = _json_decode(val)
        d[key] = val
    return d


def dict_to_orm(cls: type[Base], data: dict) -> Base:
    kwargs = {}
    for col in cls.__table__.columns:
        key = col.key
        if key in data:
            val = data[key]
            if key in _JSON_FIELDS:
                val = _json_encode(val)
            attr_name = "metadata_" if key == "metadata" else key
            kwargs[attr_name] = val
    return cls(**kwargs)


# ═══════════════════════════════════════════════════════════════════════
#  Helpers
# ═══════════════════════════════════════════════════════════════════════


def _new_id() -> str:
    return str(uuid.uuid4())


def _now_iso() -> str:
    return datetime.now().isoformat()


def status_rank(status: str, kind: str = "node") -> int:
    rank_map = _NODE_STATUS_RANK if kind == "node" else _RUN_STATUS_RANK
    return rank_map.get(status, -1)


def is_terminal(status: str, kind: str = "node") -> bool:
    return status in _NODE_TERMINAL_STATUSES if kind == "node" else status in {
        RunStatus.COMPLETED.value, RunStatus.FAILED.value,
        RunStatus.BLOCKED.value, RunStatus.CANCELLED.value,
    }


# ═══════════════════════════════════════════════════════════════════════
#  Pydantic Schemas
# ═══════════════════════════════════════════════════════════════════════


class DAGDefinitionSchema(BaseModel):
    id: str
    name: str
    description: str = ""
    template: Dict[str, Any] = Field(default_factory=dict)
    version: int = 1
    created_at: str
    updated_at: str
    model_config = {"from_attributes": True}


class DAGRunSchema(BaseModel):
    id: str
    definition_id: str
    name: str = ""
    status: str = RunStatus.PENDING.value
    params: Dict[str, Any] = Field(default_factory=dict)
    result: Any = None
    error: Any = None
    created_at: str
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    model_config = {"from_attributes": True}


class DAGNodeSchema(BaseModel):
    id: str
    run_id: str
    node_id: str
    node_type: str
    name: str = ""
    status: str = NodeStatus.PENDING.value
    priority: int = 100
    params: Dict[str, Any] = Field(default_factory=dict)
    result: Any = None
    error: Any = None
    retry_count: int = 0
    max_retries: int = 3
    timeout_seconds: int = 3600
    created_at: str
    queued_at: Optional[str] = None
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    model_config = {"from_attributes": True}


class DAGEdgeSchema(BaseModel):
    id: str
    run_id: str
    from_node: str
    to_node: str
    edge_type: str = "dependency"
    condition: Optional[str] = None
    created_at: str
    model_config = {"from_attributes": True}


class NodeRunSchema(BaseModel):
    id: str
    node_id: str
    attempt: int = 1
    status: str = NodeStatus.PENDING.value
    runner: str = ""
    prompt: Optional[str] = None
    context: Dict[str, Any] = Field(default_factory=dict)
    result: Any = None
    error: Any = None
    started_at: str
    completed_at: Optional[str] = None
    model_config = {"from_attributes": True}


class AgentSchema(BaseModel):
    id: str
    name: str
    host: str
    port: int = 9000
    capabilities: List[str] = Field(default_factory=list)
    status: str = AgentStatus.OFFLINE.value
    current_node_id: Optional[str] = None
    max_concurrent: int = 1
    heartbeat_at: Optional[str] = None
    registered_at: str
    config: Dict[str, Any] = Field(default_factory=dict)
    model_config = {"from_attributes": True}


class EventLogSchema(BaseModel):
    id: Optional[int] = None
    event_type: str
    entity_type: str
    entity_id: str
    old_state: Any = None
    new_state: Any = None
    metadata: Any = None
    actor: str = "system"
    created_at: str
    model_config = {"from_attributes": True}


# ═══════════════════════════════════════════════════════════════════════
#  工厂函数
# ═══════════════════════════════════════════════════════════════════════


def make_dag_definition(name: str, template: dict, description: str = "") -> dict:
    now = _now_iso()
    return {
        "id": _new_id(),
        "name": name,
        "description": description,
        "template": template,
        "version": 1,
        "created_at": now,
        "updated_at": now,
    }


def make_dag_run(definition_id: str, name: str = "", params: dict = None) -> dict:
    return {
        "id": _new_id(),
        "definition_id": definition_id,
        "name": name,
        "status": RunStatus.PENDING.value,
        "params": params or {},
        "result": None,
        "error": None,
        "created_at": _now_iso(),
        "started_at": None,
        "completed_at": None,
    }


def make_dag_node(run_id: str, node_id: str, node_type: str, name: str = "",
                  priority: int = 100, params: dict = None,
                  timeout: int = 3600, max_retries: int = 3) -> dict:
    return {
        "id": _new_id(),
        "run_id": run_id,
        "node_id": node_id,
        "node_type": node_type,
        "name": name or node_id,
        "status": NodeStatus.PENDING.value,
        "priority": priority,
        "params": params or {},
        "result": None,
        "error": None,
        "retry_count": 0,
        "max_retries": max_retries,
        "timeout_seconds": timeout,
        "created_at": _now_iso(),
        "queued_at": None,
        "started_at": None,
        "completed_at": None,
    }


def make_dag_edge(run_id: str, from_node: str, to_node: str,
                  edge_type: str = "dependency", condition: str = None) -> dict:
    return {
        "id": _new_id(),
        "run_id": run_id,
        "from_node": from_node,
        "to_node": to_node,
        "edge_type": edge_type,
        "condition": condition,
        "created_at": _now_iso(),
    }


def make_node_run(node_id: str, attempt: int = 1, runner: str = "") -> dict:
    return {
        "id": _new_id(),
        "node_id": node_id,
        "attempt": attempt,
        "status": NodeStatus.PENDING.value,
        "runner": runner,
        "prompt": None,
        "context": {},
        "result": None,
        "error": None,
        "started_at": _now_iso(),
        "completed_at": None,
    }


def make_agent(agent_id: str, name: str, host: str, port: int = 9000,
               capabilities: List[str] = None, config: dict = None) -> dict:
    return {
        "id": agent_id,
        "name": name,
        "host": host,
        "port": port,
        "capabilities": capabilities or [],
        "status": AgentStatus.OFFLINE.value,
        "current_node_id": None,
        "max_concurrent": 1,
        "heartbeat_at": None,
        "registered_at": _now_iso(),
        "config": config or {},
    }


def make_event_log(event_type: str, entity_type: str, entity_id: str,
                   old_state: Any = None, new_state: Any = None,
                   metadata: Any = None, actor: str = "system") -> dict:
    return {
        "event_type": event_type,
        "entity_type": entity_type,
        "entity_id": entity_id,
        "old_state": old_state,
        "new_state": new_state,
        "metadata": metadata,
        "actor": actor,
        "created_at": _now_iso(),
    }
