"""SQLAlchemy 异步数据库引擎 — 连接管理 + Session 工厂。

设计要点:
  - SQLAlchemy 2.0 async engine + AsyncSession
  - aiosqlite 驱动（sqlite+aiosqlite://）
  - 单进程单连接：NullPool（每次请求独立连接）+ DELETE journal_mode
  - 统一 session 生命周期管理
  - 所有 CRUD 操作下沉到 repositories.py

为什么不用 WAL + StaticPool
----------------------------
WAL 的核心优势是「多并发读不阻塞写」，适合多进程/多连接并发读写场景。
本系统是单 FastAPI 进程，所有 DB 访问都在同一 asyncio event loop 内串行执行
（asyncio 不会真正并发执行多个 coroutine，只是交替挂起/恢复）。

StaticPool 意图"保持单连接"，但 aiosqlite 在其内部 worker 线程上管理 sqlite3
句柄。当 SQLAlchemy 通过 StaticPool 复用连接时，aiosqlite worker 上的隐式事务
（sqlite3 默认 isolation_level=''，即 autocommit=False）可能仍持有上一个
读事务的快照，导致：
  - session A: UPDATE tasks SET status='success' WHERE id=?  → commit OK
  - session B: SELECT status FROM tasks WHERE id=?          → 仍读到 'running'

这是已经观察到的 bug：event_logs 里有 task.completed {status: success} 的
写入记录，但 tasks 表里该行状态依然是 running。

修复方式：
  1. 使用 NullPool：每次 checkout 创建新连接，用完即关闭，不存在跨操作快照污染。
  2. journal_mode=DELETE（SQLite 默认）：rollback journal，写完立即可见，无 WAL
     快照窗口。
  3. synchronous=FULL：单进程场景下持久性比性能更重要；NORMAL 的性能优势
     在单连接串行操作下几乎为零。
  4. busy_timeout=5000：防止偶发锁竞争导致 OperationalError。
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

from bot_server.models import Base

logger = logging.getLogger(__name__)


class Database:
    """异步 SQLAlchemy 数据库管理器。

    Usage::

        db = Database("cubeclaw.db")
        await db.connect()

        async with db.session() as session:
            ...

        await db.close()
    """

    def __init__(self, db_path: str = "cubeclaw.db"):
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
            # NullPool: 每次请求独立建立/关闭 aiosqlite 连接，彻底消除跨操作的
            # 隐式事务快照污染（StaticPool + aiosqlite 的已知一致性 bug 根源）。
            poolclass=NullPool,
        )

        # PRAGMAs — 在每个新原始连接上执行
        @event.listens_for(self._engine.sync_engine, "connect")
        def _set_sqlite_pragmas(dbapi_conn, connection_record):
            cursor = dbapi_conn.cursor()
            # DELETE journal（SQLite 默认）：事务 commit 后对所有后续连接立即可见，
            # 不存在 WAL 快照窗口。单进程应用不需要 WAL 的多读者并发优势。
            cursor.execute("PRAGMA journal_mode=DELETE")
            # FULL synchronous：每次 commit 都 fsync，确保状态变更真正落盘，
            # 优先正确性而非吞吐量（task 状态是关键业务数据）。
            cursor.execute("PRAGMA synchronous=FULL")
            cursor.execute("PRAGMA cache_size=-32768")  # 32 MiB page cache
            cursor.execute("PRAGMA foreign_keys=ON")
            # 5s 锁等待，防止偶发并发操作导致 OperationalError: database is locked
            cursor.execute("PRAGMA busy_timeout=5000")
            cursor.close()

        # 建表
        async with self._engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        # Session 工厂
        self._session_factory = async_sessionmaker(
            self._engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )

        logger.info("数据库已连接: %s (SQLAlchemy async + NullPool + DELETE journal)", self.db_path)

    async def close(self) -> None:
        """关闭引擎。"""
        if self._engine:
            await self._engine.dispose()
            self._engine = None
            self._session_factory = None

    @property
    def engine(self) -> AsyncEngine:
        assert self._engine, "Database not connected"
        return self._engine

    def session(self) -> AsyncSession:
        """创建一个新的 AsyncSession（用于 async with）。"""
        assert self._session_factory, "Database not connected"
        return self._session_factory()

    async def get_stats(self) -> dict:
        """数据库统计。"""
        stats = {}
        tables = [
            "projects", "workspaces", "batches", "sub_batches",
            "tasks", "task_runs", "agents", "sessions", "event_logs", "messages",
        ]
        async with self.session() as session:
            for table in tables:
                result = await session.execute(text(f"SELECT COUNT(*) FROM {table}"))
                stats[table] = result.scalar() or 0

        if os.path.exists(self.db_path):
            stats["db_size_bytes"] = os.path.getsize(self.db_path)
        return stats

    async def check_integrity(self) -> bool:
        """检查数据库完整性。"""
        try:
            async with self.session() as session:
                result = await session.execute(text("PRAGMA integrity_check"))
                row = result.first()
                return row is not None and row[0] == "ok"
        except Exception:
            return False
