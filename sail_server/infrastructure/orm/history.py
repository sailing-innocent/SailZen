# -*- coding: utf-8 -*-
# @file history.py
# @brief History ORM Models
# @author sailing-innocent
# @date 2026-03-01
# @version 1.0
# ---------------------------------

"""
历史事件模块 ORM 模型

从 sail_server/data/history.py 迁移
"""

from sqlalchemy import Column, Integer, String, TIMESTAMP, func, Text

from sail_server.infrastructure.orm import ORMBase
from sail_server.data.types import JSONB, ARRAY


class HistoryEvent(ORMBase):
    """
    历史事件表
    用于记录和组织历史事件，支持嵌套结构和关联检索
    """

    __tablename__ = "history_events"

    id = Column(Integer, primary_key=True)
    receive_time = Column(
        TIMESTAMP, server_default=func.current_timestamp()
    )  # 接收消息的时间
    title = Column(String, nullable=False)  # 事件标题
    description = Column(Text, nullable=False)  # 事件描述
    rar_tags = Column(ARRAY(String), default=[])  # 手动标注的标签
    tags = Column(ARRAY(String), default=[])  # 机器处理后用于检索的标签
    start_time = Column(TIMESTAMP, nullable=True)  # 估计的开始时间
    end_time = Column(TIMESTAMP, nullable=True)  # 估计的结束时间
    related_events = Column(ARRAY(Integer), default=[])  # 相关事件的ID列表
    parent_event = Column(Integer, nullable=True)  # 父事件ID
    details = Column(JSONB, default={})  # 更多细节信息


class Person(ORMBase):
    """
    人物档案表
    用于记录历史和现实中的真实人物档案
    """

    __tablename__ = "persons"

    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)  # 人物姓名
    data = Column(Text, nullable=False)  # 人物档案数据（JSON 或文本格式）
    created_at = Column(TIMESTAMP, server_default=func.current_timestamp())
    updated_at = Column(
        TIMESTAMP,
        server_default=func.current_timestamp(),
        onupdate=func.current_timestamp(),
    )
