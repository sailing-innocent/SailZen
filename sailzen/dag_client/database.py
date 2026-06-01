# -*- coding: utf-8 -*-
# @file database.py
# @brief 独立异步数据库引擎
# @author sailing-innocent
# @date 2025-06-02
# @version 3.0
# ---------------------------------
"""SailZen DAG Client 独立 SQLite 异步数据库。

设计要点:
  - SQLAlchemy 2.0 async engine + AsyncSession
  - aiosqlite 驱动
  - NullPool: 每次请求独立连接，消除跨操作快照污染
  - DELETE journal_mode + FULL synchronous
  - 完全独立于 sail_server 的数据库路径
"""

from __future__ import annotations

import logging
import os
from typing import Optional

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy import event, text
from sqlalchemy.pool import NullPool

from sailzen.dag_client.models import Base

logger = logging.getLogger(__name__)


class Database:
    """异步 SQLAlchemy 数据库管理器。

    Usage::

        db = Database("data/dag_client.db")
        await db.connect()
        async with db.session() as session:
            ...
        await db.close()
    """

    def __init__(self, db_path: str = "data/dag_client.db"):
        self.db_path = db_path
        self._engine: Optional[AsyncEngine] = None
        self._session_factory: Optional[async_sessionmaker[AsyncSession]] = None

    async def connect(self) -> None:
        """初始化引擎、配置 PRAGMAs、建表。"""
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
            cursor.execute("PRAGMA journal_mode=DELETE")
            cursor.execute("PRAGMA synchronous=FULL")
            cursor.execute("PRAGMA cache_size=-32768")
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.execute("PRAGMA busy_timeout=5000")
            cursor.close()

        async with self._engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        self._session_factory = async_sessionmaker(
            self._engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )

        logger.info("DAG Client DB connected: %s", self.db_path)

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
            "dag_definitions", "dag_runs", "dag_nodes",
            "dag_edges", "node_runs", "agents", "event_logs", "required_skills",
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
