# -*- coding: utf-8 -*-
# @file conftest.py
# @brief tests/server 共享 fixtures（SQLite 内存库 + rhythm 测试助手）
# @author sailing-innocent
# @date 2026-10-26
# @version 1.0
# ---------------------------------

"""
tests/server 共享 fixtures

使用 SQLite 内存数据库（StaticPool），不依赖 PostgreSQL。
所有测试标记 pytest.mark.server（见各文件 pytestmark）。
"""

from datetime import date, datetime, time
from typing import Generator

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from sail_server.infrastructure.orm.orm_base import ORMBase

# 确保全部 ORM 模块被加载（建表完整）
from sail_server.infrastructure.orm import (  # noqa: F401
    finance,
    health,
    history,
    life,
    necessity,
    reminder,
    rhythm,
    text,
)

#: 测试基准日（2026-10-26 周一，ISO W2026-44）
TEST_DATE = date(2026, 10, 26)


@pytest.fixture(scope="function")
def rhythm_engine():
    """SQLite 内存引擎（StaticPool 保证跨会话共享同一内存库）"""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    ORMBase.metadata.create_all(bind=engine)
    yield engine
    engine.dispose()


@pytest.fixture(scope="function")
def db(rhythm_engine) -> Generator[Session, None, None]:
    SessionLocal = sessionmaker(bind=rhythm_engine)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


# ============================================================================
# 测试助手
# ============================================================================


def make_template_payload(name="weekday", mask=None, priority=0):
    """默认骨架：通勤 + 上午工作窗(90/15 微节律) + 午餐 + 下午工作窗"""
    return {
        "name": name,
        "description": "测试骨架",
        "weekday_mask": mask or [1, 1, 1, 1, 1, 0, 0],
        "priority": priority,
        "slots": [
            {"label": "通勤", "start": "08:20", "end": "09:00", "block_type": "commute"},
            {
                "label": "上午工作窗",
                "start": "09:00",
                "end": "12:00",
                "block_type": "work_window",
                "micro_cycle": {"work_min": 90, "rest_min": 15},
            },
            {"label": "午餐", "start": "12:00", "end": "13:00", "block_type": "meal"},
            {"label": "下午工作窗", "start": "13:00", "end": "18:00", "block_type": "work_window"},
        ],
    }


def dt(d: date, hhmm: str) -> datetime:
    """测试基准时间构造"""
    h, m = hhmm.split(":")
    return datetime.combine(d, time(int(h), int(m)))
