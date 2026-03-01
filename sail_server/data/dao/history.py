# -*- coding: utf-8 -*-
# @file history.py
# @brief History DAO
# @author sailing-innocent
# @date 2026-03-01
# @version 1.0
# ---------------------------------

"""
历史事件模块 DAO

从 sail_server/data/history.py 迁移数据访问逻辑
"""

from typing import List, Optional
from sqlalchemy.orm import Session

from sail_server.infrastructure.orm.history import HistoryEvent
from sail_server.data.dao.base import BaseDAO


class HistoryEventDAO(BaseDAO[HistoryEvent]):
    """历史事件 DAO"""
    
    def __init__(self, db: Session):
        super().__init__(db, HistoryEvent)
    
    def get_by_parent(self, parent_event_id: int) -> List[HistoryEvent]:
        """获取父事件的所有子事件"""
        return self.db.query(HistoryEvent).filter(
            HistoryEvent.parent_event == parent_event_id
        ).order_by(HistoryEvent.start_time).all()
    
    def get_by_tag(self, tag: str) -> List[HistoryEvent]:
        """获取包含指定标签的所有事件"""
        return self.db.query(HistoryEvent).filter(
            HistoryEvent.tags.contains([tag])
        ).order_by(HistoryEvent.start_time.desc()).all()
    
    def get_root_events(self) -> List[HistoryEvent]:
        """获取所有根事件（没有父事件的事件）"""
        return self.db.query(HistoryEvent).filter(
            HistoryEvent.parent_event.is_(None)
        ).order_by(HistoryEvent.start_time.desc()).all()
