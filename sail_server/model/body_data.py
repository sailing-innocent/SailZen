# -*- coding: utf-8 -*-
# @file body_data.py
# @brief Body Data (身体数据) business implementation
# @author sailing-innocent
# @date 2026-09-06
# @version 1.0
# ---------------------------------

"""
身体数据业务实现层。

核心语义：
- ``data`` JSON 中不存在某 key = 本次未测量（与 null/0 严格区分）；
- dual-write：``data`` 含 weight 且 source=manual 时，同事务同步一条 weights 表记录
  （体重计划/预测/dashboard 依赖 weights 表），weight_id 回存关联 ID；
  同步失败仅记日志、不阻塞 body_data 主流程（与 create_weight_impl 的 Rhythm 联动模式一致）。
- series/metrics 提取在 Python 层做（SQLite 下 JSONB 退化为 Text，避免跨库 JSON SQL 差异）。
"""

import logging
from datetime import datetime
from typing import Dict, List, Optional, Tuple

import numpy as np
from sqlalchemy.orm import Session

from sail_server.application.dto.body_data import (
    BUILTIN_METRICS,
    BUILTIN_METRIC_MAP,
    BodyDataCreateRequest,
    BodyDataResponse,
    BodyDataSeriesPoint,
    BodyDataSeriesResponse,
    BodyDataUpdateRequest,
    BodyMetricCategory,
    BodyMetricDefinition,
)
from sail_server.infrastructure.orm.health import BodyData, Weight

logger = logging.getLogger(__name__)


# ============================================================================
# ORM -> DTO
# ============================================================================


def read_from_body_data(record: BodyData) -> BodyDataResponse:
    """Convert BodyData ORM to BodyDataResponse."""
    return BodyDataResponse(
        id=record.id,
        htime=record.htime.timestamp(),
        data={k: float(v) for k, v in (record.data or {}).items()},
        tag=record.tag,
        description=record.description,
        source=record.source,
        weight_id=record.weight_id,
    )


# ============================================================================
# Weight dual-write helpers
# ============================================================================


def _create_dual_weight(db: Session, record: BodyData) -> Optional[Weight]:
    """创建 body_data 时 dual-write：data 含 weight 且 source=manual 才写 weights 表。

    成功时回存 record.weight_id 并返回 Weight 对象；否则返回 None。
    """
    if record.source != "manual":
        return None
    data = record.data or {}
    if "weight" not in data:
        return None
    weight = Weight(
        value=str(data["weight"]),
        htime=record.htime,
        tag=record.tag,
        description=record.description,
    )
    db.add(weight)
    db.flush()
    record.weight_id = weight.id
    return weight


def _sync_dual_weight_on_update(
    db: Session,
    record: BodyData,
    new_data: Dict[str, float],
    new_htime: datetime,
    new_tag: str,
    new_description: str,
) -> None:
    """更新 body_data 时同步 dual-write 的 Weight 行（靠 weight_id 精确定位）。

    - new_data 含 weight 且 weight_id 存在 → 更新对应 Weight 行；
    - new_data 含 weight 且无 weight_id（且 source=manual）→ 补建 Weight 行；
    - new_data 不含 weight 且 weight_id 存在 → 删除对应 Weight 行并清空 weight_id。
    """
    weight: Optional[Weight] = None
    if record.weight_id is not None:
        weight = db.query(Weight).filter(Weight.id == record.weight_id).first()
        if weight is None:
            # 关联行已不存在（异常情况），清空悬挂引用
            record.weight_id = None

    if "weight" in new_data:
        if weight is not None:
            weight.value = str(new_data["weight"])
            weight.htime = new_htime
            weight.tag = new_tag
            weight.description = new_description
            db.flush()
        elif record.source == "manual":
            weight = Weight(
                value=str(new_data["weight"]),
                htime=new_htime,
                tag=new_tag,
                description=new_description,
            )
            db.add(weight)
            db.flush()
            record.weight_id = weight.id
    else:
        if weight is not None:
            db.delete(weight)
            db.flush()
            record.weight_id = None


def _sync_weight_rhythm_feedback(db: Session, weight: Weight) -> None:
    """与 create_weight_impl 保持一致的 Rhythm feedback 联动（失败不阻塞）。"""
    try:
        from sail_server.model.health import (
            _get_active_weight_plan,
            _sync_weight_to_rhythm_checkin,
        )

        plan = _get_active_weight_plan(db)
        if plan is not None and plan.feedback_enabled and plan.rhythm_affair_id is not None:
            _sync_weight_to_rhythm_checkin(db, weight, plan)
    except Exception as e:
        logger.warning(f"[body_data] Rhythm feedback sync failed: {e}")


# ============================================================================
# CRUD Implementation
# ============================================================================


def create_body_data_impl(db: Session, data: BodyDataCreateRequest) -> BodyDataResponse:
    """Create a new body data record (with weight dual-write)."""
    record = BodyData(
        htime=datetime.fromtimestamp(data.htime) if data.htime else datetime.now(),
        data={k: float(v) for k, v in data.data.items()},
        tag=data.tag,
        description=data.description,
        source="manual",
    )
    db.add(record)
    db.flush()

    weight: Optional[Weight] = None
    try:
        with db.begin_nested():  # SAVEPOINT：dual-write 失败不影响主记录
            weight = _create_dual_weight(db, record)
        db.commit()
    except Exception as e:
        logger.warning(f"[body_data] weight dual-write failed, body_data kept: {e}")
        db.commit()
    db.refresh(record)

    if weight is not None:
        _sync_weight_rhythm_feedback(db, weight)
    return read_from_body_data(record)


def read_body_data_impl(db: Session, record_id: int) -> Optional[BodyDataResponse]:
    """Read a single body data record by ID."""
    record = db.query(BodyData).filter(BodyData.id == record_id).first()
    return read_from_body_data(record) if record else None


def read_body_data_list_impl(
    db: Session,
    skip: int = 0,
    limit: int = -1,
    start_time: float = None,  # timestamp in seconds
    end_time: float = None,  # timestamp in seconds
    metric: str = None,  # metric key filter（Python 层过滤，见决策 D7）
) -> List[BodyDataResponse]:
    """Read body data records with time range and optional metric filter."""
    query = db.query(BodyData)
    if start_time is not None:
        query = query.filter(BodyData.htime >= datetime.fromtimestamp(start_time))
    if end_time is not None:
        query = query.filter(BodyData.htime <= datetime.fromtimestamp(end_time))
    records = query.order_by(BodyData.htime.asc()).all()

    results = [read_from_body_data(r) for r in records]
    if metric is not None:
        # 未测量语义：仅返回本次实际测了该指标的记录
        results = [r for r in results if metric in r.data]
    if skip:
        results = results[skip:]
    if limit != -1:
        results = results[:limit]
    return results


def update_body_data_impl(
    db: Session, record_id: int, data: BodyDataUpdateRequest
) -> Optional[BodyDataResponse]:
    """Update an existing body data record (with weight dual-write sync)."""
    record = db.query(BodyData).filter(BodyData.id == record_id).first()
    if record is None:
        return None

    new_data = {k: float(v) for k, v in data.data.items()} if data.data is not None else dict(record.data or {})
    new_htime = datetime.fromtimestamp(data.htime) if data.htime is not None else record.htime
    new_tag = data.tag if data.tag is not None else record.tag
    new_description = data.description if data.description is not None else record.description

    record.data = new_data
    record.htime = new_htime
    record.tag = new_tag
    record.description = new_description
    db.flush()

    try:
        with db.begin_nested():  # SAVEPOINT
            _sync_dual_weight_on_update(db, record, new_data, new_htime, new_tag, new_description)
        db.commit()
    except Exception as e:
        logger.warning(f"[body_data] weight dual-write sync failed, body_data kept: {e}")
        db.commit()
    db.refresh(record)
    return read_from_body_data(record)


def delete_body_data_impl(db: Session, record_id: int) -> bool:
    """Delete a body data record, cascading to the dual-written Weight row."""
    record = db.query(BodyData).filter(BodyData.id == record_id).first()
    if record is None:
        return False
    weight_id = record.weight_id
    db.delete(record)
    db.flush()
    if weight_id is not None:
        try:
            with db.begin_nested():  # SAVEPOINT：级联失败不阻塞主记录删除
                db.query(Weight).filter(Weight.id == weight_id).delete()
        except Exception as e:
            logger.warning(f"[body_data] cascade weight delete failed: {e}")
    db.commit()
    return True


# ============================================================================
# Metric schema & series
# ============================================================================


def get_metric_schema_impl(db: Session) -> List[BodyMetricDefinition]:
    """返回指标注册表：内置指标 + 扫描历史数据动态发现的自定义指标。"""
    metrics = [m.model_copy(deep=True) for m in BUILTIN_METRICS]
    seen = {m.key for m in metrics}

    # 扫描全部 body_data 的 data keys，发现自定义指标（builtin=false）
    custom_keys: Dict[str, int] = {}
    for (raw_data,) in db.query(BodyData.data).all():
        if not raw_data:
            continue
        for key in raw_data.keys():
            if key not in seen:
                custom_keys[key] = custom_keys.get(key, 0) + 1

    for key in sorted(custom_keys.keys()):
        metrics.append(
            BodyMetricDefinition(
                key=key,
                label_zh=key,
                label_en=key,
                unit="",
                category=BodyMetricCategory.BODY,
                precision=1,
                builtin=False,
            )
        )
    return metrics


def get_metric_series_impl(
    db: Session,
    metric: str,
    start_time: float = None,
    end_time: float = None,
) -> BodyDataSeriesResponse:
    """提取单指标时序（仅含实际测量了该指标的记录，按时间升序）。"""
    records = read_body_data_list_impl(db, 0, -1, start_time, end_time)
    points = [
        BodyDataSeriesPoint(id=r.id, htime=r.htime, value=float(r.data[metric]))
        for r in records
        if metric in r.data
    ]
    unit = BUILTIN_METRIC_MAP[metric].unit if metric in BUILTIN_METRIC_MAP else ""
    return BodyDataSeriesResponse(metric=metric, unit=unit, points=points)


# ============================================================================
# Trend analysis（泛化回归，weight 原端点共用核心）
# ============================================================================


def _analyze_series(
    points: List[Tuple[float, float]],
    model_type: str = "linear",
) -> dict:
    """对 (htime, value) 点集做回归分析（weight / 任意 body 指标共用核心）。

    Args:
        points: 按时间升序的 (timestamp_seconds, value) 点集
        model_type: 'linear' 或 'polynomial'（二阶）

    Returns:
        dict，包含 model_type / slope / intercept / r_squared /
        current_value / current_trend / predicted_points。
    """
    result = {
        "model_type": model_type,
        "slope": 0.0,
        "intercept": 0.0,
        "r_squared": 0.0,
        "current_value": 0.0,
        "current_trend": "stable",
        "predicted_points": [],
    }
    if len(points) < 2:
        return result

    first_time = points[0][0]
    x = np.array([(t - first_time) / 86400 for t, _ in points])  # days
    y = np.array([v for _, v in points])

    if model_type == "linear":
        coeffs = np.polyfit(x, y, 1)
        slope, intercept = coeffs[0], coeffs[1]
        y_pred = slope * x + intercept
    else:
        coeffs = np.polyfit(x, y, 2)
        slope = coeffs[0]
        intercept = coeffs[2]
        y_pred = np.polyval(coeffs, x)

    ss_res = np.sum((y - y_pred) ** 2)
    ss_tot = np.sum((y - np.mean(y)) ** 2)
    r_squared = 1 - (ss_res / ss_tot) if ss_tot != 0 else 0

    if slope < -0.05:
        trend = "decreasing"
    elif slope > 0.05:
        trend = "increasing"
    else:
        trend = "stable"

    predicted_points = [
        {"htime": t, "value": float(v), "is_actual": True} for t, v in points
    ]
    last_time = points[-1][0]
    last_day = (last_time - first_time) / 86400
    for day in range(1, 31):
        future_day = last_day + day
        future_time = last_time + day * 86400
        if model_type == "linear":
            pred_value = slope * future_day + intercept
        else:
            pred_value = np.polyval(coeffs, future_day)
        predicted_points.append(
            {"htime": float(future_time), "value": float(pred_value), "is_actual": False}
        )

    result.update(
        {
            "slope": float(slope),
            "intercept": float(intercept),
            "r_squared": float(r_squared),
            "current_value": float(points[-1][1]),
            "current_trend": trend,
            "predicted_points": predicted_points,
        }
    )
    return result


def analyze_body_metric_trend_impl(
    db: Session,
    metric: str,
    start_time: float = None,
    end_time: float = None,
    model_type: str = "linear",
) -> dict:
    """分析任意身体指标的趋势（numpy 回归，与 weight analysis 同核心）。"""
    series = get_metric_series_impl(db, metric, start_time, end_time)
    points = [(p.htime, p.value) for p in series.points]
    result = _analyze_series(points, model_type)
    result["metric"] = metric
    result["unit"] = series.unit
    return result
