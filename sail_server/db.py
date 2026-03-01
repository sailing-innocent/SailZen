# -*- coding: utf-8 -*-
# @file postgre.py
# @brief The PostgreSQL Database
# @author sailing-innocent
# @date 2025-01-29
# @version 1.0
# ---------------------------------

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.orm import Session
from sqlalchemy import MetaData
from typing import Generator
import functools

from sail_server.data.orm import ORMBase

# import all ORM models
import sail_server.data.health
import sail_server.data.finance
import sail_server.data.life
import sail_server.data.project
import sail_server.data.history
import sail_server.data.text
import sail_server.data.necessity
import sail_server.data.analysis
import os

# 设置 PostgreSQL 客户端编码环境变量，解决 Windows 中文系统的编码问题
os.environ["PGCLIENTENCODING"] = "UTF8"

__all__ = ["Database", "g_db_func", "db_session", "provide_db_session", "get_db_dependency", "get_db_session"]


class Database:
    __instance = None
    __engine = None
    __uri = None

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

        __uri = os.environ.get("POSTGRE_URI")
        # 将 postgresql:// 转换为 postgresql+psycopg:// 以使用 psycopg3
        if __uri and __uri.startswith("postgresql://"):
            __uri = __uri.replace("postgresql://", "postgresql+psycopg://", 1)
        print("Connecting to ", __uri)
        # psycopg3 对编码处理更好，不需要额外的 client_encoding 参数
        self.__engine = create_engine(__uri)
        self.SessionLocal = sessionmaker(
            autocommit=False, autoflush=False, bind=self.__engine
        )
        self.create_all()

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
        return "sqlite database in " + str(self.__uri)


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
