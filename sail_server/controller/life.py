# -*- coding: utf-8 -*-
# @file life.py
# @brief Life Time Management Controller
# @author sailing-innocent
# @date 2026-03-01
# @version 1.0
# ---------------------------------

"""
生活时间管理控制器

提供 Day 与 TimeSpan 的 REST API。
"""

from datetime import date
from typing import Generator, Optional
import logging

from litestar import Controller, delete, get, post, put, Request
from litestar.exceptions import HTTPException
from litestar.params import Parameter
from sqlalchemy.orm import Session

from sail_server.application.dto.life import (
    TimeSpanClass,
    DayCreateRequest,
    DayUpdateRequest,
    DayResponse,
    DayListResponse,
    TimeSpanCreateRequest,
    TimeSpanUpdateRequest,
    TimeSpanResponse,
    TimeSpanListResponse,
)
from sail_server.model.life import (
    create_day_impl,
    get_day_impl,
    get_day_by_date_impl,
    get_days_impl,
    update_day_impl,
    delete_day_impl,
    create_timespan_impl,
    get_timespan_impl,
    get_timespan_by_name_impl,
    get_timespans_impl,
    get_timespan_children_impl,
    get_timespans_by_day_impl,
    update_timespan_impl,
    delete_timespan_impl,
    init_time_system_impl,
)

logger = logging.getLogger(__name__)


# ============================================================================
# Day Controller
# ============================================================================


class DayController(Controller):
    path = "/day"

    @get("/")
    async def get_day_list(
        self,
        router_dependency: Generator[Session, None, None],
        request: Request,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        skip: int = 0,
        limit: int = -1,
    ) -> DayListResponse:
        """获取自然日列表"""
        try:
            db = next(router_dependency)
            days = get_days_impl(db, start_date, end_date, skip, limit)
            total = len(days)
            if limit > 0 and total == limit:
                # 粗略统计总数（分页场景下）
                total = len(get_days_impl(db, start_date, end_date, 0, -1))
            return DayListResponse(days=days, total=total)
        except Exception as e:
            logger.error(f"Error getting day list: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    @get("/{day_id:int}")
    async def get_day(
        self,
        day_id: int,
        router_dependency: Generator[Session, None, None],
        request: Request,
    ) -> DayResponse:
        """通过 ID 获取自然日"""
        try:
            db = next(router_dependency)
            day = get_day_impl(db, day_id)
            if day is None:
                raise HTTPException(status_code=404, detail="Day not found")
            return day
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error getting day {day_id}: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    @get("/by-date")
    async def get_day_by_date(
        self,
        router_dependency: Generator[Session, None, None],
        request: Request,
        date: date,
    ) -> DayResponse:
        """通过日期获取自然日"""
        try:
            db = next(router_dependency)
            day = get_day_by_date_impl(db, date)
            if day is None:
                raise HTTPException(status_code=404, detail="Day not found")
            return day
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error getting day by date {date}: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    @post("/")
    async def create_day(
        self,
        data: DayCreateRequest,
        router_dependency: Generator[Session, None, None],
        request: Request,
    ) -> DayResponse:
        """创建自然日"""
        try:
            db = next(router_dependency)
            day = create_day_impl(db, data)
            logger.info(f"Created day via API: {day.date} (id={day.id})")
            return day
        except ValueError as e:
            logger.error(f"Error creating day: {e}")
            raise HTTPException(status_code=400, detail=str(e))
        except Exception as e:
            logger.error(f"Error creating day: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    @put("/{day_id:int}")
    async def update_day(
        self,
        day_id: int,
        data: DayUpdateRequest,
        router_dependency: Generator[Session, None, None],
        request: Request,
    ) -> DayResponse:
        """更新自然日"""
        try:
            db = next(router_dependency)
            day = update_day_impl(db, day_id, data)
            if day is None:
                raise HTTPException(status_code=404, detail="Day not found")
            logger.info(f"Updated day via API: {day.date} (id={day.id})")
            return day
        except HTTPException:
            raise
        except ValueError as e:
            logger.error(f"Error updating day {day_id}: {e}")
            raise HTTPException(status_code=400, detail=str(e))
        except Exception as e:
            logger.error(f"Error updating day {day_id}: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    @delete("/{day_id:int}", status_code=200)
    async def delete_day(
        self,
        day_id: int,
        router_dependency: Generator[Session, None, None],
        request: Request,
    ) -> dict:
        """删除自然日"""
        try:
            db = next(router_dependency)
            day = delete_day_impl(db, day_id)
            if day is None:
                raise HTTPException(status_code=404, detail="Day not found")
            logger.info(f"Deleted day via API: {day.date} (id={day_id})")
            return {
                "id": day_id,
                "status": "success",
                "message": f"Day {day_id} deleted successfully",
            }
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error deleting day {day_id}: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    @post("/init")
    async def init_days(
        self,
        router_dependency: Generator[Session, None, None],
        request: Request,
    ) -> dict:
        """触发自然日初始化（幂等）"""
        try:
            db = next(router_dependency)
            result = init_time_system_impl(db)
            logger.info(f"Init time system via API: {result}")
            return {
                "status": "success",
                "days_created": result["days_created"],
                "total_days": result["total_days"],
                "total_spans": result["total_spans"],
                "timespans": result["timespans"],
            }
        except Exception as e:
            logger.error(f"Error initializing time system: {e}")
            raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# TimeSpan Controller
# ============================================================================


class TimeSpanController(Controller):
    path = "/timespan"

    @get("/")
    async def get_timespan_list(
        self,
        router_dependency: Generator[Session, None, None],
        request: Request,
        class_: Optional[TimeSpanClass] = Parameter(query="class", default=None),
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        name: Optional[str] = None,
        skip: int = 0,
        limit: int = -1,
    ) -> TimeSpanListResponse:
        """获取时间跨度列表"""
        try:
            db = next(router_dependency)
            spans = get_timespans_impl(
                db, class_, start_date, end_date, name, skip, limit
            )
            total = len(spans)
            if limit > 0 and total == limit:
                total = len(
                    get_timespans_impl(db, class_, start_date, end_date, name, 0, -1)
                )
            return TimeSpanListResponse(timespans=spans, total=total)
        except Exception as e:
            logger.error(f"Error getting timespan list: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    @get("/{span_id:int}")
    async def get_timespan(
        self,
        span_id: int,
        router_dependency: Generator[Session, None, None],
        request: Request,
    ) -> TimeSpanResponse:
        """通过 ID 获取时间跨度"""
        try:
            db = next(router_dependency)
            span = get_timespan_impl(db, span_id)
            if span is None:
                raise HTTPException(status_code=404, detail="TimeSpan not found")
            return span
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error getting timespan {span_id}: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    @get("/by-name")
    async def get_timespan_by_name(
        self,
        router_dependency: Generator[Session, None, None],
        request: Request,
        name: str,
        class_: TimeSpanClass = Parameter(query="class"),
    ) -> TimeSpanResponse:
        """通过类型和名称获取时间跨度"""
        try:
            db = next(router_dependency)
            span = get_timespan_by_name_impl(db, class_, name)
            if span is None:
                raise HTTPException(status_code=404, detail="TimeSpan not found")
            return span
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error getting timespan by name {class_}/{name}: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    @get("/{span_id:int}/children")
    async def get_timespan_children(
        self,
        span_id: int,
        router_dependency: Generator[Session, None, None],
        request: Request,
    ) -> TimeSpanListResponse:
        """获取子时间跨度"""
        try:
            db = next(router_dependency)
            children = get_timespan_children_impl(db, span_id)
            return TimeSpanListResponse(timespans=children, total=len(children))
        except Exception as e:
            logger.error(f"Error getting children of timespan {span_id}: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    @get("/by-day")
    async def get_timespans_by_day(
        self,
        router_dependency: Generator[Session, None, None],
        request: Request,
        date: date,
    ) -> TimeSpanListResponse:
        """获取包含指定日期的时间跨度"""
        try:
            db = next(router_dependency)
            spans = get_timespans_by_day_impl(db, date)
            return TimeSpanListResponse(timespans=spans, total=len(spans))
        except Exception as e:
            logger.error(f"Error getting timespans by day {date}: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    @post("/")
    async def create_timespan(
        self,
        data: TimeSpanCreateRequest,
        router_dependency: Generator[Session, None, None],
        request: Request,
    ) -> TimeSpanResponse:
        """创建时间跨度"""
        try:
            db = next(router_dependency)
            span = create_timespan_impl(db, data)
            logger.info(
                f"Created timespan via API: {span.class_}/{span.name} (id={span.id})"
            )
            return span
        except ValueError as e:
            logger.error(f"Error creating timespan: {e}")
            raise HTTPException(status_code=400, detail=str(e))
        except Exception as e:
            logger.error(f"Error creating timespan: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    @put("/{span_id:int}")
    async def update_timespan(
        self,
        span_id: int,
        data: TimeSpanUpdateRequest,
        router_dependency: Generator[Session, None, None],
        request: Request,
    ) -> TimeSpanResponse:
        """更新时间跨度"""
        try:
            db = next(router_dependency)
            span = update_timespan_impl(db, span_id, data)
            if span is None:
                raise HTTPException(status_code=404, detail="TimeSpan not found")
            logger.info(
                f"Updated timespan via API: {span.class_}/{span.name} (id={span.id})"
            )
            return span
        except HTTPException:
            raise
        except ValueError as e:
            logger.error(f"Error updating timespan {span_id}: {e}")
            raise HTTPException(status_code=400, detail=str(e))
        except Exception as e:
            logger.error(f"Error updating timespan {span_id}: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    @delete("/{span_id:int}", status_code=200)
    async def delete_timespan(
        self,
        span_id: int,
        router_dependency: Generator[Session, None, None],
        request: Request,
    ) -> dict:
        """删除时间跨度"""
        try:
            db = next(router_dependency)
            span = delete_timespan_impl(db, span_id)
            if span is None:
                raise HTTPException(status_code=404, detail="TimeSpan not found")
            logger.info(
                f"Deleted timespan via API: {span.class_}/{span.name} (id={span_id})"
            )
            return {
                "id": span_id,
                "status": "success",
                "message": f"TimeSpan {span_id} deleted successfully",
            }
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error deleting timespan {span_id}: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    @post("/init")
    async def init_timespans(
        self,
        router_dependency: Generator[Session, None, None],
        request: Request,
    ) -> dict:
        """触发时间跨度初始化（幂等）"""
        try:
            db = next(router_dependency)
            result = init_time_system_impl(db)
            logger.info(f"Init time system via API: {result}")
            return {
                "status": "success",
                "days_created": result["days_created"],
                "total_days": result["total_days"],
                "total_spans": result["total_spans"],
                "timespans": result["timespans"],
            }
        except Exception as e:
            logger.error(f"Error initializing time system: {e}")
            raise HTTPException(status_code=500, detail=str(e))
