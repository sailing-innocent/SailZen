# -*- coding: utf-8 -*-
# @file rhythm.py
# @brief Rhythm Controller (统一事务/时间线/模板/打卡/事业/精力/策略/计划/复盘)
# @author sailing-innocent
# @date 2026-10-26
# @version 1.0
# ---------------------------------

"""
节奏（Rhythm）模块控制器

REST 契约见 doc/design/manager/rhythm.md §6。

鉴权：仅当环境变量 SAILZEN_API_TOKEN 非空时校验
``Authorization: Bearer <token>``；未配置则全部放行（局域网自用，复用 reminder 模式）。
"""

from __future__ import annotations

import logging
import os
from contextlib import contextmanager
from datetime import date as date_type
from datetime import datetime
from typing import Generator, List, Optional

from litestar import Controller, Request, delete, get, post, put
from litestar.exceptions import (
    ClientException,
    NotAuthorizedException,
    NotFoundException,
)
from litestar.params import Parameter
from sqlalchemy.orm import Session

from sail_server.application.dto.rhythm import (
    AffairCreateRequest,
    AffairListResponse,
    AffairResponse,
    AffairSplitRequest,
    AffairStateRequest,
    AffairUpdateRequest,
    BlockMoveRequest,
    BlockStatusRequest,
    CheckinListResponse,
    CheckinRequest,
    CheckinLogResponse,
    CheckinTodayResponse,
    ConfirmHintRequest,
    ConflictReportResponse,
    DayTemplateListResponse,
    DayTemplateResponse,
    DayTemplateUpsertRequest,
    DayTimelineResponse,
    DomainTrendResponse,
    EncroachmentItem,
    EnergyProfileResponse,
    EnergyProfileUpsertRequest,
    EnsureTemplatesResponse,
    HabitHeatmapResponse,
    HealthCheckinRequest,
    HealthCheckinResponse,
    InfoCollectionType,
    PlanDayRequest,
    PlanDayResponse,
    PolicyCreateRequest,
    PolicyListResponse,
    PolicyResponse,
    PolicyUpdateRequest,
    RebalanceRequest,
    ReviewResponse,
    ReviewSummaryUpdateRequest,
    ReviewTimespanResponse,
    RhythmDashboardResponse,
    RhythmDayDashboardResponse,
    RhythmDayViewResponse,
    TimeBlockCreateRequest,
    TimeBlockResponse,
    VentureBurndownResponse,
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
    create_policy_impl,
    delete_affair_impl,
    delete_policy_impl,
    delete_template_impl,
    ensure_default_templates_impl,
    get_active_template_impl,
    get_affair_impl,
    get_day_dashboard_impl,
    get_energy_profile_impl,
    get_rhythm_day_view_impl,
    get_template_impl,
    health_checkin_impl,
    list_affairs_impl,
    list_checkins_impl,
    list_policies_impl,
    list_templates_impl,
    milestone_done_impl,
    move_block_impl,
    recalibrate_profile_impl,
    review_timespan_impl,
    set_block_status_impl,
    split_affair_impl,
    today_checkins_impl,
    transit_affair_state_impl,
    update_affair_impl,
    update_policy_impl,
    upsert_energy_profile_impl,
    upsert_template_impl,
    venture_progress_impl,
)
from sail_server.model.rhythm_planner import (
    detect_conflicts_impl,
    get_dashboard_impl,
    get_day_review_impl,
    get_day_timeline_impl,
    get_domain_trend_impl,
    get_habit_heatmap_impl,
    get_venture_burndown_impl,
    get_week_review_impl,
    list_encroachments_impl,
    plan_day_impl,
    rebalance_impl,
    update_review_summary_impl,
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
    except RhythmNotFoundError as e:
        raise NotFoundException(detail=str(e)) from e
    except RhythmStateConflictError as e:
        raise ClientException(status_code=409, detail=str(e)) from e
    except RhythmBadRequestError as e:
        raise ClientException(status_code=400, detail=str(e)) from e
    except ValueError as e:
        raise ClientException(status_code=400, detail=str(e)) from e


# ============================================================================
# Dashboard Controller（PC Dashboard / Android 提醒端共享聚合入口）
# ============================================================================


class DashboardController(Controller):
    path = "/dashboard"

    @get("/")
    async def dashboard(
        self,
        request: Request,
        router_dependency: Generator[Session, None, None],
        date: date_type,
    ) -> RhythmDashboardResponse:
        """GET /api/v1/rhythm/dashboard?date=YYYY-MM-DD

        一次性聚合 Dashboard 与 Android 提醒端所需的当日全部数据。
        """
        _check_auth(request)
        db = next(router_dependency)
        with _map_errors():
            return get_dashboard_impl(db, date)


# ============================================================================
# Admin Controller（旧数据校准 / 默认模板 / 精力画像）
# ============================================================================


class AdminController(Controller):
    path = "/admin"

    @post("/recalibrate-profile")
    async def recalibrate_profile(
        self,
        data: EnergyProfileUpsertRequest,
        request: Request,
        router_dependency: Generator[Session, None, None],
    ) -> EnergyProfileResponse:
        """覆盖/创建默认精力画像（首次引导校准）。"""
        _check_auth(request)
        db = next(router_dependency)
        with _map_errors():
            return recalibrate_profile_impl(db, data)

    @post("/ensure-default-templates")
    async def ensure_default_templates(
        self,
        request: Request,
        router_dependency: Generator[Session, None, None],
    ) -> EnsureTemplatesResponse:
        """幂等生成 weekday/weekend/travel_day 三套默认模板。"""
        _check_auth(request)
        db = next(router_dependency)
        return ensure_default_templates_impl(db)



# ============================================================================
# Affair Controller（事务：捕获/分拣确认/状态机/拆分）
# ============================================================================


class AffairController(Controller):
    path = "/affair"

    @post("/")
    async def create_affair(
        self,
        data: AffairCreateRequest,
        request: Request,
        router_dependency: Generator[Session, None, None],
    ) -> AffairResponse:
        """快速捕获（仅 title 即可，kind=generic → INBOX）"""
        _check_auth(request)
        db = next(router_dependency)
        with _map_errors():
            return create_affair_impl(db, data)

    @get("/")
    async def list_affairs(
        self,
        request: Request,
        router_dependency: Generator[Session, None, None],
        state_: Optional[str] = Parameter(query="state", default=None),
        domain: Optional[str] = None,
        kind: Optional[List[str]] = Parameter(query="kind", default=None),
        day_id: Optional[int] = None,
        parent_id: Optional[int] = None,
        urgency_ddl_before: Optional[datetime] = None,
        urgency_ddl_after: Optional[datetime] = None,
        skip: int = 0,
        limit: int = -1,
    ) -> AffairListResponse:
        """事务列表（state/domain/kind[多值]/day_id/urgency_ddl 范围过滤）"""
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
        """获取单个事务"""
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
        """编辑（含 kind 改判 + kind_meta 校验 + ai_hint 更新）"""
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
        """删除事务"""
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
        """状态转移 {action: confirm|defer|cancel|start|finish|pause|resume|archive|graduate|dismiss|replan}"""
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
        """采纳/驳回 AI 建议（含 kind/kind_meta 改判确认）"""
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
        """拆分（AI 建议经确认后落地）"""
        _check_auth(request)
        db = next(router_dependency)
        with _map_errors():
            return split_affair_impl(db, affair_id, data)


# ============================================================================
# Template Controller（基础节奏模板）
# ============================================================================


class TemplateController(Controller):
    path = "/template"

    @get("/")
    async def list_templates(
        self,
        request: Request,
        router_dependency: Generator[Session, None, None],
        enabled_only: bool = False,
    ) -> DayTemplateListResponse:
        """模板列表"""
        _check_auth(request)
        db = next(router_dependency)
        templates = list_templates_impl(db, enabled_only)
        return DayTemplateListResponse(templates=templates, total=len(templates))

    @post("/")
    async def upsert_template(
        self,
        data: DayTemplateUpsertRequest,
        request: Request,
        router_dependency: Generator[Session, None, None],
    ) -> DayTemplateResponse:
        """模板创建/更新（按 name upsert）"""
        _check_auth(request)
        db = next(router_dependency)
        with _map_errors():
            return upsert_template_impl(db, data)

    @get("/active")
    async def get_active_template(
        self,
        request: Request,
        router_dependency: Generator[Session, None, None],
        date: date_type,
    ) -> DayTemplateResponse:
        """查询某日命中的模板"""
        _check_auth(request)
        db = next(router_dependency)
        tpl = get_active_template_impl(db, date)
        if tpl is None:
            raise NotFoundException(detail=f"No active template for {date}")
        return tpl

    @get("/{template_id:int}")
    async def get_template(
        self,
        template_id: int,
        request: Request,
        router_dependency: Generator[Session, None, None],
    ) -> DayTemplateResponse:
        """获取模板"""
        _check_auth(request)
        db = next(router_dependency)
        tpl = get_template_impl(db, template_id)
        if tpl is None:
            raise NotFoundException(detail=f"Template {template_id} not found")
        return tpl

    @put("/{template_id:int}")
    async def update_template(
        self,
        template_id: int,
        data: DayTemplateUpsertRequest,
        request: Request,
        router_dependency: Generator[Session, None, None],
    ) -> DayTemplateResponse:
        """更新模板（按 id，body 中 name 需一致）"""
        _check_auth(request)
        db = next(router_dependency)
        tpl = get_template_impl(db, template_id)
        if tpl is None:
            raise NotFoundException(detail=f"Template {template_id} not found")
        with _map_errors():
            return upsert_template_impl(db, data)

    @delete("/{template_id:int}", status_code=200)
    async def delete_template(
        self,
        template_id: int,
        request: Request,
        router_dependency: Generator[Session, None, None],
    ) -> dict:
        """删除模板"""
        _check_auth(request)
        db = next(router_dependency)
        tpl = delete_template_impl(db, template_id)
        if tpl is None:
            raise NotFoundException(detail=f"Template {template_id} not found")
        return {"id": template_id, "status": "success"}


# ============================================================================
# Checkin Controller（戒律/习惯打卡核销）
# ============================================================================


class CheckinController(Controller):
    path = "/checkin"

    @post("/")
    async def checkin(
        self,
        data: CheckinRequest,
        request: Request,
        router_dependency: Generator[Session, None, None],
    ) -> CheckinLogResponse:
        """打卡 {affair_id, result, log_date?, note?}"""
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
        """日志查询（affair_id + 日期范围 + cycle_key）"""
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
        """今日待打卡清单（时间线页/打卡中心用）"""
        _check_auth(request)
        db = next(router_dependency)
        return today_checkins_impl(db, date)

    @get("/heatmap")
    async def heatmap(
        self,
        request: Request,
        router_dependency: Generator[Session, None, None],
        affair_id: int,
        start_date: date_type,
        end_date: date_type,
    ) -> HabitHeatmapResponse:
        """habit/precept 打卡热力图"""
        _check_auth(request)
        db = next(router_dependency)
        with _map_errors():
            return get_habit_heatmap_impl(db, affair_id, start_date, end_date)

    @post("/health")
    async def health_checkin(
        self,
        data: HealthCheckinRequest,
        request: Request,
        router_dependency: Generator[Session, None, None],
    ) -> HealthCheckinResponse:
        """健康速记（体重/饮食/运动/用药/睡眠/情绪），双写 health 表与 rhythm 打卡日志"""
        _check_auth(request)
        db = next(router_dependency)
        with _map_errors():
            return health_checkin_impl(db, data)


# ============================================================================
# Venture Controller（长期事业进度）
# ============================================================================


class VentureController(Controller):
    path = "/venture"

    @get("/{venture_id:int}/progress")
    async def venture_progress(
        self,
        venture_id: int,
        request: Request,
        router_dependency: Generator[Session, None, None],
    ) -> VentureProgressResponse:
        """倒排进度（weeks_left/周预算消耗/里程碑完成度/倒排压力）"""
        _check_auth(request)
        db = next(router_dependency)
        with _map_errors():
            return venture_progress_impl(db, venture_id)

    @get("/{venture_id:int}/burndown")
    async def burndown(
        self,
        venture_id: int,
        request: Request,
        router_dependency: Generator[Session, None, None],
    ) -> VentureBurndownResponse:
        """事业燃尽图"""
        _check_auth(request)
        db = next(router_dependency)
        with _map_errors():
            return get_venture_burndown_impl(db, venture_id)

    @post("/{venture_id:int}/milestone")
    async def add_milestone(
        self,
        venture_id: int,
        data: VentureMilestoneRequest,
        request: Request,
        router_dependency: Generator[Session, None, None],
    ) -> AffairResponse:
        """添加里程碑子事务（锚定 TimeSpan/QBW）"""
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
        """勾选里程碑完成"""
        _check_auth(request)
        db = next(router_dependency)
        with _map_errors():
            return milestone_done_impl(db, milestone_id)


# ============================================================================
# Timeline Controller（日时间线）
# ============================================================================


class TimelineController(Controller):
    path = "/timeline"

    @get("/day")
    async def day_timeline(
        self,
        request: Request,
        router_dependency: Generator[Session, None, None],
        date: date_type,
    ) -> DayTimelineResponse:
        """日时间线（blocks + 三域余量统计 + 待打卡清单）"""
        _check_auth(request)
        db = next(router_dependency)
        with _map_errors():
            return get_day_timeline_impl(db, date)

    @get("/day-view")
    async def day_view(
        self,
        request: Request,
        router_dependency: Generator[Session, None, None],
        date: date_type,
    ) -> RhythmDayViewResponse:
        """统一日视图（PEMS 合并）：时间线 + 能量 + 打卡 + 健康信号"""
        _check_auth(request)
        db = next(router_dependency)
        with _map_errors():
            return get_rhythm_day_view_impl(db, date)

    @get("/day-dashboard")
    async def day_dashboard(
        self,
        request: Request,
        router_dependency: Generator[Session, None, None],
        date: date_type,
    ) -> RhythmDayDashboardResponse:
        """统一日仪表板：时间线 + 精力 + 打卡 + 优先级事务"""
        _check_auth(request)
        db = next(router_dependency)
        with _map_errors():
            return get_day_dashboard_impl(db, date)

    @post("/block")
    async def create_block(
        self,
        data: TimeBlockCreateRequest,
        request: Request,
        router_dependency: Generator[Session, None, None],
    ) -> TimeBlockResponse:
        """手动创建时间线块"""
        _check_auth(request)
        db = next(router_dependency)
        with _map_errors():
            return create_block_impl(db, data)

    @post("/block/{block_id:int}/status")
    async def block_status(
        self,
        block_id: int,
        data: BlockStatusRequest,
        request: Request,
        router_dependency: Generator[Session, None, None],
    ) -> TimeBlockResponse:
        """块反馈 done/skipped（habit 块 done 自动写 DisciplineLog）"""
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
        """手动拖改（pinned 块拒绝，409）"""
        _check_auth(request)
        db = next(router_dependency)
        with _map_errors():
            return move_block_impl(db, block_id, data)


# ============================================================================
# Plan Controller（计划生成/再平衡/侵占检测）
# ============================================================================


class PlanController(Controller):
    path = "/plan"

    @post("/day")
    async def plan_day(
        self,
        data: PlanDayRequest,
        request: Request,
        router_dependency: Generator[Session, None, None],
    ) -> PlanDayResponse:
        """生成/重生成日计划（plan_version+1）"""
        _check_auth(request)
        db = next(router_dependency)
        with _map_errors():
            return plan_day_impl(db, data)

    @post("/rebalance")
    async def rebalance(
        self,
        data: RebalanceRequest,
        request: Request,
        router_dependency: Generator[Session, None, None],
    ) -> PlanDayResponse:
        """再平衡（trigger: defer|new_affair|manual|checkin_missed）"""
        _check_auth(request)
        db = next(router_dependency)
        with _map_errors():
            return rebalance_impl(db, data)

    @get("/conflicts")
    async def conflicts(
        self,
        request: Request,
        router_dependency: Generator[Session, None, None],
        date: date_type,
    ) -> ConflictReportResponse:
        """冲突/侵占报告"""
        _check_auth(request)
        db = next(router_dependency)
        items = detect_conflicts_impl(db, date)
        return ConflictReportResponse(date=date, encroachments=items)


# ============================================================================
# Energy Controller（精力画像）
# ============================================================================


class EnergyController(Controller):
    path = "/energy"

    @get("/profile")
    async def get_profile(
        self,
        request: Request,
        router_dependency: Generator[Session, None, None],
    ) -> EnergyProfileResponse:
        """获取精力画像（无则创建默认）"""
        _check_auth(request)
        db = next(router_dependency)
        return get_energy_profile_impl(db)

    @put("/profile")
    async def upsert_profile(
        self,
        data: EnergyProfileUpsertRequest,
        request: Request,
        router_dependency: Generator[Session, None, None],
    ) -> EnergyProfileResponse:
        """精力画像单行 upsert（含 spare_time_windows 与三域权重）"""
        _check_auth(request)
        db = next(router_dependency)
        with _map_errors():
            return upsert_energy_profile_impl(db, data)


# ============================================================================
# Policy Controller（守护策略）
# ============================================================================


class PolicyController(Controller):
    path = "/policy"

    @get("/")
    async def list_policies(
        self,
        request: Request,
        router_dependency: Generator[Session, None, None],
        enabled_only: bool = False,
    ) -> PolicyListResponse:
        """策略列表"""
        _check_auth(request)
        db = next(router_dependency)
        policies = list_policies_impl(db, enabled_only)
        return PolicyListResponse(policies=policies, total=len(policies))

    @post("/")
    async def create_policy(
        self,
        data: PolicyCreateRequest,
        request: Request,
        router_dependency: Generator[Session, None, None],
    ) -> PolicyResponse:
        """创建策略"""
        _check_auth(request)
        db = next(router_dependency)
        with _map_errors():
            return create_policy_impl(db, data)

    @put("/{policy_id:int}")
    async def update_policy(
        self,
        policy_id: int,
        data: PolicyUpdateRequest,
        request: Request,
        router_dependency: Generator[Session, None, None],
    ) -> PolicyResponse:
        """更新策略（含启停 toggle）"""
        _check_auth(request)
        db = next(router_dependency)
        with _map_errors():
            policy = update_policy_impl(db, policy_id, data)
            if policy is None:
                raise NotFoundException(detail=f"Policy {policy_id} not found")
            return policy

    @delete("/{policy_id:int}", status_code=200)
    async def delete_policy(
        self,
        policy_id: int,
        request: Request,
        router_dependency: Generator[Session, None, None],
    ) -> dict:
        """删除策略"""
        _check_auth(request)
        db = next(router_dependency)
        policy = delete_policy_impl(db, policy_id)
        if policy is None:
            raise NotFoundException(detail=f"Policy {policy_id} not found")
        return {"id": policy_id, "status": "success"}


# ============================================================================
# Review Controller（节奏评分/周报快照）
# ============================================================================


class ReviewController(Controller):
    path = "/review"

    @get("/day")
    async def day_review(
        self,
        request: Request,
        router_dependency: Generator[Session, None, None],
        date: date_type,
    ) -> ReviewResponse:
        """日评分（无则即时计算并落库）"""
        _check_auth(request)
        db = next(router_dependency)
        with _map_errors():
            return get_day_review_impl(db, date)

    @get("/week")
    async def week_review(
        self,
        request: Request,
        router_dependency: Generator[Session, None, None],
        span: Optional[str] = None,
    ) -> ReviewResponse:
        """周评分（span=W2026-44 或日期；缺省本周）"""
        _check_auth(request)
        db = next(router_dependency)
        with _map_errors():
            return get_week_review_impl(db, span)

    @put("/{review_scope:str}/{period_key:str}/summary")
    async def update_summary(
        self,
        review_scope: str,
        period_key: str,
        data: ReviewSummaryUpdateRequest,
        request: Request,
        router_dependency: Generator[Session, None, None],
    ) -> ReviewResponse:
        """Agent 写回周评语"""
        _check_auth(request)
        db = next(router_dependency)
        with _map_errors():
            resp = update_review_summary_impl(db, review_scope, period_key, data.ai_summary)
            if resp is None:
                raise NotFoundException(
                    detail=f"Review {review_scope}/{period_key} not found（先 GET 生成）"
                )
            return resp

    @get("/encroachments")
    async def encroachments(
        self,
        request: Request,
        router_dependency: Generator[Session, None, None],
        start_date: Optional[date_type] = None,
        end_date: Optional[date_type] = None,
    ) -> List[EncroachmentItem]:
        """侵占事件列表（默认最近 7 天）"""
        _check_auth(request)
        db = next(router_dependency)
        return list_encroachments_impl(db, start_date, end_date)

    @get("/domain-trend")
    async def domain_trend(
        self,
        request: Request,
        router_dependency: Generator[Session, None, None],
        start_date: date_type,
        end_date: date_type,
    ) -> DomainTrendResponse:
        """三域时长趋势"""
        _check_auth(request)
        db = next(router_dependency)
        with _map_errors():
            return get_domain_trend_impl(db, start_date, end_date)

    @get("/timespan/{timespan_id:int}")
    async def timespan_review(
        self,
        timespan_id: int,
        request: Request,
        router_dependency: Generator[Session, None, None],
    ) -> ReviewTimespanResponse:
        """周期复盘（TimeSpan 级别聚合）"""
        _check_auth(request)
        db = next(router_dependency)
        with _map_errors():
            return review_timespan_impl(db, timespan_id)
