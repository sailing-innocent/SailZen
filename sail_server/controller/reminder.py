# -*- coding: utf-8 -*-
# @file reminder.py
# @brief Reminder Controller (REST + 反馈中枢)
# @author sailing-innocent
# @date 2026-08-03
# @version 1.0
# ---------------------------------

"""
提醒模块控制器（Android App M1）

REST 契约见 doc/design/android_app/ACCEPTANCE_M1.md：
- POST /device/register   设备注册/心跳
- GET  /pending           补偿拉取
- GET  /history           历史
- GET  /summary/today     当日小结
- POST /                  创建提醒
- DELETE /{id}            撤销
- POST /{id}/feedback     反馈中枢（dismiss|snooze|open|resolve）
- POST /ack               投递确认
- GET  /{id}/events       事件日志（验收核对）
- GET/POST/PUT /rules     规则 CRUD

鉴权：仅当环境变量 SAILZEN_API_TOKEN 非空时校验
``Authorization: Bearer <token>``；未配置则全部放行（MVP 局域网自用）。
"""

from __future__ import annotations

import logging
import os
from contextlib import contextmanager
from datetime import datetime
from typing import Generator, List, Optional

from litestar import Controller, Request, delete, get, post, put
from litestar.exceptions import (
    ClientException,
    NotAuthorizedException,
    NotFoundException,
)
from sqlalchemy.orm import Session

from sail_server.application.dto.reminder import (
    AckRequest,
    DeviceRegisterRequest,
    DeviceResponse,
    FeedbackRequest,
    OkResponse,
    ReminderCreateRequest,
    ReminderEventResponse,
    ReminderResponse,
    ReminderRuleCreateRequest,
    ReminderRuleResponse,
    ReminderRuleUpdateRequest,
    ReminderSourceConfigCreateRequest,
    ReminderSourceConfigResponse,
    ReminderSourceConfigUpdateRequest,
    ReminderSummaryResponse,
    _to_naive_local,
)
from sail_server.model.reminder import (
    ReminderBadRequestError,
    ReminderNotFoundError,
    ReminderStateConflictError,
    ack_reminder_impl,
    cancel_reminder_impl,
    create_reminder_impl,
    create_rule_impl,
    feedback_reminder_impl,
    get_summary_today_impl,
    list_events_impl,
    list_history_impl,
    list_pending_impl,
    list_rules_impl,
    list_source_configs_impl,
    register_device_impl,
    update_rule_impl,
    update_source_config_impl,
    upsert_source_config_impl,
)

logger = logging.getLogger(__name__)


# ============================================================================
# Helpers
# ============================================================================


def _check_auth(request: Request) -> None:
    """可选 Bearer Token 鉴权：env SAILZEN_API_TOKEN 未设置则放行"""
    expected = os.environ.get("SAILZEN_API_TOKEN", "")
    if not expected:
        return
    auth = request.headers.get("Authorization", "")
    if auth != f"Bearer {expected}":
        raise NotAuthorizedException(detail="invalid or missing bearer token")


@contextmanager
def _map_errors():
    """model 层异常 → HTTP 状态码（404/409/400）"""
    try:
        yield
    except ReminderNotFoundError as e:
        raise NotFoundException(detail=str(e)) from e
    except ReminderStateConflictError as e:
        raise ClientException(status_code=409, detail=str(e)) from e
    except ReminderBadRequestError as e:
        raise ClientException(status_code=400, detail=str(e)) from e


# ============================================================================
# Reminder Controller
# ============================================================================


class ReminderController(Controller):
    path = "/"

    # ------------------------------------------------------------------
    # 设备与通道
    # ------------------------------------------------------------------

    @post("/device/register")
    async def register_device(
        self,
        data: DeviceRegisterRequest,
        request: Request,
        router_dependency: Generator[Session, None, None],
    ) -> DeviceResponse:
        """注册/心跳设备（按 device_id upsert）"""
        _check_auth(request)
        db = next(router_dependency)
        device = register_device_impl(db, data)
        logger.info(f"[reminder] device registered: {device.device_id}")
        return device

    @post("/ack")
    async def ack(
        self,
        data: AckRequest,
        request: Request,
        router_dependency: Generator[Session, None, None],
    ) -> OkResponse:
        """投递确认：写 ack 事件"""
        _check_auth(request)
        db = next(router_dependency)
        with _map_errors():
            ack_reminder_impl(db, data.reminder_id, data.device_id, data.client_event_ts)
        return OkResponse(ok=True)

    # ------------------------------------------------------------------
    # 提醒查询
    # ------------------------------------------------------------------

    @get("/pending")
    async def get_pending(
        self,
        request: Request,
        router_dependency: Generator[Session, None, None],
        since: Optional[str] = None,
    ) -> List[ReminderResponse]:
        """补偿拉取：活跃状态提醒（since 为 ISO-8601 增量同步起点）"""
        _check_auth(request)
        db = next(router_dependency)
        with _map_errors():
            since_dt = _to_naive_local(since) if since else None
            return list_pending_impl(db, since_dt)

    @get("/history")
    async def get_history(
        self,
        request: Request,
        router_dependency: Generator[Session, None, None],
        date: str = "",
        type: Optional[str] = None,
    ) -> List[ReminderResponse]:
        """历史：按 trigger_time 当日过滤，可选类型筛选"""
        _check_auth(request)
        db = next(router_dependency)
        if not date:
            date = datetime.now().strftime("%Y-%m-%d")
        with _map_errors():
            return list_history_impl(db, date, type)

    @get("/summary/today")
    async def get_summary_today(
        self,
        request: Request,
        router_dependency: Generator[Session, None, None],
    ) -> ReminderSummaryResponse:
        """当日小结（Inbox 小结卡片）"""
        _check_auth(request)
        db = next(router_dependency)
        return get_summary_today_impl(db)

    @get("/{reminder_id:int}/events")
    async def get_events(
        self,
        reminder_id: int,
        request: Request,
        router_dependency: Generator[Session, None, None],
    ) -> List[ReminderEventResponse]:
        """事件日志（验收核对用）"""
        _check_auth(request)
        db = next(router_dependency)
        with _map_errors():
            return list_events_impl(db, reminder_id)

    # ------------------------------------------------------------------
    # 提醒本体
    # ------------------------------------------------------------------

    @post("/")
    async def create_reminder(
        self,
        data: ReminderCreateRequest,
        request: Request,
        router_dependency: Generator[Session, None, None],
    ) -> ReminderResponse:
        """创建提醒（Agent / 业务模块 / 手工测试）"""
        _check_auth(request)
        db = next(router_dependency)
        with _map_errors():
            reminder = create_reminder_impl(db, data)
        logger.info(f"[reminder] created: id={reminder.id} type={reminder.type}")
        return reminder

    @delete("/{reminder_id:int}", status_code=200)
    async def cancel_reminder(
        self,
        reminder_id: int,
        request: Request,
        router_dependency: Generator[Session, None, None],
    ) -> ReminderResponse:
        """撤销提醒：非终态 → CANCELED"""
        _check_auth(request)
        db = next(router_dependency)
        with _map_errors():
            return cancel_reminder_impl(db, reminder_id)

    @post("/{reminder_id:int}/feedback")
    async def feedback(
        self,
        reminder_id: int,
        data: FeedbackRequest,
        request: Request,
        router_dependency: Generator[Session, None, None],
    ) -> ReminderResponse:
        """反馈中枢：dismiss / snooze / open / resolve 驱动状态机"""
        _check_auth(request)
        db = next(router_dependency)
        with _map_errors():
            reminder = feedback_reminder_impl(db, reminder_id, data)
        logger.info(
            f"[reminder] feedback: id={reminder_id} action={data.action} "
            f"-> state={reminder.state}"
        )
        return reminder

    # ------------------------------------------------------------------
    # 规则 CRUD
    # ------------------------------------------------------------------

    @get("/rules")
    async def get_rules(
        self,
        request: Request,
        router_dependency: Generator[Session, None, None],
    ) -> List[ReminderRuleResponse]:
        _check_auth(request)
        db = next(router_dependency)
        return list_rules_impl(db)

    @post("/rules")
    async def create_rule(
        self,
        data: ReminderRuleCreateRequest,
        request: Request,
        router_dependency: Generator[Session, None, None],
    ) -> ReminderRuleResponse:
        _check_auth(request)
        db = next(router_dependency)
        with _map_errors():
            return create_rule_impl(db, data)

    @put("/rules/{rule_id:int}")
    async def update_rule(
        self,
        rule_id: int,
        data: ReminderRuleUpdateRequest,
        request: Request,
        router_dependency: Generator[Session, None, None],
    ) -> ReminderRuleResponse:
        _check_auth(request)
        db = next(router_dependency)
        with _map_errors():
            return update_rule_impl(db, rule_id, data)

    # ------------------------------------------------------------------
    # 提醒来源配置
    # ------------------------------------------------------------------

    @get("/sources")
    async def get_sources(
        self,
        request: Request,
        router_dependency: Generator[Session, None, None],
    ) -> List[ReminderSourceConfigResponse]:
        """列出所有提醒来源配置"""
        _check_auth(request)
        db = next(router_dependency)
        return list_source_configs_impl(db)

    @get("/source-configs")
    async def get_source_configs(
        self,
        request: Request,
        router_dependency: Generator[Session, None, None],
    ) -> List[ReminderSourceConfigResponse]:
        """列出所有提醒来源配置（别名）"""
        _check_auth(request)
        db = next(router_dependency)
        return list_source_configs_impl(db)

    @post("/source-configs")
    async def create_or_update_source_config(
        self,
        data: ReminderSourceConfigCreateRequest,
        request: Request,
        router_dependency: Generator[Session, None, None],
    ) -> ReminderSourceConfigResponse:
        """创建或更新提醒来源配置（按 source upsert）"""
        _check_auth(request)
        db = next(router_dependency)
        with _map_errors():
            return upsert_source_config_impl(db, data)

    @put("/source-configs/{id:int}")
    async def update_source_config(
        self,
        id: int,
        data: ReminderSourceConfigUpdateRequest,
        request: Request,
        router_dependency: Generator[Session, None, None],
    ) -> ReminderSourceConfigResponse:
        """按 id 更新提醒来源配置"""
        _check_auth(request)
        db = next(router_dependency)
        with _map_errors():
            return update_source_config_impl(db, id, data)
