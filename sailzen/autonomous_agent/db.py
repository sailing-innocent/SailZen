# -*- coding: utf-8 -*-
# @file db.py
# @brief Agent isolated SQLite ORM and database manager
# @author sailing-innocent
# @date 2025-06-02
# @version 1.0
# ---------------------------------
"""Agent isolated SQLite database.

CRITICAL: This database is COMPLETELY SEPARATE from sail_server's database.
It must NEVER be synced by scripts/db_sync.py.

Schema:
  - agent_schedules: Cron and interval schedules
  - agent_memories: Short-term and long-term memory
  - agent_reminders: Notification queue
  - agent_goals: High-level objectives
  - agent_run_log: Pipeline execution history (agent's view)
"""

from __future__ import annotations

import json as _json
import logging
import os
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import event, text, Index
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.pool import NullPool

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════
#  ORM Base
# ═══════════════════════════════════════════════════════════════════════


class AgentBase(DeclarativeBase):
    pass


# ═══════════════════════════════════════════════════════════════════════
#  ORM Models
# ═══════════════════════════════════════════════════════════════════════


class DBAgentSchedule(AgentBase):
    """Agent schedules (cron + interval)."""
    __tablename__ = "agent_schedules"

    id: Mapped[str] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(nullable=False)
    pipeline_id: Mapped[str] = mapped_column(nullable=False)
    schedule_type: Mapped[str] = mapped_column(nullable=False)  # 'cron' | 'interval' | 'date'
    schedule_expr: Mapped[str] = mapped_column(nullable=False)
    timezone: Mapped[str] = mapped_column(default="Asia/Shanghai")
    enabled: Mapped[int] = mapped_column(default=1)
    params: Mapped[str] = mapped_column(default="{}")  # JSON
    next_run_time: Mapped[Optional[str]] = mapped_column(nullable=True)
    last_run_time: Mapped[Optional[str]] = mapped_column(nullable=True)
    last_run_status: Mapped[Optional[str]] = mapped_column(nullable=True)
    created_at: Mapped[str] = mapped_column(default=lambda: _now_iso())
    updated_at: Mapped[str] = mapped_column(default=lambda: _now_iso())


class DBAgentMemory(AgentBase):
    """Agent memory (ephemeral + persistent context)."""
    __tablename__ = "agent_memories"

    id: Mapped[str] = mapped_column(primary_key=True)
    memory_type: Mapped[str] = mapped_column(nullable=False)  # 'short_term' | 'long_term' | 'context'
    key: Mapped[str] = mapped_column(nullable=False)
    value: Mapped[str] = mapped_column(nullable=False)  # JSON
    ttl_seconds: Mapped[Optional[int]] = mapped_column(nullable=True)
    created_at: Mapped[str] = mapped_column(default=lambda: _now_iso())
    expires_at: Mapped[Optional[str]] = mapped_column(nullable=True)

    __table_args__ = (
        Index("idx_memories_type_key", "memory_type", "key"),
        Index("idx_memories_expires", "expires_at"),
    )


class DBAgentReminder(AgentBase):
    """Reminders and alerts emitted by the agent."""
    __tablename__ = "agent_reminders"

    id: Mapped[str] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(nullable=False)
    content: Mapped[Optional[str]] = mapped_column(nullable=True)
    channel: Mapped[str] = mapped_column(nullable=False)  # 'lark_im' | 'lark_group' | 'log'
    priority: Mapped[str] = mapped_column(default="normal")  # 'low' | 'normal' | 'high' | 'urgent'
    status: Mapped[str] = mapped_column(default="pending")  # 'pending' | 'sent' | 'dismissed' | 'snoozed'
    scheduled_at: Mapped[Optional[str]] = mapped_column(nullable=True)
    sent_at: Mapped[Optional[str]] = mapped_column(nullable=True)
    pipeline_run_id: Mapped[Optional[str]] = mapped_column(nullable=True)
    context: Mapped[str] = mapped_column(default="{}")  # JSON
    created_at: Mapped[str] = mapped_column(default=lambda: _now_iso())

    __table_args__ = (
        Index("idx_reminders_status_scheduled", "status", "scheduled_at"),
    )


class DBAgentGoal(AgentBase):
    """Agent goals (higher-level objectives)."""
    __tablename__ = "agent_goals"

    id: Mapped[str] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(nullable=False)
    description: Mapped[Optional[str]] = mapped_column(nullable=True)
    status: Mapped[str] = mapped_column(default="active")  # 'active' | 'paused' | 'completed' | 'abandoned'
    priority: Mapped[int] = mapped_column(default=100)
    target_date: Mapped[Optional[str]] = mapped_column(nullable=True)
    completion_criteria: Mapped[Optional[str]] = mapped_column(nullable=True)  # JSON
    created_at: Mapped[str] = mapped_column(default=lambda: _now_iso())
    updated_at: Mapped[str] = mapped_column(default=lambda: _now_iso())


class DBAgentRunLog(AgentBase):
    """Pipeline execution log (agent's view)."""
    __tablename__ = "agent_run_log"

    id: Mapped[str] = mapped_column(primary_key=True)
    schedule_id: Mapped[Optional[str]] = mapped_column(nullable=True)
    pipeline_id: Mapped[str] = mapped_column(nullable=False)
    dag_run_id: Mapped[Optional[str]] = mapped_column(nullable=True)
    status: Mapped[str] = mapped_column(nullable=False)  # 'started' | 'completed' | 'failed'
    summary: Mapped[Optional[str]] = mapped_column(nullable=True)
    started_at: Mapped[str] = mapped_column(default=lambda: _now_iso())
    completed_at: Mapped[Optional[str]] = mapped_column(nullable=True)
    error: Mapped[Optional[str]] = mapped_column(nullable=True)

    __table_args__ = (
        Index("idx_run_log_schedule", "schedule_id", "started_at"),
    )


# ═══════════════════════════════════════════════════════════════════════
#  Helpers
# ═══════════════════════════════════════════════════════════════════════


def _now_iso() -> str:
    return datetime.now().isoformat()


def _new_id() -> str:
    return str(uuid.uuid4())


# ═══════════════════════════════════════════════════════════════════════
#  Database Manager
# ═══════════════════════════════════════════════════════════════════════


class AgentDatabase:
    """Async SQLAlchemy database manager for the autonomous agent.

    Usage::

        db = AgentDatabase("data/agent/db/agent.db")
        await db.connect()
        async with db.session() as session:
            ...
        await db.close()
    """

    def __init__(self, db_path: str = "data/agent/db/agent.db"):
        self.db_path = db_path
        self._engine: Optional[AsyncEngine] = None
        self._session_factory: Optional[async_sessionmaker[AsyncSession]] = None

    async def connect(self) -> None:
        """Initialize engine, configure PRAGMAs, create tables."""
        os.makedirs(os.path.dirname(self.db_path) or ".", exist_ok=True)

        url = f"sqlite+aiosqlite:///{self.db_path}"
        self._engine = create_async_engine(
            url,
            echo=False,
            poolclass=NullPool,
        )

        @event.listens_for(self._engine.sync_engine, "connect")
        def _set_sqlite_pragmas(dbapi_conn, connection_record):
            cursor = dbapi_conn.cursor()
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA synchronous=NORMAL")
            cursor.execute("PRAGMA cache_size=-32768")
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.execute("PRAGMA busy_timeout=5000")
            cursor.close()

        async with self._engine.begin() as conn:
            await conn.run_sync(AgentBase.metadata.create_all)

        self._session_factory = async_sessionmaker(
            self._engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )

        logger.info("Agent DB connected: %s", self.db_path)

    async def close(self) -> None:
        if self._engine:
            await self._engine.dispose()
            self._engine = None
            self._session_factory = None

    @property
    def engine(self) -> AsyncEngine:
        assert self._engine, "Database not connected"
        return self._engine

    def session(self) -> AsyncSession:
        assert self._session_factory, "Database not connected"
        return self._session_factory()

    async def get_stats(self) -> dict:
        stats = {}
        tables = [
            "agent_schedules", "agent_memories", "agent_reminders",
            "agent_goals", "agent_run_log",
        ]
        async with self.session() as session:
            for table in tables:
                result = await session.execute(text(f"SELECT COUNT(*) FROM {table}"))
                stats[table] = result.scalar() or 0
        if os.path.exists(self.db_path):
            stats["db_size_bytes"] = os.path.getsize(self.db_path)
        return stats

    async def check_integrity(self) -> bool:
        try:
            async with self.session() as session:
                result = await session.execute(text("PRAGMA integrity_check"))
                row = result.first()
                return row is not None and row[0] == "ok"
        except Exception:
            return False

    # ── CRUD helpers for schedules ────────────────────────────────────

    async def create_schedule(self, data: dict) -> dict:
        data.setdefault("id", _new_id())
        data.setdefault("created_at", _now_iso())
        data.setdefault("updated_at", _now_iso())
        async with self.session() as session:
            obj = DBAgentSchedule(**data)
            session.add(obj)
            await session.commit()
        return data

    async def list_schedules(self, enabled_only: bool = False) -> List[dict]:
        async with self.session() as session:
            query = "SELECT * FROM agent_schedules"
            if enabled_only:
                query += " WHERE enabled = 1"
            result = await session.execute(text(query))
            rows = result.mappings().all()
            return [dict(row) for row in rows]

    async def get_schedule(self, schedule_id: str) -> Optional[dict]:
        async with self.session() as session:
            result = await session.execute(
                text("SELECT * FROM agent_schedules WHERE id = :id"),
                {"id": schedule_id}
            )
            row = result.mappings().first()
            return dict(row) if row else None

    async def update_schedule(self, schedule_id: str, data: dict) -> bool:
        data["updated_at"] = _now_iso()
        async with self.session() as session:
            obj = await session.get(DBAgentSchedule, schedule_id)
            if not obj:
                return False
            for key, val in data.items():
                if hasattr(obj, key):
                    setattr(obj, key, val)
            await session.commit()
        return True

    async def delete_schedule(self, schedule_id: str) -> bool:
        async with self.session() as session:
            obj = await session.get(DBAgentSchedule, schedule_id)
            if not obj:
                return False
            await session.delete(obj)
            await session.commit()
        return True

    # ── CRUD helpers for memories ─────────────────────────────────────

    async def create_memory(self, data: dict) -> dict:
        data.setdefault("id", _new_id())
        data.setdefault("created_at", _now_iso())
        async with self.session() as session:
            obj = DBAgentMemory(**data)
            session.add(obj)
            await session.commit()
        return data

    async def get_memory(self, memory_type: str, key: str) -> Optional[dict]:
        async with self.session() as session:
            result = await session.execute(
                text("SELECT * FROM agent_memories WHERE memory_type = :mt AND key = :k ORDER BY created_at DESC LIMIT 1"),
                {"mt": memory_type, "k": key}
            )
            row = result.mappings().first()
            return dict(row) if row else None

    async def list_memories(self, memory_type: Optional[str] = None, key_prefix: Optional[str] = None) -> List[dict]:
        async with self.session() as session:
            conditions = []
            params = {}
            if memory_type:
                conditions.append("memory_type = :mt")
                params["mt"] = memory_type
            if key_prefix:
                conditions.append("key LIKE :kp")
                params["kp"] = f"{key_prefix}%"
            query = "SELECT * FROM agent_memories"
            if conditions:
                query += " WHERE " + " AND ".join(conditions)
            query += " ORDER BY created_at DESC"
            result = await session.execute(text(query), params)
            rows = result.mappings().all()
            return [dict(row) for row in rows]

    async def delete_memory(self, memory_id: str) -> bool:
        async with self.session() as session:
            obj = await session.get(DBAgentMemory, memory_id)
            if not obj:
                return False
            await session.delete(obj)
            await session.commit()
        return True

    async def cleanup_expired_memories(self) -> int:
        now = _now_iso()
        async with self.session() as session:
            result = await session.execute(
                text("DELETE FROM agent_memories WHERE expires_at IS NOT NULL AND expires_at < :now"),
                {"now": now}
            )
            await session.commit()
            return result.rowcount or 0

    # ── CRUD helpers for reminders ────────────────────────────────────

    async def create_reminder(self, data: dict) -> dict:
        data.setdefault("id", _new_id())
        data.setdefault("created_at", _now_iso())
        async with self.session() as session:
            obj = DBAgentReminder(**data)
            session.add(obj)
            await session.commit()
        return data

    async def list_reminders(self, status: Optional[str] = None, limit: int = 100) -> List[dict]:
        async with self.session() as session:
            query = "SELECT * FROM agent_reminders"
            params = {}
            if status:
                query += " WHERE status = :st"
                params["st"] = status
            query += " ORDER BY created_at DESC LIMIT :limit"
            params["limit"] = limit
            result = await session.execute(text(query), params)
            rows = result.mappings().all()
            return [dict(row) for row in rows]

    async def update_reminder(self, reminder_id: str, data: dict) -> bool:
        async with self.session() as session:
            obj = await session.get(DBAgentReminder, reminder_id)
            if not obj:
                return False
            for key, val in data.items():
                if hasattr(obj, key):
                    setattr(obj, key, val)
            await session.commit()
        return True

    # ── CRUD helpers for goals ────────────────────────────────────────

    async def create_goal(self, data: dict) -> dict:
        data.setdefault("id", _new_id())
        data.setdefault("created_at", _now_iso())
        data.setdefault("updated_at", _now_iso())
        async with self.session() as session:
            obj = DBAgentGoal(**data)
            session.add(obj)
            await session.commit()
        return data

    async def list_goals(self, status: Optional[str] = None) -> List[dict]:
        async with self.session() as session:
            query = "SELECT * FROM agent_goals"
            if status:
                query += f" WHERE status = '{status}'"
            query += " ORDER BY priority ASC, created_at DESC"
            result = await session.execute(text(query))
            rows = result.mappings().all()
            return [dict(row) for row in rows]

    async def update_goal(self, goal_id: str, data: dict) -> bool:
        data["updated_at"] = _now_iso()
        async with self.session() as session:
            obj = await session.get(DBAgentGoal, goal_id)
            if not obj:
                return False
            for key, val in data.items():
                if hasattr(obj, key):
                    setattr(obj, key, val)
            await session.commit()
        return True

    # ── CRUD helpers for run log ──────────────────────────────────────

    async def create_run_log(self, data: dict) -> dict:
        data.setdefault("id", _new_id())
        data.setdefault("started_at", _now_iso())
        async with self.session() as session:
            obj = DBAgentRunLog(**data)
            session.add(obj)
            await session.commit()
        return data

    async def update_run_log(self, log_id: str, data: dict) -> bool:
        async with self.session() as session:
            obj = await session.get(DBAgentRunLog, log_id)
            if not obj:
                return False
            for key, val in data.items():
                if hasattr(obj, key):
                    setattr(obj, key, val)
            await session.commit()
        return True

    async def list_run_logs(self, schedule_id: Optional[str] = None, limit: int = 100) -> List[dict]:
        async with self.session() as session:
            query = "SELECT * FROM agent_run_log"
            params = {"limit": limit}
            if schedule_id:
                query += " WHERE schedule_id = :sid"
                params["sid"] = schedule_id
            query += " ORDER BY started_at DESC LIMIT :limit"
            result = await session.execute(text(query), params)
            rows = result.mappings().all()
            return [dict(row) for row in rows]
