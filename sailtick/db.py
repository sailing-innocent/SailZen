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


class DBRuntimeState(TickBase):
    """运行时键值状态（灰度开关、熔断器状态等，跨重启持久化）。"""

    __tablename__ = "st_runtime_state"

    key: Mapped[str] = mapped_column(primary_key=True)
    value: Mapped[str] = mapped_column(nullable=False)  # JSON
    updated_at: Mapped[str] = mapped_column(default=_now_iso)


class DBAITrace(TickBase):
    """AI 全链路 Trace 主记录（本地隔离库权威副本）。"""

    __tablename__ = "st_ai_traces"

    trace_id: Mapped[str] = mapped_column(primary_key=True, default=_new_id)
    service: Mapped[str] = mapped_column(default="sailtick")
    tick_id: Mapped[str] = mapped_column(default="")
    slot: Mapped[str] = mapped_column(default="")
    tick_date: Mapped[str] = mapped_column(default="")
    trigger_source: Mapped[str] = mapped_column(default="scheduler")
    mode: Mapped[str] = mapped_column(default="live")
    status: Mapped[str] = mapped_column(default="running")
    plan_source: Mapped[str] = mapped_column(default="none")
    started_at: Mapped[str] = mapped_column(default=_now_iso)
    ended_at: Mapped[Optional[str]] = mapped_column(nullable=True)
    duration_ms: Mapped[float] = mapped_column(default=0.0)
    llm_calls_count: Mapped[int] = mapped_column(default=0)
    prompt_tokens: Mapped[int] = mapped_column(default=0)
    completion_tokens: Mapped[int] = mapped_column(default=0)
    total_tokens: Mapped[int] = mapped_column(default=0)
    cost_usd: Mapped[float] = mapped_column(default=0.0)
    tickets_created: Mapped[int] = mapped_column(default=0)
    tickets_throttled: Mapped[int] = mapped_column(default=0)
    actions_executed: Mapped[int] = mapped_column(default=0)
    actions_failed: Mapped[int] = mapped_column(default=0)
    summary: Mapped[str] = mapped_column(default="")
    error: Mapped[Optional[str]] = mapped_column(nullable=True)
    meta_json: Mapped[str] = mapped_column(default="{}")

    __table_args__ = (
        Index("idx_st_ai_traces_started", "started_at"),
        Index("idx_st_ai_traces_tick", "tick_id"),
    )


class DBAITraceSpan(TickBase):
    """AI Trace 子阶段与调用 Span 明细。"""

    __tablename__ = "st_ai_trace_spans"

    id: Mapped[str] = mapped_column(primary_key=True, default=_new_id)
    trace_id: Mapped[str] = mapped_column(nullable=False)
    span_id: Mapped[str] = mapped_column(nullable=False)
    parent_span_id: Mapped[Optional[str]] = mapped_column(nullable=True)
    seq: Mapped[int] = mapped_column(default=0)
    stage: Mapped[str] = mapped_column(nullable=False)
    name: Mapped[str] = mapped_column(nullable=False)
    status: Mapped[str] = mapped_column(default="ok")
    started_at: Mapped[str] = mapped_column(default=_now_iso)
    ended_at: Mapped[Optional[str]] = mapped_column(nullable=True)
    duration_ms: Mapped[float] = mapped_column(default=0.0)
    input_summary: Mapped[str] = mapped_column(default="")
    output_summary: Mapped[str] = mapped_column(default="")
    payload_json: Mapped[str] = mapped_column(default="{}")
    error: Mapped[Optional[str]] = mapped_column(nullable=True)

    __table_args__ = (
        Index("idx_st_ai_trace_spans_trace", "trace_id", "seq"),
    )


class DBModelSnapshot(TickBase):
    """夜间数学建模与预测快照（st_model_snapshots）。"""

    __tablename__ = "st_model_snapshots"

    id: Mapped[str] = mapped_column(primary_key=True, default=_new_id)
    snapshot_date: Mapped[str] = mapped_column(nullable=False)  # YYYY-MM-DD
    window_days: Mapped[int] = mapped_column(default=90)
    model_type: Mapped[str] = mapped_column(default="ewma_wls")
    sample_count: Mapped[int] = mapped_column(default=0)
    latest_weight_kg: Mapped[Optional[float]] = mapped_column(nullable=True)
    ewma_weight_kg: Mapped[Optional[float]] = mapped_column(nullable=True)
    target_weight_kg: Mapped[float] = mapped_column(default=70.0)
    weekly_rate_kg: Mapped[Optional[float]] = mapped_column(nullable=True)
    eta_date: Mapped[Optional[str]] = mapped_column(nullable=True)
    eta_optimistic_date: Mapped[Optional[str]] = mapped_column(nullable=True)
    eta_conservative_date: Mapped[Optional[str]] = mapped_column(nullable=True)
    confidence_score: Mapped[float] = mapped_column(default=0.0)
    plateau_detected: Mapped[int] = mapped_column(default=0)
    metrics_json: Mapped[str] = mapped_column(default="{}")
    insights_json: Mapped[str] = mapped_column(default="[]")
    created_at: Mapped[str] = mapped_column(default=_now_iso)

    __table_args__ = (Index("idx_model_snapshots_date", "snapshot_date"),)


class DBFoodNutrition(TickBase):
    """自主沉淀的食物热量与营养知识库（st_food_nutrition）。"""

    __tablename__ = "st_food_nutrition"

    id: Mapped[str] = mapped_column(primary_key=True, default=_new_id)
    name: Mapped[str] = mapped_column(nullable=False, unique=True)
    aliases_json: Mapped[str] = mapped_column(default="[]")
    category: Mapped[str] = mapped_column(default="dish")  # dish|staple|snack|drink|protein|fruit
    serving_desc: Mapped[str] = mapped_column(default="1份")
    kcal_per_100g: Mapped[Optional[float]] = mapped_column(nullable=True)
    kcal_per_serving: Mapped[Optional[float]] = mapped_column(nullable=True)
    protein_g: Mapped[Optional[float]] = mapped_column(nullable=True)
    carbs_g: Mapped[Optional[float]] = mapped_column(nullable=True)
    fat_g: Mapped[Optional[float]] = mapped_column(nullable=True)
    gi_level: Mapped[str] = mapped_column(default="medium")  # low|medium|high
    satiety_score: Mapped[int] = mapped_column(default=3)     # 1-5
    lighter_swap: Mapped[str] = mapped_column(default="")
    notes: Mapped[str] = mapped_column(default="")
    source: Mapped[str] = mapped_column(default="builtin")   # builtin|web_search|llm_verified|llm_estimate
    confidence: Mapped[float] = mapped_column(default=0.7)
    updated_at: Mapped[str] = mapped_column(default=_now_iso)

    __table_args__ = (Index("idx_food_nutrition_cat", "category"),)


class DBKnowledgeItem(TickBase):
    """健康师专业知识库（运动/饮食/心理调节，st_knowledge_items）。"""

    __tablename__ = "st_knowledge_items"

    id: Mapped[str] = mapped_column(primary_key=True, default=_new_id)
    domain: Mapped[str] = mapped_column(nullable=False)  # diet|exercise|psychology|sleep|general
    topic_key: Mapped[str] = mapped_column(nullable=False, unique=True)
    title: Mapped[str] = mapped_column(nullable=False)
    summary: Mapped[str] = mapped_column(default="")
    key_points_json: Mapped[str] = mapped_column(default="[]")
    applicable_scenarios_json: Mapped[str] = mapped_column(default="[]")
    source: Mapped[str] = mapped_column(default="curated")
    confidence: Mapped[float] = mapped_column(default=0.8)
    updated_at: Mapped[str] = mapped_column(default=_now_iso)

    __table_args__ = (Index("idx_knowledge_domain", "domain"),)


class DBQuickChatMessage(TickBase):
    """白天快速对话短期上下文与动作审计（st_quick_chats）。"""

    __tablename__ = "st_quick_chats"

    id: Mapped[str] = mapped_column(primary_key=True, default=_new_id)
    session_key: Mapped[str] = mapped_column(nullable=False)
    channel: Mapped[str] = mapped_column(default="api")  # qq|api|cli|web
    user_id: Mapped[str] = mapped_column(default="")
    role: Mapped[str] = mapped_column(nullable=False)    # user|assistant
    content: Mapped[str] = mapped_column(nullable=False)
    actions_json: Mapped[str] = mapped_column(default="[]")
    created_at: Mapped[str] = mapped_column(default=_now_iso)

    __table_args__ = (Index("idx_quick_chats_session", "session_key", "created_at"),)


class DBScheduledNudge(TickBase):
    """本地轻量定时提醒队列（同步 sail_server Reminder，支持 QQ Bot 到点双推）。"""

    __tablename__ = "st_scheduled_nudges"

    id: Mapped[str] = mapped_column(primary_key=True, default=_new_id)
    channel: Mapped[str] = mapped_column(default="qq")  # qq|android|all
    target_id: Mapped[str] = mapped_column(default="")  # QQ 号或群号
    target_type: Mapped[str] = mapped_column(default="private")  # private|group
    title: Mapped[str] = mapped_column(nullable=False)
    body: Mapped[str] = mapped_column(default="")
    trigger_at: Mapped[str] = mapped_column(nullable=False)  # ISO naive local time
    server_reminder_id: Mapped[Optional[int]] = mapped_column(nullable=True)
    status: Mapped[str] = mapped_column(default="pending")   # pending|sent|failed|canceled
    sent_at: Mapped[Optional[str]] = mapped_column(nullable=True)
    created_at: Mapped[str] = mapped_column(default=_now_iso)

    __table_args__ = (Index("idx_nudges_status_trigger", "status", "trigger_at"),)


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

    async def create_tick(
        self, slot: str, tick_date: str, idempotency_key: Optional[str] = None
    ) -> dict:
        """创建 Tick 实例。幂等键冲突时返回已有实例。"""
        key = idempotency_key or f"{slot}:{tick_date}"
        async with self.session() as s:
            existing = await s.execute(
                select(DBTick).where(DBTick.idempotency_key == key)
            )
            row = existing.scalar_one_or_none()
            if row:
                return self._tick_dict(row)
            row = DBTick(slot=slot, tick_date=tick_date, idempotency_key=key)
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

    async def sum_cost_today(self, today: Optional[str] = None) -> int:
        day = today or datetime.now().strftime("%Y-%m-%d")
        async with self.session() as s:
            result = await s.execute(
                text("SELECT COALESCE(SUM(cost_tokens),0) FROM st_ticks WHERE tick_date = :d"),
                {"d": day},
            )
            return int(result.scalar() or 0)

    async def sum_cost_usd_today(self, today: Optional[str] = None) -> float:
        day = today or datetime.now().strftime("%Y-%m-%d")
        async with self.session() as s:
            result = await s.execute(
                text("SELECT COALESCE(SUM(cost_usd),0.0) FROM st_ticks WHERE tick_date = :d"),
                {"d": day},
            )
            return float(result.scalar() or 0.0)

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
            existing = await s.get(DBSchedule, data["id"])
            if existing is not None:
                existing.name = data.get("name", existing.name)
                existing.slot = data.get("slot", existing.slot)
                existing.enabled = 1 if data.get("enabled", True) else 0
                existing.params = _json.dumps(data.get("params", {}), ensure_ascii=False)
                if data.get("next_run_time") is not None:
                    existing.next_run_time = data["next_run_time"]
                if data.get("last_run_time") is not None:
                    existing.last_run_time = data["last_run_time"]
                if data.get("last_run_status") is not None:
                    existing.last_run_status = data["last_run_status"]
                existing.updated_at = _now_iso()
            else:
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

    # ── Runtime State (Canary / Switches) ─────────────────────────────

    async def set_runtime_state(self, key: str, value: Any) -> dict:
        async with self.session() as s:
            row = await s.get(DBRuntimeState, key)
            if not row:
                row = DBRuntimeState(key=key, value="")
                s.add(row)
            row.value = _json.dumps(value, ensure_ascii=False, default=str)
            row.updated_at = _now_iso()
            await s.commit()
            return {"key": key, "updated_at": row.updated_at}

    async def get_runtime_state(self, key: str) -> Optional[Any]:
        async with self.session() as s:
            row = await s.get(DBRuntimeState, key)
            if not row:
                return None
            try:
                return _json.loads(row.value)
            except (_json.JSONDecodeError, TypeError):
                return row.value

    # ── AI Traces ─────────────────────────────────────────────────────

    async def save_trace(self, trace: Dict[str, Any]) -> dict:
        """持久化整条 AI Trace 及其所有 Spans（幂等覆盖）。"""
        trace_id = str(trace.get("trace_id") or _new_id())
        spans = trace.get("spans") or []
        async with self.session() as s:
            existing = await s.get(DBAITrace, trace_id)
            if existing is None:
                existing = DBAITrace(trace_id=trace_id)
                s.add(existing)
            existing.service = str(trace.get("service") or "sailtick")
            existing.tick_id = str(trace.get("tick_id") or "")
            existing.slot = str(trace.get("slot") or "")
            existing.tick_date = str(trace.get("tick_date") or "")
            existing.trigger_source = str(trace.get("trigger_source") or "scheduler")
            existing.mode = str(trace.get("mode") or "live")
            existing.status = str(trace.get("status") or "completed")
            existing.plan_source = str(trace.get("plan_source") or "none")
            existing.started_at = str(trace.get("started_at") or _now_iso())
            existing.ended_at = trace.get("ended_at")
            existing.duration_ms = float(trace.get("duration_ms") or 0.0)
            existing.llm_calls_count = int(trace.get("llm_calls_count") or 0)
            existing.prompt_tokens = int(trace.get("prompt_tokens") or 0)
            existing.completion_tokens = int(trace.get("completion_tokens") or 0)
            existing.total_tokens = int(trace.get("total_tokens") or 0)
            existing.cost_usd = float(trace.get("cost_usd") or 0.0)
            existing.tickets_created = int(trace.get("tickets_created") or 0)
            existing.tickets_throttled = int(trace.get("tickets_throttled") or 0)
            existing.actions_executed = int(trace.get("actions_executed") or 0)
            existing.actions_failed = int(trace.get("actions_failed") or 0)
            existing.summary = str(trace.get("summary") or "")
            existing.error = trace.get("error")
            existing.meta_json = _json.dumps(
                trace.get("meta") or {}, ensure_ascii=False, default=str
            )

            await s.execute(delete(DBAITraceSpan).where(DBAITraceSpan.trace_id == trace_id))
            for idx, sp in enumerate(spans):
                s.add(
                    DBAITraceSpan(
                        trace_id=trace_id,
                        span_id=str(sp.get("span_id") or f"sp_{idx}"),
                        parent_span_id=sp.get("parent_span_id"),
                        seq=int(sp.get("seq", idx)),
                        stage=str(sp.get("stage") or "unknown"),
                        name=str(sp.get("name") or ""),
                        status=str(sp.get("status") or "ok"),
                        started_at=str(sp.get("started_at") or _now_iso()),
                        ended_at=sp.get("ended_at"),
                        duration_ms=float(sp.get("duration_ms") or 0.0),
                        input_summary=str(sp.get("input_summary") or ""),
                        output_summary=str(sp.get("output_summary") or ""),
                        payload_json=_json.dumps(
                            sp.get("payload") or {}, ensure_ascii=False, default=str
                        ),
                        error=sp.get("error"),
                    )
                )
            await s.commit()
            return {"trace_id": trace_id, "spans": len(spans)}

    async def list_traces(
        self,
        limit: int = 50,
        slot: Optional[str] = None,
        status: Optional[str] = None,
    ) -> List[dict]:
        async with self.session() as s:
            stmt = select(DBAITrace).order_by(DBAITrace.started_at.desc()).limit(limit)
            if slot:
                stmt = stmt.where(DBAITrace.slot == slot)
            if status:
                stmt = stmt.where(DBAITrace.status == status)
            result = await s.execute(stmt)
            return [self._trace_dict(r) for r in result.scalars().all()]

    async def get_trace(self, trace_id: str) -> Optional[dict]:
        async with self.session() as s:
            row = await s.get(DBAITrace, trace_id)
            if not row:
                return None
            spans_res = await s.execute(
                select(DBAITraceSpan)
                .where(DBAITraceSpan.trace_id == trace_id)
                .order_by(DBAITraceSpan.seq.asc())
            )
            out = self._trace_dict(row)
            out["spans"] = [self._span_dict(sp) for sp in spans_res.scalars().all()]
            return out

    @staticmethod
    def _trace_dict(row: DBAITrace) -> dict:
        try:
            meta = _json.loads(row.meta_json or "{}")
        except (_json.JSONDecodeError, TypeError):
            meta = {}
        return {
            "trace_id": row.trace_id,
            "service": row.service,
            "tick_id": row.tick_id,
            "slot": row.slot,
            "tick_date": row.tick_date,
            "trigger_source": row.trigger_source,
            "mode": row.mode,
            "status": row.status,
            "plan_source": row.plan_source,
            "started_at": row.started_at,
            "ended_at": row.ended_at,
            "duration_ms": row.duration_ms,
            "llm_calls_count": row.llm_calls_count,
            "prompt_tokens": row.prompt_tokens,
            "completion_tokens": row.completion_tokens,
            "total_tokens": row.total_tokens,
            "cost_usd": row.cost_usd,
            "tickets_created": row.tickets_created,
            "tickets_throttled": row.tickets_throttled,
            "actions_executed": row.actions_executed,
            "actions_failed": row.actions_failed,
            "summary": row.summary,
            "error": row.error,
            "meta": meta,
        }

    @staticmethod
    def _span_dict(row: DBAITraceSpan) -> dict:
        try:
            payload = _json.loads(row.payload_json or "{}")
        except (_json.JSONDecodeError, TypeError):
            payload = {}
        return {
            "span_id": row.span_id,
            "parent_span_id": row.parent_span_id,
            "seq": row.seq,
            "stage": row.stage,
            "name": row.name,
            "status": row.status,
            "started_at": row.started_at,
            "ended_at": row.ended_at,
            "duration_ms": row.duration_ms,
            "input_summary": row.input_summary,
            "output_summary": row.output_summary,
            "payload": payload,
            "error": row.error,
        }

    # ── Model Snapshots (夜间数学建模快照) ────────────────────────────

    async def save_model_snapshot(self, snapshot: Dict[str, Any]) -> dict:
        async with self.session() as s:
            row = DBModelSnapshot(
                snapshot_date=str(snapshot.get("snapshot_date") or datetime.now().strftime("%Y-%m-%d")),
                window_days=int(snapshot.get("window_days") or 90),
                model_type=str(snapshot.get("model_type") or "ewma_wls"),
                sample_count=int(snapshot.get("sample_count") or 0),
                latest_weight_kg=snapshot.get("latest_weight_kg"),
                ewma_weight_kg=snapshot.get("ewma_weight_kg"),
                target_weight_kg=float(snapshot.get("target_weight_kg") or 70.0),
                weekly_rate_kg=snapshot.get("weekly_rate_kg"),
                eta_date=snapshot.get("eta_date"),
                eta_optimistic_date=snapshot.get("eta_optimistic_date"),
                eta_conservative_date=snapshot.get("eta_conservative_date"),
                confidence_score=float(snapshot.get("confidence_score") or 0.0),
                plateau_detected=1 if snapshot.get("plateau_detected") else 0,
                metrics_json=_json.dumps(snapshot.get("metrics") or {}, ensure_ascii=False, default=str),
                insights_json=_json.dumps(snapshot.get("insights") or [], ensure_ascii=False, default=str),
            )
            s.add(row)
            await s.commit()
            return self._model_snapshot_dict(row)

    async def get_latest_model_snapshot(self) -> Optional[dict]:
        async with self.session() as s:
            result = await s.execute(
                select(DBModelSnapshot).order_by(DBModelSnapshot.created_at.desc()).limit(1)
            )
            row = result.scalar_one_or_none()
            return self._model_snapshot_dict(row) if row else None

    async def list_model_snapshots(self, limit: int = 14) -> List[dict]:
        async with self.session() as s:
            result = await s.execute(
                select(DBModelSnapshot).order_by(DBModelSnapshot.created_at.desc()).limit(limit)
            )
            return [self._model_snapshot_dict(r) for r in result.scalars().all()]

    @staticmethod
    def _model_snapshot_dict(row: DBModelSnapshot) -> dict:
        try:
            metrics = _json.loads(row.metrics_json or "{}")
        except (_json.JSONDecodeError, TypeError):
            metrics = {}
        try:
            insights = _json.loads(row.insights_json or "[]")
        except (_json.JSONDecodeError, TypeError):
            insights = []
        return {
            "id": row.id,
            "snapshot_date": row.snapshot_date,
            "window_days": row.window_days,
            "model_type": row.model_type,
            "sample_count": row.sample_count,
            "latest_weight_kg": row.latest_weight_kg,
            "ewma_weight_kg": row.ewma_weight_kg,
            "target_weight_kg": row.target_weight_kg,
            "weekly_rate_kg": row.weekly_rate_kg,
            "eta_date": row.eta_date,
            "eta_optimistic_date": row.eta_optimistic_date,
            "eta_conservative_date": row.eta_conservative_date,
            "confidence_score": row.confidence_score,
            "plateau_detected": bool(row.plateau_detected),
            "metrics": metrics,
            "insights": insights,
            "created_at": row.created_at,
        }

    # ── Food Nutrition Knowledge Base (自主食物热量库) ────────────────

    async def upsert_food_nutrition(self, item: Dict[str, Any]) -> dict:
        name = str(item.get("name") or "").strip()
        if not name:
            raise ValueError("food name is required")
        async with self.session() as s:
            res = await s.execute(select(DBFoodNutrition).where(DBFoodNutrition.name == name))
            row = res.scalar_one_or_none()
            if row is None:
                row = DBFoodNutrition(name=name)
                s.add(row)
            if "aliases" in item:
                row.aliases_json = _json.dumps(list(item.get("aliases") or []), ensure_ascii=False)
            if item.get("category"):
                row.category = str(item["category"])
            if item.get("serving_desc"):
                row.serving_desc = str(item["serving_desc"])
            for col in ("kcal_per_100g", "kcal_per_serving", "protein_g", "carbs_g", "fat_g"):
                if item.get(col) is not None:
                    setattr(row, col, float(item[col]))
            if item.get("gi_level"):
                row.gi_level = str(item["gi_level"])
            if item.get("satiety_score") is not None:
                row.satiety_score = int(item["satiety_score"])
            if item.get("lighter_swap") is not None:
                row.lighter_swap = str(item["lighter_swap"])
            if item.get("notes") is not None:
                row.notes = str(item["notes"])
            if item.get("source"):
                row.source = str(item["source"])
            if item.get("confidence") is not None:
                row.confidence = float(item["confidence"])
            row.updated_at = _now_iso()
            await s.commit()
            return self._food_dict(row)

    async def list_food_nutrition(self, limit: int = 200, query: Optional[str] = None) -> List[dict]:
        async with self.session() as s:
            result = await s.execute(
                select(DBFoodNutrition).order_by(DBFoodNutrition.updated_at.desc()).limit(limit)
            )
            rows = [self._food_dict(r) for r in result.scalars().all()]
            if query and query.strip():
                q = query.strip().lower()
                rows = [
                    r for r in rows
                    if q in r["name"].lower()
                    or any(q in str(a).lower() for a in r.get("aliases", []))
                    or r["name"].lower() in q
                    or any(str(a).lower() in q for a in r.get("aliases", []) if str(a).strip())
                ]
            return rows

    @staticmethod
    def _food_dict(row: DBFoodNutrition) -> dict:
        try:
            aliases = _json.loads(row.aliases_json or "[]")
        except (_json.JSONDecodeError, TypeError):
            aliases = []
        return {
            "id": row.id,
            "name": row.name,
            "aliases": aliases,
            "category": row.category,
            "serving_desc": row.serving_desc,
            "kcal_per_100g": row.kcal_per_100g,
            "kcal_per_serving": row.kcal_per_serving,
            "protein_g": row.protein_g,
            "carbs_g": row.carbs_g,
            "fat_g": row.fat_g,
            "gi_level": row.gi_level,
            "satiety_score": row.satiety_score,
            "lighter_swap": row.lighter_swap,
            "notes": row.notes,
            "source": row.source,
            "confidence": row.confidence,
            "updated_at": row.updated_at,
        }

    # ── Health Coach Knowledge Base (专业健康师知识库) ────────────────

    async def upsert_knowledge_item(self, item: Dict[str, Any]) -> dict:
        topic_key = str(item.get("topic_key") or "").strip()
        if not topic_key:
            raise ValueError("topic_key is required")
        async with self.session() as s:
            res = await s.execute(select(DBKnowledgeItem).where(DBKnowledgeItem.topic_key == topic_key))
            row = res.scalar_one_or_none()
            if row is None:
                row = DBKnowledgeItem(
                    topic_key=topic_key,
                    domain=str(item.get("domain") or "general"),
                    title=str(item.get("title") or topic_key),
                )
                s.add(row)
            row.domain = str(item.get("domain") or row.domain)
            row.title = str(item.get("title") or row.title)
            row.summary = str(item.get("summary") or "")
            row.key_points_json = _json.dumps(list(item.get("key_points") or []), ensure_ascii=False)
            row.applicable_scenarios_json = _json.dumps(
                list(item.get("applicable_scenarios") or []), ensure_ascii=False
            )
            row.source = str(item.get("source") or "curated")
            row.confidence = float(item.get("confidence", 0.85))
            row.updated_at = _now_iso()
            await s.commit()
            return self._knowledge_dict(row)

    async def list_knowledge_items(
        self, domain: Optional[str] = None, limit: int = 100
    ) -> List[dict]:
        async with self.session() as s:
            stmt = select(DBKnowledgeItem).order_by(DBKnowledgeItem.updated_at.desc()).limit(limit)
            if domain:
                stmt = stmt.where(DBKnowledgeItem.domain == domain)
            result = await s.execute(stmt)
            return [self._knowledge_dict(r) for r in result.scalars().all()]

    @staticmethod
    def _knowledge_dict(row: DBKnowledgeItem) -> dict:
        try:
            key_points = _json.loads(row.key_points_json or "[]")
        except (_json.JSONDecodeError, TypeError):
            key_points = []
        try:
            scenarios = _json.loads(row.applicable_scenarios_json or "[]")
        except (_json.JSONDecodeError, TypeError):
            scenarios = []
        return {
            "id": row.id,
            "domain": row.domain,
            "topic_key": row.topic_key,
            "title": row.title,
            "summary": row.summary,
            "key_points": key_points,
            "applicable_scenarios": scenarios,
            "source": row.source,
            "confidence": row.confidence,
            "updated_at": row.updated_at,
        }

    # ── Quick Chat History (快反对话短期上下文) ────────────────────────

    async def append_quick_chat(
        self,
        session_key: str,
        role: str,
        content: str,
        channel: str = "api",
        user_id: str = "",
        actions: Optional[List[Dict[str, Any]]] = None,
    ) -> dict:
        async with self.session() as s:
            row = DBQuickChatMessage(
                session_key=session_key,
                channel=channel,
                user_id=str(user_id or ""),
                role=role,
                content=content,
                actions_json=_json.dumps(actions or [], ensure_ascii=False, default=str),
            )
            s.add(row)
            await s.commit()
            return {
                "id": row.id,
                "session_key": row.session_key,
                "channel": row.channel,
                "user_id": row.user_id,
                "role": row.role,
                "content": row.content,
                "actions": actions or [],
                "created_at": row.created_at,
            }

    async def list_quick_chat_history(self, session_key: str, limit: int = 10) -> List[dict]:
        async with self.session() as s:
            result = await s.execute(
                select(DBQuickChatMessage)
                .where(DBQuickChatMessage.session_key == session_key)
                .order_by(DBQuickChatMessage.created_at.desc())
                .limit(limit)
            )
            rows = list(result.scalars().all())
            rows.reverse()
            out = []
            for r in rows:
                try:
                    actions = _json.loads(r.actions_json or "[]")
                except (_json.JSONDecodeError, TypeError):
                    actions = []
                out.append(
                    {
                        "id": r.id,
                        "session_key": r.session_key,
                        "channel": r.channel,
                        "user_id": r.user_id,
                        "role": r.role,
                        "content": r.content,
                        "actions": actions,
                        "created_at": r.created_at,
                    }
                )
            return out

    # ── Scheduled Nudges (本地提醒队列，支持 QQ Bot 到点推送) ──────────

    async def create_scheduled_nudge(
        self,
        title: str,
        trigger_at: str,
        body: str = "",
        channel: str = "qq",
        target_id: str = "",
        target_type: str = "private",
        server_reminder_id: Optional[int] = None,
    ) -> dict:
        async with self.session() as s:
            row = DBScheduledNudge(
                channel=channel,
                target_id=str(target_id or ""),
                target_type=target_type,
                title=title,
                body=body,
                trigger_at=trigger_at,
                server_reminder_id=server_reminder_id,
                status="pending",
            )
            s.add(row)
            await s.commit()
            return self._nudge_dict(row)

    async def list_due_nudges(self, now_iso: Optional[str] = None) -> List[dict]:
        cutoff = now_iso or _now_iso()
        async with self.session() as s:
            result = await s.execute(
                select(DBScheduledNudge)
                .where(
                    DBScheduledNudge.status == "pending",
                    DBScheduledNudge.trigger_at <= cutoff,
                )
                .order_by(DBScheduledNudge.trigger_at.asc())
            )
            return [self._nudge_dict(r) for r in result.scalars().all()]

    async def list_pending_nudges(self, limit: int = 30) -> List[dict]:
        async with self.session() as s:
            result = await s.execute(
                select(DBScheduledNudge)
                .where(DBScheduledNudge.status == "pending")
                .order_by(DBScheduledNudge.trigger_at.asc())
                .limit(limit)
            )
            return [self._nudge_dict(r) for r in result.scalars().all()]

    async def mark_nudge_status(self, nudge_id: str, status: str) -> bool:
        async with self.session() as s:
            row = await s.get(DBScheduledNudge, nudge_id)
            if not row:
                return False
            row.status = status
            if status == "sent":
                row.sent_at = _now_iso()
            await s.commit()
            return True

    @staticmethod
    def _nudge_dict(row: DBScheduledNudge) -> dict:
        return {
            "id": row.id,
            "channel": row.channel,
            "target_id": row.target_id,
            "target_type": row.target_type,
            "title": row.title,
            "body": row.body,
            "trigger_at": row.trigger_at,
            "server_reminder_id": row.server_reminder_id,
            "status": row.status,
            "sent_at": row.sent_at,
            "created_at": row.created_at,
        }

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
                "st_runtime_state",
                "st_ai_traces",
                "st_ai_trace_spans",
                "st_model_snapshots",
                "st_food_nutrition",
                "st_knowledge_items",
                "st_quick_chats",
                "st_scheduled_nudges",
            ):
                result = await s.execute(text(f"SELECT COUNT(*) FROM {table}"))
                stats[table] = int(result.scalar() or 0)
            if os.path.exists(self.db_path):
                stats["db_size_bytes"] = os.path.getsize(self.db_path)
            return stats
