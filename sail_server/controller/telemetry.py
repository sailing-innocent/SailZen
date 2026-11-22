# -*- coding: utf-8 -*-
# @file telemetry.py
# @brief Telemetry, AI Trace & System Profile Controller (REST)
# @author sailing-innocent
# @date 2026-11-23
# @version 1.0
# ---------------------------------
"""Telemetry & AI Trace REST 控制器（/api/v1/telemetry）。"""

from __future__ import annotations

import logging
import os
from typing import Any, Dict, Generator, List, Optional

from litestar import Controller, Request, get, post
from litestar.exceptions import NotAuthorizedException, NotFoundException
from sqlalchemy.orm import Session

from sail_server.application.dto.telemetry import (
    AITraceDetailResponse,
    AITraceIngestRequest,
    AITraceStatsResponse,
    AITraceSummaryResponse,
    ApiProfileResponse,
    ClientEventBatchRequest,
    ModulesProfileResponse,
    SailTickTriggerRequest,
    SystemRuntimeProfileResponse,
)
from sail_server.model.telemetry import (
    fetch_sailtick_live_impl,
    get_ai_trace_detail_impl,
    get_ai_trace_stats_impl,
    get_api_profile_impl,
    get_modules_profile_impl,
    get_system_runtime_profile_impl,
    ingest_ai_trace_impl,
    ingest_client_events_impl,
    list_ai_traces_impl,
    trigger_sailtick_slot_impl,
)

logger = logging.getLogger(__name__)


def _check_auth(request: Request) -> None:
    """可选 Bearer Token 鉴权（与 tick 控制器一致，未配置 SAILZEN_API_TOKEN 时放行）。"""
    expected = os.environ.get("SAILZEN_API_TOKEN", "")
    if not expected:
        return
    auth = request.headers.get("Authorization", "")
    if auth != f"Bearer {expected}":
        raise NotAuthorizedException(detail="invalid or missing bearer token")


class TelemetryController(Controller):
    """线上埋点、AI 全链路 Trace 与系统 Profile 控制器。"""

    path = "/"

    # ── AI Traces ──────────────────────────────────────────────────────

    @post("/ai-traces")
    async def ingest_ai_trace(
        self,
        data: AITraceIngestRequest,
        request: Request,
        router_dependency: Generator[Session, None, None],
    ) -> AITraceSummaryResponse:
        _check_auth(request)
        db = next(router_dependency)
        return ingest_ai_trace_impl(db, data)

    @get("/ai-traces")
    async def list_ai_traces(
        self,
        request: Request,
        router_dependency: Generator[Session, None, None],
        service: Optional[str] = None,
        slot: Optional[str] = None,
        status: Optional[str] = None,
        plan_source: Optional[str] = None,
        days: int = 7,
        limit: int = 50,
    ) -> List[AITraceSummaryResponse]:
        _check_auth(request)
        db = next(router_dependency)
        return list_ai_traces_impl(
            db,
            service=service,
            slot=slot,
            status=status,
            plan_source=plan_source,
            days=days,
            limit=limit,
        )

    @get("/ai-traces/stats")
    async def get_ai_trace_stats(
        self,
        request: Request,
        router_dependency: Generator[Session, None, None],
        service: str = "sailtick",
        days: int = 7,
    ) -> AITraceStatsResponse:
        _check_auth(request)
        db = next(router_dependency)
        return get_ai_trace_stats_impl(db, service=service, days=days)

    @get("/ai-traces/{trace_id:str}")
    async def get_ai_trace_detail(
        self,
        trace_id: str,
        request: Request,
        router_dependency: Generator[Session, None, None],
    ) -> AITraceDetailResponse:
        _check_auth(request)
        db = next(router_dependency)
        detail = get_ai_trace_detail_impl(db, trace_id)
        if detail is None:
            raise NotFoundException(detail=f"AI trace {trace_id} not found")
        return detail

    # ── Client Events ──────────────────────────────────────────────────

    @post("/events")
    async def ingest_client_events(
        self,
        data: ClientEventBatchRequest,
        request: Request,
        router_dependency: Generator[Session, None, None],
    ) -> Dict[str, Any]:
        _check_auth(request)
        db = next(router_dependency)
        accepted = ingest_client_events_impl(db, data)
        return {"accepted": accepted}

    # ── System & Module Profile ────────────────────────────────────────

    @get("/profile/api")
    async def get_api_profile(
        self,
        request: Request,
        router_dependency: Generator[Session, None, None],
        hours: int = 24,
        include_self: bool = False,
    ) -> ApiProfileResponse:
        _check_auth(request)
        db = next(router_dependency)
        return get_api_profile_impl(db, window_hours=hours, include_self=include_self)

    @get("/profile/modules")
    async def get_modules_profile(
        self,
        request: Request,
        router_dependency: Generator[Session, None, None],
        days: int = 7,
    ) -> ModulesProfileResponse:
        _check_auth(request)
        db = next(router_dependency)
        return get_modules_profile_impl(db, window_days=days)

    @get("/profile/runtime")
    async def get_runtime_profile(
        self,
        request: Request,
        router_dependency: Generator[Session, None, None],
    ) -> SystemRuntimeProfileResponse:
        _check_auth(request)
        db = next(router_dependency)
        return get_system_runtime_profile_impl(db)

    # ── SailTick Daemon Live Proxy ─────────────────────────────────────

    @get("/sailtick/live")
    async def get_sailtick_live(self, request: Request) -> Dict[str, Any]:
        _check_auth(request)
        return await fetch_sailtick_live_impl()

    @post("/sailtick/trigger")
    async def trigger_sailtick_slot(
        self,
        data: SailTickTriggerRequest,
        request: Request,
    ) -> Dict[str, Any]:
        _check_auth(request)
        return await trigger_sailtick_slot_impl(
            slot=data.slot,
            idempotency_suffix=data.idempotency_suffix,
            params=data.params,
        )
