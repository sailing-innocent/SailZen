# -*- coding: utf-8 -*-
# @file rhythm.py
# @brief Rhythm v2 Controller (极简项目/事务 + AI 可视化时间线 + 占用 + 轻量打卡)
# @author sailing-innocent
# @date 2026-11-24
# @version 2.0
# ---------------------------------

"""
节奏（Rhythm v2）模块控制器

精简后的核心 REST 契约（/api/v1/rhythm）:
- Dashboard:  GET /dashboard?date=
- Affair:     POST/GET /affair/, GET/PUT/DELETE /affair/{id}, POST /affair/{id}/state|confirm-hint|split
- Venture:    GET /venture/projects, GET /venture/{id}/progress, POST /venture/{id}/milestone, POST /venture/milestone/{mid}/done
- Timeline:   GET /timeline/day?date=, GET /timeline/range?start_date=&end_date=, GET /timeline/day-view?date=,
              POST /timeline/ai-sync, POST /timeline/block, DELETE /timeline/block/{id},
              POST /timeline/block/{id}/status, POST /timeline/block/{id}/move
- Occupancy:  POST/GET /occupancy/, DELETE /occupancy/{block_id}
- Checkin:    POST/GET /checkin/, GET /checkin/today, POST /checkin/health
"""

from __future__ import annotations

import logging
import os
from contextlib import contextmanager
from datetime import date as date_type
from datetime import datetime
from typing import Generator, List, Optional

from litestar import Controller, Request, delete, get, post, put
from litestar.exceptions import ClientException, NotAuthorizedException, NotFoundException
from litestar.params import Parameter
from sqlalchemy.orm import Session

from sail_server.application.dto.rhythm import (
    AITimelineSyncRequest,
    AITimelineSyncResponse,
    AffairCreateRequest,
    AffairListResponse,
    AffairResponse,
    AffairSplitRequest,
    AffairStateRequest,
    AffairUpdateRequest,
    BlockMoveRequest,
    BlockStatusRequest,
    CheckinListResponse,
    CheckinLogResponse,
    CheckinRequest,
    CheckinTodayResponse,
    ConfirmHintRequest,
    DayTimelineResponse,
    HealthCheckinRequest,
    HealthCheckinResponse,
    OccupancyCreateRequest,
    OccupancyListResponse,
    OccupancyResponse,
    RhythmDashboardResponse,
    RhythmDayViewResponse,
    TimeBlockCreateRequest,
    TimeBlockResponse,
    TimelineRangeResponse,
    VentureMilestoneRequest,
    VentureProgressResponse,
)
from sail_server.model.rhythm import (
    RhythmBadRequestError,
    RhythmNotFoundError,
    RhythmStateConflictError,
    add_milestone_impl,
    checkin_impl,
    confirm_hint_impl,
    create_affair_impl,
    create_block_impl,
    create_occupancy_impl,
    delete_affair_impl,
    delete_block_impl,
    delete_occupancy_impl,
    get_affair_impl,
    get_dashboard_impl,
    get_day_timeline_impl,
    get_rhythm_day_view_impl,
    health_checkin_impl,
    list_active_projects_progress_impl,
    list_affairs_impl,
    list_checkins_impl,
    list_occupancies_impl,
    list_timeline_range_impl,
    milestone_done_impl,
    move_block_impl,
    set_block_status_impl,
    split_affair_impl,
    sync_ai_timeline_impl,
    today_checkins_impl,
    transit_affair_state_impl,
    update_affair_impl,
    venture_progress_impl,
)

logger = logging.getLogger(__name__)


def _check_auth(request: Request) -> None:
    expected = os.environ.get("SAILZEN_API_TOKEN", "")
    if not expected:
        return
    auth = request.headers.get("Authorization", "")
    if auth != f"Bearer {expected}":
        raise NotAuthorizedException(detail="invalid or missing bearer token")


@contextmanager
def _map_errors():
    try:
        yield
    except RhythmNotFoundError as exc:
        raise NotFoundException(detail=str(exc)) from exc
    except RhythmStateConflictError as exc:
        raise ClientException(status_code=409, detail=str(exc)) from exc
    except (RhythmBadRequestError, ValueError) as exc:
        raise ClientException(status_code=400, detail=str(exc)) from exc


class DashboardController(Controller):
    path = "/dashboard"

    @get("/")
    async def dashboard(
        self,
        request: Request,
        router_dependency: Generator[Session, None, None],
        date: Optional[date_type] = None,
    ) -> RhythmDashboardResponse:
        """GET /api/v1/rhythm/dashboard?date=YYYY-MM-DD"""
        _check_auth(request)
        db = next(router_dependency)
        target = date or datetime.now().date()
        with _map_errors():
            return get_dashboard_impl(db, target)


class AffairController(Controller):
    path = "/affair"

    @post("/")
    async def create_affair(
        self,
        data: AffairCreateRequest,
        request: Request,
        router_dependency: Generator[Session, None, None],
    ) -> AffairResponse:
        _check_auth(request)
        db = next(router_dependency)
        with _map_errors():
            return create_affair_impl(db, data)

    @get("/")
    async def list_affairs(
        self,
        request: Request,
        router_dependency: Generator[Session, None, None],
        state_: Optional[List[str]] = Parameter(query="state", default=None),
        domain: Optional[List[str]] = Parameter(query="domain", default=None),
        kind: Optional[List[str]] = Parameter(query="kind", default=None),
        day_id: Optional[int] = None,
        parent_id: Optional[int] = None,
        urgency_ddl_before: Optional[datetime] = None,
        urgency_ddl_after: Optional[datetime] = None,
        skip: int = 0,
        limit: int = -1,
    ) -> AffairListResponse:
        _check_auth(request)
        db = next(router_dependency)
        affairs = list_affairs_impl(
            db,
            state_,
            domain,
            kind,
            day_id,
            parent_id,
            urgency_ddl_before,
            urgency_ddl_after,
            skip,
            limit,
        )
        return AffairListResponse(affairs=affairs, total=len(affairs))

    @get("/{affair_id:int}")
    async def get_affair(
        self,
        affair_id: int,
        request: Request,
        router_dependency: Generator[Session, None, None],
    ) -> AffairResponse:
        _check_auth(request)
        db = next(router_dependency)
        affair = get_affair_impl(db, affair_id)
        if affair is None:
            raise NotFoundException(detail=f"Affair {affair_id} not found")
        return affair

    @put("/{affair_id:int}")
    async def update_affair(
        self,
        affair_id: int,
        data: AffairUpdateRequest,
        request: Request,
        router_dependency: Generator[Session, None, None],
    ) -> AffairResponse:
        _check_auth(request)
        db = next(router_dependency)
        with _map_errors():
            affair = update_affair_impl(db, affair_id, data)
            if affair is None:
                raise NotFoundException(detail=f"Affair {affair_id} not found")
            return affair

    @delete("/{affair_id:int}", status_code=200)
    async def delete_affair(
        self,
        affair_id: int,
        request: Request,
        router_dependency: Generator[Session, None, None],
    ) -> dict:
        _check_auth(request)
        db = next(router_dependency)
        with _map_errors():
            affair = delete_affair_impl(db, affair_id)
            if affair is None:
                raise NotFoundException(detail=f"Affair {affair_id} not found")
            return {"id": affair_id, "status": "success"}

    @post("/{affair_id:int}/state")
    async def transit_state(
        self,
        affair_id: int,
        data: AffairStateRequest,
        request: Request,
        router_dependency: Generator[Session, None, None],
    ) -> AffairResponse:
        _check_auth(request)
        db = next(router_dependency)
        with _map_errors():
            return transit_affair_state_impl(db, affair_id, data)

    @post("/{affair_id:int}/confirm-hint")
    async def confirm_hint(
        self,
        affair_id: int,
        data: ConfirmHintRequest,
        request: Request,
        router_dependency: Generator[Session, None, None],
    ) -> AffairResponse:
        _check_auth(request)
        db = next(router_dependency)
        with _map_errors():
            return confirm_hint_impl(db, affair_id, data)

    @post("/{affair_id:int}/split")
    async def split_affair(
        self,
        affair_id: int,
        data: AffairSplitRequest,
        request: Request,
        router_dependency: Generator[Session, None, None],
    ) -> AffairListResponse:
        _check_auth(request)
        db = next(router_dependency)
        with _map_errors():
            return split_affair_impl(db, affair_id, data)


class VentureController(Controller):
    path = "/venture"

    @get("/projects")
    async def list_projects(
        self,
        request: Request,
        router_dependency: Generator[Session, None, None],
    ) -> List[VentureProgressResponse]:
        """获取所有活跃重要项目的倒排进度与里程碑。"""
        _check_auth(request)
        db = next(router_dependency)
        with _map_errors():
            return list_active_projects_progress_impl(db)

    @get("/{venture_id:int}/progress")
    async def venture_progress(
        self,
        venture_id: int,
        request: Request,
        router_dependency: Generator[Session, None, None],
    ) -> VentureProgressResponse:
        _check_auth(request)
        db = next(router_dependency)
        with _map_errors():
            return venture_progress_impl(db, venture_id)

    @post("/{venture_id:int}/milestone")
    async def add_milestone(
        self,
        venture_id: int,
        data: VentureMilestoneRequest,
        request: Request,
        router_dependency: Generator[Session, None, None],
    ) -> AffairResponse:
        _check_auth(request)
        db = next(router_dependency)
        with _map_errors():
            return add_milestone_impl(db, venture_id, data)

    @post("/milestone/{milestone_id:int}/done")
    async def milestone_done(
        self,
        milestone_id: int,
        request: Request,
        router_dependency: Generator[Session, None, None],
    ) -> AffairResponse:
        _check_auth(request)
        db = next(router_dependency)
        with _map_errors():
            return milestone_done_impl(db, milestone_id)


class TimelineController(Controller):
    path = "/timeline"

    @get("/day")
    async def day_timeline(
        self,
        request: Request,
        router_dependency: Generator[Session, None, None],
        date: Optional[date_type] = None,
    ) -> DayTimelineResponse:
        _check_auth(request)
        db = next(router_dependency)
        target = date or datetime.now().date()
        with _map_errors():
            return get_day_timeline_impl(db, target)

    @get("/range")
    async def timeline_range(
        self,
        request: Request,
        router_dependency: Generator[Session, None, None],
        start_date: date_type,
        end_date: date_type,
    ) -> TimelineRangeResponse:
        """批量拉取多日时间线执行情况（供 SailTick 夜间深度分析）。"""
        _check_auth(request)
        db = next(router_dependency)
        with _map_errors():
            return list_timeline_range_impl(db, start_date, end_date)

    @get("/day-view")
    async def day_view(
        self,
        request: Request,
        router_dependency: Generator[Session, None, None],
        date: Optional[date_type] = None,
    ) -> RhythmDayViewResponse:
        _check_auth(request)
        db = next(router_dependency)
        target = date or datetime.now().date()
        with _map_errors():
            return get_rhythm_day_view_impl(db, target)

    @post("/ai-sync")
    async def ai_sync_timeline(
        self,
        data: AITimelineSyncRequest,
        request: Request,
        router_dependency: Generator[Session, None, None],
    ) -> AITimelineSyncResponse:
        """SailTick AI 自主编排某日时间线并直接落库（保留已完成与刚性钉）。"""
        _check_auth(request)
        db = next(router_dependency)
        with _map_errors():
            return sync_ai_timeline_impl(db, data)

    @post("/block")
    async def create_block(
        self,
        data: TimeBlockCreateRequest,
        request: Request,
        router_dependency: Generator[Session, None, None],
    ) -> TimeBlockResponse:
        _check_auth(request)
        db = next(router_dependency)
        with _map_errors():
            return create_block_impl(db, data)

    @delete("/block/{block_id:int}", status_code=200)
    async def delete_block(
        self,
        block_id: int,
        request: Request,
        router_dependency: Generator[Session, None, None],
    ) -> dict:
        _check_auth(request)
        db = next(router_dependency)
        with _map_errors():
            delete_block_impl(db, block_id)
        return {"id": block_id, "status": "success"}

    @post("/block/{block_id:int}/status")
    async def block_status(
        self,
        block_id: int,
        data: BlockStatusRequest,
        request: Request,
        router_dependency: Generator[Session, None, None],
    ) -> TimeBlockResponse:
        _check_auth(request)
        db = next(router_dependency)
        with _map_errors():
            return set_block_status_impl(db, block_id, data)

    @post("/block/{block_id:int}/move")
    async def block_move(
        self,
        block_id: int,
        data: BlockMoveRequest,
        request: Request,
        router_dependency: Generator[Session, None, None],
    ) -> TimeBlockResponse:
        _check_auth(request)
        db = next(router_dependency)
        with _map_errors():
            return move_block_impl(db, block_id, data)


class OccupancyController(Controller):
    path = "/occupancy"

    @post("/")
    async def create_occupancy(
        self,
        data: OccupancyCreateRequest,
        request: Request,
        router_dependency: Generator[Session, None, None],
    ) -> OccupancyResponse:
        _check_auth(request)
        db = next(router_dependency)
        with _map_errors():
            return create_occupancy_impl(db, data)

    @get("/")
    async def list_occupancies(
        self,
        request: Request,
        router_dependency: Generator[Session, None, None],
        date: Optional[date_type] = None,
    ) -> OccupancyListResponse:
        _check_auth(request)
        db = next(router_dependency)
        target = date or datetime.now().date()
        with _map_errors():
            return list_occupancies_impl(db, target)

    @delete("/{block_id:int}", status_code=200)
    async def delete_occupancy(
        self,
        block_id: int,
        request: Request,
        router_dependency: Generator[Session, None, None],
    ) -> dict:
        _check_auth(request)
        db = next(router_dependency)
        with _map_errors():
            delete_occupancy_impl(db, block_id)
        return {"id": block_id, "status": "success"}


class CheckinController(Controller):
    path = "/checkin"

    @post("/")
    async def checkin(
        self,
        data: CheckinRequest,
        request: Request,
        router_dependency: Generator[Session, None, None],
    ) -> CheckinLogResponse:
        _check_auth(request)
        db = next(router_dependency)
        with _map_errors():
            return checkin_impl(db, data)

    @get("/")
    async def list_checkins(
        self,
        request: Request,
        router_dependency: Generator[Session, None, None],
        affair_id: Optional[int] = None,
        start_date: Optional[date_type] = None,
        end_date: Optional[date_type] = None,
        cycle_key: Optional[str] = None,
        skip: int = 0,
        limit: int = -1,
    ) -> CheckinListResponse:
        _check_auth(request)
        db = next(router_dependency)
        logs = list_checkins_impl(db, affair_id, start_date, end_date, cycle_key, skip, limit)
        return CheckinListResponse(logs=logs, total=len(logs))

    @get("/today")
    async def checkin_today(
        self,
        request: Request,
        router_dependency: Generator[Session, None, None],
        date: Optional[date_type] = None,
    ) -> CheckinTodayResponse:
        _check_auth(request)
        db = next(router_dependency)
        return today_checkins_impl(db, date)

    @post("/health")
    async def health_checkin(
        self,
        data: HealthCheckinRequest,
        request: Request,
        router_dependency: Generator[Session, None, None],
    ) -> HealthCheckinResponse:
        _check_auth(request)
        db = next(router_dependency)
        with _map_errors():
            return health_checkin_impl(db, data)
