# -*- coding: utf-8 -*-
# @file history.py
# @brief The History Events Data Storage
# @author sailing-innocent
# @date 2025-10-12
# @version 1.0
# ---------------------------------

from sqlalchemy import Column, Integer, String, TIMESTAMP, func, Text
from sqlalchemy.dialects.postgresql import JSONB, ARRAY
from .orm import ORMBase
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, List, Dict, Any


class HistoryEvent(ORMBase):
    """
    历史事件表
    用于记录和组织历史事件，支持嵌套结构和关联检索
    """
    __tablename__ = "history_events"
    
    id = Column(Integer, primary_key=True)
    receive_time = Column(TIMESTAMP, server_default=func.current_timestamp())  # 接收消息的时间
    title = Column(String, nullable=False)  # 事件标题
    description = Column(Text, nullable=False)  # 事件描述
    rar_tags = Column(ARRAY(String), default=[])  # 手动标注的标签
    tags = Column(ARRAY(String), default=[])  # 机器处理后用于检索的标签
    start_time = Column(TIMESTAMP, nullable=True)  # 估计的开始时间
    end_time = Column(TIMESTAMP, nullable=True)  # 估计的结束时间
    related_events = Column(ARRAY(Integer), default=[])  # 相关事件的ID列表
    parent_event = Column(Integer, nullable=True)  # 父事件ID
    details = Column(JSONB, default={})  # 更多细节信息


@dataclass
class HistoryEventData:
    """
    历史事件数据传输对象
    """
    title: str
    description: str
    id: int = field(default=-1)
    receive_time: Optional[datetime] = field(default=None)
    rar_tags: List[str] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)
    start_time: Optional[datetime] = field(default=None)
    end_time: Optional[datetime] = field(default=None)
    related_events: List[int] = field(default_factory=list)
    parent_event: Optional[int] = field(default=None)
    details: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def read_from_orm(cls, orm: HistoryEvent):
        """从ORM模型创建数据对象"""
        return cls(
            id=orm.id,
            receive_time=orm.receive_time,
            title=orm.title,
            description=orm.description,
            rar_tags=orm.rar_tags or [],
            tags=orm.tags or [],
            start_time=orm.start_time,
            end_time=orm.end_time,
            related_events=orm.related_events or [],
            parent_event=orm.parent_event,
            details=orm.details or {},
        )

    def create_event(self):
        """创建ORM模型"""
        return HistoryEvent(
            title=self.title,
            description=self.description,
            rar_tags=self.rar_tags,
            tags=self.tags,
            start_time=self.start_time,
            end_time=self.end_time,
            related_events=self.related_events,
            parent_event=self.parent_event,
            details=self.details,
        )

    def update_event(self, event: HistoryEvent):
        """更新ORM模型"""
        event.title = self.title
        event.description = self.description
        event.rar_tags = self.rar_tags
        event.tags = self.tags
        event.start_time = self.start_time
        event.end_time = self.end_time
        event.related_events = self.related_events
        event.parent_event = self.parent_event
        event.details = self.details

