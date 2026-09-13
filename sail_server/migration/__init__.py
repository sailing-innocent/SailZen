# -*- coding: utf-8 -*-
# @file __init__.py
# @brief Database Migration Runner
# @author sailing-innocent
# @date 2026-08-15
# @version 2.0
# ---------------------------------

"""
数据库迁移运行器。

设计目标：
- 启动时自动补齐数据库 schema 与 ORM 模型之间的差异（无痛迁移）。
- 仅支持 SQL 迁移文件（PostgreSQL 后端）：触发器、索引、PG 原生 DDL 等。
- 全部脚本均为幂等，可反复安全执行。

重要决策：不支持 Python 迁移脚本。
Python 迁移机制已被实践证明不可靠，已从本框架完全移除（2026-09-13），原因：
- ORM 层报错被 SQLAlchemy 层层包装，难以定位根因；
- 与 PG 原生 DDL 行为差异大（如 naive/aware datetime 混用直接 TypeError
  崩溃，20260906_backfill_body_data 曾因此迁移失败、阻断服务器启动）；
- 数据 backfill/数据修正类需求，请改用一次性 CLI/手工脚本（scripts/ 或
  sailzen cli）单独执行，禁止挂进启动迁移流程。

用法：
    from sail_server.migration import run_migrations
    run_migrations()

 runner 默认使用 Database 单例创建会话；也可传入已有会话：
    run_migrations(db)
"""

import logging
from pathlib import Path
from typing import List, Optional

from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

MIGRATION_DIR = Path(__file__).parent

# SQL 迁移脚本（PostgreSQL 专用，用于触发器、索引、PG 原生类型/DDL）。
# 注意：这里只接受 .sql 文件。不要新增 Python 迁移脚本（见模块 docstring）。
SQL_MIGRATIONS: List[Path] = [
    MIGRATION_DIR / "20260906_add_rhythm_is_default.sql",
    MIGRATION_DIR / "20260906_add_rhythm_profile_v2.sql",
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


def run_migrations(db: Optional[Session] = None) -> None:
    """自动运行所有迁移脚本。

    在 Database.__init__ 之后调用，确保所有 ORM 表已存在。
    迁移脚本均为幂等，可安全地在每次启动时执行。

    仅执行 SQL_MIGRATIONS（PostgreSQL 后端）；SQLite 后端由
    SQLAlchemy create_all 自动建表/补列，无需迁移脚本。

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

        db.commit()
        logger.info("[Migration] All migrations completed successfully")
    except Exception:
        db.rollback()
        logger.exception("[Migration] Migration failed")
        raise
    finally:
        if close_after:
            db.close()
