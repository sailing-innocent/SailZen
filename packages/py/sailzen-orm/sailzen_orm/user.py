# -*- coding: utf-8 -*-
# @file user.py
# @brief UserProfile ORM Models (统一用户面身份、偏好与共享画像)
# @author sailing-innocent
# @date 2026-11-24
# @version 1.0
# ---------------------------------
"""统一 UserProfile ORM 模型。

作为 SailZen 全栈（Web / Android / SailTick / CLI / VSCode 插件）的单一用户面事实源：
- 当前单用户阶段通过 is_default=True 支持免登录自动引导（AUTH_MODE=single_user_auto）；
- 统一收口安静时段（quiet_hours）、通知偏好（notification_prefs）与跨模块健康/作息画像；
- 为未来多用户与细粒度设备/会话权限预留清晰字段边界。
"""

from datetime import datetime

from sqlalchemy import (
    Boolean,
    Column,
    Integer,
    String,
    TIMESTAMP,
    func,
)

from sailzen_orm import ORMBase
from sailzen_orm.types import JSONB


def default_quiet_hours() -> dict:
    return {"enabled": True, "start": "23:00", "end": "08:00"}


def default_notification_prefs() -> dict:
    return {
        "android_push": True,
        "web_realtime": True,
        "auto_resolve_on_domain_action": True,
        "digest_time": "21:45",
    }


class UserProfile(ORMBase):
    """统一用户档案与多端偏好中心。"""

    __tablename__ = "user_profiles"

    id = Column(Integer, primary_key=True, autoincrement=True)
    # 稳定标识符（单用户默认 "owner"）
    slug = Column(String(64), unique=True, nullable=False, index=True, default="owner")
    display_name = Column(String(128), nullable=False, default="SailZen Owner")
    avatar_url = Column(String(512), nullable=True, default="")
    # owner | member
    role = Column(String(32), nullable=False, default="owner")
    # active | disabled
    status = Column(String(32), nullable=False, default="active", index=True)
    # 单用户免登录自动引导命中标记
    is_default = Column(Boolean, nullable=False, default=False, index=True)
    timezone = Column(String(64), nullable=False, default="Asia/Shanghai")
    locale = Column(String(16), nullable=False, default="zh-CN")
    # 统一安静时段：{"enabled": true, "start": "23:00", "end": "08:00"}
    quiet_hours = Column(JSONB, default=default_quiet_hours)
    # 通知与自动消解偏好
    notification_prefs = Column(JSONB, default=default_notification_prefs)
    # 跨 Health / Rhythm / SailTick 共享的用户画像（目标体重、作息、饮食习惯等）
    health_profile = Column(JSONB, default=dict)
    # 端侧与 UI 扩展偏好
    preferences = Column(JSONB, default=dict)
    created_at = Column(
        TIMESTAMP, default=datetime.now, server_default=func.current_timestamp()
    )
    updated_at = Column(
        TIMESTAMP,
        default=datetime.now,
        server_default=func.current_timestamp(),
        onupdate=func.current_timestamp(),
    )
