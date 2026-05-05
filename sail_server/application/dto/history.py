# -*- coding: utf-8 -*-
# @file history.py
# @brief History Pydantic DTOs
# @author sailing-innocent
# @date 2026-03-01
# @version 1.0
# ---------------------------------

"""
历史事件模块 Pydantic DTOs

原位置: sail_server/data/history.py
"""

from datetime import datetime
from typing import Optional, List, Dict, Any

from pydantic import BaseModel, Field, ConfigDict


# ============================================================================
# HistoryEvent DTOs
# ============================================================================


class HistoryEventBase(BaseModel):
    """历史事件基础信息"""

    model_config = ConfigDict(from_attributes=True)

    title: str = Field(description="事件标题")
    description: str = Field(description="事件描述")
    rar_tags: List[str] = Field(default_factory=list, description="手动标注的标签")
    tags: List[str] = Field(
        default_factory=list, description="机器处理后用于检索的标签"
    )
    start_time: Optional[datetime] = Field(default=None, description="估计的开始时间")
    end_time: Optional[datetime] = Field(default=None, description="估计的结束时间")
    related_events: List[int] = Field(
        default_factory=list, description="相关事件的ID列表"
    )
    parent_event: Optional[int] = Field(default=None, description="父事件ID")
    details: Dict[str, Any] = Field(default_factory=dict, description="更多细节信息")


class HistoryEventCreateRequest(BaseModel):
    """创建历史事件请求"""

    model_config = ConfigDict(from_attributes=True)

    title: str = Field(description="事件标题")
    description: str = Field(description="事件描述")
    rar_tags: List[str] = Field(default_factory=list, description="手动标注的标签")
    tags: List[str] = Field(
        default_factory=list, description="机器处理后用于检索的标签"
    )
    start_time: Optional[datetime] = Field(default=None, description="估计的开始时间")
    end_time: Optional[datetime] = Field(default=None, description="估计的结束时间")
    related_events: List[int] = Field(
        default_factory=list, description="相关事件的ID列表"
    )
    parent_event: Optional[int] = Field(default=None, description="父事件ID")
    details: Dict[str, Any] = Field(default_factory=dict, description="更多细节信息")


class HistoryEventUpdateRequest(BaseModel):
    """更新历史事件请求"""

    model_config = ConfigDict(from_attributes=True)

    title: Optional[str] = Field(default=None, description="事件标题")
    description: Optional[str] = Field(default=None, description="事件描述")
    rar_tags: Optional[List[str]] = Field(default=None, description="手动标注的标签")
    tags: Optional[List[str]] = Field(
        default=None, description="机器处理后用于检索的标签"
    )
    start_time: Optional[datetime] = Field(default=None, description="估计的开始时间")
    end_time: Optional[datetime] = Field(default=None, description="估计的结束时间")
    related_events: Optional[List[int]] = Field(
        default=None, description="相关事件的ID列表"
    )
    parent_event: Optional[int] = Field(default=None, description="父事件ID")
    details: Optional[Dict[str, Any]] = Field(default=None, description="更多细节信息")


class HistoryEventResponse(HistoryEventBase):
    """历史事件响应"""

    id: int = Field(description="事件ID")
    receive_time: datetime = Field(description="接收消息的时间")


class HistoryEventListResponse(BaseModel):
    """历史事件列表响应"""

    events: List[HistoryEventResponse]
    total: int


# ============================================================================
# Person DTOs
# ============================================================================


class PersonBase(BaseModel):
    """人物档案基础信息"""

    model_config = ConfigDict(from_attributes=True)

    name: str = Field(description="人物姓名")
    data: str = Field(description="人物档案数据（JSON 或文本格式）")


class PersonCreateRequest(BaseModel):
    """创建人物档案请求"""

    model_config = ConfigDict(from_attributes=True)

    name: str = Field(description="人物姓名")
    data: str = Field(description="人物档案数据（JSON 或文本格式）")


class PersonUpdateRequest(BaseModel):
    """更新人物档案请求"""

    model_config = ConfigDict(from_attributes=True)

    name: Optional[str] = Field(default=None, description="人物姓名")
    data: Optional[str] = Field(
        default=None, description="人物档案数据（JSON 或文本格式）"
    )


class PersonResponse(PersonBase):
    """人物档案响应"""

    id: int = Field(description="人物ID")
    created_at: datetime = Field(description="创建时间")
    updated_at: datetime = Field(description="更新时间")


class PersonListResponse(BaseModel):
    """人物档案列表响应"""

    persons: List[PersonResponse]
    total: int
