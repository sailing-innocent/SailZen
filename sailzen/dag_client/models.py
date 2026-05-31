"""核心数据模型 — Pydantic Schemas + SQLAlchemy ORM。

架构:
  Layer 1: Enums          — 业务状态枚举 (str Enum)
  Layer 2: SQLAlchemy ORM — 数据库表定义 + 关系
  Layer 3: Pydantic       — API 输入/输出验证 + 序列化

设计约定:
  - ORM model 以 `DB` 前缀命名 (DBProject, DBBatch, ...)
  - Pydantic schema 直接用业务名 (Project, Batch, ...)
  - 工厂函数 make_xxx() 返回 Pydantic schema 实例（兼容旧 dict 接口）
  - schema.model_dump() 产出 dict，保证下游 scheduler/handler 无感切换
"""

from __future__ import annotations

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


class BatchType(str, Enum):
    GLOBAL = "global"
    NETEASE = "netease"


class BatchStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    BLOCKED = "blocked"
    COMPLETED = "completed"
    FAILED = "failed"
    AWAITING_REBASE = "awaiting_rebase"


class BatchLifecycle(str, Enum):
    ACTIVE = "active"
    MERGED = "merged"


class SubBatchStatus(str, Enum):
    PENDING = "pending"
    PICK_RUNNING = "pick_running"
    PICK_DONE = "pick_done"
    BUILD_RUNNING = "build_running"
    REVIEW_RUNNING = "review_running"
    REBASE_PENDING = "rebase_pending"
    REBASE_RUNNING = "rebase_running"
    COMPLETED = "completed"
    BLOCKED = "blocked"


class TaskType(str, Enum):
    INIT_WORKSPACE = "init_workspace"
    PICK = "pick"
    SUMMARY = "summary"
    ENSURE_WORKTREE = "ensure_worktree"
    REBASE = "rebase"
    BUILD_WIN = "build_win"
    BUILD_IOS = "build_ios"
    REVIEW = "review"
    FINAL_REVIEW = "final_review"
    REPORT = "report"
    FINALIZATION = "finalization"


class TaskStatus(str, Enum):
    PENDING = "pending"
    QUEUED = "queued"
    ASSIGNED = "assigned"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    BLOCKED = "blocked"
    CANCELLED = "cancelled"
    SUPERSEDED = "superseded"


class AgentStatus(str, Enum):
    ONLINE = "online"
    OFFLINE = "offline"
    BUSY = "busy"
    MAINTENANCE = "maintenance"


class Platform(str, Enum):
    WINDOWS = "windows"
    MACOS = "macos"
    LINUX = "linux"


class SessionStatus(str, Enum):
    STARTING = "starting"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    TIMEOUT = "timeout"


class TaskRunStatus(str, Enum):
    STARTING = "starting"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    BLOCKED = "blocked"
    CANCELLED = "cancelled"


class AlertLevel(str, Enum):
    L1 = "L1"
    L2 = "L2"
    L3 = "L3"
    L4 = "L4"
    L5 = "L5"


# ── 超时配置 ────────────────────────────────────────────────────────


class TaskTimeoutConfig:
    """各类型任务默认超时（秒）。"""
    INIT_WORKSPACE = 7200
    PICK = 3600
    SUMMARY = 300
    ENSURE_WORKTREE = 600
    REBASE = 1800
    BUILD_WIN = 14400
    BUILD_IOS = 14400
    REVIEW = 1800
    FINAL_REVIEW = 3600
    REPORT = 300
    FINALIZATION = 600

    @classmethod
    def get_timeout(cls, task_type: TaskType) -> int:
        return getattr(cls, task_type.name, 3600)


# ═══════════════════════════════════════════════════════════════════════
#  SQLAlchemy ORM — 声明式基类
# ═══════════════════════════════════════════════════════════════════════


class Base(DeclarativeBase):
    """SQLAlchemy 声明式基类。"""
    pass


# ── ORM: Project ──────────────────────────────────────────────────────

class DBProject(Base):
    __tablename__ = "projects"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    description: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[str] = mapped_column(String, default=lambda: now_iso())
    updated_at: Mapped[str] = mapped_column(String, default=lambda: now_iso())

    # Relationships
    workspaces: Mapped[List["DBWorkspace"]] = relationship(back_populates="project", lazy="selectin")


# ── ORM: Workspace ────────────────────────────────────────────────────

class DBWorkspace(Base):
    __tablename__ = "workspaces"
    __table_args__ = (
        UniqueConstraint("project_id", "name", name="uq_workspace_project_name"),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True)
    project_id: Mapped[str] = mapped_column(String, ForeignKey("projects.id"), nullable=False)
    name: Mapped[str] = mapped_column(String, nullable=False)
    repo_path: Mapped[str] = mapped_column(String, nullable=False)
    locked_files: Mapped[str] = mapped_column(Text, default="[]")      # JSON
    mirror_rules: Mapped[str] = mapped_column(Text, default="{}")      # JSON
    config: Mapped[str] = mapped_column(Text, default="{}")            # JSON
    created_at: Mapped[str] = mapped_column(String, default=lambda: now_iso())
    updated_at: Mapped[str] = mapped_column(String, default=lambda: now_iso())

    # Relationships
    project: Mapped["DBProject"] = relationship(back_populates="workspaces")
    batches: Mapped[List["DBBatch"]] = relationship(back_populates="workspace", lazy="selectin")


# ── ORM: Batch ────────────────────────────────────────────────────────

class DBBatch(Base):
    __tablename__ = "batches"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    workspace_id: Mapped[str] = mapped_column(String, ForeignKey("workspaces.id"), nullable=False)
    batch_type: Mapped[str] = mapped_column(String, nullable=False)
    predecessor_id: Mapped[Optional[str]] = mapped_column(String, ForeignKey("batches.id"), nullable=True)
    commits: Mapped[str] = mapped_column(Text, nullable=False, default="[]")  # JSON
    predecessor_branch: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False, default=BatchStatus.PENDING.value)
    lifecycle: Mapped[str] = mapped_column(String, nullable=False, default=BatchLifecycle.ACTIVE.value)
    config: Mapped[str] = mapped_column(Text, default="{}")            # JSON
    created_at: Mapped[str] = mapped_column(String, default=lambda: now_iso())
    started_at: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    completed_at: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    merged_at: Mapped[Optional[str]] = mapped_column(String, nullable=True)

    # Relationships
    workspace: Mapped["DBWorkspace"] = relationship(back_populates="batches")
    sub_batches: Mapped[List["DBSubBatch"]] = relationship(back_populates="batch", lazy="selectin")


# ── ORM: SubBatch ─────────────────────────────────────────────────────

class DBSubBatch(Base):
    __tablename__ = "sub_batches"
    __table_args__ = (
        UniqueConstraint("batch_id", "index_num", name="uq_subbatch_batch_index"),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True)
    batch_id: Mapped[str] = mapped_column(String, ForeignKey("batches.id"), nullable=False)
    index_num: Mapped[int] = mapped_column(Integer, nullable=False)
    branch_name: Mapped[str] = mapped_column(String, nullable=False)
    subbatch_base_branch: Mapped[str] = mapped_column(String, nullable=False)
    commits: Mapped[str] = mapped_column(Text, nullable=False, default="[]")  # JSON
    rebase_generation: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[str] = mapped_column(String, nullable=False, default=SubBatchStatus.PENDING.value)
    worktree_path: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    created_at: Mapped[str] = mapped_column(String, default=lambda: now_iso())
    updated_at: Mapped[str] = mapped_column(String, default=lambda: now_iso())

    # Relationships
    batch: Mapped["DBBatch"] = relationship(back_populates="sub_batches")
    tasks: Mapped[List["DBTask"]] = relationship(back_populates="sub_batch", lazy="selectin")


# ── ORM: Task ─────────────────────────────────────────────────────────

class DBTask(Base):
    __tablename__ = "tasks"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    sub_batch_id: Mapped[str] = mapped_column(String, ForeignKey("sub_batches.id"), nullable=False)
    type: Mapped[str] = mapped_column(String, nullable=False)
    rebase_generation: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[str] = mapped_column(String, nullable=False, default=TaskStatus.PENDING.value)
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=100)
    dependencies: Mapped[str] = mapped_column(Text, default="[]")     # JSON
    agent_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    max_retries: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    timeout_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=3600)
    payload: Mapped[str] = mapped_column(Text, default="{}")          # JSON
    result: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[str] = mapped_column(String, default=lambda: now_iso())
    queued_at: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    started_at: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    completed_at: Mapped[Optional[str]] = mapped_column(String, nullable=True)

    # Relationships
    sub_batch: Mapped["DBSubBatch"] = relationship(back_populates="tasks")
    runs: Mapped[List["DBTaskRun"]] = relationship(back_populates="task", lazy="selectin")


# ── ORM: TaskRun ───────────────────────────────────────────────────────

class DBTaskRun(Base):
    __tablename__ = "task_runs"
    __table_args__ = (
        UniqueConstraint("task_id", "attempt", name="uq_task_run_task_attempt"),
        Index("idx_task_runs_task_started", "task_id", "started_at"),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True)
    task_id: Mapped[str] = mapped_column(String, ForeignKey("tasks.id"), nullable=False)
    attempt: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    status: Mapped[str] = mapped_column(String, nullable=False, default=TaskRunStatus.STARTING.value)
    runner: Mapped[str] = mapped_column(String, nullable=False, default="")
    agent_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    session_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    session_key: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    prompt: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    context: Mapped[str] = mapped_column(Text, default="{}")          # JSON
    result: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    transcript_path: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    started_at: Mapped[str] = mapped_column(String, default=lambda: now_iso())
    completed_at: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    last_activity_at: Mapped[Optional[str]] = mapped_column(String, nullable=True)

    task: Mapped["DBTask"] = relationship(back_populates="runs")


# ── ORM: Agent ────────────────────────────────────────────────────────

class DBAgent(Base):
    __tablename__ = "agents"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    host: Mapped[str] = mapped_column(String, nullable=False)
    port: Mapped[int] = mapped_column(Integer, nullable=False, default=9000)
    platform: Mapped[str] = mapped_column(String, nullable=False)
    capabilities: Mapped[str] = mapped_column(Text, nullable=False, default="[]")  # JSON
    status: Mapped[str] = mapped_column(String, nullable=False, default=AgentStatus.OFFLINE.value)
    current_task_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    max_concurrent: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    heartbeat_at: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    registered_at: Mapped[str] = mapped_column(String, default=lambda: now_iso())
    config: Mapped[str] = mapped_column(Text, default="{}")           # JSON


# ── ORM: Session ──────────────────────────────────────────────────────

class DBSession(Base):
    __tablename__ = "sessions"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    task_id: Mapped[str] = mapped_column(String, ForeignKey("tasks.id"), nullable=False)
    agent_id: Mapped[str] = mapped_column(String, nullable=False)
    session_key: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    skill: Mapped[str] = mapped_column(String, nullable=False)
    working_dir: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False, default=SessionStatus.STARTING.value)
    context: Mapped[str] = mapped_column(Text, default="{}")          # JSON
    result: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    started_at: Mapped[str] = mapped_column(String, default=lambda: now_iso())
    completed_at: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    last_activity_at: Mapped[Optional[str]] = mapped_column(String, nullable=True)


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
    created_at: Mapped[str] = mapped_column(String, default=lambda: now_iso())


# ── ORM: Message ──────────────────────────────────────────────────────

class DBMessage(Base):
    __tablename__ = "messages"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    queue_name: Mapped[str] = mapped_column(String, nullable=False)
    message_type: Mapped[str] = mapped_column(String, nullable=False)
    payload: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False, default="pending")
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=100)
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    max_retries: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    created_at: Mapped[str] = mapped_column(String, default=lambda: now_iso())
    processed_at: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    completed_at: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)


# ── ORM: Snapshot ─────────────────────────────────────────────────────

class DBSnapshot(Base):
    __tablename__ = "snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    snapshot_type: Mapped[str] = mapped_column(String, nullable=False)
    file_path: Mapped[str] = mapped_column(String, nullable=False)
    checksum: Mapped[str] = mapped_column(String, nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[str] = mapped_column(String, default=lambda: now_iso())


# ═══════════════════════════════════════════════════════════════════════
#  Pydantic Schemas
# ═══════════════════════════════════════════════════════════════════════

# JSON 字段集 — 这些字段在 ORM 中存储为 TEXT，Pydantic 中为原生类型
_JSON_FIELDS = frozenset([
    "commits", "locked_files", "mirror_rules", "config",
    "capabilities", "dependencies", "payload", "result",
    "error", "context", "old_state", "new_state", "metadata",
])


class ProjectSchema(BaseModel):
    """Project Pydantic schema."""
    id: str
    name: str
    description: str = ""
    created_at: str
    updated_at: str

    model_config = {"from_attributes": True}


class WorkspaceSchema(BaseModel):
    """Workspace Pydantic schema."""
    id: str
    project_id: str
    name: str
    repo_path: str
    locked_files: List[str] = Field(default_factory=list)
    mirror_rules: Dict[str, Any] = Field(default_factory=dict)
    config: Dict[str, Any] = Field(default_factory=dict)
    created_at: str
    updated_at: str

    model_config = {"from_attributes": True}


class BatchSchema(BaseModel):
    """Batch Pydantic schema."""
    id: str
    workspace_id: str
    batch_type: str
    predecessor_id: Optional[str] = None
    commits: List[str] = Field(default_factory=list)
    predecessor_branch: str
    status: str = BatchStatus.PENDING.value
    lifecycle: str = BatchLifecycle.ACTIVE.value
    config: Dict[str, Any] = Field(default_factory=dict)
    created_at: str
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    merged_at: Optional[str] = None

    model_config = {"from_attributes": True}


class SubBatchSchema(BaseModel):
    """SubBatch Pydantic schema."""
    id: str
    batch_id: str
    index_num: int
    branch_name: str
    subbatch_base_branch: str
    commits: List[str] = Field(default_factory=list)
    rebase_generation: int = 0
    status: str = SubBatchStatus.PENDING.value
    worktree_path: Optional[str] = None
    created_at: str
    updated_at: str

    model_config = {"from_attributes": True}


class TaskSchema(BaseModel):
    """Task Pydantic schema."""
    id: str
    sub_batch_id: str
    type: str
    rebase_generation: int = 0
    status: str = TaskStatus.PENDING.value
    priority: int = 100
    dependencies: List[str] = Field(default_factory=list)
    agent_id: Optional[str] = None
    retry_count: int = 0
    max_retries: int = 3
    timeout_seconds: int = 3600
    payload: Dict[str, Any] = Field(default_factory=dict)
    result: Any = None
    error: Any = None
    created_at: str
    queued_at: Optional[str] = None
    started_at: Optional[str] = None
    completed_at: Optional[str] = None

    model_config = {"from_attributes": True}


class AgentSchema(BaseModel):
    """Agent Pydantic schema."""
    id: str
    name: str
    host: str
    port: int = 9000
    platform: str
    capabilities: List[str] = Field(default_factory=list)
    status: str = AgentStatus.OFFLINE.value
    current_task_id: Optional[str] = None
    max_concurrent: int = 1
    heartbeat_at: Optional[str] = None
    registered_at: str
    config: Dict[str, Any] = Field(default_factory=dict)

    model_config = {"from_attributes": True}


class SessionSchema(BaseModel):
    """Session Pydantic schema."""
    id: str
    task_id: str
    agent_id: str
    session_key: str
    skill: str
    working_dir: str
    status: str = SessionStatus.STARTING.value
    context: Dict[str, Any] = Field(default_factory=dict)
    result: Any = None
    started_at: str
    completed_at: Optional[str] = None
    last_activity_at: Optional[str] = None

    model_config = {"from_attributes": True}


class TaskRunSchema(BaseModel):
    """One immutable execution attempt for a Task."""
    id: str
    task_id: str
    attempt: int = 1
    status: str = TaskRunStatus.STARTING.value
    runner: str = ""
    agent_id: Optional[str] = None
    session_id: Optional[str] = None
    session_key: Optional[str] = None
    prompt: Optional[str] = None
    context: Dict[str, Any] = Field(default_factory=dict)
    result: Any = None
    error: Any = None
    transcript_path: Optional[str] = None
    started_at: str
    completed_at: Optional[str] = None
    last_activity_at: Optional[str] = None

    model_config = {"from_attributes": True}


class EventLogSchema(BaseModel):
    """EventLog Pydantic schema."""
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
#  Helpers
# ═══════════════════════════════════════════════════════════════════════


def new_id() -> str:
    return str(uuid.uuid4())


def now_iso() -> str:
    return datetime.now().isoformat()


# ═══════════════════════════════════════════════════════════════════════
#  JSON 序列化/反序列化工具
# ═══════════════════════════════════════════════════════════════════════

import json as _json


def _json_encode(val: Any) -> Optional[str]:
    """将 Python 对象序列化为 JSON 字符串（None 保持 None）。"""
    if val is None:
        return None
    if isinstance(val, str):
        return val
    return _json.dumps(val, ensure_ascii=False, default=str)


def _json_decode(val: Any) -> Any:
    """将 JSON 字符串反序列化为 Python 对象。"""
    if val is None:
        return None
    if isinstance(val, str):
        try:
            return _json.loads(val)
        except (_json.JSONDecodeError, TypeError):
            return val
    return val


# ═══════════════════════════════════════════════════════════════════════
#  ORM ↔ dict 转换工具
# ═══════════════════════════════════════════════════════════════════════


def orm_to_dict(obj: Base) -> dict:
    """将 ORM 对象转为 dict，JSON 字段自动反序列化。"""
    d = {}
    for col in obj.__table__.columns:
        key = col.key
        val = getattr(obj, key if key != "metadata" else "metadata_")
        if key in _JSON_FIELDS:
            val = _json_decode(val)
        d[key] = val
    return d


def dict_to_orm(cls: type[Base], data: dict) -> Base:
    """将 dict 转为 ORM 对象，JSON 字段自动序列化。"""
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
#  工厂函数 — 兼容旧接口，返回 dict
# ═══════════════════════════════════════════════════════════════════════


def make_project(name: str, description: str = "") -> dict:
    return {
        "id": new_id(),
        "name": name,
        "description": description,
        "created_at": now_iso(),
        "updated_at": now_iso(),
    }


def make_workspace(
    project_id: str,
    name: str,
    repo_path: str,
    locked_files: List[str] | None = None,
    mirror_rules: Dict[str, List[str]] | None = None,
    config: dict | None = None,
) -> dict:
    return {
        "id": new_id(),
        "project_id": project_id,
        "name": name,
        "repo_path": repo_path,
        "locked_files": locked_files or [],
        "mirror_rules": mirror_rules or {},
        "config": config or {},
        "created_at": now_iso(),
        "updated_at": now_iso(),
    }


def make_batch(
    workspace_id: str,
    batch_type: str,
    commits: List[str],
    predecessor_branch: str,
    predecessor_id: str | None = None,
    config: dict | None = None,
    batch_id: str | None = None,
) -> dict:
    return {
        "id": batch_id or new_id(),
        "workspace_id": workspace_id,
        "batch_type": batch_type,
        "predecessor_id": predecessor_id,
        "commits": commits,
        "predecessor_branch": predecessor_branch,
        "status": BatchStatus.PENDING.value,
        "lifecycle": BatchLifecycle.ACTIVE.value,
        "config": config or {},
        "created_at": now_iso(),
        "started_at": None,
        "completed_at": None,
        "merged_at": None,
    }


def make_sub_batch(
    batch_id: str,
    index: int,
    branch_name: str,
    subbatch_base_branch: str,
    commits: List[str],
    sub_batch_id: str | None = None,
) -> dict:
    return {
        "id": sub_batch_id or f"{batch_id}_{chr(ord('a') + index)}",
        "batch_id": batch_id,
        "index_num": index,
        "branch_name": branch_name,
        "subbatch_base_branch": subbatch_base_branch,
        "commits": commits,
        "rebase_generation": 0,
        "status": SubBatchStatus.PENDING.value,
        "worktree_path": None,
        "created_at": now_iso(),
        "updated_at": now_iso(),
    }


def make_task(
    sub_batch_id: str,
    task_type: str,
    rebase_generation: int = 0,
    priority: int = 100,
    payload: dict | None = None,
    timeout_seconds: int | None = None,
) -> dict:
    tt = TaskType(task_type)
    return {
        "id": new_id(),
        "sub_batch_id": sub_batch_id,
        "type": task_type,
        "rebase_generation": rebase_generation,
        "status": TaskStatus.PENDING.value,
        "priority": priority,
        "dependencies": [],
        "agent_id": None,
        "retry_count": 0,
        "max_retries": 3,
        "timeout_seconds": timeout_seconds or TaskTimeoutConfig.get_timeout(tt),
        "payload": payload or {},
        "result": None,
        "error": None,
        "created_at": now_iso(),
        "queued_at": None,
        "started_at": None,
        "completed_at": None,
    }


def make_agent(
    agent_id: str,
    name: str,
    host: str,
    port: int = 9000,
    platform: str = "windows",
    capabilities: List[str] | None = None,
    config: dict | None = None,
) -> dict:
    return {
        "id": agent_id,
        "name": name,
        "host": host,
        "port": port,
        "platform": platform,
        "capabilities": capabilities or [],
        "status": AgentStatus.OFFLINE.value,
        "current_task_id": None,
        "max_concurrent": 1,
        "heartbeat_at": None,
        "registered_at": now_iso(),
        "config": config or {},
    }


def make_session(
    task_id: str,
    agent_id: str,
    session_key: str,
    skill: str,
    working_dir: str,
    context: dict | None = None,
) -> dict:
    return {
        "id": new_id(),
        "task_id": task_id,
        "agent_id": agent_id,
        "session_key": session_key,
        "skill": skill,
        "working_dir": working_dir,
        "status": SessionStatus.STARTING.value,
        "context": context or {},
        "result": None,
        "started_at": now_iso(),
        "completed_at": None,
        "last_activity_at": now_iso(),
    }


def make_task_run(
    task_id: str,
    attempt: int,
    runner: str = "",
    agent_id: str | None = None,
    session_key: str | None = None,
    prompt: str | None = None,
    context: dict | None = None,
) -> dict:
    return {
        "id": new_id(),
        "task_id": task_id,
        "attempt": attempt,
        "status": TaskRunStatus.STARTING.value,
        "runner": runner,
        "agent_id": agent_id,
        "session_id": None,
        "session_key": session_key,
        "prompt": prompt,
        "context": context or {},
        "result": None,
        "error": None,
        "transcript_path": None,
        "started_at": now_iso(),
        "completed_at": None,
        "last_activity_at": now_iso(),
    }


def make_event_log(
    event_type: str,
    entity_type: str,
    entity_id: str,
    old_state: Any = None,
    new_state: Any = None,
    metadata: Any = None,
    actor: str = "system",
) -> dict:
    return {
        "event_type": event_type,
        "entity_type": entity_type,
        "entity_id": entity_id,
        "old_state": old_state,
        "new_state": new_state,
        "metadata": metadata,
        "actor": actor,
        "created_at": now_iso(),
    }
