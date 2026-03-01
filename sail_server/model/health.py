# -*- coding: utf-8 -*-
# @file health.py
# @brief The Health Data Storage
# @author sailing-innocent
# @date 2025-04-24
# @version 1.0
# ---------------------------------

from sail_server.data.health import (
    Weight,
    Exercise,
    WeightPlan,
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
    WeightPlanResponse,
)
import numpy as np
from datetime import datetime
from sqlalchemy import func
from sqlalchemy import func, cast, Float


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
        htime=datetime.fromtimestamp(weight_create.htime) if weight_create.htime else datetime.now(),
        tag=weight_create.tag,
        description=weight_create.description,
    )
    db.add(weight)
    db.commit()
    db.refresh(weight)
    return read_from_weight(weight)


def read_weight_impl(db, weight_record_id: int = -1, _tag: str = None) -> WeightResponse | None:
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


def target_weight_impl(db, target_date: datetime) -> dict:
    """
    Get the target weight for a specific date.
    """
    # hard-code here
    start_date = "2025-04-02"
    start_weight = 115.0
    # duration = 365 # one year
    duration = 270  # 9 months
    target_dec = 30  # 30kg in one year
    decay_rate = target_dec / duration

    # Linear Approximation for target weight
    start_date = datetime.strptime(start_date, "%Y-%m-%d").date()
    if target_date < start_date:
        return None
    days_passed = (target_date - start_date).days
    target_weight = start_weight - decay_rate * days_passed
    return {
        "id": -1,  # No ID for target weight
        "value": target_weight,
        "htime": -1,
        "tag": "target",
        "description": "Target weight based on linear approximation",
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
        predicted_weights.append({
            "htime": w.htime,
            "value": float(w.value),
            "is_actual": True,
        })

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

        predicted_weights.append({
            "htime": future_time,
            "value": float(pred_value),
            "is_actual": False,
        })

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
        start_time=plan.start_time,
        target_time=plan.target_time,
        description=plan.description,
        created_at=plan.created_at,
    )


def create_weight_plan_impl(db, plan_data: WeightPlanCreateRequest) -> WeightPlanResponse:
    """Create a new weight plan"""
    plan = WeightPlan(
        target_weight=plan_data.target_weight,
        start_time=plan_data.start_time if plan_data.start_time else datetime.now(),
        target_time=plan_data.target_time if plan_data.target_time else datetime.now(),
        description=plan_data.description,
    )
    db.add(plan)
    db.commit()
    db.refresh(plan)
    return read_from_weight_plan(plan)


def get_active_weight_plan_impl(db) -> WeightPlanResponse | None:
    """Get the most recent active weight plan"""
    plan = db.query(WeightPlan).order_by(WeightPlan.created_at.desc()).first()
    return read_from_weight_plan(plan) if plan else None


def get_weight_plan_progress_impl(db, plan_id: int = None) -> dict | None:
    """
    Calculate weight plan progress with daily predictions.

    Returns control rate (0-100) and daily expected vs actual weights.
    """
    # Get the plan
    if plan_id:
        plan = db.query(WeightPlan).filter(WeightPlan.id == plan_id).first()
    else:
        plan = db.query(WeightPlan).order_by(WeightPlan.created_at.desc()).first()

    if not plan:
        return None

    plan_data = read_from_weight_plan(plan)
    now = datetime.now().timestamp()

    # Get actual weights from plan start to now
    actual_weights = read_weights_impl(db, 0, -1, plan_data.start_time.timestamp(), now, "raw")

    if not actual_weights:
        return {
            "plan": plan_data.model_dump(),
            "control_rate": 0.0,
            "current_weight": 0.0,
            "expected_current_weight": float(plan_data.target_weight),
            "daily_predictions": [],
            "is_on_track": False,
        }

    current_weight = float(actual_weights[-1].value)

    # Calculate expected weight progression (linear from start to target)
    start_weight = float(actual_weights[0].value)
    target_weight = float(plan_data.target_weight)
    total_days = (plan_data.target_time.timestamp() - plan_data.start_time.timestamp()) / 86400
    days_passed = (now - plan_data.start_time.timestamp()) / 86400

    # Linear interpolation for expected weight at current time
    if total_days > 0:
        progress_ratio = min(days_passed / total_days, 1.0)
        expected_current_weight = (
            start_weight + (target_weight - start_weight) * progress_ratio
        )
    else:
        expected_current_weight = target_weight

    # Calculate control rate (100% = exactly on track, 0% = completely off)
    weight_diff = abs(current_weight - expected_current_weight)
    # Allow 2kg tolerance for 100%, linear decrease after that
    control_rate = max(0, 100 - (weight_diff / 2) * 100)

    # Check if on track (within 2kg of expected)
    is_on_track = weight_diff <= 2.0

    # Generate daily predictions for the entire plan period
    daily_predictions = []
    total_days_int = int(total_days) + 1

    for day in range(total_days_int + 1):
        day_time = plan_data.start_time.timestamp() + day * 86400
        day_progress = day / total_days if total_days > 0 else 1.0
        expected_weight = start_weight + (target_weight - start_weight) * day_progress

        # Find actual weight for this day (if any)
        actual_for_day = None
        for w in actual_weights:
            w_day = int((w.htime - plan_data.start_time.timestamp()) / 86400)
            if w_day == day:
                actual_for_day = float(w.value)
                break

        daily_predictions.append({
            "htime": day_time,
            "expected_weight": float(expected_weight),
            "actual_weight": actual_for_day,
            "day": day,
        })

    return {
        "plan": plan_data.model_dump(),
        "control_rate": float(control_rate),
        "current_weight": float(current_weight),
        "expected_current_weight": float(expected_current_weight),
        "daily_predictions": daily_predictions,
        "is_on_track": is_on_track,
    }


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
    # Get the plan
    if plan_id:
        plan = db.query(WeightPlan).filter(WeightPlan.id == plan_id).first()
    else:
        plan = db.query(WeightPlan).order_by(WeightPlan.created_at.desc()).first()
    
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
    
    # Get start weight (first weight at or after plan start)
    weights_after_start = read_weights_impl(db, 0, -1, plan_data.start_time.timestamp(), None, "raw")
    if weights_after_start:
        start_weight = float(weights_after_start[0].value)
    else:
        start_weight = float(weights[0].value) if weights else float(plan_data.target_weight)
    
    target_weight = float(plan_data.target_weight)
    total_days = (plan_data.target_time.timestamp() - plan_data.start_time.timestamp()) / 86400
    
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
            # During plan period, interpolate
            days_from_start = (weight_time - plan_data.start_time.timestamp()) / 86400
            progress = days_from_start / total_days if total_days > 0 else 1.0
            expected_value = start_weight + (target_weight - start_weight) * progress
            
            diff = weight_value - expected_value
            if diff > tolerance:
                status = "above"  # Above expected (red)
            elif diff < -tolerance:
                status = "below"  # Below expected (green)
            else:
                status = "normal"  # Within tolerance (blue)
        
        result.append({
            "id": w.id,
            "value": weight_value,
            "htime": weight_time,
            "expected_value": float(expected_value),
            "status": status,
            "diff": float(diff),
        })
    
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


def create_exercise_impl(db, exercise_create: ExerciseCreateRequest) -> ExerciseResponse:
    """Create a new exercise record"""
    exercise = Exercise(
        htime=datetime.fromtimestamp(exercise_create.htime) if exercise_create.htime else datetime.now(),
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


def update_exercise_impl(db, id: int, exercise: ExerciseBase) -> ExerciseResponse | None:
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
