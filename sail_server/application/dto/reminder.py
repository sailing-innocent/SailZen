# -*- coding: utf-8 -*-
# @file reminder.py
# @brief Reminder Pydantic DTOs (Android App M1 提醒闭环)
# @author sailing-innocent
# @date 2026-08-03
# @version 1.0
# ---------------------------------

"""
提醒模块 Pydantic DTOs

时间字段语义：
- 服务端→客户端：naive datetime（服务器本地时间），JSON 序列化为 ISO-8601 字符串
- 客户端→服务端（client_event_ts 等）：ISO-8601 字符串，可带时区偏移，
  入库前归一化为 naive 本地时间
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


def _to_naive_local(v: Any) -> Optional[datetime]:
    """把带 tz 的 ISO 字符串 / datetime 归一化为 naive 本地时间"""
    if v is None:
        return None
    if isinstance(v, str):
        # 兼容结尾 Z
        v = datetime.fromisoformat(v.replace("Z", "+00:00"))
    if isinstance(v, datetime) and v.tzinfo is not None:
        return v.astimezone().replace(tzinfo=None)
    return v


# ============================================================================
# Reminder DTOs
# ============================================================================


class ReminderCreateRequest(BaseModel):
    """创建提醒请求（Agent / 业务模块 / 手工测试）"""

    model_config = ConfigDict(from_attributes=True)

    type: str = Field(description="提醒类型，如 attendance.checkin / test.ping")
    title: str = Field(description="标题")
    body: str = Field(default="", description="正文")
    priority: str = Field(default="normal", description="low|normal|high|urgent")
    source: str = Field(
        default="manual", description="schedule|agent|business|geofence|manual"
    )
    trigger_time: datetime = Field(description="触发时间（naive 本地时间）")
    expire_after_minutes: int = Field(default=240, description="投递后有效期（分钟）")
    payload: Dict[str, Any] = Field(default_factory=dict, description="业务负载")
    rule_id: Optional[int] = Field(default=None, description="关联规则 ID")

    _naive = field_validator("trigger_time", mode="before")(_to_naive_local)


class ReminderResponse(BaseModel):
    """提醒响应"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    type: str
    title: str
    body: str = ""
    priority: str = "normal"
    source: str = "manual"
    state: str = "PENDING"
    trigger_time: datetime
    expire_after_minutes: int = 240
    snooze_count: int = 0
    retry_count: int = 0
    next_trigger_time: Optional[datetime] = None
    last_delivered_at: Optional[datetime] = None
    payload: Dict[str, Any] = Field(default_factory=dict)
    rule_id: Optional[int] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


# ============================================================================
# Feedback / Ack DTOs
# ============================================================================


class FeedbackRequest(BaseModel):
    """反馈请求（闭环中枢）"""

    model_config = ConfigDict(from_attributes=True)

    action: str = Field(description="dismiss|snooze|open|resolve")
    option: Optional[str] = Field(
        default=None, description="snooze 选项：15m|1h|tonight|tomorrow"
    )
    client_event_ts: Optional[datetime] = Field(
        default=None, description="客户端实际发生时间（离线补偿）"
    )

    _naive = field_validator("client_event_ts", mode="before")(_to_naive_local)


class AckRequest(BaseModel):
    """投递确认请求"""

    model_config = ConfigDict(from_attributes=True)

    reminder_id: int
    device_id: str
    client_event_ts: Optional[datetime] = None

    _naive = field_validator("client_event_ts", mode="before")(_to_naive_local)


# ============================================================================
# Event DTOs
# ============================================================================


class ReminderEventResponse(BaseModel):
    """提醒事件响应"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    reminder_id: int
    event: str
    detail: Dict[str, Any] = Field(default_factory=dict)
    client_event_ts: Optional[datetime] = None
    created_at: Optional[datetime] = None


# ============================================================================
# Rule DTOs
# ============================================================================


class ReminderRuleCreateRequest(BaseModel):
    """创建提醒规则请求"""

    model_config = ConfigDict(from_attributes=True)

    type: str
    cron: Optional[str] = None
    enabled: bool = True
    priority: str = "normal"
    retry_policy: Dict[str, Any] = Field(default_factory=dict)
    quiet_hours: Optional[Dict[str, Any]] = None
    frequency_level: int = 0


class ReminderRuleUpdateRequest(BaseModel):
    """更新提醒规则请求（仅更新出现的字段）"""

    model_config = ConfigDict(from_attributes=True)

    type: Optional[str] = None
    cron: Optional[str] = None
    enabled: Optional[bool] = None
    priority: Optional[str] = None
    retry_policy: Optional[Dict[str, Any]] = None
    quiet_hours: Optional[Dict[str, Any]] = None
    frequency_level: Optional[int] = None


class ReminderRuleResponse(BaseModel):
    """提醒规则响应"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    type: str
    cron: Optional[str] = None
    enabled: bool = True
    priority: str = "normal"
    retry_policy: Dict[str, Any] = Field(default_factory=dict)
    quiet_hours: Optional[Dict[str, Any]] = None
    frequency_level: int = 0
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


# ============================================================================
# Device DTOs
# ============================================================================


class DeviceRegisterRequest(BaseModel):
    """设备注册/心跳请求"""

    model_config = ConfigDict(from_attributes=True)

    device_id: str = Field(description="App 端 UUID")
    device_name: str = Field(default="", description="设备名")
    app_version: str = Field(default="", description="App 版本")
    push_token: Optional[str] = Field(default=None, description="预留推送 token")


class DeviceResponse(BaseModel):
    """设备响应"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    device_id: str
    device_name: str = ""
    platform: str = "android"
    app_version: str = ""
    push_token: Optional[str] = None
    last_seen_at: Optional[datetime] = None


# ============================================================================
# Summary DTOs
# ============================================================================


class ReminderSummaryResponse(BaseModel):
    """当日小结响应（Inbox 小结卡片）"""

    model_config = ConfigDict(from_attributes=True)

    date: str = Field(description="YYYY-MM-DD（服务器本地日期）")
    pending: int = Field(description="待处理数（DELIVERED+OPENED+SNOOZED+今日PENDING）")
    resolved: int = 0
    ignored: int = 0
    expired: int = 0
    delivered_total: int = Field(default=0, description="今日投递总数（delivered 事件数）")


class OkResponse(BaseModel):
    """通用 OK 响应"""

    ok: bool = True
