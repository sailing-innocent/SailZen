# -*- coding: utf-8 -*-
# @file history.py
# @brief The History Events Data Storage
# @author sailing-innocent
# @date 2025-10-12
# @version 2.0
# ---------------------------------

"""
历史事件模块数据层

ORM 模型已从 infrastructure.orm.history 迁移
DTO 模型已从 application.dto.history 迁移

此文件保留向后兼容的导出和遗留的 dataclass DTOs
（因为 controller 层仍使用 Litestar DataclassDTO）
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, List, Dict, Any

# 从 infrastructure.orm 导入 ORM 模型
from sail_server.infrastructure.orm.history import (
    HistoryEvent,
)

# 从 application.dto 导入 Pydantic DTOs
from sail_server.application.dto.history import (
    HistoryEventBase,
    HistoryEventCreateRequest,
    HistoryEventUpdateRequest,
    HistoryEventResponse,
    HistoryEventListResponse,
)


# ============================================================================
# Legacy Dataclass DTOs (保留以兼容现有 controller)
# TODO: 迁移到 Pydantic DTOs 后删除
# ============================================================================

@dataclass
class HistoryEventData:
    """历史事件数据传输对象 (legacy dataclass)"""
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


__all__ = [
    # ORM Models
    "HistoryEvent",
    # Pydantic DTOs
    "HistoryEventBase",
    "HistoryEventCreateRequest",
    "HistoryEventUpdateRequest",
    "HistoryEventResponse",
    "HistoryEventListResponse",
    # Legacy Dataclass DTOs
    "HistoryEventData",
]
