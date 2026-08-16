# -*- coding: utf-8 -*-
# @file health.py
# @brief The Health Data Storage
# @author sailing-innocent
# @date 2025-04-24
# @version 1.0
# ---------------------------------

from sail_server.infrastructure.orm.health import (
    Weight,
    Exercise,
    WeightPlan,
    Sleep,
    EnergyLevel,
    Mood,
    HealthSignal,
)
from sail_server.application.dto.health import (
    WeightBase,
    WeightCreateRequest,
    WeightResponse,
    ExerciseBase,
    ExerciseCreateRequest,
    ExerciseResponse,
    WeightPlanBase,
    WeightPlanCreateRequest,
    WeightPlanUpdateRequest,
    WeightPlanResponse,
    WeightPlanCurveType,
    WeightExpectedRangeResponse,
    WeightExpectedPoint,
    SleepCreateRequest,
    SleepResponse,
    EnergyLevelCreateRequest,
    EnergyLevelResponse,
    MoodCreateRequest,
    MoodResponse,
    HealthSignalCreateRequest,
    HealthSignalResponse,
)
import numpy as np
from datetime import datetime, date, timedelta
from sqlalchemy import func
from sqlalchemy import func, cast, Float


# ===================================================
# Weight Plan Helpers
# ===================================================


def _resolve_initial_weight(db, plan: WeightPlan) -> float:
    """解析计划起始体重。

    优先使用 plan.initial_weight；未设置时取 start_time 之后第一次记录；
    仍不存在时取 start_time 之前最近一条记录；否则回退到目标体重。
    """
    if plan.initial_weight is not None:
        try:
            return float(plan.initial_weight)
        except (ValueError, TypeError):
            pass

    start_dt = plan.start_time
    # start_time 之后的第一次记录
    after = (
        db.query(Weight)
        .filter(Weight.htime >= start_dt)
        .order_by(Weight.htime.asc())
        .first()
    )
    if after is not None:
        return float(after.value)

    # start_time 之前最近一条记录
    before = (
        db.query(Weight)
        .filter(Weight.htime < start_dt)
        .order_by(Weight.htime.desc())
        .first()
    )
    if before is not None:
        return float(before.value)

    return float(plan.target_weight)


def _compute_expected_weight(
    initial_weight: float, target_weight: float, progress: float, curve_type: str
) -> float:
    """根据曲线类型计算预期体重。

    progress 已裁剪到 [0, 1]。
    - linear: 线性插值
    - polynomial: 二次缓出 (ease-out)，前期变化快、后期慢
    - exponential: 指数缓出
    """
    progress = max(0.0, min(1.0, progress))
    if curve_type == WeightPlanCurveType.POLYNOMIAL.value:
        # ease-out quad: 1 - (1 - p)^2 = p * (2 - p)
        t = progress * (2.0 - progress)
    elif curve_type == WeightPlanCurveType.EXPONENTIAL.value:
        # (1 - exp(-k * p)) / (1 - exp(-k)), k=3
        k = 3.0
        t = (1.0 - np.exp(-k * progress)) / (1.0 - np.exp(-k))
    else:
        # linear (default)
        t = progress
    return initial_weight + (target_weight - initial_weight) * t


def _get_active_weight_plan(db) -> WeightPlan | None:
    """获取最近创建且未过期的活跃体重计划。"""
    now = datetime.now()
    return (
        db.query(WeightPlan)
        .filter(WeightPlan.target_time >= now)
        .order_by(WeightPlan.created_at.desc())
        .first()
    )


def _get_weight_plan_by_id(db, plan_id: int) -> WeightPlan | None:
    """按 ID 获取体重计划。"""
    return db.query(WeightPlan).filter(WeightPlan.id == plan_id).first()


# ===================================================
# Weight Implementation
# ===================================================


def read_from_weight(weight: Weight) -> WeightResponse:
    """Convert Weight ORM to WeightResponse"""
    return WeightResponse(
        id=weight.id,
        value=float(weight.value),
        htime=weight.htime.timestamp(),
        tag=weight.tag,
        description=weight.description,
    )


def create_weight_impl(db, weight_create: WeightCreateRequest) -> WeightResponse:
    """Create a new weight record"""
    weight = Weight(
        value=str(weight_create.value),
        htime=datetime.fromtimestamp(weight_create.htime)
        if weight_create.htime
        else datetime.now(),
        tag=weight_create.tag,
        description=weight_create.description,
    )
    db.add(weight)
    db.commit()
    db.refresh(weight)

    # 若存在启用 feedback 的活跃体重计划，同步写入 Rhythm 打卡日志
    try:
        plan = _get_active_weight_plan(db)
        if plan is not None and plan.feedback_enabled and plan.rhythm_affair_id is not None:
            _sync_weight_to_rhythm_checkin(db, weight, plan)
    except Exception as e:
        # Rhythm 联动失败不应阻塞体重记录保存
        import logging

        logging.getLogger(__name__).warning(f"[health] Rhythm feedback sync failed: {e}")

    return read_from_weight(weight)


def read_weight_impl(
    db, weight_record_id: int = -1, _tag: str = None
) -> WeightResponse | None:
    """Read a single weight record by ID or tag"""
    q = db.query(Weight)
    if _tag is not None:
        q = q.filter(Weight.tag == _tag)
    if weight_record_id != -1:
        q = q.filter(Weight.id == weight_record_id)
    weight = q.first()
    return read_from_weight(weight) if weight else None


def read_weights_impl(
    db,
    skip: int = 0,
    limit: int = -1,
    start_time: float = None,  # timestamp in seconds
    end_time: float = None,  # timestamp in seconds
    _tag: str = "raw",
) -> list[WeightResponse]:
    """Read multiple weight records with filtering"""
    query = db.query(Weight)
    if _tag is not None:
        query = query.filter(Weight.tag == _tag)
    if start_time is not None:
        query = query.filter(Weight.htime >= datetime.fromtimestamp(start_time))
    if end_time is not None:
        query = query.filter(Weight.htime <= datetime.fromtimestamp(end_time))
    weights = query.order_by(Weight.htime).offset(skip)
    if limit != -1:
        weights = weights.limit(limit)
    weights = weights.all()
    res = [read_from_weight(weight) for weight in weights]
    return res


def read_weights_avg_impl(
    db,
    start_time: float = None,  # timestamp in seconds
    end_time: float = None,  # timestamp in seconds
    _tag: str = "raw",
) -> float | None:
    """Calculate average weight in a time range"""
    query = db.query(func.avg(cast(Weight.value, Float)))
    if _tag is not None:
        query = query.filter(Weight.tag == _tag)
    if start_time is not None:
        query = query.filter(Weight.htime >= datetime.fromtimestamp(start_time))
    if end_time is not None:
        query = query.filter(Weight.htime <= datetime.fromtimestamp(end_time))

    return query.scalar()


def update_weight_impl(db, id: int, weight: WeightBase) -> WeightResponse | None:
    """Update an existing weight record"""
    weight_rec = db.query(Weight).filter(Weight.id == id).first()
    if weight_rec is None:
        return None
    weight_rec.value = str(weight.value)
    # Note: htime is not in WeightBase, so we don't update it here
    weight_rec.tag = weight.tag
    weight_rec.description = weight.description
    db.commit()
    return read_weight_impl(db, id)


def delete_weight_impl(db, id=None):
    """Delete weight record(s)"""
    if id is not None:
        db.query(Weight).filter(Weight.id == id).delete()
    else:
        db.query(Weight).delete()
    db.commit()


def target_weight_impl(db, target_date: date) -> dict | None:
    """
    Get the expected weight for a specific date based on the active weight plan.
    """
    plan = _get_active_weight_plan(db)
    if plan is None:
        return None

    if target_date < plan.start_time.date():
        return None

    start_weight = _resolve_initial_weight(db, plan)
    target_weight = float(plan.target_weight)
    total_days = (plan.target_time.date() - plan.start_time.date()).days
    days_passed = (target_date - plan.start_time.date()).days
    progress = min(days_passed / total_days, 1.0) if total_days > 0 else 1.0

    expected = _compute_expected_weight(
        start_weight, target_weight, progress, plan.curve_type or WeightPlanCurveType.LINEAR.value
    )
    return {
        "plan_id": plan.id,
        "value": expected,
        "htime": datetime.combine(target_date, datetime.min.time()).timestamp(),
        "tag": "target",
        "curve_type": plan.curve_type or WeightPlanCurveType.LINEAR.value,
        "description": f"Expected weight from plan #{plan.id}",
    }


# ===================================================
# Weight Analysis and Prediction
# ===================================================


def analyze_weight_trend_impl(
    db,
    start_time: float = None,
    end_time: float = None,
    model_type: str = "linear",
) -> dict:
    """
    Analyze weight trend using statistical models.

    Args:
        start_time: Start timestamp for analysis window
        end_time: End timestamp for analysis window
        model_type: 'linear' or 'polynomial'

    Returns:
        Dict with model parameters and predictions
    """
    # Get weights in time range
    weights = read_weights_impl(db, 0, -1, start_time, end_time, "raw")

    if len(weights) < 2:
        return {
            "model_type": model_type,
            "slope": 0.0,
            "intercept": 0.0,
            "r_squared": 0.0,
            "current_weight": 0.0,
            "current_trend": "stable",
            "predicted_weights": [],
        }

    # Convert to numpy arrays
    # Use days since first measurement as x
    first_time = weights[0].htime
    x = np.array([(w.htime - first_time) / 86400 for w in weights])  # days
    y = np.array([float(w.value) for w in weights])

    # Linear regression
    if model_type == "linear":
        coeffs = np.polyfit(x, y, 1)
        slope, intercept = coeffs[0], coeffs[1]

        # Calculate R-squared
        y_pred = slope * x + intercept
        ss_res = np.sum((y - y_pred) ** 2)
        ss_tot = np.sum((y - np.mean(y)) ** 2)
        r_squared = 1 - (ss_res / ss_tot) if ss_tot != 0 else 0
    else:
        # Polynomial regression (degree 2)
        coeffs = np.polyfit(x, y, 2)
        slope = coeffs[0]  # Store leading coefficient
        intercept = coeffs[2]  # Store constant term

        # Calculate R-squared for polynomial
        y_pred = np.polyval(coeffs, x)
        ss_res = np.sum((y - y_pred) ** 2)
        ss_tot = np.sum((y - np.mean(y)) ** 2)
        r_squared = 1 - (ss_res / ss_tot) if ss_tot != 0 else 0

    # Determine trend
    if slope < -0.05:
        trend = "decreasing"
    elif slope > 0.05:
        trend = "increasing"
    else:
        trend = "stable"

    # Generate predicted weights for visualization (actual + 30 days prediction)
    predicted_weights = []

    # Add actual data points
    for w in weights:
        predicted_weights.append(
            {
                "htime": w.htime,
                "value": float(w.value),
                "is_actual": True,
            }
        )

    # Add prediction points for next 30 days
    last_time = weights[-1].htime
    last_day = (last_time - first_time) / 86400

    for day in range(1, 31):
        future_day = last_day + day
        future_time = last_time + day * 86400

        if model_type == "linear":
            pred_value = slope * future_day + intercept
        else:
            pred_value = np.polyval(coeffs, future_day)

        predicted_weights.append(
            {
                "htime": future_time,
                "value": float(pred_value),
                "is_actual": False,
            }
        )

    return {
        "model_type": model_type,
        "slope": float(slope),
        "intercept": float(intercept),
        "r_squared": float(r_squared),
        "current_weight": float(weights[-1].value),
        "current_trend": trend,
        "predicted_weights": predicted_weights,
    }


def predict_weight_impl(
    db,
    target_timestamp: float,
    model_type: str = "linear",
    start_time: float = None,
    end_time: float = None,
) -> float:
    """
    Predict weight at a specific future timestamp.

    Args:
        target_timestamp: Target timestamp for prediction
        model_type: 'linear' or 'polynomial'
        start_time: Analysis window start
        end_time: Analysis window end

    Returns:
        Predicted weight value
    """
    weights = read_weights_impl(db, 0, -1, start_time, end_time, "raw")

    if len(weights) < 2:
        return 0.0

    first_time = weights[0].htime
    x = np.array([(w.htime - first_time) / 86400 for w in weights])
    y = np.array([float(w.value) for w in weights])

    if model_type == "linear":
        coeffs = np.polyfit(x, y, 1)
        slope, intercept = coeffs[0], coeffs[1]
        target_day = (target_timestamp - first_time) / 86400
        predicted = slope * target_day + intercept
    else:
        coeffs = np.polyfit(x, y, 2)
        target_day = (target_timestamp - first_time) / 86400
        predicted = np.polyval(coeffs, target_day)

    return float(predicted)


# ===================================================
# Weight Plan Implementation
# ===================================================


def read_from_weight_plan(plan: WeightPlan) -> WeightPlanResponse:
    """Convert WeightPlan ORM to WeightPlanResponse"""
    return WeightPlanResponse(
        id=plan.id,
        target_weight=plan.target_weight,
        initial_weight=plan.initial_weight,
        curve_type=plan.curve_type or WeightPlanCurveType.LINEAR.value,
        start_time=plan.start_time,
        target_time=plan.target_time,
        description=plan.description,
        created_at=plan.created_at,
        notify_enabled=bool(plan.notify_enabled),
        notify_time=plan.notify_time or "08:30",
        feedback_enabled=bool(plan.feedback_enabled),
        rhythm_affair_id=plan.rhythm_affair_id,
    )


def _create_or_update_weight_plan_affair(
    db, plan: WeightPlan, title: str = "记录体重"
) -> int | None:
    """为体重计划创建或更新 Rhythm 提醒事务（PRECEPT）。

    返回 affair_id，失败时返回 None（不阻塞计划保存）。
    """
    from sail_server.infrastructure.orm.rhythm import RhythmAffair
    from sail_server.application.dto.rhythm import AffairKind, AffairDomain, AffairState

    try:
        if plan.rhythm_affair_id is not None:
            affair = (
                db.query(RhythmAffair)
                .filter(RhythmAffair.id == plan.rhythm_affair_id)
                .first()
            )
            if affair is not None:
                affair.state = AffairState.ACTIVE.value
                affair.title = title
                affair.kind_meta = {
                    "rule_text": title,
                    "cycle": "daily",
                    "check_time": plan.notify_time or "08:30",
                    "severity": "soft",
                }
                affair.info_collection_type = "weight"
                db.commit()
                db.refresh(affair)
                return affair.id

        affair = RhythmAffair(
            title=title,
            kind=AffairKind.PRECEPT.value,
            domain=AffairDomain.LIFE.value,
            state=AffairState.ACTIVE.value,
            info_collection_type="weight",
            kind_meta={
                "rule_text": title,
                "cycle": "daily",
                "check_time": plan.notify_time or "08:30",
                "severity": "soft",
            },
        )
        db.add(affair)
        db.commit()
        db.refresh(affair)
        return affair.id
    except Exception as e:
        import logging

        logging.getLogger(__name__).warning(f"[health] create/update weight plan affair failed: {e}")
        db.rollback()
        return None


def _archive_weight_plan_affair(db, plan: WeightPlan) -> None:
    """将体重计划关联的 Rhythm 事务归档。"""
    from sail_server.infrastructure.orm.rhythm import RhythmAffair
    from sail_server.application.dto.rhythm import AffairState

    if plan.rhythm_affair_id is None:
        return
    affair = (
        db.query(RhythmAffair)
        .filter(RhythmAffair.id == plan.rhythm_affair_id)
        .first()
    )
    if affair is not None:
        affair.state = AffairState.ARCHIVED.value
        db.commit()


def _sync_weight_to_rhythm_checkin(db, weight: Weight, plan: WeightPlan) -> None:
    """将体重记录同步为 Rhythm 打卡日志。"""
    from sail_server.infrastructure.orm.rhythm import (
        RhythmAffair,
        RhythmDisciplineLog,
    )
    from sail_server.application.dto.rhythm import CheckinResult

    affair_id = plan.rhythm_affair_id
    if affair_id is None:
        return
    affair = db.query(RhythmAffair).filter(RhythmAffair.id == affair_id).first()
    if affair is None:
        return

    log_date = weight.htime.date()
    log = RhythmDisciplineLog(
        affair_id=affair.id,
        log_date=log_date,
        cycle_key=log_date.isoformat(),
        result=CheckinResult.DONE.value,
        note=f"体重 {weight.value} kg",
        source="weight_plan",
    )
    db.add(log)
    db.commit()


def create_weight_plan_impl(
    db, plan_data: WeightPlanCreateRequest
) -> WeightPlanResponse:
    """Create a new weight plan"""
    plan = WeightPlan(
        target_weight=plan_data.target_weight,
        initial_weight=plan_data.initial_weight,
        curve_type=(
            plan_data.curve_type.value
            if isinstance(plan_data.curve_type, WeightPlanCurveType)
            else str(plan_data.curve_type)
        ),
        start_time=plan_data.start_time if plan_data.start_time else datetime.now(),
        target_time=plan_data.target_time if plan_data.target_time else datetime.now(),
        description=plan_data.description,
        notify_enabled=plan_data.notify_enabled,
        notify_time=plan_data.notify_time or "08:30",
        feedback_enabled=plan_data.feedback_enabled,
    )
    db.add(plan)
    db.commit()
    db.refresh(plan)

    if plan.notify_enabled or plan.feedback_enabled:
        affair_id = _create_or_update_weight_plan_affair(db, plan)
        if affair_id is not None:
            plan.rhythm_affair_id = affair_id
            db.commit()
            db.refresh(plan)

    return read_from_weight_plan(plan)


def update_weight_plan_impl(
    db, plan_id: int, plan_data: WeightPlanUpdateRequest
) -> WeightPlanResponse | None:
    """Update an existing weight plan."""
    plan = db.query(WeightPlan).filter(WeightPlan.id == plan_id).first()
    if plan is None:
        return None

    if plan_data.target_weight is not None:
        plan.target_weight = plan_data.target_weight
    if plan_data.initial_weight is not None:
        plan.initial_weight = plan_data.initial_weight
    if plan_data.curve_type is not None:
        plan.curve_type = (
            plan_data.curve_type.value
            if isinstance(plan_data.curve_type, WeightPlanCurveType)
            else str(plan_data.curve_type)
        )
    if plan_data.start_time is not None:
        plan.start_time = plan_data.start_time
    if plan_data.target_time is not None:
        plan.target_time = plan_data.target_time
    if plan_data.description is not None:
        plan.description = plan_data.description
    if plan_data.notify_enabled is not None:
        plan.notify_enabled = plan_data.notify_enabled
    if plan_data.notify_time is not None:
        plan.notify_time = plan_data.notify_time
    if plan_data.feedback_enabled is not None:
        plan.feedback_enabled = plan_data.feedback_enabled

    db.commit()
    db.refresh(plan)

    if plan.notify_enabled or plan.feedback_enabled:
        affair_id = _create_or_update_weight_plan_affair(db, plan)
        if affair_id is not None:
            plan.rhythm_affair_id = affair_id
            db.commit()
            db.refresh(plan)
    elif plan.rhythm_affair_id is not None:
        _archive_weight_plan_affair(db, plan)

    return read_from_weight_plan(plan)


def delete_weight_plan_impl(db, plan_id: int) -> dict | None:
    """Delete a weight plan and archive its Rhythm affair."""
    plan = db.query(WeightPlan).filter(WeightPlan.id == plan_id).first()
    if plan is None:
        return None

    _archive_weight_plan_affair(db, plan)

    db.delete(plan)
    db.commit()
    return {"id": plan_id, "status": "deleted"}


def get_active_weight_plan_impl(db) -> WeightPlanResponse | None:
    """Get the most recent active weight plan"""
    plan = _get_active_weight_plan(db)
    return read_from_weight_plan(plan) if plan else None


def get_weight_plan_by_id_impl(db, plan_id: int) -> WeightPlanResponse | None:
    """Get a weight plan by ID."""
    plan = _get_weight_plan_by_id(db, plan_id)
    return read_from_weight_plan(plan) if plan else None


def get_weight_plan_progress_impl(db, plan_id: int = None) -> dict | None:
    """
    Calculate weight plan progress with daily predictions.

    Returns control rate (0-100) and daily expected vs actual weights.
    """
    plan = _get_weight_plan_by_id(db, plan_id) if plan_id else _get_active_weight_plan(db)

    if not plan:
        return None

    plan_data = read_from_weight_plan(plan)
    now = datetime.now().timestamp()

    start_weight = _resolve_initial_weight(db, plan)
    target_weight = float(plan_data.target_weight)
    total_days = (
        plan_data.target_time.timestamp() - plan_data.start_time.timestamp()
    ) / 86400
    days_passed = (now - plan_data.start_time.timestamp()) / 86400
    progress_ratio = min(days_passed / total_days, 1.0) if total_days > 0 else 1.0

    expected_current_weight = _compute_expected_weight(
        start_weight, target_weight, progress_ratio, plan_data.curve_type
    )

    # Get actual weights from plan start to now
    actual_weights = read_weights_impl(
        db, 0, -1, plan_data.start_time.timestamp(), now, "raw"
    )

    current_weight = 0.0
    control_rate = 0.0
    is_on_track = False

    if actual_weights:
        current_weight = float(actual_weights[-1].value)

        # 方向感知控制率：减重计划低于预期为优，增重计划高于预期为优
        weight_direction = 1 if target_weight > start_weight else -1
        direction_diff = weight_direction * (current_weight - expected_current_weight)
        # 2kg 容差：在正确方向或偏差 <= 2kg 时控制率 100%
        control_rate = max(0.0, 100.0 - max(0.0, direction_diff) / 2.0 * 100.0)
        is_on_track = control_rate >= 50.0

    # Generate daily predictions for the entire plan period
    daily_predictions = []
    total_days_int = max(0, int(total_days)) + 1

    # Build a map of actual weights by day index for status calculation
    actual_by_day: dict[int, float] = {}
    for w in actual_weights:
        w_day = int((w.htime - plan_data.start_time.timestamp()) / 86400)
        # Keep the latest record of the day
        actual_by_day[w_day] = float(w.value)

    tolerance = 0.5
    for day in range(total_days_int + 1):
        day_time = plan_data.start_time.timestamp() + day * 86400
        day_progress = day / total_days if total_days > 0 else 1.0
        expected_weight = _compute_expected_weight(
            start_weight, target_weight, day_progress, plan_data.curve_type
        )
        actual_for_day = actual_by_day.get(day)

        status = "normal"
        if actual_for_day is not None:
            diff = actual_for_day - expected_weight
            if diff > tolerance:
                status = "above"
            elif diff < -tolerance:
                status = "below"

        daily_predictions.append(
            {
                "htime": day_time,
                "expected_weight": float(expected_weight),
                "actual_weight": actual_for_day,
                "day": day,
                "status": status,
            }
        )

    return {
        "plan": plan_data.model_dump(),
        "control_rate": float(control_rate),
        "current_weight": float(current_weight),
        "expected_current_weight": float(expected_current_weight),
        "daily_predictions": daily_predictions,
        "is_on_track": is_on_track,
    }


def get_weight_plan_checkin_status_impl(db, plan_id: int = None) -> dict | None:
    """获取体重计划关联的 Rhythm 打卡状态（今日是否打卡 + 连续打卡天数）。"""
    from sail_server.infrastructure.orm.rhythm import RhythmDisciplineLog

    plan = _get_weight_plan_by_id(db, plan_id) if plan_id else _get_active_weight_plan(db)
    if plan is None or plan.rhythm_affair_id is None:
        return None

    affair_id = plan.rhythm_affair_id
    today = date.today()
    logs = (
        db.query(RhythmDisciplineLog)
        .filter(
            RhythmDisciplineLog.affair_id == affair_id,
            RhythmDisciplineLog.result == "done",
        )
        .order_by(RhythmDisciplineLog.log_date.desc())
        .all()
    )

    today_done = any(log.log_date == today for log in logs)

    # 计算连续打卡天数（从最近一天往前数，允许今天未打卡时从昨天开始）
    streak = 0
    if logs:
        check_day = today if today_done else today - timedelta(days=1)
        dates = sorted({log.log_date for log in logs}, reverse=True)
        for d in dates:
            if d == check_day:
                streak += 1
                check_day -= timedelta(days=1)
            elif d > check_day:
                continue
            else:
                break

    return {
        "plan_id": plan.id,
        "affair_id": affair_id,
        "today_done": today_done,
        "streak": streak,
    }


def get_expected_weights_impl(
    db,
    start_time: float,
    end_time: float,
    plan_id: int = None,
) -> WeightExpectedRangeResponse | None:
    """返回 [start_time, end_time] 闭区间内每一天的预期体重。

    区间早于计划开始：使用 initial_weight 填充。
    区间晚于计划结束：使用 target_weight 填充。
    区间内跨计划起止：按 curve_type 分段计算。
    """
    if start_time is None or end_time is None or start_time > end_time:
        return None

    plan = _get_weight_plan_by_id(db, plan_id) if plan_id else _get_active_weight_plan(db)
    if not plan:
        return None

    plan_data = read_from_weight_plan(plan)
    start_weight = _resolve_initial_weight(db, plan)
    target_weight = float(plan_data.target_weight)
    plan_start_ts = plan_data.start_time.timestamp()
    plan_end_ts = plan_data.target_time.timestamp()
    total_days = (plan_end_ts - plan_start_ts) / 86400

    start_date = datetime.fromtimestamp(start_time).date()
    end_date = datetime.fromtimestamp(end_time).date()

    points = []
    day = start_date
    while day <= end_date:
        day_ts = datetime.combine(day, datetime.min.time()).timestamp()
        if day_ts <= plan_start_ts:
            expected = start_weight
        elif day_ts >= plan_end_ts:
            expected = target_weight
        else:
            progress = (day_ts - plan_start_ts) / 86400 / total_days if total_days > 0 else 1.0
            expected = _compute_expected_weight(
                start_weight, target_weight, progress, plan_data.curve_type
            )
        points.append(WeightExpectedPoint(htime=day_ts, expected_weight=float(expected)))
        day += timedelta(days=1)

    return WeightExpectedRangeResponse(plan=plan_data, points=points)


def get_weights_with_plan_status_impl(
    db,
    start_time: float = None,
    end_time: float = None,
    plan_id: int = None,
) -> list[dict]:
    """
    Get weight records with comparison status against plan.

    Args:
        start_time: Start timestamp for weight records (None = no limit)
        end_time: End timestamp for weight records (None = no limit)
        plan_id: Specific plan ID, or None to use latest plan

    Returns:
        List of dicts with comparison info
    """
    plan = _get_weight_plan_by_id(db, plan_id) if plan_id else _get_active_weight_plan(db)

    # Get weight records (no default time limit, return all if not specified)
    weights = read_weights_impl(db, 0, -1, start_time, end_time, "raw")

    if not plan:
        # No plan, return records without status
        return [
            {
                "id": w.id,
                "value": float(w.value),
                "htime": w.htime,
                "expected_value": 0.0,
                "status": "normal",
                "diff": 0.0,
            }
            for w in weights
        ]

    plan_data = read_from_weight_plan(plan)
    start_weight = _resolve_initial_weight(db, plan)
    target_weight = float(plan_data.target_weight)
    total_days = (
        plan_data.target_time.timestamp() - plan_data.start_time.timestamp()
    ) / 86400

    # Calculate status for each weight record
    result = []
    tolerance = 0.5  # kg tolerance for "normal" status

    for w in weights:
        weight_value = float(w.value)
        weight_time = w.htime

        # Calculate expected weight at this time
        if weight_time < plan_data.start_time.timestamp():
            # Before plan start, no expectation
            expected_value = weight_value
            diff = 0.0
            status = "normal"
        elif weight_time > plan_data.target_time.timestamp():
            # After plan end, use target weight
            expected_value = target_weight
            diff = weight_value - expected_value
            if diff > tolerance:
                status = "above"
            elif diff < -tolerance:
                status = "below"
            else:
                status = "normal"
        else:
            # During plan period, interpolate using curve type
            days_from_start = (weight_time - plan_data.start_time.timestamp()) / 86400
            progress = days_from_start / total_days if total_days > 0 else 1.0
            expected_value = _compute_expected_weight(
                start_weight, target_weight, progress, plan_data.curve_type
            )

            diff = weight_value - expected_value
            if diff > tolerance:
                status = "above"  # Above expected (red)
            elif diff < -tolerance:
                status = "below"  # Below expected (green)
            else:
                status = "normal"  # Within tolerance (blue)

        result.append(
            {
                "id": w.id,
                "value": weight_value,
                "htime": weight_time,
                "expected_value": float(expected_value),
                "status": status,
                "diff": float(diff),
            }
        )

    return result
    return result


# ===================================================
# Exercise implementations
# ===================================================


def read_from_exercise(exercise: Exercise) -> ExerciseResponse:
    """Convert Exercise ORM to ExerciseResponse"""
    return ExerciseResponse(
        id=exercise.id,
        htime=exercise.htime.timestamp(),
        description=exercise.description,
    )


def create_exercise_impl(
    db, exercise_create: ExerciseCreateRequest
) -> ExerciseResponse:
    """Create a new exercise record"""
    exercise = Exercise(
        htime=datetime.fromtimestamp(exercise_create.htime)
        if exercise_create.htime
        else datetime.now(),
        description=exercise_create.description,
    )
    db.add(exercise)
    db.commit()
    db.refresh(exercise)
    return read_from_exercise(exercise)


def read_exercise_impl(db, exercise_id: int = -1) -> ExerciseResponse | None:
    """Read a single exercise record by ID"""
    exercise = db.query(Exercise).filter(Exercise.id == exercise_id).first()
    return read_from_exercise(exercise) if exercise else None


def read_exercises_impl(
    db,
    skip: int = 0,
    limit: int = -1,
    start_time: float = None,
    end_time: float = None,
) -> list[ExerciseResponse]:
    """Read multiple exercise records with filtering"""
    query = db.query(Exercise)
    if start_time is not None:
        query = query.filter(Exercise.htime >= datetime.fromtimestamp(start_time))
    if end_time is not None:
        query = query.filter(Exercise.htime <= datetime.fromtimestamp(end_time))
    exercises = query.order_by(Exercise.htime.desc()).offset(skip)
    if limit != -1:
        exercises = exercises.limit(limit)
    exercises = exercises.all()
    return [read_from_exercise(exercise) for exercise in exercises]


def update_exercise_impl(
    db, id: int, exercise: ExerciseBase
) -> ExerciseResponse | None:
    """Update an existing exercise record"""
    exercise_rec = db.query(Exercise).filter(Exercise.id == id).first()
    if exercise_rec is None:
        return None
    # Note: htime is not in ExerciseBase, so we don't update it here
    exercise_rec.description = exercise.description
    db.commit()
    return read_exercise_impl(db, id)


def delete_exercise_impl(db, id=None):
    """Delete exercise record(s)"""
    if id is not None:
        db.query(Exercise).filter(Exercise.id == id).delete()
    else:
        db.query(Exercise).delete()
    db.commit()

# ===================================================
# Sleep implementations
# ===================================================


def _sleep_hours_to_minutes(hours: float) -> int:
    return int(round(hours * 60))


def _sleep_minutes_to_hours(minutes: int) -> float:
    return round(minutes / 60.0, 2)


def read_from_sleep(sleep: Sleep) -> SleepResponse:
    """Convert Sleep ORM to SleepResponse"""
    return SleepResponse(
        id=sleep.id,
        day_id=sleep.day_id,
        hours=_sleep_minutes_to_hours(sleep.hours),
        quality=sleep.quality,
        description=sleep.description,
        htime=sleep.htime.timestamp() if sleep.htime else None,
    )


def create_sleep_impl(db, sleep_create: SleepCreateRequest) -> SleepResponse:
    """Create a new sleep record"""
    htime = datetime.now()
    if sleep_create.htime:
        htime = datetime.fromtimestamp(sleep_create.htime)
    sleep = Sleep(
        day_id=sleep_create.day_id,
        htime=htime,
        hours=_sleep_hours_to_minutes(sleep_create.hours),
        quality=sleep_create.quality,
        description=sleep_create.description,
    )
    db.add(sleep)
    db.commit()
    db.refresh(sleep)
    return read_from_sleep(sleep)


def read_sleep_impl(db, sleep_id: int) -> SleepResponse | None:
    """Read a single sleep record by ID"""
    sleep = db.query(Sleep).filter(Sleep.id == sleep_id).first()
    return read_from_sleep(sleep) if sleep else None


def read_sleeps_impl(
    db,
    skip: int = 0,
    limit: int = -1,
    day_id: int = None,
    start_time: float = None,
    end_time: float = None,
) -> list[SleepResponse]:
    """Read multiple sleep records with filtering"""
    query = db.query(Sleep)
    if day_id is not None:
        query = query.filter(Sleep.day_id == day_id)
    if start_time is not None:
        query = query.filter(Sleep.htime >= datetime.fromtimestamp(start_time))
    if end_time is not None:
        query = query.filter(Sleep.htime <= datetime.fromtimestamp(end_time))
    query = query.order_by(Sleep.htime.desc()).offset(skip)
    if limit != -1:
        query = query.limit(limit)
    sleeps = query.all()
    return [read_from_sleep(s) for s in sleeps]


# ===================================================
# Energy Level implementations
# ===================================================


def read_from_energy_level(energy: EnergyLevel) -> EnergyLevelResponse:
    """Convert EnergyLevel ORM to EnergyLevelResponse"""
    return EnergyLevelResponse(
        id=energy.id,
        day_id=energy.day_id,
        score=energy.score,
        description=energy.description,
        htime=energy.htime.timestamp() if energy.htime else None,
    )


def create_energy_level_impl(
    db, energy_create: EnergyLevelCreateRequest
) -> EnergyLevelResponse:
    """Create a new energy level record"""
    htime = datetime.now()
    if energy_create.htime:
        htime = datetime.fromtimestamp(energy_create.htime)
    energy = EnergyLevel(
        day_id=energy_create.day_id,
        htime=htime,
        score=energy_create.score,
        description=energy_create.description,
    )
    db.add(energy)
    db.commit()
    db.refresh(energy)
    return read_from_energy_level(energy)


def read_energy_level_impl(db, energy_id: int) -> EnergyLevelResponse | None:
    """Read a single energy level record by ID"""
    energy = db.query(EnergyLevel).filter(EnergyLevel.id == energy_id).first()
    return read_from_energy_level(energy) if energy else None


def read_energy_levels_impl(
    db,
    skip: int = 0,
    limit: int = -1,
    day_id: int = None,
    start_time: float = None,
    end_time: float = None,
) -> list[EnergyLevelResponse]:
    """Read multiple energy level records with filtering"""
    query = db.query(EnergyLevel)
    if day_id is not None:
        query = query.filter(EnergyLevel.day_id == day_id)
    if start_time is not None:
        query = query.filter(EnergyLevel.htime >= datetime.fromtimestamp(start_time))
    if end_time is not None:
        query = query.filter(EnergyLevel.htime <= datetime.fromtimestamp(end_time))
    query = query.order_by(EnergyLevel.htime.desc()).offset(skip)
    if limit != -1:
        query = query.limit(limit)
    energies = query.all()
    return [read_from_energy_level(e) for e in energies]


# ===================================================
# Mood implementations
# ===================================================


def read_from_mood(mood: Mood) -> MoodResponse:
    """Convert Mood ORM to MoodResponse"""
    return MoodResponse(
        id=mood.id,
        day_id=mood.day_id,
        score=mood.score,
        description=mood.description,
        htime=mood.htime.timestamp() if mood.htime else None,
    )


def create_mood_impl(db, mood_create: MoodCreateRequest) -> MoodResponse:
    """Create a new mood record"""
    htime = datetime.now()
    if mood_create.htime:
        htime = datetime.fromtimestamp(mood_create.htime)
    mood = Mood(
        day_id=mood_create.day_id,
        htime=htime,
        score=mood_create.score,
        description=mood_create.description,
    )
    db.add(mood)
    db.commit()
    db.refresh(mood)
    return read_from_mood(mood)


def read_mood_impl(db, mood_id: int) -> MoodResponse | None:
    """Read a single mood record by ID"""
    mood = db.query(Mood).filter(Mood.id == mood_id).first()
    return read_from_mood(mood) if mood else None


def read_moods_impl(
    db,
    skip: int = 0,
    limit: int = -1,
    day_id: int = None,
    start_time: float = None,
    end_time: float = None,
) -> list[MoodResponse]:
    """Read multiple mood records with filtering"""
    query = db.query(Mood)
    if day_id is not None:
        query = query.filter(Mood.day_id == day_id)
    if start_time is not None:
        query = query.filter(Mood.htime >= datetime.fromtimestamp(start_time))
    if end_time is not None:
        query = query.filter(Mood.htime <= datetime.fromtimestamp(end_time))
    query = query.order_by(Mood.htime.desc()).offset(skip)
    if limit != -1:
        query = query.limit(limit)
    moods = query.all()
    return [read_from_mood(m) for m in moods]


# ===================================================
# HealthSignal implementations
# ===================================================


def read_from_health_signal(signal: HealthSignal) -> HealthSignalResponse:
    """Convert HealthSignal ORM to HealthSignalResponse"""
    return HealthSignalResponse(
        id=signal.id,
        signal_type=signal.signal_type,
        ref_id=signal.ref_id,
        day_id=signal.day_id,
        htime=signal.htime.timestamp() if signal.htime else None,
        value_json=signal.value_json or {},
        score=signal.score,
    )


def create_health_signal_impl(
    db, signal_create: HealthSignalCreateRequest
) -> HealthSignalResponse:
    """Create a new health signal index"""
    htime = datetime.now()
    if signal_create.htime:
        htime = datetime.fromtimestamp(signal_create.htime)
    signal = HealthSignal(
        signal_type=signal_create.signal_type,
        ref_id=signal_create.ref_id,
        day_id=signal_create.day_id,
        htime=htime,
        value_json=signal_create.value_json or {},
        score=signal_create.score,
    )
    db.add(signal)
    db.commit()
    db.refresh(signal)
    return read_from_health_signal(signal)


def read_health_signals_impl(
    db,
    skip: int = 0,
    limit: int = -1,
    day_id: int = None,
    signal_type: str = None,
    start_time: float = None,
    end_time: float = None,
) -> list[HealthSignalResponse]:
    """Read multiple health signals with filtering"""
    query = db.query(HealthSignal)
    if day_id is not None:
        query = query.filter(HealthSignal.day_id == day_id)
    if signal_type is not None:
        query = query.filter(HealthSignal.signal_type == signal_type)
    if start_time is not None:
        query = query.filter(HealthSignal.htime >= datetime.fromtimestamp(start_time))
    if end_time is not None:
        query = query.filter(HealthSignal.htime <= datetime.fromtimestamp(end_time))
    query = query.order_by(HealthSignal.htime.desc()).offset(skip)
    if limit != -1:
        query = query.limit(limit)
    signals = query.all()
    return [read_from_health_signal(s) for s in signals]


def delete_health_signal_impl(db, signal_id: int) -> bool:
    """Delete a health signal index by ID"""
    signal = db.query(HealthSignal).filter(HealthSignal.id == signal_id).first()
    if signal is None:
        return False
    db.delete(signal)
    db.commit()
    return True
