from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.orm import Session
from sqlalchemy import MetaData
from typing import Generator
import functools

from server.data.orm import ORMBase

# import all ORM models
from server.model import (
    Universe,
    Work,
    UniverseMembership,
    WorkAlias,
    Edition,
    EditionFile,
    EditionTag,
    DocumentNode,
    TextSpan,
    Entity,
    EntityAlias,
    EntityAttribute,
    EntityMention,
    EntityRelation,
    RelationEvidence,
)
import os

__all__ = ["Database", "g_db_func", "db_session"]


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
        print("Connecting to ", __uri)
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


def db_session(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        db = Database.get_instance().get_db_session()
        return func(db, *args, **kwargs)

    return wrapper
