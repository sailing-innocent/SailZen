# -*- coding: utf-8 -*-
# @file user.py
# @brief UserProfile & Multi-Device Management Business Logic
# @author sailing-innocent
# @date 2026-11-24
# @version 1.0
# ---------------------------------
"""UserProfile 领域业务逻辑。

负责：
- 幂等引导默认单用户 owner（id=1, slug="owner", is_default=True）；
- 统一管理用户资料、安静时段、通知偏好、跨模块健康画像；
- 管理用户绑定的全部终端（Android / Web / CLI / VSCode）及在线态；
- 变更 UserProfile 时通过 UserSyncHub 向全端广播 profile.updated。
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from sail_server.application.dto.user import (
    UserBootstrapResponse,
    UserDeviceRegisterRequest,
    UserDeviceResponse,
    UserProfileResponse,
    UserProfileUpdateRequest,
)
from sail_server.utils.user_context import (
    AUTH_MODE_SINGLE_AUTO,
    UserContext,
    get_auth_mode,
)
from sail_server.utils.user_sync_ws import get_user_sync_hub
from sailzen_orm.reminder import Device
from sailzen_orm.user import (
    UserProfile,
    default_notification_prefs,
    default_quiet_hours,
)

logger = logging.getLogger(__name__)


class UserError(Exception):
    """用户模块错误基类。"""


class UserNotFoundError(UserError):
    """用户或设备不存在。"""


class UserBadRequestError(UserError):
    """用户请求参数错误。"""


def _merge_dict(base: Optional[Dict[str, Any]], patch: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    merged = dict(base or {})
    if patch:
        merged.update(patch)
    return merged


def _to_profile_response(u: UserProfile) -> UserProfileResponse:
    qh = _merge_dict(default_quiet_hours(), u.quiet_hours if isinstance(u.quiet_hours, dict) else {})
    prefs = _merge_dict(
        default_notification_prefs(),
        u.notification_prefs if isinstance(u.notification_prefs, dict) else {},
    )
    return UserProfileResponse(
        id=u.id,
        slug=u.slug or "owner",
        display_name=u.display_name or "SailZen Owner",
        avatar_url=u.avatar_url or "",
        role=u.role or "owner",
        status=u.status or "active",
        is_default=bool(u.is_default),
        timezone=u.timezone or "Asia/Shanghai",
        locale=u.locale or "zh-CN",
        quiet_hours=qh,
        notification_prefs=prefs,
        health_profile=dict(u.health_profile) if isinstance(u.health_profile, dict) else {},
        preferences=dict(u.preferences) if isinstance(u.preferences, dict) else {},
        created_at=u.created_at,
        updated_at=u.updated_at,
    )


def _to_device_response(d: Device) -> UserDeviceResponse:
    hub = get_user_sync_hub()
    return UserDeviceResponse(
        id=d.id,
        user_id=getattr(d, "user_id", None) or 1,
        device_id=d.device_id,
        device_name=d.device_name or "",
        platform=d.platform or "android",
        client_type=getattr(d, "client_type", None) or d.platform or "android",
        app_version=d.app_version or "",
        push_token=d.push_token,
        capabilities=dict(d.capabilities) if isinstance(getattr(d, "capabilities", None), dict) else {},
        is_active=True if getattr(d, "is_active", None) is None else bool(d.is_active),
        is_online=hub.is_online(d.device_id),
        last_sync_seq=int(getattr(d, "last_sync_seq", None) or 0),
        last_seen_at=d.last_seen_at,
    )


def _seed_health_profile_hints(db: Session) -> Dict[str, Any]:
    """初次引导默认用户时，尽力从现有 RhythmEnergyProfile 与 WeightPlan 吸收基础画像（非致命）。"""
    hints: Dict[str, Any] = {}
    try:
        from sailzen_orm.rhythm import RhythmEnergyProfile

        rp = (
            db.query(RhythmEnergyProfile)
            .filter(RhythmEnergyProfile.is_default == True)  # noqa: E712
            .first()
        )
        if rp is not None:
            if getattr(rp, "sleep_start", None):
                hints["sleep_time"] = str(rp.sleep_start)
            if getattr(rp, "sleep_end", None):
                hints["wake_time"] = str(rp.sleep_end)
    except Exception:
        pass
    try:
        from sailzen_orm.health import WeightPlan

        wp = (
            db.query(WeightPlan)
            .order_by(WeightPlan.id.desc())
            .first()
        )
        if wp is not None and getattr(wp, "target_weight", None) is not None:
            hints["target_weight_kg"] = float(wp.target_weight)
    except Exception:
        pass
    return hints


def ensure_default_user_profile(db: Session) -> UserProfile:
    """幂等确保默认单用户 owner（id=1, slug='owner'）存在。"""
    u = (
        db.query(UserProfile)
        .filter(UserProfile.is_default == True)  # noqa: E712
        .order_by(UserProfile.id.asc())
        .first()
    )
    if u is not None:
        return u

    u = db.query(UserProfile).filter(UserProfile.slug == "owner").first()
    if u is not None:
        u.is_default = True
        db.commit()
        db.refresh(u)
        return u

    now = datetime.now()
    u = UserProfile(
        id=1,
        slug="owner",
        display_name="SailZen Owner",
        avatar_url="",
        role="owner",
        status="active",
        is_default=True,
        timezone="Asia/Shanghai",
        locale="zh-CN",
        quiet_hours=default_quiet_hours(),
        notification_prefs=default_notification_prefs(),
        health_profile=_seed_health_profile_hints(db),
        preferences={},
        created_at=now,
        updated_at=now,
    )
    db.add(u)
    db.commit()
    db.refresh(u)
    logger.info("[user] bootstrapped default owner UserProfile id=%s slug=%s", u.id, u.slug)
    return u


def resolve_or_bootstrap_user(
    db: Session, user_hint: Optional[str] = None
) -> UserProfile:
    """按 slug/id 解析用户；未指定或找不到时在单用户模式下回退到默认 owner。"""
    if user_hint:
        hint = user_hint.strip()
        if hint.isdigit():
            u = db.get(UserProfile, int(hint))
            if u is not None and u.status == "active":
                return u
        else:
            u = (
                db.query(UserProfile)
                .filter(UserProfile.slug == hint, UserProfile.status == "active")
                .first()
            )
            if u is not None:
                return u
    return ensure_default_user_profile(db)


def get_user_profile_impl(db: Session, user_id: int) -> UserProfileResponse:
    u = db.get(UserProfile, user_id)
    if u is None:
        u = ensure_default_user_profile(db)
    return _to_profile_response(u)


def update_user_profile_impl(
    db: Session,
    user_id: int,
    req: UserProfileUpdateRequest,
    *,
    exclude_device_id: Optional[str] = None,
) -> UserProfileResponse:
    """更新用户档案并广播 profile.updated 到该用户的全部在线终端。"""
    u = db.get(UserProfile, user_id)
    if u is None:
        u = ensure_default_user_profile(db)

    data = req.model_dump(exclude_unset=True)
    if "display_name" in data and data["display_name"] is not None:
        name = str(data["display_name"]).strip()
        if not name:
            raise UserBadRequestError("display_name cannot be empty")
        u.display_name = name[:128]
    if "avatar_url" in data and data["avatar_url"] is not None:
        u.avatar_url = str(data["avatar_url"]).strip()[:512]
    if "timezone" in data and data["timezone"] is not None:
        u.timezone = str(data["timezone"]).strip()[:64] or "Asia/Shanghai"
    if "locale" in data and data["locale"] is not None:
        u.locale = str(data["locale"]).strip()[:16] or "zh-CN"
    if "quiet_hours" in data and isinstance(data["quiet_hours"], dict):
        u.quiet_hours = _merge_dict(
            u.quiet_hours if isinstance(u.quiet_hours, dict) else default_quiet_hours(),
            data["quiet_hours"],
        )
    if "notification_prefs" in data and isinstance(data["notification_prefs"], dict):
        u.notification_prefs = _merge_dict(
            u.notification_prefs if isinstance(u.notification_prefs, dict) else default_notification_prefs(),
            data["notification_prefs"],
        )
    if "health_profile" in data and isinstance(data["health_profile"], dict):
        u.health_profile = _merge_dict(
            u.health_profile if isinstance(u.health_profile, dict) else {},
            data["health_profile"],
        )
    if "preferences" in data and isinstance(data["preferences"], dict):
        u.preferences = _merge_dict(
            u.preferences if isinstance(u.preferences, dict) else {},
            data["preferences"],
        )

    u.updated_at = datetime.now()
    db.commit()
    db.refresh(u)

    resp = _to_profile_response(u)
    hub = get_user_sync_hub()
    hub.fire_and_forget(
        hub.broadcast_profile_updated(
            user_id=u.id,
            profile=resp.model_dump(mode="json"),
            exclude_device_id=exclude_device_id,
        )
    )
    return resp


def is_user_in_quiet_hours(
    db: Session, user_id: int = 1, now: Optional[datetime] = None
) -> bool:
    """基于 UserProfile.quiet_hours 的统一安静时段判断（兼容跨午夜如 23:00-08:00）。"""
    now = now or datetime.now()
    u = db.get(UserProfile, user_id)
    qh = (
        u.quiet_hours
        if (u is not None and isinstance(u.quiet_hours, dict))
        else default_quiet_hours()
    )
    if qh.get("enabled") is False:
        return False

    def _parse(val: Any) -> Optional[int]:
        try:
            parts = str(val).strip().split(":")
            return int(parts[0]) * 60 + int(parts[1])
        except Exception:
            return None

    st = _parse(qh.get("start", "23:00"))
    et = _parse(qh.get("end", "08:00"))
    if st is None or et is None:
        return False
    cur = now.hour * 60 + now.minute
    if st <= et:
        return st <= cur < et
    return cur >= st or cur < et


def is_auto_resolve_enabled(db: Session, user_id: int = 1) -> bool:
    """检查用户是否启用业务域动作自动消解收件箱条目（默认开启）。"""
    u = db.get(UserProfile, user_id)
    if u is None or not isinstance(u.notification_prefs, dict):
        return True
    return bool(u.notification_prefs.get("auto_resolve_on_domain_action", True))


def register_user_device_impl(
    db: Session, user_id: int, req: UserDeviceRegisterRequest
) -> UserDeviceResponse:
    """注册或刷新某用户下的终端设备（支持 Android / Web / CLI / VSCode）。"""
    did = (req.device_id or "").strip()
    if not did:
        raise UserBadRequestError("device_id is required")

    device = db.query(Device).filter(Device.device_id == did).first()
    if device is None:
        device = Device(
            user_id=user_id,
            device_id=did,
            platform=req.platform or req.client_type or "android",
            client_type=req.client_type or req.platform or "android",
            capabilities=req.capabilities or {},
            is_active=True,
            last_sync_seq=0,
        )
        db.add(device)
    else:
        device.user_id = user_id
        device.is_active = True
        if req.platform:
            device.platform = req.platform
        if req.client_type:
            device.client_type = req.client_type
        if req.capabilities:
            device.capabilities = _merge_dict(
                device.capabilities if isinstance(device.capabilities, dict) else {},
                req.capabilities,
            )

    if req.device_name:
        device.device_name = req.device_name
    if req.app_version:
        device.app_version = req.app_version
    if req.push_token is not None:
        device.push_token = req.push_token
    device.last_seen_at = datetime.now()
    db.commit()
    db.refresh(device)
    return _to_device_response(device)


def list_user_devices_impl(
    db: Session, user_id: int, active_only: bool = True
) -> List[UserDeviceResponse]:
    q = db.query(Device).filter(Device.user_id == user_id)
    if active_only:
        q = q.filter((Device.is_active == True) | (Device.is_active.is_(None)))  # noqa: E712
    rows = q.order_by(Device.last_seen_at.desc(), Device.id.desc()).all()
    return [_to_device_response(r) for r in rows]


def deactivate_user_device_impl(
    db: Session, user_id: int, device_id: str
) -> bool:
    device = (
        db.query(Device)
        .filter(Device.user_id == user_id, Device.device_id == device_id)
        .first()
    )
    if device is None:
        raise UserNotFoundError(f"device {device_id!r} not found")
    device.is_active = False
    db.commit()
    get_user_sync_hub().unregister(device_id)
    return True


def get_user_bootstrap_impl(
    db: Session, ctx: UserContext
) -> UserBootstrapResponse:
    """客户端静默启动引导：聚合 UserProfile + 未读计数 + 最新同步游标 + 终端列表。"""
    from sail_server.model.inbox import get_inbox_cursor_stats

    profile = get_user_profile_impl(db, ctx.user_id)
    stats = get_inbox_cursor_stats(db, ctx.user_id)
    devices = list_user_devices_impl(db, ctx.user_id, active_only=True)
    hub = get_user_sync_hub()
    auth_mode = get_auth_mode()
    return UserBootstrapResponse(
        auth_mode=auth_mode,
        requires_login=(auth_mode != AUTH_MODE_SINGLE_AUTO),
        user=profile,
        unread_inbox_count=stats["unread_count"],
        active_inbox_count=stats["active_count"],
        latest_sync_seq=stats["latest_sync_seq"],
        online_device_count=hub.online_count(ctx.user_id),
        devices=devices,
    )
