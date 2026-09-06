# -*- coding: utf-8 -*-
# @file test_db_init_interrupted.py
# @brief 数据库初始化被 Ctrl+C 中断 / 连接失败时的优雅退出行为
# @author sailing-innocent
# @date 2026-09-06
# @version 1.0
# ---------------------------------

"""
覆盖场景：数据库不可达时 psycopg 连接长时间阻塞，用户按 Ctrl+C 不应打印
一长串 traceback（KeyboardInterrupt 继承自 BaseException，except Exception
捕获不到），而应一行提示后优雅退出；连接失败时应给出可操作的错误提示。
"""

import pytest
from sqlalchemy.exc import OperationalError


@pytest.fixture
def sqlite_env(tmp_path, monkeypatch):
    """隔离的 sqlite 环境 + 重置 Database 单例（防止其他测试影响）"""
    monkeypatch.setenv("DB_BACKEND", "sqlite")
    monkeypatch.setenv("SQLITE_PATH", str(tmp_path / "test.db"))
    monkeypatch.delenv("POSTGRE_URI", raising=False)

    from sail_server.db import Database

    Database._Database__instance = None
    Database._Database__engine = None
    Database._Database__uri = None
    Database._Database__backend = None
    yield Database
    if Database._Database__instance is not None:
        Database._Database__instance.engine.dispose()
    Database._Database__instance = None
    Database._Database__engine = None
    Database._Database__uri = None
    Database._Database__backend = None


def test_ctrl_c_during_connect_exits_cleanly(sqlite_env, monkeypatch):
    """模拟连接阻塞时被 Ctrl+C：应 SystemExit(130) 且单例被重置，不抛 traceback"""
    Database = sqlite_env

    def _fake_create_all(self):
        raise KeyboardInterrupt

    monkeypatch.setattr(Database, "create_all", _fake_create_all)

    with pytest.raises(SystemExit) as exc_info:
        Database.get_instance()

    assert exc_info.value.code == 130
    assert Database._Database__instance is None


def test_connect_failure_has_actionable_hint(sqlite_env, monkeypatch):
    """连接失败应抛出带可操作提示的 RuntimeError，且单例被重置"""
    Database = sqlite_env

    def _fake_create_all(self):
        raise OperationalError("SELECT 1", {}, Exception("connection refused"))

    monkeypatch.setattr(Database, "create_all", _fake_create_all)

    with pytest.raises(RuntimeError, match="Cannot connect to database"):
        Database.get_instance()

    assert Database._Database__instance is None


def test_retry_after_interrupted_init(sqlite_env, monkeypatch):
    """中断后单例已重置，再次 get_instance 会重新初始化而不是返回半成品"""
    Database = sqlite_env
    calls = {"n": 0}

    def _flaky_create_all(self):
        calls["n"] += 1
        if calls["n"] == 1:
            raise KeyboardInterrupt

    monkeypatch.setattr(Database, "create_all", _flaky_create_all)

    with pytest.raises(SystemExit):
        Database.get_instance()

    db = Database.get_instance()  # 第二次应成功初始化
    assert db.backend == "sqlite"
    assert calls["n"] == 2


def test_mask_db_uri_hides_password(sqlite_env):
    """_mask_db_uri 应隐藏密码，防止凭证随日志泄露"""
    from sail_server.db import _mask_db_uri

    uri = "postgresql+psycopg://postgres:zzh666@localhost:5432/main"
    masked = _mask_db_uri(uri)
    assert "zzh666" not in masked
    assert masked == "postgresql+psycopg://postgres:***@localhost:5432/main"


def test_mask_db_uri_without_password_unchanged(sqlite_env):
    """无密码的 URI 应保持原样"""
    from sail_server.db import _mask_db_uri

    assert (
        _mask_db_uri("postgresql://user@localhost/db")
        == "postgresql://user@localhost/db"
    )
    assert _mask_db_uri("sqlite:////data/sailzen.db") == "sqlite:////data/sailzen.db"
