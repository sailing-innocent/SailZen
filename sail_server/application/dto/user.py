# -*- coding: utf-8 -*-
# @file user.py
# @brief UserProfile & Device Pydantic DTOs
# @author sailing-innocent
# @date 2026-11-24
# @version 1.0
# ---------------------------------
"""UserProfile 与终端管理 Pydantic DTO。"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field


class QuietHoursDto(BaseModel):
    """统一安静时段配置（覆盖全端：Android / Web / Reminder / SailTick）。"""

    model_config = ConfigDict(from_attributes=True)

    enabled: bool = True
    start: str = "23:00"
    end: str = "08:00"


class UserProfileResponse(BaseModel):
    """用户档案响应。"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    slug: str = "owner"
    display_name: str = "SailZen Owner"
    avatar_url: str = ""
    role: str = "owner"
    status: str = "active"
    is_default: bool = True
    timezone: str = "Asia/Shanghai"
    locale: str = "zh-CN"
    quiet_hours: Dict[str, Any] = Field(
        default_factory=lambda: {"enabled": True, "start": "23:00", "end": "08:00"}
    )
    notification_prefs: Dict[str, Any] = Field(default_factory=dict)
    health_profile: Dict[str, Any] = Field(default_factory=dict)
    preferences: Dict[str, Any] = Field(default_factory=dict)
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class UserProfileUpdateRequest(BaseModel):
    """部分更新 UserProfile 请求。"""

    model_config = ConfigDict(from_attributes=True)

    display_name: Optional[str] = None
    avatar_url: Optional[str] = None
    timezone: Optional[str] = None
    locale: Optional[str] = None
    quiet_hours: Optional[Dict[str, Any]] = None
    notification_prefs: Optional[Dict[str, Any]] = None
    health_profile: Optional[Dict[str, Any]] = None
    preferences: Optional[Dict[str, Any]] = None


class UserDeviceRegisterRequest(BaseModel):
    """终端注册/心跳请求（Android / Web / CLI / VSCode 通用）。"""

    model_config = ConfigDict(from_attributes=True)

    device_id: str
    device_name: str = ""
    platform: str = "android"
    client_type: str = "android"
    app_version: str = ""
    push_token: Optional[str] = None
    capabilities: Dict[str, Any] = Field(default_factory=dict)


class UserDeviceResponse(BaseModel):
    """终端设备响应。"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int = 1
    device_id: str
    device_name: str = ""
    platform: str = "android"
    client_type: str = "android"
    app_version: str = ""
    push_token: Optional[str] = None
    capabilities: Dict[str, Any] = Field(default_factory=dict)
    is_active: bool = True
    is_online: bool = False
    last_sync_seq: int = 0
    last_seen_at: Optional[datetime] = None


class UserBootstrapResponse(BaseModel):
    """客户端静默启动引导响应（单用户免登录自动打开）。"""

    model_config = ConfigDict(from_attributes=True)

    auth_mode: str = "single_user_auto"
    requires_login: bool = False
    user: UserProfileResponse
    unread_inbox_count: int = 0
    active_inbox_count: int = 0
    latest_sync_seq: int = 0
    online_device_count: int = 0
    devices: List[UserDeviceResponse] = Field(default_factory=list)
