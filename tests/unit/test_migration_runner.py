# -*- coding: utf-8 -*-
# @file test_migration_runner.py
# @brief Test the automatic migration runner
# @author sailing-innocent
# @date 2026-08-15
# @version 1.0
# ---------------------------------

import os
import sys

import pytest
from sqlalchemy import inspect, text


@pytest.fixture
def sqlite_db():
    """在 SQLite 内存数据库中初始化 Database 单例并返回会话。"""
    # 必须在导入 sail_server.db 之前设置，否则 Database 单例会按 dev 配置连接 PG
    os.environ["DB_BACKEND"] = "sqlite"
    os.environ.pop("POSTGRE_URI", None)

    # 清除可能已经存在的 Database 单例（防止其他测试影响）
    from sail_server.db import Database

    Database._Database__instance = None
    Database._Database__engine = None
    Database._Database__uri = None
    Database._Database__backend = None

    db = Database.get_instance().get_db_session()
    try:
        yield db
    finally:
        db.close()
        Database.get_instance().engine.dispose()
        Database._Database__instance = None
        Database._Database__engine = None
        Database._Database__uri = None
        Database._Database__backend = None


def test_migration_schema_matches_orm(sqlite_db):
    """验证自动迁移后的 schema 与当前 ORM 一致。"""
    engine = sqlite_db.get_bind()
    inspector = inspect(engine)

    # rhythm_affairs 新增字段
    rhythm_cols = {c["name"] for c in inspector.get_columns("rhythm_affairs")}
    assert "info_collection_type" in rhythm_cols


def test_migration_is_idempotent(sqlite_db):
    """验证迁移 runner 可重复执行且不会报错。"""
    from sail_server.migration import run_migrations

    # 第二次运行应无副作用
    run_migrations(sqlite_db)
    sqlite_db.commit()

    # 验证仍能正常查询
    result = sqlite_db.execute(text("SELECT COUNT(*) FROM rhythm_affairs")).scalar()
    assert result == 0


