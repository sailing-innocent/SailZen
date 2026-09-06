# -*- coding: utf-8 -*-
# @file db.py
# @brief The Database Layer (supports PostgreSQL and SQLite)
# @author sailing-innocent
# @date 2025-01-29
# @version 2.0
# ---------------------------------

from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.orm import Session
from sqlalchemy import MetaData
from typing import Generator
import functools
import os

from sail_server.infrastructure.orm.orm_base import ORMBase

# import all ORM models
from sail_server.infrastructure.orm import health
from sail_server.infrastructure.orm import finance
from sail_server.infrastructure.orm import life
from sail_server.infrastructure.orm import history
from sail_server.infrastructure.orm import text
from sail_server.infrastructure.orm import necessity
from sail_server.infrastructure.orm import reminder
from sail_server.infrastructure.orm import rhythm

__all__ = [
    "Database",
    "g_db_func",
    "db_session",
    "provide_db_session",
    "get_db_dependency",
    "get_db_session",
]


def _get_db_backend() -> str:
    """获取数据库后端类型: 'postgres' 或 'sqlite'"""
    return os.environ.get("DB_BACKEND", "postgres").lower().strip()


def _mask_db_uri(uri: str) -> str:
    """打码 URI 中的密码，避免日志/终端输出泄露凭证"""
    if "@" not in uri or "://" not in uri:
        return uri
    try:
        head, tail = uri.rsplit("@", 1)
        scheme, rest = head.split("://", 1)
        if ":" in rest:
            user, _pwd = rest.split(":", 1)
            return f"{scheme}://{user}:***@{tail}"
    except ValueError:
        pass
    return uri


def _get_db_uri() -> str:
    """根据 DB_BACKEND 环境变量构建数据库 URI"""
    backend = _get_db_backend()

    if backend == "sqlite":
        from sail_server.config.paths import SQLITE_DB_PATH

        sqlite_path = str(SQLITE_DB_PATH)
        # 确保目录存在
        SQLITE_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        # SQLite URI
        return f"sqlite:///{sqlite_path}"
    else:
        # PostgreSQL
        os.environ["PGCLIENTENCODING"] = "UTF8"
        uri = os.environ.get("POSTGRE_URI")
        if not uri:
            raise RuntimeError(
                "POSTGRE_URI environment variable is not set. "
                "Set DB_BACKEND=sqlite to use SQLite instead."
            )
        # 将 postgresql:// 转换为 postgresql+psycopg:// 以使用 psycopg3
        if uri.startswith("postgresql://"):
            uri = uri.replace("postgresql://", "postgresql+psycopg://", 1)
        return uri


class Database:
    __instance = None
    __engine = None
    __uri = None
    __backend = None

    @staticmethod
    def get_instance():
        if Database.__instance is None:
            Database()
        return Database.__instance

    def __init__(self):
        if Database.__instance is not None:
            raise Exception("This class is a singleton!")
        else:
            Database.__instance = self

        self.__backend = _get_db_backend()
        self.__uri = _get_db_uri()

        print(f"[Database] Backend: {self.__backend}")
        print(f"[Database] Connecting to: {_mask_db_uri(self.__uri)}")

        if self.__backend == "sqlite":
            # SQLite: 启用 WAL 模式以获得更好的并发性能
            self.__engine = create_engine(
                self.__uri,
                connect_args={"check_same_thread": False},
            )

            # 启用外键约束（SQLite 默认不启用）
            @event.listens_for(self.__engine, "connect")
            def _set_sqlite_pragma(dbapi_connection, connection_record):
                cursor = dbapi_connection.cursor()
                cursor.execute("PRAGMA journal_mode=WAL")
                cursor.execute("PRAGMA foreign_keys=ON")
                cursor.close()
        else:
            # PostgreSQL: psycopg3 对编码处理更好，不需要额外的 client_encoding 参数
            # connect_timeout 避免数据库不可达时连接无限阻塞（可用 DB_CONNECT_TIMEOUT 调整）
            connect_timeout = int(os.environ.get("DB_CONNECT_TIMEOUT", "10"))
            self.__engine = create_engine(
                self.__uri, connect_args={"connect_timeout": connect_timeout}
            )

        self.SessionLocal = sessionmaker(
            autocommit=False, autoflush=False, bind=self.__engine
        )

        try:
            self.create_all()
        except KeyboardInterrupt:
            # 数据库不可达时 psycopg 连接会长时间阻塞，此时用户 Ctrl+C
            # 属于主动放弃启动，打印一行提示并优雅退出，而不是抛一长串 traceback
            Database.__instance = None
            print("\n[Database] Database connection interrupted by user (Ctrl+C)")
            raise SystemExit(130) from None
        except Exception as e:
            # 连接失败（拒绝/超时/认证等）：给出可操作的提示后再抛出
            Database.__instance = None
            raise RuntimeError(
                f"Cannot connect to database ({_mask_db_uri(self.__uri)}). "
                "Please check that the database server is running and reachable, "
                "or set DB_BACKEND=sqlite in your .env file to use SQLite instead."
            ) from e

        # 自动运行迁移脚本，保证 schema 与 ORM 模型一致（无痛迁移）
        try:
            from sail_server.migration import run_migrations

            run_migrations()
        except KeyboardInterrupt:
            Database.__instance = None
            print("\n[Database] Database migration interrupted by user (Ctrl+C)")
            raise SystemExit(130) from None
        except Exception as e:
            print(f"[Database] Migration failed: {e}")
            raise

    @property
    def backend(self) -> str:
        """返回当前数据库后端类型: 'postgres' 或 'sqlite'"""
        return self.__backend

    @property
    def engine(self):
        return self.__engine

    def drop_all(self):
        ORMBase.metadata.drop_all(bind=self.__engine)

    def create_all(self):
        ORMBase.metadata.create_all(bind=self.__engine)

    def get_db(self) -> Generator[Session, None, None]:
        if self.__engine is None:
            raise Exception("Database engine is not initialized")
        db = self.SessionLocal()
        try:
            yield db
        finally:
            db.close()

    def get_db_session(self) -> Session:
        if self.__engine is None:
            raise Exception("Database engine is not initialized")
        return self.SessionLocal()

    def __str__(self):
        return f"{self.__backend} database at {self.__uri}"


g_db_func = Database.get_instance().get_db


async def get_db_dependency():
    return g_db_func()


def provide_db_session():
    """Litestar dependency that provides a database session (for analysis router)."""
    yield from Database.get_instance().get_db()


def db_session(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        db = Database.get_instance().get_db_session()
        return func(db, *args, **kwargs)

    return wrapper


from contextlib import contextmanager


@contextmanager
def get_db_session():
    """Context manager for getting a database session (useful for background tasks)."""
    db = Database.get_instance().get_db_session()
    try:
        yield db
    finally:
        db.close()
