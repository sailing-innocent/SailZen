# -*- coding: utf-8 -*-
# @file db.py
# @brief SailTick 隔离 SQLite 数据库（st_* 表族）
# @author sailing-innocent
# @date 2026-10-27
# @version 1.0
# ---------------------------------
"""SailTick 隔离数据库。

CRITICAL: 本库与 sail_server 主库完全隔离，禁止被 scripts/db_sync.py 同步
（db_sync.py 的排除清单已含 data/sailtick）。

Schema（设计文档 §9.2）:
  st_ticks       Tick 实例（幂等键 slot+date、状态机、成本）
  st_handoffs    交接文档指针与摘要
  st_memories    记忆（episodic/semantic/procedural 三层）
  st_profile     用户画像（confidence + source）
  st_plans       计划版本（active 标记当前生效版本）
  st_episodes    Tick 事件流
  st_schedules   唤醒排程（APScheduler 持久化）
  st_run_log     运行日志
"""

from __future__ import annotations

import json as _json
import logging
import os
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import Index, delete, select, text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.pool import NullPool

logger = logging.getLogger(__name__)


def _now_iso() -> str:
    return datetime.now().isoformat()


def _new_id() -> str:
    return uuid.uuid4().hex


class TickBase(DeclarativeBase):
    pass


# ═══════════════════════════════════════════════════════════════════════
#  ORM Models
# ═══════════════════════════════════════════════════════════════════════


class DBTick(TickBase):
    """Tick 实例。"""

    __tablename__ = "st_ticks"

    id: Mapped[str] = mapped_column(primary_key=True, default=_new_id)
    slot: Mapped[str] = mapped_column(nullable=False)  # morning_checkin 等
    tick_date: Mapped[str] = mapped_column(nullable=False)  # YYYY-MM-DD
    idempotency_key: Mapped[str] = mapped_column(nullable=False, unique=True)  # slot:date
    state: Mapped[str] = mapped_column(default="running")  # running|completed|interrupted|skipped|failed
    plan_json: Mapped[Optional[str]] = mapped_column(nullable=True)
    cost_tokens: Mapped[int] = mapped_column(default=0)
    cost_usd: Mapped[float] = mapped_column(default=0.0)
    error: Mapped[Optional[str]] = mapped_column(nullable=True)
    started_at: Mapped[str] = mapped_column(default=_now_iso)
    ended_at: Mapped[Optional[str]] = mapped_column(nullable=True)

    __table_args__ = (Index("idx_ticks_date", "tick_date"),)


class DBHandoff(TickBase):
    """交接文档。"""

    __tablename__ = "st_handoffs"

    id: Mapped[str] = mapped_column(primary_key=True, default=_new_id)
    tick_id: Mapped[str] = mapped_column(nullable=False)
    path: Mapped[str] = mapped_column(nullable=False)
    summary: Mapped[str] = mapped_column(default="")
    created_at: Mapped[str] = mapped_column(default=_now_iso)


class DBMemory(TickBase):
    """记忆（episodic/semantic/procedural）。"""

    __tablename__ = "st_memories"

    id: Mapped[str] = mapped_column(primary_key=True, default=_new_id)
    memory_type: Mapped[str] = mapped_column(nullable=False)
    key: Mapped[str] = mapped_column(nullable=False)
    value: Mapped[str] = mapped_column(nullable=False)  # JSON
    ttl_seconds: Mapped[Optional[int]] = mapped_column(nullable=True)
    expires_at: Mapped[Optional[str]] = mapped_column(nullable=True)
    created_at: Mapped[str] = mapped_column(default=_now_iso)

    __table_args__ = (
        Index("idx_mem_type_key", "memory_type", "key"),
        Index("idx_mem_expires", "expires_at"),
    )


class DBProfile(TickBase):
    """用户画像项。"""

    __tablename__ = "st_profile"

    key: Mapped[str] = mapped_column(primary_key=True)
    value: Mapped[str] = mapped_column(nullable=False)  # JSON
    confidence: Mapped[float] = mapped_column(default=0.5)
    source: Mapped[str] = mapped_column(default="assumed")  # asked|observed|assumed
    updated_at: Mapped[str] = mapped_column(default=_now_iso)


class DBPlan(TickBase):
    """计划版本。"""

    __tablename__ = "st_plans"

    id: Mapped[str] = mapped_column(primary_key=True, default=_new_id)
    version: Mapped[str] = mapped_column(nullable=False)  # v0.1 / v1.0
    goal: Mapped[str] = mapped_column(default="70kg")
    content: Mapped[str] = mapped_column(nullable=False)
    rationale: Mapped[str] = mapped_column(default="")
    active: Mapped[int] = mapped_column(default=0)
    created_at: Mapped[str] = mapped_column(default=_now_iso)


class DBEpisode(TickBase):
    """Tick 事件流。"""

    __tablename__ = "st_episodes"

    id: Mapped[str] = mapped_column(primary_key=True, default=_new_id)
    tick_id: Mapped[Optional[str]] = mapped_column(nullable=True)
    kind: Mapped[str] = mapped_column(nullable=False)  # scan|plan|work|handoff|note
    content: Mapped[str] = mapped_column(nullable=False)
    created_at: Mapped[str] = mapped_column(default=_now_iso)

    __table_args__ = (Index("idx_episodes_tick", "tick_id"),)


class DBSchedule(TickBase):
    """唤醒排程。"""

    __tablename__ = "st_schedules"

    id: Mapped[str] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(nullable=False)
    slot: Mapped[str] = mapped_column(nullable=False)
    enabled: Mapped[int] = mapped_column(default=1)
    params: Mapped[str] = mapped_column(default="{}")  # JSON
    next_run_time: Mapped[Optional[str]] = mapped_column(nullable=True)
    last_run_time: Mapped[Optional[str]] = mapped_column(nullable=True)
    last_run_status: Mapped[Optional[str]] = mapped_column(nullable=True)
    created_at: Mapped[str] = mapped_column(default=_now_iso)
    updated_at: Mapped[str] = mapped_column(default=_now_iso)


class DBRunLog(TickBase):
    """运行日志。"""

    __tablename__ = "st_run_log"

    id: Mapped[str] = mapped_column(primary_key=True, default=_new_id)
    schedule_id: Mapped[Optional[str]] = mapped_column(nullable=True)
    tick_id: Mapped[Optional[str]] = mapped_column(nullable=True)
    pipeline_id: Mapped[str] = mapped_column(nullable=False)
    status: Mapped[str] = mapped_column(nullable=False)  # started|completed|failed
    summary: Mapped[Optional[str]] = mapped_column(nullable=True)
    started_at: Mapped[str] = mapped_column(default=_now_iso)
    completed_at: Mapped[Optional[str]] = mapped_column(nullable=True)
    error: Mapped[Optional[str]] = mapped_column(nullable=True)


# ═══════════════════════════════════════════════════════════════════════
#  Database
# ═══════════════════════════════════════════════════════════════════════


class TickDatabase:
    """SailTick 隔离 SQLite 数据库管理器。"""

    def __init__(self, db_path: str):
        self.db_path = db_path
        self._engine: Optional[AsyncEngine] = None
        self._session_factory: Optional[async_sessionmaker[AsyncSession]] = None

    async def connect(self) -> None:
        os.makedirs(os.path.dirname(self.db_path) or ".", exist_ok=True)
        url = f"sqlite+aiosqlite:///{self.db_path}"
        self._engine = create_async_engine(url, echo=False, poolclass=NullPool)

        from sqlalchemy import event

        @event.listens_for(self._engine.sync_engine, "connect")
        def _set_pragmas(dbapi_conn, _record):
            cursor = dbapi_conn.cursor()
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA synchronous=NORMAL")
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.execute("PRAGMA busy_timeout=5000")
            cursor.close()

        async with self._engine.begin() as conn:
            await conn.run_sync(TickBase.metadata.create_all)

        self._session_factory = async_sessionmaker(
            self._engine, class_=AsyncSession, expire_on_commit=False
        )
        logger.info("SailTick DB connected: %s", self.db_path)

    async def close(self) -> None:
        if self._engine:
            await self._engine.dispose()
            self._engine = None
            self._session_factory = None

    @property
    def engine(self) -> AsyncEngine:
        assert self._engine, "TickDatabase not connected"
        return self._engine

    def session(self) -> AsyncSession:
        assert self._session_factory, "TickDatabase not connected"
        return self._session_factory()

    # ── Ticks ─────────────────────────────────────────────────────────

    async def create_tick(self, slot: str, tick_date: str) -> dict:
        """创建 Tick 实例。幂等键冲突时返回已有实例。"""
        async with self.session() as s:
            existing = await s.execute(
                select(DBTick).where(DBTick.idempotency_key == f"{slot}:{tick_date}")
            )
            row = existing.scalar_one_or_none()
            if row:
                return self._tick_dict(row)
            row = DBTick(slot=slot, tick_date=tick_date, idempotency_key=f"{slot}:{tick_date}")
            s.add(row)
            await s.commit()
            return self._tick_dict(row)

    async def get_tick(self, tick_id: str) -> Optional[dict]:
        async with self.session() as s:
            row = await s.get(DBTick, tick_id)
            return self._tick_dict(row) if row else None

    async def find_tick(self, slot: str, tick_date: str) -> Optional[dict]:
        async with self.session() as s:
            result = await s.execute(
                select(DBTick).where(DBTick.idempotency_key == f"{slot}:{tick_date}")
            )
            row = result.scalar_one_or_none()
            return self._tick_dict(row) if row else None

    async def update_tick(
        self, tick_id: str, state: Optional[str] = None, **fields: Any
    ) -> Optional[dict]:
        async with self.session() as s:
            row = await s.get(DBTick, tick_id)
            if not row:
                return None
            if state is not None:
                row.state = state
            for k, v in fields.items():
                col = "plan_json" if k == "plan" else k
                if col == "plan_json" and not isinstance(v, str):
                    v = _json.dumps(v, ensure_ascii=False)
                setattr(row, col, v)
            await s.commit()
            return self._tick_dict(row)

    async def add_tick_cost(self, tick_id: str, tokens: int, usd: float) -> None:
        async with self.session() as s:
            row = await s.get(DBTick, tick_id)
            if row:
                row.cost_tokens = (row.cost_tokens or 0) + tokens
                row.cost_usd = (row.cost_usd or 0.0) + usd
                await s.commit()

    async def list_ticks(self, limit: int = 50) -> List[dict]:
        async with self.session() as s:
            result = await s.execute(
                select(DBTick).order_by(DBTick.started_at.desc()).limit(limit)
            )
            return [self._tick_dict(r) for r in result.scalars().all()]

    async def get_running_ticks(self) -> List[dict]:
        async with self.session() as s:
            result = await s.execute(select(DBTick).where(DBTick.state == "running"))
            return [self._tick_dict(r) for r in result.scalars().all()]

    async def sum_cost_today(self) -> int:
        today = datetime.now().strftime("%Y-%m-%d")
        async with self.session() as s:
            result = await s.execute(
                text("SELECT COALESCE(SUM(cost_tokens),0) FROM st_ticks WHERE tick_date = :d"),
                {"d": today},
            )
            return int(result.scalar() or 0)

    @staticmethod
    def _tick_dict(row: DBTick) -> dict:
        return {
            "id": row.id,
            "slot": row.slot,
            "tick_date": row.tick_date,
            "idempotency_key": row.idempotency_key,
            "state": row.state,
            "plan": _json.loads(row.plan_json) if row.plan_json else None,
            "cost_tokens": row.cost_tokens,
            "cost_usd": row.cost_usd,
            "error": row.error,
            "started_at": row.started_at,
            "ended_at": row.ended_at,
        }

    # ── Handoffs ──────────────────────────────────────────────────────

    async def create_handoff(self, tick_id: str, path: str, summary: str) -> dict:
        async with self.session() as s:
            row = DBHandoff(tick_id=tick_id, path=path, summary=summary)
            s.add(row)
            await s.commit()
            return {"id": row.id, "tick_id": tick_id, "path": path, "summary": summary}

    async def get_latest_handoff(self) -> Optional[dict]:
        async with self.session() as s:
            result = await s.execute(
                select(DBHandoff).order_by(DBHandoff.created_at.desc()).limit(1)
            )
            row = result.scalar_one_or_none()
            if not row:
                return None
            return {
                "id": row.id,
                "tick_id": row.tick_id,
                "path": row.path,
                "summary": row.summary,
                "created_at": row.created_at,
            }

    async def list_handoffs(self, limit: int = 30) -> List[dict]:
        async with self.session() as s:
            result = await s.execute(
                select(DBHandoff).order_by(DBHandoff.created_at.desc()).limit(limit)
            )
            return [
                {
                    "id": r.id,
                    "tick_id": r.tick_id,
                    "path": r.path,
                    "summary": r.summary,
                    "created_at": r.created_at,
                }
                for r in result.scalars().all()
            ]

    # ── Memories ──────────────────────────────────────────────────────

    async def create_memory(
        self,
        memory_type: str,
        key: str,
        value: Any,
        ttl_seconds: Optional[int] = None,
        expires_at: Optional[str] = None,
    ) -> dict:
        async with self.session() as s:
            row = DBMemory(
                memory_type=memory_type,
                key=key,
                value=_json.dumps(value, ensure_ascii=False, default=str),
                ttl_seconds=ttl_seconds,
                expires_at=expires_at,
            )
            s.add(row)
            await s.commit()
            return {"id": row.id, "memory_type": memory_type, "key": key}

    async def get_memory(self, memory_type: str, key: str) -> Optional[dict]:
        async with self.session() as s:
            result = await s.execute(
                select(DBMemory).where(
                    DBMemory.memory_type == memory_type, DBMemory.key == key
                )
            )
            row = result.scalar_one_or_none()
            if not row:
                return None
            return self._memory_dict(row)

    async def list_memories(
        self, memory_type: Optional[str] = None, key_prefix: Optional[str] = None, limit: int = 200
    ) -> List[dict]:
        async with self.session() as s:
            stmt = select(DBMemory).order_by(DBMemory.created_at.desc()).limit(limit)
            if memory_type:
                stmt = stmt.where(DBMemory.memory_type == memory_type)
            result = await s.execute(stmt)
            rows = [self._memory_dict(r) for r in result.scalars().all()]
            if key_prefix:
                rows = [r for r in rows if r["key"].startswith(key_prefix)]
            return rows

    async def delete_memory(self, memory_id: str) -> bool:
        async with self.session() as s:
            result = await s.execute(delete(DBMemory).where(DBMemory.id == memory_id))
            await s.commit()
            return result.rowcount > 0

    async def cleanup_expired_memories(self) -> int:
        now = _now_iso()
        async with self.session() as s:
            result = await s.execute(
                delete(DBMemory).where(
                    DBMemory.expires_at.isnot(None), DBMemory.expires_at < now
                )
            )
            await s.commit()
            return result.rowcount or 0

    @staticmethod
    def _memory_dict(row: DBMemory) -> dict:
        try:
            value = _json.loads(row.value)
        except (_json.JSONDecodeError, TypeError):
            value = row.value
        return {
            "id": row.id,
            "memory_type": row.memory_type,
            "key": row.key,
            "value": value,
            "expires_at": row.expires_at,
            "created_at": row.created_at,
        }

    # ── Profile ───────────────────────────────────────────────────────

    async def set_profile(self, key: str, value: Any, confidence: float, source: str) -> dict:
        async with self.session() as s:
            row = await s.get(DBProfile, key)
            if not row:
                row = DBProfile(key=key, value="", confidence=confidence, source=source)
                s.add(row)
            row.value = _json.dumps(value, ensure_ascii=False, default=str)
            row.confidence = confidence
            row.source = source
            row.updated_at = _now_iso()
            await s.commit()
            return {"key": key, "confidence": confidence, "source": source}

    async def get_profile(self, key: str) -> Optional[dict]:
        async with self.session() as s:
            row = await s.get(DBProfile, key)
            if not row:
                return None
            try:
                value = _json.loads(row.value)
            except (_json.JSONDecodeError, TypeError):
                value = row.value
            return {
                "key": row.key,
                "value": value,
                "confidence": row.confidence,
                "source": row.source,
                "updated_at": row.updated_at,
            }

    async def list_profile(self) -> List[dict]:
        async with self.session() as s:
            result = await s.execute(select(DBProfile))
            out = []
            for row in result.scalars().all():
                try:
                    value = _json.loads(row.value)
                except (_json.JSONDecodeError, TypeError):
                    value = row.value
                out.append(
                    {
                        "key": row.key,
                        "value": value,
                        "confidence": row.confidence,
                        "source": row.source,
                        "updated_at": row.updated_at,
                    }
                )
            return out

    # ── Plans ─────────────────────────────────────────────────────────

    async def create_plan(
        self, version: str, goal: str, content: str, rationale: str, active: bool = False
    ) -> dict:
        async with self.session() as s:
            if active:
                result = await s.execute(select(DBPlan))
                for row in result.scalars().all():
                    row.active = 0
            row = DBPlan(
                version=version, goal=goal, content=content, rationale=rationale, active=1 if active else 0
            )
            s.add(row)
            await s.commit()
            return {"id": row.id, "version": version, "goal": goal, "active": active}

    async def get_active_plan(self) -> Optional[dict]:
        async with self.session() as s:
            result = await s.execute(select(DBPlan).where(DBPlan.active == 1))
            row = result.scalar_one_or_none()
            return self._plan_dict(row) if row else None

    async def list_plans(self, limit: int = 20) -> List[dict]:
        async with self.session() as s:
            result = await s.execute(
                select(DBPlan).order_by(DBPlan.created_at.desc()).limit(limit)
            )
            return [self._plan_dict(r) for r in result.scalars().all()]

    @staticmethod
    def _plan_dict(row: DBPlan) -> dict:
        return {
            "id": row.id,
            "version": row.version,
            "goal": row.goal,
            "content": row.content,
            "rationale": row.rationale,
            "active": bool(row.active),
            "created_at": row.created_at,
        }

    # ── Episodes ──────────────────────────────────────────────────────

    async def create_episode(self, tick_id: Optional[str], kind: str, content: Any) -> dict:
        async with self.session() as s:
            row = DBEpisode(
                tick_id=tick_id,
                kind=kind,
                content=_json.dumps(content, ensure_ascii=False, default=str),
            )
            s.add(row)
            await s.commit()
            return {"id": row.id, "tick_id": tick_id, "kind": kind}

    async def list_episodes(
        self, tick_id: Optional[str] = None, limit: int = 100
    ) -> List[dict]:
        async with self.session() as s:
            stmt = select(DBEpisode).order_by(DBEpisode.created_at.desc()).limit(limit)
            if tick_id:
                stmt = stmt.where(DBEpisode.tick_id == tick_id)
            result = await s.execute(stmt)
            out = []
            for row in result.scalars().all():
                try:
                    content = _json.loads(row.content)
                except (_json.JSONDecodeError, TypeError):
                    content = row.content
                out.append(
                    {
                        "id": row.id,
                        "tick_id": row.tick_id,
                        "kind": row.kind,
                        "content": content,
                        "created_at": row.created_at,
                    }
                )
            return out

    # ── Schedules ─────────────────────────────────────────────────────

    async def create_schedule(self, data: dict) -> dict:
        async with self.session() as s:
            row = DBSchedule(
                id=data["id"],
                name=data.get("name", data["id"]),
                slot=data.get("slot", ""),
                enabled=1 if data.get("enabled", True) else 0,
                params=_json.dumps(data.get("params", {}), ensure_ascii=False),
                next_run_time=data.get("next_run_time"),
                last_run_time=data.get("last_run_time"),
                last_run_status=data.get("last_run_status"),
            )
            s.add(row)
            await s.merge(row)
            await s.commit()
            return data

    async def list_schedules(self, enabled_only: bool = False) -> List[dict]:
        async with self.session() as s:
            stmt = select(DBSchedule)
            if enabled_only:
                stmt = stmt.where(DBSchedule.enabled == 1)
            result = await s.execute(stmt)
            return [
                {
                    "id": r.id,
                    "name": r.name,
                    "slot": r.slot,
                    "enabled": bool(r.enabled),
                    "params": _json.loads(r.params or "{}"),
                    "next_run_time": r.next_run_time,
                    "last_run_time": r.last_run_time,
                    "last_run_status": r.last_run_status,
                }
                for r in result.scalars().all()
            ]

    async def update_schedule(self, schedule_id: str, fields: dict) -> bool:
        async with self.session() as s:
            row = await s.get(DBSchedule, schedule_id)
            if not row:
                return False
            for k, v in fields.items():
                if k == "params" and not isinstance(v, str):
                    v = _json.dumps(v, ensure_ascii=False)
                setattr(row, k, v)
            row.updated_at = _now_iso()
            await s.commit()
            return True

    async def delete_schedule(self, schedule_id: str) -> bool:
        async with self.session() as s:
            row = await s.get(DBSchedule, schedule_id)
            if not row:
                return False
            await s.delete(row)
            await s.commit()
            return True

    # ── Run log ───────────────────────────────────────────────────────

    async def create_run_log(self, data: dict) -> dict:
        async with self.session() as s:
            row = DBRunLog(
                schedule_id=data.get("schedule_id"),
                tick_id=data.get("tick_id"),
                pipeline_id=data.get("pipeline_id", ""),
                status=data.get("status", "started"),
                summary=data.get("summary"),
                error=data.get("error"),
                completed_at=data.get("completed_at"),
            )
            s.add(row)
            await s.commit()
            return {"id": row.id, "pipeline_id": row.pipeline_id, "status": row.status}

    async def update_run_log(self, log_id: str, fields: dict) -> bool:
        async with self.session() as s:
            row = await s.get(DBRunLog, log_id)
            if not row:
                return False
            for k, v in fields.items():
                setattr(row, k, v)
            await s.commit()
            return True

    # ── Stats ─────────────────────────────────────────────────────────

    async def get_stats(self) -> dict:
        async with self.session() as s:
            stats: Dict[str, int] = {}
            for table in (
                "st_ticks",
                "st_handoffs",
                "st_memories",
                "st_profile",
                "st_plans",
                "st_episodes",
                "st_schedules",
                "st_run_log",
            ):
                result = await s.execute(text(f"SELECT COUNT(*) FROM {table}"))
                stats[table] = int(result.scalar() or 0)
            if os.path.exists(self.db_path):
                stats["db_size_bytes"] = os.path.getsize(self.db_path)
            return stats
