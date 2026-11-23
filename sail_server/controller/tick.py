# -*- coding: utf-8 -*-
# @file tick.py
# @brief SailTick Ticket Controller (REST)
# @author sailing-innocent
# @date 2026-10-27
# @version 1.0
# ---------------------------------
"""SailTick 票据控制器。

REST 契约（/api/v1/tick）:
- GET  /tickets               列表（status/channel 过滤）
- POST /tickets               创建（SailTick agent / 手工）
- GET  /tickets/{id}          详情
- POST /tickets/{id}/reply    用户回复
- POST /tickets/{id}/resolve  关闭
- POST /tickets/{id}/snooze   暂缓
- GET  /replies?since=        增量拉取已回复/关闭票据（agent SCAN 用）
- POST /expire-overdue        超期票据置 expired（幂等）

鉴权：复用 SAILZEN_API_TOKEN 可选 Bearer 模式（未配置则放行）。
"""

from __future__ import annotations

import logging
import os
from contextlib import contextmanager
from datetime import datetime
from typing import Generator, List, Optional

from litestar import Controller, Request, get, post
from litestar.datastructures import UploadFile
from litestar.exceptions import ClientException, NotAuthorizedException, NotFoundException
from litestar.response import File
from sqlalchemy.orm import Session

from sail_server.application.dto.tick import (
    DailyReportResponse,
    DailyReportUpsertRequest,
    HealthCoachSummaryResponse,
    ImageIntakeCommitRequest,
    ImageIntakeCommitResponse,
    ImageIntakeDraftResponse,
    TickMessageCreateRequest,
    TickMessageIngestRequest,
    TickMessageResponse,
    TicketCreateRequest,
    TicketReplyRequest,
    TicketResolveRequest,
    TicketResponse,
    TicketSnoozeRequest,
)
from sail_server.model.tick import (
    TicketBadRequestError,
    TicketNotFoundError,
    TicketStateConflictError,
    create_message_impl,
    create_ticket_impl,
    expire_overdue_impl,
    get_daily_report_by_date_impl,
    get_health_coach_summary_impl,
    get_latest_daily_report_impl,
    get_ticket_impl,
    ingest_messages_impl,
    list_daily_reports_impl,
    list_messages_impl,
    list_replies_since_impl,
    list_tickets_impl,
    reply_ticket_impl,
    resolve_ticket_impl,
    snooze_ticket_impl,
    upsert_daily_report_impl,
)
from sail_server.model.tick_intake import (
    analyze_image_intake_impl,
    commit_image_intake_impl,
    discard_image_intake_impl,
    get_image_intake_draft_impl,
    list_image_intake_drafts_impl,
    resolve_tick_media_path,
)

logger = logging.getLogger(__name__)


def _check_auth(request: Request) -> None:
    """可选 Bearer Token 鉴权：env SAILZEN_API_TOKEN 未设置则放行。"""
    expected = os.environ.get("SAILZEN_API_TOKEN", "")
    if not expected:
        return
    auth = request.headers.get("Authorization", "")
    if auth != f"Bearer {expected}":
        raise NotAuthorizedException(detail="invalid or missing bearer token")


@contextmanager
def _map_errors():
    """model 层异常 → HTTP 状态码（404/409/400）。"""
    try:
        yield
    except TicketNotFoundError as e:
        raise NotFoundException(detail=str(e)) from e
    except TicketStateConflictError as e:
        raise ClientException(status_code=409, detail=str(e)) from e
    except TicketBadRequestError as e:
        raise ClientException(status_code=400, detail=str(e)) from e


class TicketController(Controller):
    """SailTick 票据 REST 控制器。"""

    path = "/"

    @get("/tickets")
    async def list_tickets(
        self,
        request: Request,
        router_dependency: Generator[Session, None, None],
        status: Optional[str] = None,
        channel: Optional[str] = None,
        type: Optional[str] = None,
        limit: int = 100,
    ) -> List[TicketResponse]:
        """列出票据，默认按期待回复时间升序（最急最前）。"""
        _check_auth(request)
        db = next(router_dependency)
        with _map_errors():
            return list_tickets_impl(db, status=status, channel=channel, type_=type, limit=limit)

    @post("/tickets")
    async def create_ticket(
        self,
        data: TicketCreateRequest,
        request: Request,
        router_dependency: Generator[Session, None, None],
    ) -> TicketResponse:
        _check_auth(request)
        db = next(router_dependency)
        with _map_errors():
            return create_ticket_impl(db, data)

    @get("/tickets/{ticket_id:int}")
    async def get_ticket(
        self,
        ticket_id: int,
        request: Request,
        router_dependency: Generator[Session, None, None],
    ) -> TicketResponse:
        _check_auth(request)
        db = next(router_dependency)
        with _map_errors():
            return get_ticket_impl(db, ticket_id)

    @post("/tickets/{ticket_id:int}/reply")
    async def reply_ticket(
        self,
        ticket_id: int,
        data: TicketReplyRequest,
        request: Request,
        router_dependency: Generator[Session, None, None],
    ) -> TicketResponse:
        _check_auth(request)
        db = next(router_dependency)
        with _map_errors():
            return reply_ticket_impl(db, ticket_id, data.reply)

    @post("/tickets/{ticket_id:int}/resolve")
    async def resolve_ticket(
        self,
        ticket_id: int,
        data: TicketResolveRequest,
        request: Request,
        router_dependency: Generator[Session, None, None],
    ) -> TicketResponse:
        _check_auth(request)
        db = next(router_dependency)
        with _map_errors():
            return resolve_ticket_impl(db, ticket_id, data.resolution)

    @post("/tickets/{ticket_id:int}/snooze")
    async def snooze_ticket(
        self,
        ticket_id: int,
        data: TicketSnoozeRequest,
        request: Request,
        router_dependency: Generator[Session, None, None],
    ) -> TicketResponse:
        _check_auth(request)
        db = next(router_dependency)
        with _map_errors():
            return snooze_ticket_impl(db, ticket_id, data.hours)

    @get("/replies")
    async def list_replies(
        self,
        request: Request,
        router_dependency: Generator[Session, None, None],
        since: Optional[str] = None,
    ) -> List[TicketResponse]:
        """增量拉取已回复/关闭票据（agent SCAN 同步用）。since 为 ISO-8601。"""
        _check_auth(request)
        db = next(router_dependency)
        since_dt: Optional[datetime] = None
        if since:
            since_dt = datetime.fromisoformat(since.replace("Z", "+00:00"))
            if since_dt.tzinfo is not None:
                since_dt = since_dt.astimezone().replace(tzinfo=None)
        with _map_errors():
            return list_replies_since_impl(db, since=since_dt)

    @post("/expire-overdue")
    async def expire_overdue(
        self, request: Request, router_dependency: Generator[Session, None, None]
    ) -> dict:
        """超期 pending 票据置 expired（幂等）。"""
        _check_auth(request)
        db = next(router_dependency)
        with _map_errors():
            return {"expired": expire_overdue_impl(db)}

    # ── 用户主动消息 / 静默餐饮上报 ─────────────────────────────────────────

    @post("/messages")
    async def create_message(
        self,
        data: TickMessageCreateRequest,
        request: Request,
        router_dependency: Generator[Session, None, None],
    ) -> TickMessageResponse:
        """用户主动上报餐饮/日常信息（非阻塞，SailTick 将在后续 Tick 与睡前日报整合）。"""
        _check_auth(request)
        db = next(router_dependency)
        with _map_errors():
            return create_message_impl(db, data)

    @get("/messages")
    async def list_messages(
        self,
        request: Request,
        router_dependency: Generator[Session, None, None],
        status: Optional[str] = None,
        category: Optional[str] = None,
        direction: Optional[str] = None,
        since: Optional[str] = None,
        limit: int = 100,
    ) -> List[TickMessageResponse]:
        """查询用户/教练异步消息列表（agent SCAN 拉取 status=unread）。"""
        _check_auth(request)
        db = next(router_dependency)
        since_dt: Optional[datetime] = None
        if since:
            since_dt = datetime.fromisoformat(since.replace("Z", "+00:00"))
            if since_dt.tzinfo is not None:
                since_dt = since_dt.astimezone().replace(tzinfo=None)
        with _map_errors():
            return list_messages_impl(
                db,
                status=status,
                category=category,
                direction=direction,
                since=since_dt,
                limit=limit,
            )

    @post("/messages/ingest")
    async def ingest_messages(
        self,
        data: TickMessageIngestRequest,
        request: Request,
        router_dependency: Generator[Session, None, None],
    ) -> dict:
        """SailTick 批量标记用户消息已吸收（幂等）。"""
        _check_auth(request)
        db = next(router_dependency)
        with _map_errors():
            count = ingest_messages_impl(db, data.message_ids, data.tick_id)
            return {"ingested": count}

    # ── 每日睡前体重与健康日报 ──────────────────────────────────────────────

    @post("/reports")
    async def upsert_daily_report(
        self,
        data: DailyReportUpsertRequest,
        request: Request,
        router_dependency: Generator[Session, None, None],
    ) -> DailyReportResponse:
        """SailTick 幂等写入/更新每日睡前体重与健康日报，并按需推送到手机。"""
        _check_auth(request)
        db = next(router_dependency)
        with _map_errors():
            return upsert_daily_report_impl(db, data)

    @get("/reports")
    async def list_daily_reports(
        self,
        request: Request,
        router_dependency: Generator[Session, None, None],
        limit: int = 14,
    ) -> List[DailyReportResponse]:
        """获取最近 N 天的睡前健康日报列表。"""
        _check_auth(request)
        db = next(router_dependency)
        with _map_errors():
            return list_daily_reports_impl(db, limit=limit)

    @get("/reports/latest")
    async def get_latest_daily_report(
        self,
        request: Request,
        router_dependency: Generator[Session, None, None],
    ) -> Optional[DailyReportResponse]:
        """获取最新一份睡前健康日报。"""
        _check_auth(request)
        db = next(router_dependency)
        with _map_errors():
            return get_latest_daily_report_impl(db)

    @get("/reports/{report_date:str}")
    async def get_daily_report(
        self,
        report_date: str,
        request: Request,
        router_dependency: Generator[Session, None, None],
    ) -> Optional[DailyReportResponse]:
        """按日期 YYYY-MM-DD 获取睡前健康日报。"""
        _check_auth(request)
        db = next(router_dependency)
        with _map_errors():
            return get_daily_report_by_date_impl(db, report_date)

    # ── 健康页 AI 教练聚合视图 ──────────────────────────────────────────────

    @get("/health-summary")
    async def get_health_coach_summary(
        self,
        request: Request,
        router_dependency: Generator[Session, None, None],
    ) -> HealthCoachSummaryResponse:
        """聚合健康页展示所需的 AI 动态计划、最新日报、待回复提问与今日主动记录。"""
        _check_auth(request)
        db = next(router_dependency)
        with _map_errors():
            return get_health_coach_summary_impl(db)

    # ── 通用图片识图与二段式确认落库 ──────────────────────────────────────────

    @post("/intake/analyze")
    async def analyze_image_intake(
        self,
        request: Request,
        router_dependency: Generator[Session, None, None],
    ) -> ImageIntakeDraftResponse:
        """上传图片 → DeepSeek Vision（按需叠加 OCR）→ 返回可编辑结构化草稿。

        接受 multipart/form-data：
        - file: 图片文件（必需）
        - note: 可选用户备注
        - source_channel: web | android | android_share
        - ticket_id: 可选关联待回票据 ID
        - use_ocr_assist: auto | true | false
        """
        _check_auth(request)
        db = next(router_dependency)
        form = await request.form()
        upload = form.get("file")
        if not isinstance(upload, UploadFile):
            raise ClientException(status_code=400, detail="请通过 multipart 字段 file 上传图片")

        file_bytes = await upload.read()
        filename = upload.filename or "upload.jpg"
        note = str(form.get("note") or "")
        source_channel = str(form.get("source_channel") or "web")
        use_ocr_assist = str(form.get("use_ocr_assist") or "auto")
        raw_ticket_id = form.get("ticket_id")
        ticket_id: Optional[int] = None
        if raw_ticket_id not in (None, ""):
            try:
                ticket_id = int(str(raw_ticket_id).strip())
            except ValueError as exc:
                raise ClientException(status_code=400, detail="invalid ticket_id") from exc

        with _map_errors():
            return await analyze_image_intake_impl(
                db=db,
                file_bytes=file_bytes,
                filename=filename,
                note=note,
                source_channel=source_channel,
                ticket_id=ticket_id,
                use_ocr_assist=use_ocr_assist,
            )

    @get("/intake/drafts")
    async def list_image_intake_drafts(
        self,
        request: Request,
        router_dependency: Generator[Session, None, None],
        status: Optional[str] = None,
        limit: int = 20,
    ) -> List[ImageIntakeDraftResponse]:
        """列出最近的识图草稿（可按 status=pending_confirm 过滤）。"""
        _check_auth(request)
        db = next(router_dependency)
        with _map_errors():
            return list_image_intake_drafts_impl(db, status=status, limit=limit)

    @get("/intake/{draft_id:int}")
    async def get_image_intake_draft(
        self,
        draft_id: int,
        request: Request,
        router_dependency: Generator[Session, None, None],
    ) -> ImageIntakeDraftResponse:
        """获取单个识图草稿详情。"""
        _check_auth(request)
        db = next(router_dependency)
        with _map_errors():
            return get_image_intake_draft_impl(db, draft_id)

    @post("/intake/{draft_id:int}/commit")
    async def commit_image_intake(
        self,
        draft_id: int,
        data: ImageIntakeCommitRequest,
        request: Request,
        router_dependency: Generator[Session, None, None],
    ) -> ImageIntakeCommitResponse:
        """人工确认微调后，将识图草稿正式写入对应健康主表与教练消息。"""
        _check_auth(request)
        db = next(router_dependency)
        with _map_errors():
            return commit_image_intake_impl(db, draft_id, data)

    @post("/intake/{draft_id:int}/discard")
    async def discard_image_intake(
        self,
        draft_id: int,
        request: Request,
        router_dependency: Generator[Session, None, None],
    ) -> ImageIntakeDraftResponse:
        """丢弃一条待确认的识图草稿。"""
        _check_auth(request)
        db = next(router_dependency)
        with _map_errors():
            return discard_image_intake_impl(db, draft_id)

    @get("/media/{year_month:str}/{filename:str}")
    async def get_tick_media(
        self,
        year_month: str,
        filename: str,
        request: Request,
    ) -> File:
        """安全返回已留存的识图媒体原图（支持浏览器 img 标签与 Android 预览）。"""
        # 注意：浏览器 <img> 无法直接带 Authorization header，支持 ?token= 或 Bearer
        expected = os.environ.get("SAILZEN_API_TOKEN", "")
        if expected:
            auth = request.headers.get("Authorization", "")
            qtoken = request.query_params.get("token", "")
            if auth != f"Bearer {expected}" and qtoken != expected:
                raise NotAuthorizedException(detail="invalid or missing token")
        with _map_errors():
            path = resolve_tick_media_path(year_month, filename)
        return File(path=str(path), media_type="image/jpeg")
