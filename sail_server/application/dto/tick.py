# -*- coding: utf-8 -*-
# @file tick.py
# @brief SailTick Ticket Pydantic DTOs
# @author sailing-innocent
# @date 2026-10-27
# @version 1.0
# ---------------------------------
"""SailTick 票据 DTOs。

时间字段语义与 reminder 模块对齐：服务端→客户端 naive datetime；
客户端→服务端 ISO-8601 字符串归一化为 naive 本地时间。
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


def _to_naive_local(v: Any) -> Optional[datetime]:
    """把带 tz 的 ISO 字符串 / datetime 归一化为 naive 本地时间。"""
    if v is None:
        return None
    if isinstance(v, str):
        v = datetime.fromisoformat(v.replace("Z", "+00:00"))
    if isinstance(v, datetime) and v.tzinfo is not None:
        return v.astimezone().replace(tzinfo=None)
    return v


class TicketCreateRequest(BaseModel):
    """创建票据（SailTick agent / 手工测试）。"""

    model_config = ConfigDict(from_attributes=True)
    tick_id: str = Field(default="", description="创建它的 tick 实例 id")
    type: str = Field(default="question", description="question|task|approval|info")
    title: str = Field(description="标题")
    body: str = Field(default="", description="正文（Markdown）")
    priority: str = Field(default="normal", description="low|normal|high|urgent")
    channel: str = Field(default="web", description="web|mobile|plugin")
    expected_reply_by: Optional[datetime] = Field(default=None, description="期待回复时间")
    fallback_assumption: str = Field(default="", description="超期后 AI 采用的假设")
    push: str = Field(default="auto", description="auto|force|none（创建时是否推送手机）")
    _naive = field_validator("expected_reply_by", mode="before")(_to_naive_local)


class TicketReplyRequest(BaseModel):
    """用户回复票据。"""

    reply: str = Field(description="回复内容")


class TicketResolveRequest(BaseModel):
    """关闭票据。"""

    resolution: str = Field(default="", description="关闭说明")


class TicketSnoozeRequest(BaseModel):
    """暂缓票据。"""

    hours: int = Field(default=24, description="暂缓小时数")


class TicketResponse(BaseModel):
    """票据响应。"""

    model_config = ConfigDict(from_attributes=True)
    id: int
    tick_id: str
    type: str
    title: str
    body: str
    status: str
    expected_reply_by: Optional[datetime]
    replied_at: Optional[datetime]
    reply: Optional[str]
    resolved_at: Optional[datetime]
    resolution: Optional[str]
    fallback_assumption: str
    priority: str
    channel: str
    created_at: datetime
    updated_at: datetime


class TicketListResponse(BaseModel):
    items: List[TicketResponse]
    total: int
