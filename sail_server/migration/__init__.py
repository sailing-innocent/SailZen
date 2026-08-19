# -*- coding: utf-8 -*-
# @file __init__.py
# @brief Database Migration Runner
# @author sailing-innocent
# @date 2026-08-15
# @version 1.0
# ---------------------------------

"""
数据库迁移运行器。

设计目标：
- 启动时自动补齐数据库 schema 与 ORM 模型之间的差异（无痛迁移）。
- 对 PostgreSQL 执行 SQL 迁移文件（触发器、索引、原生效能）。
- 对所有后端执行 Python 迁移脚本（ALTER TABLE 添加列等）。
- 全部脚本均为幂等，可反复安全执行。

用法：
    from sail_server.migration import run_migrations
    run_migrations()

 runner 默认使用 Database 单例创建会话；也可传入已有会话：
    run_migrations(db)
"""

import logging
import runpy
from pathlib import Path
from typing import List, Optional

from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

MIGRATION_DIR = Path(__file__).parent

# Python 迁移脚本（跨后端，通常用于给已有表添加列）
PYTHON_MIGRATIONS: List[Path] = [
]

# SQL 迁移脚本（PostgreSQL 专用，用于触发器、索引、PG 原生类型）
SQL_MIGRATIONS: List[Path] = [
]


def _run_sql_migration(db: Session, sql_path: Path) -> None:
    """执行单个 SQL 迁移文件（PostgreSQL 后端）。"""
    logger.info(f"[Migration] Running SQL migration: {sql_path.name}")
    raw_sql = sql_path.read_text(encoding="utf-8")

    # SQLAlchemy text() 无法执行包含触发器/函数的多语句脚本，
    # 这里直接通过底层驱动执行原始 SQL。
    conn = db.connection()
    conn.exec_driver_sql(raw_sql)

    logger.info(f"[Migration] SQL migration completed: {sql_path.name}")


def _run_python_migration(db: Session, py_path: Path) -> None:
    """执行单个 Python 迁移脚本。"""
    logger.info(f"[Migration] Running Python migration: {py_path.name}")
    module = runpy.run_path(str(py_path), run_name=f"sail_server.migration.{py_path.stem}")
    migrate_fn = module.get("migrate")
    if migrate_fn is None:
        logger.warning(f"[Migration] No migrate() function found in {py_path.name}, skipping")
        return
    migrate_fn(db)
    logger.info(f"[Migration] Python migration completed: {py_path.name}")


def run_migrations(db: Optional[Session] = None) -> None:
    """自动运行所有迁移脚本。

    在 Database.__init__ 之后调用，确保所有 ORM 表已存在。
    迁移脚本均为幂等，可安全地在每次启动时执行。

    Args:
        db: 可选的数据库会话。未提供时自动创建新会话。
    """
    from sail_server.db import Database

    close_after = False
    if db is None:
        db = Database.get_instance().get_db_session()
        close_after = True

    backend = Database.get_instance().backend
    try:
        if backend == "postgres":
            for sql_path in SQL_MIGRATIONS:
                if sql_path.exists():
                    _run_sql_migration(db, sql_path)
                else:
                    logger.warning(f"[Migration] SQL migration not found: {sql_path}")

        for py_path in PYTHON_MIGRATIONS:
            if py_path.exists():
                _run_python_migration(db, py_path)
            else:
                logger.warning(f"[Migration] Python migration not found: {py_path}")

        db.commit()
        logger.info("[Migration] All migrations completed successfully")
    except Exception:
        db.rollback()
        logger.exception("[Migration] Migration failed")
        raise
    finally:
        if close_after:
            db.close()
