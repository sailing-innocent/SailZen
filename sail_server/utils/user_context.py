# -*- coding: utf-8 -*-
# @file user_context.py
# @brief Unified User Context & Auth Resolution (支持单用户免登录自动引导)
# @author sailing-innocent
# @date 2026-11-24
# @version 1.0
# ---------------------------------
"""统一用户上下文与鉴权解析层。

支持两种运行模式（环境变量 SAILZEN_AUTH_MODE）：
- single_user_auto（默认）：单用户无感自动引导，始终解析到默认 owner（UserProfile.is_default=True），
  不阻断启动流程、不弹登录页；若配置了 SAILZEN_API_TOKEN 仍严格校验 Bearer Token。
- token_required（多用户演进预留）：强制要求 Bearer Token 并按身份头/会话解析用户。
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Optional

from litestar import Request
from litestar.exceptions import NotAuthorizedException
from sqlalchemy.orm import Session

AUTH_MODE_SINGLE_AUTO = "single_user_auto"
AUTH_MODE_TOKEN_REQUIRED = "token_required"


@dataclass(frozen=True)
class UserContext:
    """当前请求的规范化用户上下文。"""

    user_id: int
    slug: str
    client_type: str = "web"  # android | web | cli | sailtick | vscode | qq_bot | system
    device_id: str = ""
    auth_mode: str = AUTH_MODE_SINGLE_AUTO


def get_auth_mode() -> str:
    raw = (os.environ.get("SAILZEN_AUTH_MODE") or AUTH_MODE_SINGLE_AUTO).strip().lower()
    if raw in (AUTH_MODE_SINGLE_AUTO, AUTH_MODE_TOKEN_REQUIRED):
        return raw
    return AUTH_MODE_SINGLE_AUTO


def check_api_token(request: Request, allow_query_token: bool = False) -> None:
    """统一可选 Bearer Token 校验（SAILZEN_API_TOKEN 未设置时本地/自托管放行）。"""
    expected = os.environ.get("SAILZEN_API_TOKEN", "")
    if not expected:
        return
    auth = request.headers.get("Authorization", "")
    if auth == f"Bearer {expected}":
        return
    if allow_query_token and request.query_params.get("token", "") == expected:
        return
    raise NotAuthorizedException(detail="invalid or missing bearer token")


def infer_client_type(request: Request) -> str:
    """从自定义头或 User-Agent 推断调用端类型。"""
    explicit = (request.headers.get("X-SailZen-Client") or "").strip().lower()
    if explicit:
        return explicit[:32]
    ua = (request.headers.get("User-Agent") or "").lower()
    if "okhttp" in ua or "android" in ua or "sailzen-android" in ua:
        return "android"
    if "python-httpx" in ua or "sailtick" in ua:
        return "sailtick"
    if "mozilla" in ua or "chrome" in ua or "safari" in ua or "edge" in ua:
        return "web"
    return "api"


def resolve_user_context(
    request: Request,
    db: Session,
    *,
    allow_query_token: bool = False,
) -> UserContext:
    """校验鉴权并解析当前请求的 UserContext。"""
    check_api_token(request, allow_query_token=allow_query_token)
    auth_mode = get_auth_mode()

    from sail_server.model.user import resolve_or_bootstrap_user

    raw_user_hint: Optional[str] = (
        request.headers.get("X-SailZen-User")
        or request.query_params.get("user")
        or None
    )
    device_id = (
        request.headers.get("X-SailZen-Device")
        or request.query_params.get("device_id")
        or ""
    ).strip()[:128]
    client_type = infer_client_type(request)

    profile = resolve_or_bootstrap_user(db, user_hint=raw_user_hint)
    return UserContext(
        user_id=profile.id,
        slug=profile.slug,
        client_type=client_type,
        device_id=device_id,
        auth_mode=auth_mode,
    )
