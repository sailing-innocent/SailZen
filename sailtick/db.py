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
    """记忆（episodic/semantic/procedural），冷热双字段：summary(进Prompt) + value(原始证据)。"""

    __tablename__ = "st_memories"

    id: Mapped[str] = mapped_column(primary_key=True, default=_new_id)
    memory_type: Mapped[str] = mapped_column(nullable=False)
    domain: Mapped[str] = mapped_column(default="general")  # health|rhythm|finance|general
    key: Mapped[str] = mapped_column(nullable=False)
    summary: Mapped[str] = mapped_column(default="")  # <=100字极简索引，专供 Prompt 注入
    value: Mapped[str] = mapped_column(nullable=False)  # 完整原始证据 JSON
    confidence: Mapped[float] = mapped_column(default=0.8)
    salience: Mapped[float] = mapped_column(default=0.5)  # 0.0~1.0 重要性权重
    hit_count: Mapped[int] = mapped_column(default=0)
    status: Mapped[str] = mapped_column(default="active")  # active|superseded|archived
    superseded_by: Mapped[Optional[str]] = mapped_column(nullable=True)
    ttl_seconds: Mapped[Optional[int]] = mapped_column(nullable=True)
    expires_at: Mapped[Optional[str]] = mapped_column(nullable=True)
    created_at: Mapped[str] = mapped_column(default=_now_iso)
    updated_at: Mapped[str] = mapped_column(default=_now_iso)
    last_used_at: Mapped[Optional[str]] = mapped_column(nullable=True)

    __table_args__ = (
        Index("idx_mem_type_key", "memory_type", "key"),
        Index("idx_mem_expires", "expires_at"),
        Index("idx_mem_domain_status", "memory_type", "domain", "status"),
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
    """Tick 事件流（原始观察事实，超 30 天压缩冷归档）。"""

    __tablename__ = "st_episodes"

    id: Mapped[str] = mapped_column(primary_key=True, default=_new_id)
    tick_id: Mapped[Optional[str]] = mapped_column(nullable=True)
    kind: Mapped[str] = mapped_column(nullable=False)  # scan|plan|work|handoff|note
    domain: Mapped[str] = mapped_column(default="general")
    tick_date: Mapped[str] = mapped_column(default="")
    content: Mapped[str] = mapped_column(nullable=False)
    compressed_at: Mapped[Optional[str]] = mapped_column(nullable=True)
    created_at: Mapped[str] = mapped_column(default=_now_iso)

    __table_args__ = (
        Index("idx_episodes_tick", "tick_id"),
        Index("idx_episodes_created", "created_at"),
    )


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
    """白天快速对话原始记录与动作审计（st_quick_chats，支持分域会话与夜间提炼）。"""

    __tablename__ = "st_quick_chats"

    id: Mapped[str] = mapped_column(primary_key=True, default=_new_id)
    session_key: Mapped[str] = mapped_column(nullable=False)
    channel: Mapped[str] = mapped_column(default="api")  # qq|api|cli|web|android|vscode_workbench
    domain: Mapped[str] = mapped_column(default="general")  # health|rhythm|finance|general
    surface: Mapped[str] = mapped_column(default="")  # android_plan|android_health|web_rhythm|...
    user_id: Mapped[str] = mapped_column(default="")
    role: Mapped[str] = mapped_column(nullable=False)    # user|assistant
    content: Mapped[str] = mapped_column(nullable=False)
    actions_json: Mapped[str] = mapped_column(default="[]")
    prompt_tokens: Mapped[int] = mapped_column(default=0)
    completion_tokens: Mapped[int] = mapped_column(default=0)
    consolidated_at: Mapped[Optional[str]] = mapped_column(nullable=True)
    created_at: Mapped[str] = mapped_column(default=_now_iso)

    __table_args__ = (
        Index("idx_quick_chats_session", "session_key", "created_at"),
        Index("idx_quick_chats_domain", "user_id", "domain", "created_at"),
    )


class DBDomainBrief(TickBase):
    """分域物化热视图（global_core / health / rhythm / finance），毫秒读取与极简 Prompt 注入。"""

    __tablename__ = "st_domain_briefs"

    domain: Mapped[str] = mapped_column(primary_key=True)  # global_core|health|rhythm|finance
    compact_text: Mapped[str] = mapped_column(default="")  # <=450字极简 Prompt 文本
    payload_json: Mapped[str] = mapped_column(default="{}")  # 结构化指标 JSON
    source_date: Mapped[str] = mapped_column(default="")
    updated_at: Mapped[str] = mapped_column(default=_now_iso)


class DBRawSnapshot(TickBase):
    """原始数据包冷归档指针（大 JSON 压缩落盘 data/sailtick/snapshots/*.json.gz）。"""

    __tablename__ = "st_raw_snapshots"

    id: Mapped[str] = mapped_column(primary_key=True, default=_new_id)
    tick_id: Mapped[str] = mapped_column(default="")
    slot: Mapped[str] = mapped_column(default="")
    tick_date: Mapped[str] = mapped_column(default="")
    kind: Mapped[str] = mapped_column(default="scan_7d")  # scan_7d|deep_90d
    file_path: Mapped[str] = mapped_column(nullable=False)
    sha256: Mapped[str] = mapped_column(default="")
    size_bytes: Mapped[int] = mapped_column(default=0)
    metrics_json: Mapped[str] = mapped_column(default="{}")
    created_at: Mapped[str] = mapped_column(default=_now_iso)

    __table_args__ = (Index("idx_raw_snapshots_date", "tick_date", "kind"),)


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
            await conn.run_sync(self._ensure_incremental_schema)

        self._fts_available = False
        async with self._engine.begin() as conn:
            try:
                await conn.execute(
                    text(
                        "CREATE VIRTUAL TABLE IF NOT EXISTS st_memory_fts USING fts5("
                        "entity_type UNINDEXED, entity_id UNINDEXED, domain UNINDEXED, "
                        "title, content, tokenize='unicode61')"
                    )
                )
                self._fts_available = True
            except Exception as exc:
                logger.warning("SQLite FTS5 unavailable, using LIKE fallback: %s", exc)

        self._session_factory = async_sessionmaker(
            self._engine, class_=AsyncSession, expire_on_commit=False
        )
        logger.info("SailTick DB connected: %s (fts5=%s)", self.db_path, self._fts_available)

    @staticmethod
    def _ensure_incremental_schema(sync_conn: Any) -> None:
        """幂等补齐存量 sailtick.db 的新增列与索引（兼容生产旧库平滑升级）。"""
        alter_specs = {
            "st_memories": [
                ("domain", "TEXT DEFAULT 'general'"),
                ("summary", "TEXT DEFAULT ''"),
                ("confidence", "REAL DEFAULT 0.8"),
                ("salience", "REAL DEFAULT 0.5"),
                ("hit_count", "INTEGER DEFAULT 0"),
                ("status", "TEXT DEFAULT 'active'"),
                ("superseded_by", "TEXT"),
                ("updated_at", "TEXT DEFAULT ''"),
                ("last_used_at", "TEXT"),
            ],
            "st_episodes": [
                ("domain", "TEXT DEFAULT 'general'"),
                ("tick_date", "TEXT DEFAULT ''"),
                ("compressed_at", "TEXT"),
            ],
            "st_quick_chats": [
                ("domain", "TEXT DEFAULT 'general'"),
                ("surface", "TEXT DEFAULT ''"),
                ("prompt_tokens", "INTEGER DEFAULT 0"),
                ("completion_tokens", "INTEGER DEFAULT 0"),
                ("consolidated_at", "TEXT"),
            ],
        }
        for table, cols in alter_specs.items():
            res = sync_conn.execute(text(f"PRAGMA table_info({table})"))
            existing = {row[1] for row in res.fetchall()}
            if not existing:
                continue
            for col_name, col_ddl in cols:
                if col_name not in existing:
                    sync_conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {col_name} {col_ddl}"))

        index_ddls = [
            "CREATE INDEX IF NOT EXISTS idx_mem_domain_status ON st_memories (memory_type, domain, status)",
            "CREATE INDEX IF NOT EXISTS idx_episodes_created ON st_episodes (created_at)",
            "CREATE INDEX IF NOT EXISTS idx_quick_chats_domain ON st_quick_chats (user_id, domain, created_at)",
        ]
        for ddl in index_ddls:
            try:
                sync_conn.execute(text(ddl))
            except Exception:
                pass

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
        *,
        domain: str = "general",
        summary: str = "",
        confidence: float = 0.8,
        salience: float = 0.5,
    ) -> dict:
        now = _now_iso()
        async with self.session() as s:
            row = DBMemory(
                memory_type=memory_type,
                domain=domain or "general",
                key=key,
                summary=(summary or "")[:200],
                value=_json.dumps(value, ensure_ascii=False, default=str),
                confidence=float(confidence),
                salience=float(salience),
                status="active",
                ttl_seconds=ttl_seconds,
                expires_at=expires_at,
                created_at=now,
                updated_at=now,
            )
            s.add(row)
            await s.commit()
            row_id = row.id
        await self.sync_fts_entry(
            "memory", row_id, domain or "general", key, summary or str(value)[:240]
        )
        return {"id": row_id, "memory_type": memory_type, "domain": domain or "general", "key": key}

    async def upsert_memory(
        self,
        memory_type: str,
        key: str,
        value: Any,
        ttl_seconds: Optional[int] = None,
        expires_at: Optional[str] = None,
        *,
        domain: str = "general",
        summary: str = "",
        confidence: float = 0.8,
        salience: float = 0.5,
        keep_history: bool = False,
    ) -> dict:
        """按 (memory_type, key) 幂等更新活跃记忆，杜绝重复追加泄漏。"""
        now = _now_iso()
        val_json = _json.dumps(value, ensure_ascii=False, default=str)
        sum_clean = (summary or "")[:200]
        dom = domain or "general"
        async with self.session() as s:
            result = await s.execute(
                select(DBMemory)
                .where(
                    DBMemory.memory_type == memory_type,
                    DBMemory.key == key,
                    DBMemory.status == "active",
                )
                .order_by(DBMemory.updated_at.desc(), DBMemory.created_at.desc())
            )
            existing_rows = list(result.scalars().all())
            if existing_rows and not keep_history:
                row = existing_rows[0]
                row.domain = dom
                row.summary = sum_clean or row.summary
                row.value = val_json
                row.confidence = float(confidence)
                row.salience = max(float(salience), float(row.salience or 0.0))
                if ttl_seconds is not None:
                    row.ttl_seconds = ttl_seconds
                if expires_at is not None:
                    row.expires_at = expires_at
                row.updated_at = now
                # 将同 key 多余的历史活跃重复行标为 superseded
                for dup in existing_rows[1:]:
                    dup.status = "superseded"
                    dup.superseded_by = row.id
                    dup.updated_at = now
                await s.commit()
                row_id = row.id
                superseded_ids = [d.id for d in existing_rows[1:]]
            else:
                row = DBMemory(
                    memory_type=memory_type,
                    domain=dom,
                    key=key,
                    summary=sum_clean,
                    value=val_json,
                    confidence=float(confidence),
                    salience=float(salience),
                    status="active",
                    ttl_seconds=ttl_seconds,
                    expires_at=expires_at,
                    created_at=now,
                    updated_at=now,
                )
                s.add(row)
                await s.flush()
                superseded_ids = []
                for old in existing_rows:
                    old.status = "superseded"
                    old.superseded_by = row.id
                    old.updated_at = now
                    superseded_ids.append(old.id)
                await s.commit()
                row_id = row.id

        for old_id in superseded_ids:
            await self.delete_fts_entry("memory", old_id)
        await self.sync_fts_entry("memory", row_id, dom, key, sum_clean or str(value)[:240])
        return {"id": row_id, "memory_type": memory_type, "domain": dom, "key": key, "summary": sum_clean}

    async def get_memory(self, memory_type: str, key: str) -> Optional[dict]:
        async with self.session() as s:
            result = await s.execute(
                select(DBMemory)
                .where(
                    DBMemory.memory_type == memory_type,
                    DBMemory.key == key,
                    DBMemory.status == "active",
                )
                .order_by(DBMemory.updated_at.desc(), DBMemory.created_at.desc())
                .limit(1)
            )
            row = result.scalar_one_or_none()
            if not row:
                return None
            return self._memory_dict(row)

    async def list_memories(
        self,
        memory_type: Optional[str] = None,
        key_prefix: Optional[str] = None,
        *,
        domain: Optional[str] = None,
        status: Optional[str] = "active",
        limit: int = 200,
    ) -> List[dict]:
        async with self.session() as s:
            stmt = select(DBMemory).order_by(DBMemory.updated_at.desc(), DBMemory.created_at.desc()).limit(limit)
            if memory_type:
                stmt = stmt.where(DBMemory.memory_type == memory_type)
            if domain:
                stmt = stmt.where(DBMemory.domain == domain)
            if status:
                stmt = stmt.where(DBMemory.status == status)
            result = await s.execute(stmt)
            rows = [self._memory_dict(r) for r in result.scalars().all()]
            if key_prefix:
                rows = [r for r in rows if r["key"].startswith(key_prefix)]
            return rows

    async def mark_memory_status(
        self, memory_id: str, status: str, superseded_by: Optional[str] = None
    ) -> bool:
        async with self.session() as s:
            row = await s.get(DBMemory, memory_id)
            if not row:
                return False
            row.status = status
            if superseded_by is not None:
                row.superseded_by = superseded_by
            row.updated_at = _now_iso()
            await s.commit()
        if status != "active":
            await self.delete_fts_entry("memory", memory_id)
        return True

    async def touch_memory_hits(self, memory_ids: List[str]) -> None:
        if not memory_ids:
            return
        now = _now_iso()
        async with self.session() as s:
            result = await s.execute(select(DBMemory).where(DBMemory.id.in_(memory_ids)))
            for row in result.scalars().all():
                row.hit_count = int(row.hit_count or 0) + 1
                row.last_used_at = now
            await s.commit()

    async def delete_memory(self, memory_id: str) -> bool:
        async with self.session() as s:
            result = await s.execute(delete(DBMemory).where(DBMemory.id == memory_id))
            await s.commit()
            ok = result.rowcount > 0
        if ok:
            await self.delete_fts_entry("memory", memory_id)
        return ok

    async def cleanup_expired_memories(self) -> int:
        now = _now_iso()
        async with self.session() as s:
            expired_res = await s.execute(
                select(DBMemory.id).where(
                    DBMemory.expires_at.isnot(None), DBMemory.expires_at < now
                )
            )
            expired_ids = [r[0] for r in expired_res.all()]
            result = await s.execute(
                delete(DBMemory).where(
                    DBMemory.expires_at.isnot(None), DBMemory.expires_at < now
                )
            )
            await s.commit()
            count = result.rowcount or 0
        for mid in expired_ids:
            await self.delete_fts_entry("memory", mid)
        return count

    @staticmethod
    def _memory_dict(row: DBMemory) -> dict:
        try:
            value = _json.loads(row.value)
        except (_json.JSONDecodeError, TypeError):
            value = row.value
        return {
            "id": row.id,
            "memory_type": row.memory_type,
            "domain": getattr(row, "domain", None) or "general",
            "key": row.key,
            "summary": getattr(row, "summary", None) or "",
            "value": value,
            "confidence": float(getattr(row, "confidence", 0.8) or 0.8),
            "salience": float(getattr(row, "salience", 0.5) or 0.5),
            "hit_count": int(getattr(row, "hit_count", 0) or 0),
            "status": getattr(row, "status", None) or "active",
            "superseded_by": getattr(row, "superseded_by", None),
            "expires_at": row.expires_at,
            "created_at": row.created_at,
            "updated_at": getattr(row, "updated_at", None) or row.created_at,
            "last_used_at": getattr(row, "last_used_at", None),
        }

    # ── SQLite FTS5 毫秒快查索引 ──────────────────────────────────────

    @staticmethod
    def _tokenize_for_fts(raw: str) -> str:
        """为中文增加 2-gram 切词以配合 FTS5 unicode61 高命中检索。"""
        import re as _re

        s = (raw or "").strip().lower()
        if not s:
            return ""
        tokens: List[str] = []
        # 保留原始完整词与英文/数字词
        for m in _re.findall(r"[a-z0-9_]+|[\u4e00-\u9fff]+", s):
            tokens.append(m)
            if len(m) >= 2 and "\u4e00" <= m[0] <= "\u9fff":
                for i in range(len(m) - 1):
                    tokens.append(m[i : i + 2])
        return " ".join(tokens)

    async def sync_fts_entry(
        self, entity_type: str, entity_id: str, domain: str, title: str, content: str
    ) -> None:
        if not getattr(self, "_fts_available", False) or self._engine is None:
            return
        try:
            idx_title = self._tokenize_for_fts(title)
            idx_content = self._tokenize_for_fts(content)
            async with self.session() as s:
                await s.execute(
                    text("DELETE FROM st_memory_fts WHERE entity_type = :et AND entity_id = :eid"),
                    {"et": entity_type, "eid": str(entity_id)},
                )
                await s.execute(
                    text(
                        "INSERT INTO st_memory_fts (entity_type, entity_id, domain, title, content) "
                        "VALUES (:et, :eid, :dom, :t, :c)"
                    ),
                    {
                        "et": entity_type,
                        "eid": str(entity_id),
                        "dom": domain or "general",
                        "t": idx_title,
                        "c": idx_content,
                    },
                )
                await s.commit()
        except Exception as exc:
            logger.debug("sync_fts_entry skipped: %s", exc)

    async def delete_fts_entry(self, entity_type: str, entity_id: str) -> None:
        if not getattr(self, "_fts_available", False) or self._engine is None:
            return
        try:
            async with self.session() as s:
                await s.execute(
                    text("DELETE FROM st_memory_fts WHERE entity_type = :et AND entity_id = :eid"),
                    {"et": entity_type, "eid": str(entity_id)},
                )
                await s.commit()
        except Exception as exc:
            logger.debug("delete_fts_entry skipped: %s", exc)

    async def search_fts(
        self,
        query: str,
        *,
        domain: Optional[str] = None,
        entity_types: Optional[List[str]] = None,
        limit: int = 10,
    ) -> List[dict]:
        """毫秒级全文快查（优先 FTS5 BM25，不可用或零命中时降级 LIKE）。"""
        import re as _re

        q = (query or "").strip()
        if not q:
            return []

        raw_terms = _re.findall(r"[a-zA-Z0-9_]{2,}|[\u4e00-\u9fff]{2,}", q.lower())
        search_tokens: List[str] = []
        for term in raw_terms:
            if "\u4e00" <= term[0] <= "\u9fff" and len(term) > 2:
                search_tokens.extend(term[i : i + 2] for i in range(len(term) - 1))
            else:
                search_tokens.append(term)
        search_tokens = list(dict.fromkeys(search_tokens))[:12]
        if not search_tokens:
            search_tokens = [q.lower()]

        hits: List[dict] = []
        if getattr(self, "_fts_available", False) and self._engine is not None:
            fts_query = " OR ".join(f'"{t.replace(chr(34), "")}"' for t in search_tokens if t)
            if fts_query:
                try:
                    where_parts = ["st_memory_fts MATCH :q"]
                    params: Dict[str, Any] = {"q": fts_query, "lim": max(1, min(limit, 50))}
                    if domain:
                        where_parts.append("(domain = :dom OR domain = 'general')")
                        params["dom"] = domain
                    if entity_types:
                        et_ph = ", ".join(f":et{i}" for i in range(len(entity_types)))
                        where_parts.append(f"entity_type IN ({et_ph})")
                        for i, et in enumerate(entity_types):
                            params[f"et{i}"] = et
                    sql = (
                        "SELECT entity_type, entity_id, domain, bm25(st_memory_fts) AS rank "
                        "FROM st_memory_fts WHERE "
                        + " AND ".join(where_parts)
                        + " ORDER BY rank ASC LIMIT :lim"
                    )
                    async with self.session() as s:
                        res = await s.execute(text(sql), params)
                        for row in res.fetchall():
                            hits.append(
                                {
                                    "entity_type": row[0],
                                    "entity_id": row[1],
                                    "domain": row[2],
                                    "score": round(-float(row[3] or 0.0), 4),
                                }
                            )
                except Exception as exc:
                    logger.debug("search_fts MATCH fallback: %s", exc)

        # 回填实体精简内容
        if hits:
            return await self._hydrate_fts_hits(hits)

        # 降级：直接查活跃 st_memories
        if not entity_types or "memory" in entity_types:
            mems = await self.list_memories(domain=domain, status="active", limit=100)
            out = []
            for m in mems:
                hay = f"{m['key']} {m.get('summary', '')} {str(m.get('value', ''))[:200]}".lower()
                if any(t in hay for t in search_tokens):
                    out.append(
                        {
                            "entity_type": "memory",
                            "entity_id": m["id"],
                            "domain": m["domain"],
                            "title": m["key"],
                            "summary": m.get("summary") or str(m.get("value"))[:120],
                            "memory_type": m["memory_type"],
                            "score": 0.5,
                        }
                    )
                    if len(out) >= limit:
                        break
            return out
        return []

    async def _hydrate_fts_hits(self, hits: List[dict]) -> List[dict]:
        mem_ids = [h["entity_id"] for h in hits if h["entity_type"] == "memory"]
        food_ids = [h["entity_id"] for h in hits if h["entity_type"] == "food"]
        kn_ids = [h["entity_id"] for h in hits if h["entity_type"] == "knowledge"]
        mem_map: Dict[str, dict] = {}
        food_map: Dict[str, dict] = {}
        kn_map: Dict[str, dict] = {}
        async with self.session() as s:
            if mem_ids:
                res = await s.execute(
                    select(DBMemory).where(DBMemory.id.in_(mem_ids), DBMemory.status == "active")
                )
                for r in res.scalars().all():
                    mem_map[r.id] = self._memory_dict(r)
            if food_ids:
                res = await s.execute(select(DBFoodNutrition).where(DBFoodNutrition.id.in_(food_ids)))
                for r in res.scalars().all():
                    food_map[r.id] = self._food_dict(r)
            if kn_ids:
                res = await s.execute(select(DBKnowledgeItem).where(DBKnowledgeItem.id.in_(kn_ids)))
                for r in res.scalars().all():
                    kn_map[r.id] = self._knowledge_dict(r)

        hydrated: List[dict] = []
        for h in hits:
            et, eid = h["entity_type"], h["entity_id"]
            if et == "memory" and eid in mem_map:
                m = mem_map[eid]
                hydrated.append(
                    {
                        **h,
                        "title": m["key"],
                        "summary": m["summary"] or str(m["value"])[:120],
                        "memory_type": m["memory_type"],
                        "item": m,
                    }
                )
            elif et == "food" and eid in food_map:
                f = food_map[eid]
                hydrated.append(
                    {
                        **h,
                        "title": f["name"],
                        "summary": f"{f['name']}({f.get('serving_desc')}): {f.get('kcal_per_serving')}kcal",
                        "item": f,
                    }
                )
            elif et == "knowledge" and eid in kn_map:
                k = kn_map[eid]
                hydrated.append(
                    {
                        **h,
                        "title": k["title"],
                        "summary": k["summary"],
                        "item": k,
                    }
                )
        return hydrated

    # ── Domain Briefs (分域物化热视图) ────────────────────────────────

    async def upsert_domain_brief(
        self, domain: str, compact_text: str, payload: Dict[str, Any], source_date: str = ""
    ) -> dict:
        now = _now_iso()
        async with self.session() as s:
            row = await s.get(DBDomainBrief, domain)
            if row is None:
                row = DBDomainBrief(domain=domain)
                s.add(row)
            row.compact_text = (compact_text or "")[:1200]
            row.payload_json = _json.dumps(payload or {}, ensure_ascii=False, default=str)
            row.source_date = source_date or now[:10]
            row.updated_at = now
            await s.commit()
            return self._domain_brief_dict(row)

    async def get_domain_brief(self, domain: str) -> Optional[dict]:
        async with self.session() as s:
            row = await s.get(DBDomainBrief, domain)
            return self._domain_brief_dict(row) if row else None

    async def list_domain_briefs(self) -> Dict[str, dict]:
        async with self.session() as s:
            res = await s.execute(select(DBDomainBrief))
            return {r.domain: self._domain_brief_dict(r) for r in res.scalars().all()}

    @staticmethod
    def _domain_brief_dict(row: DBDomainBrief) -> dict:
        try:
            payload = _json.loads(row.payload_json or "{}")
        except (_json.JSONDecodeError, TypeError):
            payload = {}
        return {
            "domain": row.domain,
            "compact_text": row.compact_text,
            "payload": payload,
            "source_date": row.source_date,
            "updated_at": row.updated_at,
        }

    # ── Raw Snapshots (原始数据包冷快照指针) ──────────────────────────

    async def save_raw_snapshot(
        self,
        *,
        tick_id: str,
        slot: str,
        tick_date: str,
        kind: str,
        file_path: str,
        sha256: str,
        size_bytes: int,
        metrics: Optional[Dict[str, Any]] = None,
    ) -> dict:
        async with self.session() as s:
            row = DBRawSnapshot(
                tick_id=tick_id or "",
                slot=slot or "",
                tick_date=tick_date or "",
                kind=kind or "scan_7d",
                file_path=file_path,
                sha256=sha256,
                size_bytes=int(size_bytes),
                metrics_json=_json.dumps(metrics or {}, ensure_ascii=False, default=str),
            )
            s.add(row)
            await s.commit()
            return {"id": row.id, "file_path": file_path, "size_bytes": int(size_bytes)}

    async def list_raw_snapshots(self, limit: int = 30, kind: Optional[str] = None) -> List[dict]:
        async with self.session() as s:
            stmt = select(DBRawSnapshot).order_by(DBRawSnapshot.created_at.desc()).limit(limit)
            if kind:
                stmt = stmt.where(DBRawSnapshot.kind == kind)
            res = await s.execute(stmt)
            out = []
            for r in res.scalars().all():
                try:
                    metrics = _json.loads(r.metrics_json or "{}")
                except Exception:
                    metrics = {}
                out.append(
                    {
                        "id": r.id,
                        "tick_id": r.tick_id,
                        "slot": r.slot,
                        "tick_date": r.tick_date,
                        "kind": r.kind,
                        "file_path": r.file_path,
                        "sha256": r.sha256,
                        "size_bytes": r.size_bytes,
                        "metrics": metrics,
                        "created_at": r.created_at,
                    }
                )
            return out

    async def prune_raw_snapshots_before(self, cutoff_date: str) -> List[str]:
        """删除早于 cutoff_date 的快照指针并返回对应文件路径供磁盘清理。"""
        async with self.session() as s:
            res = await s.execute(
                select(DBRawSnapshot).where(DBRawSnapshot.tick_date < cutoff_date)
            )
            rows = list(res.scalars().all())
            paths = [r.file_path for r in rows]
            if rows:
                await s.execute(delete(DBRawSnapshot).where(DBRawSnapshot.tick_date < cutoff_date))
                await s.commit()
            return paths

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

    async def create_episode(
        self,
        tick_id: Optional[str],
        kind: str,
        content: Any,
        *,
        domain: str = "general",
        tick_date: str = "",
    ) -> dict:
        now = _now_iso()
        async with self.session() as s:
            row = DBEpisode(
                tick_id=tick_id,
                kind=kind,
                domain=domain or "general",
                tick_date=tick_date or now[:10],
                content=_json.dumps(content, ensure_ascii=False, default=str),
                created_at=now,
            )
            s.add(row)
            await s.commit()
            return {"id": row.id, "tick_id": tick_id, "kind": kind, "domain": domain or "general"}

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
                        "domain": getattr(row, "domain", None) or "general",
                        "tick_date": getattr(row, "tick_date", None) or "",
                        "content": content,
                        "compressed_at": getattr(row, "compressed_at", None),
                        "created_at": row.created_at,
                    }
                )
            return out

    async def list_episodes_before(self, cutoff_iso: str, limit: int = 500) -> List[dict]:
        async with self.session() as s:
            stmt = (
                select(DBEpisode)
                .where(DBEpisode.created_at < cutoff_iso)
                .order_by(DBEpisode.created_at.asc())
                .limit(limit)
            )
            res = await s.execute(stmt)
            out = []
            for row in res.scalars().all():
                try:
                    content = _json.loads(row.content)
                except Exception:
                    content = row.content
                out.append(
                    {
                        "id": row.id,
                        "tick_id": row.tick_id,
                        "kind": row.kind,
                        "domain": getattr(row, "domain", None) or "general",
                        "tick_date": getattr(row, "tick_date", None) or "",
                        "content": content,
                        "created_at": row.created_at,
                    }
                )
            return out

    async def delete_episodes_by_ids(self, episode_ids: List[str]) -> int:
        if not episode_ids:
            return 0
        async with self.session() as s:
            res = await s.execute(delete(DBEpisode).where(DBEpisode.id.in_(episode_ids)))
            await s.commit()
            return res.rowcount or 0

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
            out = self._food_dict(row)
        await self.sync_fts_entry(
            "food",
            out["id"],
            "health",
            out["name"],
            " ".join([out["name"], *(out.get("aliases") or []), out.get("lighter_swap", "")]),
        )
        return out

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
            out = self._knowledge_dict(row)
        await self.sync_fts_entry(
            "knowledge",
            out["id"],
            "health",
            out["title"],
            " ".join([out["title"], out.get("summary", ""), *(out.get("applicable_scenarios") or [])]),
        )
        return out

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

    # ── Quick Chat History (快反对话原始上下文与分域查询) ────────────────

    async def append_quick_chat(
        self,
        session_key: str,
        role: str,
        content: str,
        channel: str = "api",
        user_id: str = "",
        actions: Optional[List[Dict[str, Any]]] = None,
        *,
        domain: str = "general",
        surface: str = "",
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
    ) -> dict:
        async with self.session() as s:
            row = DBQuickChatMessage(
                session_key=session_key,
                channel=channel,
                domain=domain or "general",
                surface=surface or "",
                user_id=str(user_id or ""),
                role=role,
                content=content,
                actions_json=_json.dumps(actions or [], ensure_ascii=False, default=str),
                prompt_tokens=int(prompt_tokens or 0),
                completion_tokens=int(completion_tokens or 0),
            )
            s.add(row)
            await s.commit()
            return {
                "id": row.id,
                "session_key": row.session_key,
                "channel": row.channel,
                "domain": row.domain,
                "surface": row.surface,
                "user_id": row.user_id,
                "role": row.role,
                "content": row.content,
                "actions": actions or [],
                "prompt_tokens": row.prompt_tokens,
                "completion_tokens": row.completion_tokens,
                "created_at": row.created_at,
            }

    async def list_quick_chat_history(
        self,
        session_key: str,
        limit: int = 10,
        *,
        domain: Optional[str] = None,
    ) -> List[dict]:
        async with self.session() as s:
            stmt = select(DBQuickChatMessage).where(DBQuickChatMessage.session_key == session_key)
            if domain:
                stmt = stmt.where(DBQuickChatMessage.domain == domain)
            result = await s.execute(
                stmt.order_by(DBQuickChatMessage.created_at.desc()).limit(limit)
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
                        "domain": getattr(r, "domain", None) or "general",
                        "surface": getattr(r, "surface", None) or "",
                        "user_id": r.user_id,
                        "role": r.role,
                        "content": r.content,
                        "actions": actions,
                        "prompt_tokens": int(getattr(r, "prompt_tokens", 0) or 0),
                        "completion_tokens": int(getattr(r, "completion_tokens", 0) or 0),
                        "created_at": r.created_at,
                    }
                )
            return out

    async def list_unconsolidated_quick_chats(self, limit: int = 100) -> List[dict]:
        async with self.session() as s:
            result = await s.execute(
                select(DBQuickChatMessage)
                .where(DBQuickChatMessage.consolidated_at.is_(None))
                .order_by(DBQuickChatMessage.created_at.asc())
                .limit(limit)
            )
            out = []
            for r in result.scalars().all():
                try:
                    actions = _json.loads(r.actions_json or "[]")
                except Exception:
                    actions = []
                out.append(
                    {
                        "id": r.id,
                        "session_key": r.session_key,
                        "domain": getattr(r, "domain", None) or "general",
                        "surface": getattr(r, "surface", None) or "",
                        "role": r.role,
                        "content": r.content,
                        "actions": actions,
                        "created_at": r.created_at,
                    }
                )
            return out

    async def mark_quick_chats_consolidated(self, chat_ids: List[str]) -> int:
        if not chat_ids:
            return 0
        now = _now_iso()
        async with self.session() as s:
            res = await s.execute(select(DBQuickChatMessage).where(DBQuickChatMessage.id.in_(chat_ids)))
            rows = list(res.scalars().all())
            for r in rows:
                r.consolidated_at = now
            await s.commit()
            return len(rows)

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

    async def update_scheduled_nudge(
        self,
        nudge_id: str,
        *,
        title: Optional[str] = None,
        body: Optional[str] = None,
        trigger_at: Optional[str] = None,
        server_reminder_id: Optional[int] = None,
        status: Optional[str] = None,
    ) -> Optional[dict]:
        """原地更新本地提醒记录（改期/换绑 server_reminder_id 时复用同一行，避免分裂）。"""
        async with self.session() as s:
            row = await s.get(DBScheduledNudge, nudge_id)
            if not row:
                return None
            if title is not None:
                row.title = title
            if body is not None:
                row.body = body
            if trigger_at is not None:
                row.trigger_at = trigger_at
            if server_reminder_id is not None:
                row.server_reminder_id = server_reminder_id
            if status is not None:
                row.status = status
                if status == "sent":
                    row.sent_at = _now_iso()
            await s.commit()
            return self._nudge_dict(row)

    async def cancel_nudges_by_server_reminder_id(self, server_reminder_id: int) -> int:
        """按云端 server_reminder_id 联动取消对应的本地 pending Nudge。"""
        async with self.session() as s:
            result = await s.execute(
                select(DBScheduledNudge).where(
                    DBScheduledNudge.server_reminder_id == int(server_reminder_id),
                    DBScheduledNudge.status == "pending",
                )
            )
            rows = list(result.scalars().all())
            for r in rows:
                r.status = "canceled"
            if rows:
                await s.commit()
            return len(rows)

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
                "st_domain_briefs",
                "st_raw_snapshots",
            ):
                result = await s.execute(text(f"SELECT COUNT(*) FROM {table}"))
                stats[table] = int(result.scalar() or 0)
            if os.path.exists(self.db_path):
                stats["db_size_bytes"] = os.path.getsize(self.db_path)
            return stats
