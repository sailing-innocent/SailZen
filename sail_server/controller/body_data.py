# -*- coding: utf-8 -*-
# @file body_data.py
# @brief Body Data Controller
# @author sailing-innocent
# @date 2026-09-06
# @version 1.0
# ---------------------------------

"""
身体数据控制器。

API 契约（前缀 /api/v1/health/body-data）：
    POST   /body-data            创建记录（data 至少含 1 个指标；含 weight 时 dual-write）
    GET    /body-data            列表（skip/limit/start/end/metric 过滤）
    GET    /body-data/metrics    指标注册表（内置 + 自定义扫描）
    GET    /body-data/series     单指标时序（?metric=&start=&end=）
    GET    /body-data/analysis   单指标趋势分析（?metric=&start=&end=&model_type=）
    GET    /body-data/{id}       单条记录
    PUT    /body-data/{id}       更新记录（weight 联动更新/补建/删除）
    DELETE /body-data/{id}       删除记录（级联 dual-written Weight 行）

校验失败（data 为空 / 非法 key / 超范围 value）返回 422 及合法 key 列表。
"""
from __future__ import annotations

import logging
from typing import Generator, List

from litestar import Controller, Request, Response, delete, get, post, put
from litestar.exceptions import ValidationException
from litestar.status_codes import HTTP_422_UNPROCESSABLE_ENTITY
from sqlalchemy.orm import Session

from sail_server.application.dto.body_data import (
    BodyDataCreateRequest,
    BodyDataResponse,
    BodyDataSeriesResponse,
    BodyDataUpdateRequest,
    BodyMetricDefinition,
)
from sail_server.model.body_data import (
    analyze_body_metric_trend_impl,
    create_body_data_impl,
    delete_body_data_impl,
    get_metric_schema_impl,
    get_metric_series_impl,
    read_body_data_impl,
    read_body_data_list_impl,
    update_body_data_impl,
)

logger = logging.getLogger(__name__)


def _validation_to_422(request: Request, exc: ValidationException) -> Response:
    """将 pydantic 请求校验失败映射为 422（附合法 key 列表，见计划 2.5 节）。"""
    return Response(
        content={
            "status_code": HTTP_422_UNPROCESSABLE_ENTITY,
            "detail": exc.detail,
            "extra": exc.extra,
        },
        status_code=HTTP_422_UNPROCESSABLE_ENTITY,
    )


class BodyDataController(Controller):
    path = "/body-data"

    exception_handlers = {ValidationException: _validation_to_422}

    # POST /body-data
    @post()
    async def create_body_data(
        self,
        data: BodyDataCreateRequest,
        request: Request,
        router_dependency: Generator[Session, None, None],
    ) -> BodyDataResponse:
        """Create a new body data record."""
        db = next(router_dependency)
        record = create_body_data_impl(db, data)
        logger.info(f"[body_data] create #{record.id}: {list(record.data.keys())}")
        return record

    # GET /body-data?skip=&limit=&start=&end=&metric=
    @get()
    async def get_body_data_list(
        self,
        router_dependency: Generator[Session, None, None],
        skip: int = 0,
        limit: int = 10,
        start: float | None = None,  # timestamp as float in seconds
        end: float | None = None,
        metric: str | None = None,
    ) -> List[BodyDataResponse]:
        """List body data records with optional metric filter."""
        db = next(router_dependency)
        records = read_body_data_list_impl(db, skip, limit, start, end, metric)
        return records

    # GET /body-data/metrics
    @get("/metrics")
    async def get_metrics(
        self,
        router_dependency: Generator[Session, None, None],
    ) -> List[BodyMetricDefinition]:
        """Get metric registry (builtin + custom metrics discovered from data)."""
        db = next(router_dependency)
        return get_metric_schema_impl(db)

    # GET /body-data/series?metric=&start=&end=
    @get("/series")
    async def get_metric_series(
        self,
        router_dependency: Generator[Session, None, None],
        metric: str,
        start: float | None = None,
        end: float | None = None,
    ) -> BodyDataSeriesResponse:
        """Get single-metric time series (missing measurements are omitted)."""
        db = next(router_dependency)
        return get_metric_series_impl(db, metric, start, end)

    # GET /body-data/analysis?metric=&start=&end=&model_type=
    @get("/analysis")
    async def analyze_metric_trend(
        self,
        router_dependency: Generator[Session, None, None],
        metric: str,
        start: float | None = None,
        end: float | None = None,
        model_type: str = "linear",  # 'linear' or 'polynomial'
    ) -> dict:
        """Analyze trend for any body metric (same regression core as weight)."""
        db = next(router_dependency)
        result = analyze_body_metric_trend_impl(db, metric, start, end, model_type)
        logger.info(
            f"[body_data] analysis metric={metric} slope={result['slope']}, "
            f"trend={result['current_trend']}"
        )
        return result

    # GET /body-data/{record_id:int}
    @get("/{record_id:int}")
    async def get_body_data(
        self,
        record_id: int,
        router_dependency: Generator[Session, None, None],
        request: Request,
    ) -> BodyDataResponse | None:
        """Get a single body data record."""
        db = next(router_dependency)
        return read_body_data_impl(db, record_id)

    # PUT /body-data/{record_id:int}
    @put("/{record_id:int}")
    async def update_body_data(
        self,
        record_id: int,
        data: BodyDataUpdateRequest,
        request: Request,
        router_dependency: Generator[Session, None, None],
    ) -> BodyDataResponse | None:
        """Update a body data record (syncs dual-written Weight row)."""
        db = next(router_dependency)
        record = update_body_data_impl(db, record_id, data)
        logger.info(f"[body_data] update #{record_id}: {record is not None}")
        return record

    # DELETE /body-data/{record_id:int}
    @delete("/{record_id:int}", status_code=200)
    async def delete_body_data(
        self,
        record_id: int,
        request: Request,
        router_dependency: Generator[Session, None, None],
    ) -> dict:
        """Delete a body data record (cascades to dual-written Weight row)."""
        db = next(router_dependency)
        ok = delete_body_data_impl(db, record_id)
        logger.info(f"[body_data] delete #{record_id}: {ok}")
        return {"deleted": ok, "id": record_id}
