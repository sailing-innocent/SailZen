# -*- coding: utf-8 -*-
# @file health.py
# @brief Health Controler
# @author sailing-innocent
# @date 2025-05-20
# @version 1.0
# ---------------------------------
from __future__ import annotations
from litestar import Controller, delete, get, post, put, Request
import logging

logger = logging.getLogger(__name__)

from sail_server.application.dto.health import (
    WeightCreateRequest,
    WeightResponse,
    ExerciseCreateRequest,
    ExerciseResponse,
    WeightPlanCreateRequest,
    WeightPlanResponse,
)

from sail_server.model.health import (
    read_weight_impl,
    read_weights_impl,
    read_weights_avg_impl,
    create_weight_impl,
    target_weight_impl,
    read_exercise_impl,
    read_exercises_impl,
    create_exercise_impl,
    update_exercise_impl,
    delete_exercise_impl,
    analyze_weight_trend_impl,
    predict_weight_impl,
    create_weight_plan_impl,
    get_active_weight_plan_impl,
    get_weight_plan_progress_impl,
    get_weights_with_plan_status_impl,
)
from sqlalchemy.orm import Session
from typing import Generator

from datetime import datetime


# ===================================================
# Weight Controller
# ===================================================

class WeightController(Controller):
    path = "/weight"

    @get("/target")
    async def get_target_weight(
        self,
        date: str,
        router_dependency: Generator[Session, None, None],
        request: Request,
    ) -> dict:
        """
        Get the target weight for a specific date.
        """
        db = next(router_dependency)
        try:
            target_date = datetime.strptime(date, "%Y-%m-%d").date()
        except ValueError:
            logger.error(f"Invalid date format: {date}")
            return None

        weight = target_weight_impl(db, target_date)
        logger.info(f"Get target weight for {date}: {weight}")
        if weight is None:
            return None

        return weight

    @get("/{weight_id:int}")
    async def get_weight(
        self,
        weight_id: int,
        router_dependency: Generator[Session, None, None],
        request: Request,
    ) -> WeightResponse:
        """
        Get the weight data.
        """
        db = next(router_dependency)
        weight = read_weight_impl(db, weight_id)
        logger.info(f"Get weight: {weight}")
        if weight is None:
            return None

        return weight

    # GET /weight&skip=0&limit=10&start=<time_stamp>&end=<time_stamp>
    @get()
    async def get_weight_list(
        self,
        router_dependency: Generator[Session, None, None],
        skip: int = 0,
        limit: int = 10,
        start: float = None,  # timestamp as float in seconds
        end: float = None,  # timestamp as float in seconds
    ) -> list[WeightResponse]:
        """
        Get the weight data list.
        """
        db = next(router_dependency)
        weights = read_weights_impl(db, skip, limit, start, end)
        return weights

    # GET /weight/avg&start=<time_stamp>&end=<time_stamp>
    @get("/avg")
    async def get_weights_avg(
        self,
        router_dependency: Generator[Session, None, None],
        start: float = None,  # timestamp as float in seconds
        end: float = None,  # timestamp as float in seconds
    ) -> dict:
        """
        Get the weight data list.
        """
        db = next(router_dependency)
        result = read_weights_avg_impl(db, start, end)
        return {"result": result}

    # POST /weight
    @post()
    async def create_weight(
        self,
        data: WeightCreateRequest,
        request: Request,
        router_dependency: Generator[Session, None, None],
    ) -> WeightResponse:
        """
        Create a new weight data.
        """
        db = next(router_dependency)
        weight = create_weight_impl(db, data)
        logger.info(f"Create weight: {weight}")
        if weight is None:
            return None

        return weight

    # GET /weight/analysis?start=&end=&model_type=
    @get("/analysis")
    async def analyze_weight_trend(
        self,
        router_dependency: Generator[Session, None, None],
        request: Request,
        start: float = None,  # timestamp as float in seconds
        end: float = None,
        model_type: str = "linear",  # 'linear' or 'polynomial'
    ) -> dict:
        """
        Analyze weight trend and return model parameters with predictions.
        """
        db = next(router_dependency)
        result = analyze_weight_trend_impl(db, start, end, model_type)
        logger.info(f"Weight analysis: slope={result['slope']}, trend={result['current_trend']}")
        return result

    # GET /weight/prediction?target_time=&model_type=&start=&end=
    @get("/prediction")
    async def predict_weight(
        self,
        router_dependency: Generator[Session, None, None],
        request: Request,
        target_time: float,  # target timestamp for prediction
        model_type: str = "linear",
        start: float = None,
        end: float = None,
    ) -> dict:
        """
        Predict weight at a specific future timestamp.
        """
        db = next(router_dependency)
        predicted = predict_weight_impl(db, target_time, model_type, start, end)
        logger.info(f"Weight prediction for {target_time}: {predicted}")
        return {"predicted_weight": predicted, "target_time": target_time}


# ===================================================
# Weight Plan Controller
# ===================================================

class WeightPlanController(Controller):
    path = "/weight/plan"

    @get()
    async def get_weight_plan(
        self,
        router_dependency: Generator[Session, None, None],
        request: Request,
    ) -> WeightPlanResponse | None:
        """
        Get the active weight plan.
        """
        db = next(router_dependency)
        plan = get_active_weight_plan_impl(db)
        logger.info(f"Get weight plan: {plan}")
        if plan is None:
            return None
        return plan

    @post()
    async def create_weight_plan(
        self,
        data: WeightPlanCreateRequest,
        request: Request,
        router_dependency: Generator[Session, None, None],
    ) -> WeightPlanResponse:
        """
        Create a new weight plan.
        """
        db = next(router_dependency)
        plan = create_weight_plan_impl(db, data)
        logger.info(f"Create weight plan: {plan}")
        return plan

    @get("/progress")
    async def get_weight_plan_progress(
        self,
        router_dependency: Generator[Session, None, None],
        request: Request,
        plan_id: int | None = None,
    ) -> dict | None:
        """
        Get weight plan progress with daily predictions.
        Returns control rate and expected vs actual weights.
        """
        db = next(router_dependency)
        progress = get_weight_plan_progress_impl(db, plan_id)
        logger.info(f"Weight plan progress: control_rate={progress['control_rate'] if progress else None}")
        if progress is None:
            return None
        return progress

    @get("/weights-with-status")
    async def get_weights_with_status(
        self,
        router_dependency: Generator[Session, None, None],
        request: Request,
        start: float | None = None,
        end: float | None = None,
        plan_id: int | None = None,
    ) -> list[dict]:
        """
        Get weight records with comparison status against plan.
        
        Returns weight records with:
        - expected_value: expected weight at that time
        - status: 'above' (red), 'below' (green), 'normal' (blue)
        - diff: difference from expected
        """
        db = next(router_dependency)
        result = get_weights_with_plan_status_impl(db, start, end, plan_id)
        logger.info(f"Get {len(result)} weights with status")
        return result


# ===================================================
# Exercise Controller
# ===================================================

class ExerciseController(Controller):
    path = "/exercise"

    @get("/{exercise_id:int}")
    async def get_exercise(
        self,
        exercise_id: int,
        router_dependency: Generator[Session, None, None],
        request: Request,
    ) -> ExerciseResponse:
        """
        Get the exercise record.
        """
        db = next(router_dependency)
        exercise = read_exercise_impl(db, exercise_id)
        logger.info(f"Get exercise: {exercise}")
        if exercise is None:
            return None
        return exercise

    @get()
    async def get_exercise_list(
        self,
        router_dependency: Generator[Session, None, None],
        skip: int = 0,
        limit: int = -1,
        start: float = None,
        end: float = None,
    ) -> list[ExerciseResponse]:
        """
        Get the exercise record list.
        """
        db = next(router_dependency)
        exercises = read_exercises_impl(db, skip, limit, start, end)
        return exercises

    @post()
    async def create_exercise(
        self,
        data: ExerciseCreateRequest,
        request: Request,
        router_dependency: Generator[Session, None, None],
    ) -> ExerciseResponse:
        """
        Create a new exercise record.
        """
        db = next(router_dependency)
        exercise = create_exercise_impl(db, data)
        logger.info(f"Create exercise: {exercise}")
        if exercise is None:
            return None
        return exercise

    @put("/{exercise_id:int}")
    async def update_exercise(
        self,
        exercise_id: int,
        data: ExerciseCreateRequest,
        request: Request,
        router_dependency: Generator[Session, None, None],
    ) -> ExerciseResponse:
        """
        Update an exercise record.
        """
        db = next(router_dependency)
        exercise = update_exercise_impl(db, exercise_id, data)
        logger.info(f"Update exercise: {exercise}")
        if exercise is None:
            return None
        return exercise

    @delete("/{exercise_id:int}")
    async def delete_exercise(
        self,
        exercise_id: int,
        request: Request,
        router_dependency: Generator[Session, None, None],
    ) -> None:
        """
        Delete an exercise record.
        """
        db = next(router_dependency)
        delete_exercise_impl(db, exercise_id)
        logger.info(f"Delete exercise: {exercise_id}")
