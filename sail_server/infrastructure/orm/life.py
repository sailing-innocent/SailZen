# -*- coding: utf-8 -*-
# @file life.py
# @brief Life ORM Models
# @author sailing-innocent
# @date 2026-03-01
# @version 1.0
# ---------------------------------

"""
生活服务模块 ORM 模型

从 sail_server/data/life.py 迁移
"""

from sqlalchemy import Column, Integer, String, BigInteger, Date, ForeignKey, TIMESTAMP, func
from sqlalchemy.orm import relationship

from sail_server.infrastructure.orm import ORMBase
from sail_server.data.types import JSONB, ARRAY


class ServiceAccount(ORMBase):
    """服务资产，存在有效期限"""

    __tablename__ = "service_account"
    id = Column(Integer, primary_key=True)
    name = Column(String(255), nullable=False)  # account name
    entry = Column(String(255), nullable=False)  # entry website/app name
    username = Column(String(255), nullable=False)  # username
    password = Column(String(255), nullable=False)  # password
    desp = Column(String(255), nullable=True)  # account description
    expire_time = Column(
        BigInteger, nullable=False
    )  # expire time, store as timestamp in seconds


class Day(ORMBase):
    """自然日表

    最特殊、最基础的时间节点。每个自然日一行，顺序存储，
    作为所有节律（三餐、作息）的锚点。
    """

    __tablename__ = "days"

    id = Column(Integer, primary_key=True, autoincrement=True)
    date = Column(Date, nullable=False, unique=True, index=True)
    ref = Column(JSONB, default=dict)
    created_at = Column(TIMESTAMP, server_default=func.current_timestamp())
    updated_at = Column(
        TIMESTAMP,
        server_default=func.current_timestamp(),
        onupdate=func.current_timestamp(),
    )


class TimeSpan(ORMBase):
    """通用时间节点表

    按 class 区分类型，统一放到同一张表，通过 class 查询。
    支持一级子时间 child_spans。
    """

    __tablename__ = "timespans"

    id = Column(Integer, primary_key=True, autoincrement=True)
    # class 是 Python 关键字，使用 class_ 映射到数据库列 class
    class_ = Column("class", String(32), nullable=False, index=True)
    name = Column(String(64), nullable=False, index=True)
    start_day_id = Column(
        Integer, ForeignKey("days.id"), nullable=False, index=True
    )
    end_day_id = Column(
        Integer, ForeignKey("days.id"), nullable=False, index=True
    )
    child_span_ids = Column(ARRAY(Integer), default=list)
    ref = Column(JSONB, default=dict)
    created_at = Column(TIMESTAMP, server_default=func.current_timestamp())
    updated_at = Column(
        TIMESTAMP,
        server_default=func.current_timestamp(),
        onupdate=func.current_timestamp(),
    )

    start_day = relationship("Day", foreign_keys=[start_day_id])
    end_day = relationship("Day", foreign_keys=[end_day_id])


class Rhythm(ORMBase):
    """节律规则表

    用于描述某一天的节律分类与精力系数。day_id 为特定日规则，
    weekday 为周期性规则（0-6）。两者至少一个非空，day_id 优先。
    """

    __tablename__ = "rhythms"

    id = Column(Integer, primary_key=True, autoincrement=True)
    day_id = Column(
        Integer, ForeignKey("days.id"), nullable=True, default=None, index=True
    )
    weekday = Column(Integer, nullable=True)  # 0-6
    class_ = Column("class", String(32), nullable=False, index=True)
    energy_multiplier = Column(Integer, default=100)  # percentage * 100
    default_start_time = Column(String(8), nullable=True)  # HH:MM:SS
    default_end_time = Column(String(8), nullable=True)  # HH:MM:SS
    tags = Column(ARRAY(String), default=list)
    created_at = Column(TIMESTAMP, server_default=func.current_timestamp())
    updated_at = Column(
        TIMESTAMP,
        server_default=func.current_timestamp(),
        onupdate=func.current_timestamp(),
    )

    day = relationship("Day", foreign_keys=[day_id])


class TimeLog(ORMBase):
    """时间投入记录

    记录任务实际花费的时间与精力。
    """

    __tablename__ = "timelogs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    mission_id = Column(
        Integer, ForeignKey("missions.id"), nullable=False, index=True
    )
    day_id = Column(
        Integer, ForeignKey("days.id"), nullable=False, index=True
    )
    start_time = Column(TIMESTAMP, server_default=func.current_timestamp())
    end_time = Column(TIMESTAMP, nullable=True)
    duration_minutes = Column(Integer, default=0)
    description = Column(String, default="")
    energy_cost = Column(Integer, default=0)
    created_at = Column(TIMESTAMP, server_default=func.current_timestamp())

    day = relationship("Day", foreign_keys=[day_id])
