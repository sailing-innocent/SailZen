# -*- coding: utf-8 -*-
# @file inbox.py
# @brief Unified UserInbox Pydantic DTOs
# @author sailing-innocent
# @date 2026-11-24
# @version 1.0
# ---------------------------------
"""统一用户收件箱 Pydantic DTO。"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field


class InboxItemResponse(BaseModel):
    """统一收件箱条目响应（Android / Web / CLI 共享唯一视图）。"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int = 1
    sync_seq: int = 0
    source_domain: str = "system"
    target_domain: str = ""
    persona: str = ""
    target_clients: List[str] = Field(default_factory=list)
    item_kind: str = "notice"
    topic: str = ""
    dedup_key: str = ""
    ref_type: str = ""
    ref_id: Optional[int] = None
    reminder_id: Optional[int] = None
    ticket_id: Optional[int] = None
    title: str
    body: str = ""
    priority: str = "normal"
    status: str = "delivered"
    is_read: bool = False
    read_at: Optional[datetime] = None
    action_schema: Dict[str, Any] = Field(default_factory=dict)
    reply_text: Optional[str] = None
    resolution_source: str = ""
    resolution_summary: str = ""
    resolution_ref: Dict[str, Any] = Field(default_factory=dict)
    trigger_at: Optional[datetime] = None
    snooze_until: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    delivered_at: Optional[datetime] = None
    resolved_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class InboxEventResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    inbox_item_id: int
    user_id: int = 1
    event: str
    actor_client: str = "system"
    device_id: str = ""
    detail: Dict[str, Any] = Field(default_factory=dict)
    created_at: Optional[datetime] = None


class InboxSyncResponse(BaseModel):
    """单调游标增量同步 + 全量活跃 ID 对账响应。"""

    model_config = ConfigDict(from_attributes=True)

    latest_seq: int = 0
    unread_count: int = 0
    active_count: int = 0
    active_ids: List[int] = Field(default_factory=list)
    changes: List[InboxItemResponse] = Field(default_factory=list)


class InboxSummaryResponse(BaseModel):
    """今日收件箱聚合摘要。"""

    model_config = ConfigDict(from_attributes=True)

    date: str
    active: int = 0
    unread: int = 0
    answered: int = 0
    resolved: int = 0
    dismissed: int = 0
    expired: int = 0
    by_domain: Dict[str, int] = Field(default_factory=dict)


class InboxCreateRequest(BaseModel):
    """显式创建收件箱条目请求（供业务模块/测试调用）。"""

    model_config = ConfigDict(from_attributes=True)

    source_domain: str = "manual"
    target_domain: str = ""
    persona: str = ""
    target_clients: List[str] = Field(default_factory=list)
    item_kind: str = "notice"
    topic: str = ""
    dedup_key: str = ""
    ref_type: str = ""
    ref_id: Optional[int] = None
    reminder_id: Optional[int] = None
    ticket_id: Optional[int] = None
    title: str
    body: str = ""
    priority: str = "normal"
    status: str = "delivered"
    action_schema: Dict[str, Any] = Field(default_factory=dict)
    trigger_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    notify: bool = True


class InboxReplyRequest(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    reply: str
    source: Optional[str] = None


class InboxResolveRequest(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    resolution_summary: str = ""
    resolution_source: Optional[str] = None


class InboxSnoozeRequest(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    # 支持 reminder 风格的 15m/1h/tonight/tomorrow 或显式 hours
    option: Optional[str] = None
    hours: Optional[int] = None


class InboxDismissRequest(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    reason: str = ""
