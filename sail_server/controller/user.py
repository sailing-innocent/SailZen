# -*- coding: utf-8 -*-
# @file user.py
# @brief UserProfile & Device REST Controller (/api/v1/user)
# @author sailing-innocent
# @date 2026-11-24
# @version 1.0
# ---------------------------------
"""统一 User 面 REST 控制器。"""

from __future__ import annotations

from contextlib import contextmanager
from typing import Generator, List

from litestar import Controller, Request, delete, get, patch, post
from litestar.exceptions import ClientException, NotFoundException
from sqlalchemy.orm import Session

from sail_server.application.dto.user import (
    UserBootstrapResponse,
    UserDeviceCleanupRequest,
    UserDeviceCleanupResponse,
    UserDeviceRegisterRequest,
    UserDeviceResponse,
    UserProfileResponse,
    UserProfileUpdateRequest,
)
from sail_server.model.user import (
    UserBadRequestError,
    UserNotFoundError,
    cleanup_user_devices_impl,
    deactivate_user_device_impl,
    get_user_bootstrap_impl,
    get_user_profile_impl,
    list_user_devices_impl,
    register_user_device_impl,
    update_user_profile_impl,
)
from sail_server.utils.user_context import resolve_user_context


@contextmanager
def _map_errors():
    try:
        yield
    except UserNotFoundError as exc:
        raise NotFoundException(detail=str(exc)) from exc
    except UserBadRequestError as exc:
        raise ClientException(status_code=400, detail=str(exc)) from exc


class UserController(Controller):
    path = "/"

    @get("/bootstrap")
    async def bootstrap(
        self,
        request: Request,
        router_dependency: Generator[Session, None, None],
    ) -> UserBootstrapResponse:
        """客户端启动免登录静默引导接口（Web / Android 通用）。"""
        db = next(router_dependency)
        ctx = resolve_user_context(request, db)
        with _map_errors():
            return get_user_bootstrap_impl(db, ctx)

    @get("/profile")
    async def get_profile(
        self,
        request: Request,
        router_dependency: Generator[Session, None, None],
    ) -> UserProfileResponse:
        db = next(router_dependency)
        ctx = resolve_user_context(request, db)
        with _map_errors():
            return get_user_profile_impl(db, ctx.user_id)

    @patch("/profile")
    async def update_profile(
        self,
        data: UserProfileUpdateRequest,
        request: Request,
        router_dependency: Generator[Session, None, None],
    ) -> UserProfileResponse:
        db = next(router_dependency)
        ctx = resolve_user_context(request, db)
        with _map_errors():
            return update_user_profile_impl(
                db,
                ctx.user_id,
                data,
                exclude_device_id=ctx.device_id or None,
            )

    @get("/devices")
    async def list_devices(
        self,
        request: Request,
        router_dependency: Generator[Session, None, None],
    ) -> List[UserDeviceResponse]:
        db = next(router_dependency)
        ctx = resolve_user_context(request, db)
        with _map_errors():
            return list_user_devices_impl(db, ctx.user_id)

    @post("/devices/register")
    async def register_device(
        self,
        data: UserDeviceRegisterRequest,
        request: Request,
        router_dependency: Generator[Session, None, None],
    ) -> UserDeviceResponse:
        db = next(router_dependency)
        ctx = resolve_user_context(request, db)
        with _map_errors():
            return register_user_device_impl(db, ctx.user_id, data)

    @post("/devices/cleanup")
    async def cleanup_devices(
        self,
        request: Request,
        router_dependency: Generator[Session, None, None],
        data: UserDeviceCleanupRequest | None = None,
    ) -> UserDeviceCleanupResponse:
        """一键去重、清理模拟器与长期离线僵尸终端。"""
        db = next(router_dependency)
        ctx = resolve_user_context(request, db)
        with _map_errors():
            return cleanup_user_devices_impl(db, ctx.user_id, data)

    @delete("/devices/{device_id:str}", status_code=200)
    async def remove_device(
        self,
        device_id: str,
        request: Request,
        router_dependency: Generator[Session, None, None],
    ) -> dict:
        db = next(router_dependency)
        ctx = resolve_user_context(request, db)
        with _map_errors():
            deactivate_user_device_impl(db, ctx.user_id, device_id)
            return {"ok": True, "device_id": device_id}
