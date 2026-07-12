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
