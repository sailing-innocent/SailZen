# -*- coding: utf-8 -*-
# @file pems.py
# @brief Personal Energy Management System Controller
# @author sailing-innocent
# @date 2026-03-01
# @version 1.0
# ---------------------------------

"""
个人精力管理系统(PEMS) 控制器
"""

from datetime import date, datetime
from typing import Generator, List, Optional
import logging

from litestar import Controller, get, post, put, Request
from litestar.exceptions import HTTPException, NotFoundException
from sqlalchemy.orm import Session

from sail_server.application.dto.pems import (
    DayViewResponse,
    TimeSpanViewResponse,
    ProjectTimelineResponse,
    EnergyBudgetResponse,
    InsightResponse,
    PlanMissionRequest,
    TimeSpanReviewRequest,
    HealthQuickLogRequest,
    StatusResponse,
)
from sail_server.model.pems import (
    get_day_view_impl,
    plan_mission_on_day_impl,
    log_health_on_day_impl,
    get_timespan_view_impl,
    review_timespan_impl,
    get_project_timeline_impl,
    get_energy_budget_impl,
    get_insight_daily_impl,
    get_insight_weekly_impl,
)

logger = logging.getLogger(__name__)


class PEMSController(Controller):
    path = "/"

    @get("/day/{query_date:str}")
    async def get_day_view(
        self,
        query_date: str,
        router_dependency: Generator[Session, None, None],
        request: Request,
    ) -> DayViewResponse:
        """获取某日 PEMS 完整视图"""
        db = next(router_dependency)
        try:
            return get_day_view_impl(db, datetime.strptime(query_date, "%Y-%m-%d").date())
        except ValueError as e:
            logger.error(f"Error getting day view for {query_date}: {e}")
            raise NotFoundException(detail=str(e))
        except Exception as e:
            logger.error(f"Error getting day view for {query_date}: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    @post("/day/{query_date:str}/plan")
    async def plan_mission_on_day(
        self,
        query_date: str,
        data: PlanMissionRequest,
        router_dependency: Generator[Session, None, None],
        request: Request,
    ) -> DayViewResponse:
        """为某日安排任务"""
        db = next(router_dependency)
        try:
            query_date_obj = datetime.strptime(query_date, "%Y-%m-%d").date()
            result = plan_mission_on_day_impl(db, query_date_obj, data.mission_id)
            if result is None:
                raise NotFoundException(detail=f"Mission {data.mission_id} not found")
            return get_day_view_impl(db, query_date_obj)
        except ValueError as e:
            logger.error(f"Error planning mission on {query_date}: {e}")
            raise HTTPException(status_code=400, detail=str(e))
        except Exception as e:
            logger.error(f"Error planning mission on {query_date}: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    @post("/day/{query_date:str}/health")
    async def log_health_on_day(
        self,
        query_date: str,
        data: HealthQuickLogRequest,
        router_dependency: Generator[Session, None, None],
        request: Request,
    ) -> DayViewResponse:
        """在某日快速记录健康信号"""
        db = next(router_dependency)
        try:
            log_health_on_day_impl(
                db,
                datetime.strptime(query_date, "%Y-%m-%d").date(),
                sleep_hours=data.sleep_hours,
                sleep_quality=data.sleep_quality,
                energy_level=data.energy_level,
                mood=data.mood,
                note=data.note,
            )
            return get_day_view_impl(db, datetime.strptime(query_date, "%Y-%m-%d").date())
        except ValueError as e:
            logger.error(f"Error logging health on {query_date}: {e}")
            raise HTTPException(status_code=400, detail=str(e))
        except Exception as e:
            logger.error(f"Error logging health on {query_date}: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    @get("/timespan/{span_id:int}")
    async def get_timespan_view(
        self,
        span_id: int,
        router_dependency: Generator[Session, None, None],
        request: Request,
    ) -> TimeSpanViewResponse:
        """获取周期视图"""
        db = next(router_dependency)
        try:
            return get_timespan_view_impl(db, span_id)
        except ValueError as e:
            logger.error(f"Error getting timespan view {span_id}: {e}")
            raise NotFoundException(detail=str(e))
        except Exception as e:
            logger.error(f"Error getting timespan view {span_id}: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    @post("/timespan/{span_id:int}/review")
    async def review_timespan(
        self,
        span_id: int,
        data: TimeSpanReviewRequest,
        router_dependency: Generator[Session, None, None],
        request: Request,
    ) -> TimeSpanViewResponse:
        """提交周期复盘"""
        db = next(router_dependency)
        try:
            return review_timespan_impl(
                db,
                span_id,
                review_note=data.review_note,
                theme=data.theme,
                focus_areas=data.focus_areas,
            )
        except ValueError as e:
            logger.error(f"Error reviewing timespan {span_id}: {e}")
            raise NotFoundException(detail=str(e))
        except Exception as e:
            logger.error(f"Error reviewing timespan {span_id}: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    @get("/project/{project_id:int}/timeline")
    async def get_project_timeline(
        self,
        project_id: int,
        router_dependency: Generator[Session, None, None],
        request: Request,
    ) -> ProjectTimelineResponse:
        """获取项目时间线"""
        db = next(router_dependency)
        try:
            return get_project_timeline_impl(db, project_id)
        except ValueError as e:
            logger.error(f"Error getting project timeline {project_id}: {e}")
            raise NotFoundException(detail=str(e))
        except Exception as e:
            logger.error(f"Error getting project timeline {project_id}: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    @get("/energy/budget")
    async def get_energy_budget(
        self,
        query_date: str,
        router_dependency: Generator[Session, None, None],
        request: Request,
    ) -> EnergyBudgetResponse:
        """获取某日精力预算"""
        db = next(router_dependency)
        try:
            return get_energy_budget_impl(db, datetime.strptime(query_date, "%Y-%m-%d").date())
        except ValueError as e:
            logger.error(f"Error getting energy budget for {query_date}: {e}")
            raise NotFoundException(detail=str(e))
        except Exception as e:
            logger.error(f"Error getting energy budget for {query_date}: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    @get("/insight/daily")
    async def get_daily_insight(
        self,
        query_date: str,
        router_dependency: Generator[Session, None, None],
        request: Request,
    ) -> List[InsightResponse]:
        """获取每日洞察"""
        db = next(router_dependency)
        try:
            return get_insight_daily_impl(db, datetime.strptime(query_date, "%Y-%m-%d").date())
        except ValueError as e:
            logger.error(f"Error getting daily insight for {query_date}: {e}")
            raise NotFoundException(detail=str(e))
        except Exception as e:
            logger.error(f"Error getting daily insight for {query_date}: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    @get("/insight/weekly")
    async def get_weekly_insight(
        self,
        query_date: str,
        router_dependency: Generator[Session, None, None],
        request: Request,
    ) -> List[InsightResponse]:
        """获取双周洞察"""
        db = next(router_dependency)
        try:
            return get_insight_weekly_impl(db, datetime.strptime(query_date, "%Y-%m-%d").date())
        except ValueError as e:
            logger.error(f"Error getting weekly insight for {query_date}: {e}")
            raise NotFoundException(detail=str(e))
        except Exception as e:
            logger.error(f"Error getting weekly insight for {query_date}: {e}")
            raise HTTPException(status_code=500, detail=str(e))
