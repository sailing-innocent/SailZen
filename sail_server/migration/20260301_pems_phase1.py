# -*- coding: utf-8 -*-
# @file 20260301_pems_phase1.py
# @brief PEMS Phase 1 Migration
# @author sailing-innocent
# @date 2026-03-01
# @version 1.0
# ---------------------------------

"""
PEMS 第一阶段数据迁移脚本

- 为 projects/missions 表添加 PEMS 相关字段
- 通过 SQLAlchemy create_all 创建新表
- 兼容 PostgreSQL 与 SQLite
"""

import os
import sys

# 将项目根目录加入路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from sqlalchemy import inspect, text


def _column_exists(inspector, table_name: str, column_name: str) -> bool:
    columns = inspector.get_columns(table_name)
    return any(c["name"] == column_name for c in columns)


def migrate(db=None):
    from sail_server.db import Database

    close_after = False
    if db is None:
        db = Database.get_instance().get_db_session()
        close_after = True
    try:
        engine = db.get_bind()
        inspector = inspect(engine)
        backend = Database.get_instance().backend
        is_sqlite = backend == "sqlite"
        print(f"[migrate] Backend: {backend}")

        # ------------------------------------------------------------------
        # Add columns to existing tables
        # ------------------------------------------------------------------
        project_columns = [
            ("timespan_id", "INTEGER REFERENCES timespans(id)"),
            ("energy_budget", "INTEGER DEFAULT 0"),
            ("priority", "INTEGER DEFAULT 0"),
            (
                "tags",
                "TEXT" if is_sqlite else "TEXT[] DEFAULT '{}'",
            ),
        ]
        for col_name, col_def in project_columns:
            if not _column_exists(inspector, "projects", col_name):
                db.execute(text(f"ALTER TABLE projects ADD COLUMN {col_name} {col_def}"))
                print(f"[migrate] Added column projects.{col_name}")

        mission_columns = [
            ("planned_minutes", "INTEGER DEFAULT 0"),
            ("actual_minutes", "INTEGER DEFAULT 0"),
            ("energy_cost", "INTEGER DEFAULT 0"),
            ("day_id", "INTEGER REFERENCES days(id)"),
            ("milestone_id", "INTEGER REFERENCES milestones(id)"),
            ("health_constraint", "VARCHAR DEFAULT 'normal'"),
        ]
        for col_name, col_def in mission_columns:
            if not _column_exists(inspector, "missions", col_name):
                db.execute(text(f"ALTER TABLE missions ADD COLUMN {col_name} {col_def}"))
                print(f"[migrate] Added column missions.{col_name}")

        # ------------------------------------------------------------------
        # Create new tables via ORM metadata (idempotent, cross-backend)
        # ------------------------------------------------------------------
        Database.get_instance().create_all()
        print("[migrate] Ensured all new PEMS tables exist")

        db.commit()
        print("[migrate] PEMS Phase 1 migration completed successfully")
    except Exception as e:
        db.rollback()
        print(f"[migrate] Migration failed: {e}")
        raise
    finally:
        if close_after:
            db.close()


if __name__ == "__main__":
    migrate()
