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
    WeightPlanUpdateRequest,
    WeightPlanResponse,
    WeightExpectedRangeResponse,
    MedicationCreateRequest,
    MedicationUpdateRequest,
    MedicationResponse,
    MedicationTodayDto,
    MedicationStatsDto,
    DietCreateRequest,
    DietResponse,
    DietSummaryDto,
    NutritionGoalCreateRequest,
    NutritionGoalResponse,
    SleepCreateRequest,
    SleepResponse,
    SleepScheduleGoalCreateRequest,
    SleepScheduleGoalResponse,
    HealthDashboardResponse,
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
    update_weight_plan_impl,
    delete_weight_plan_impl,
    get_active_weight_plan_impl,
    get_weight_plan_progress_impl,
    get_weights_with_plan_status_impl,
    get_expected_weights_impl,
    get_weight_plan_checkin_status_impl,
    create_medication_impl,
    read_medication_impl,
    read_medications_impl,
    update_medication_impl,
    medication_today_impl,
    medication_stats_impl,
    create_diet_impl,
    read_diet_impl,
    read_diets_impl,
    diet_summary_impl,
    upsert_nutrition_goal_impl,
    read_nutrition_goal_impl,
    create_sleep_impl,
    read_sleep_impl,
    read_sleeps_impl,
    upsert_sleep_schedule_goal_impl,
    read_sleep_schedule_goal_impl,
    health_dashboard_impl,
)
from sqlalchemy.orm import Session
from typing import Generator

from datetime import datetime, date


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

    @get("/checkin-status")
    async def get_weight_plan_checkin_status(
        self,
        router_dependency: Generator[Session, None, None],
        request: Request,
        plan_id: int | None = None,
    ) -> dict | None:
        """
        Get Rhythm checkin status for the active weight plan (today done + streak).
        """
        db = next(router_dependency)
        status = get_weight_plan_checkin_status_impl(db, plan_id)
        logger.info(f"Weight plan checkin status: {status}")
        return status


    @put("/{plan_id:int}")
    async def update_weight_plan(
        self,
        plan_id: int,
        data: WeightPlanUpdateRequest,
        request: Request,
        router_dependency: Generator[Session, None, None],
    ) -> WeightPlanResponse | None:
        """
        Update an existing weight plan.
        """
        db = next(router_dependency)
        plan = update_weight_plan_impl(db, plan_id, data)
        logger.info(f"Update weight plan: {plan}")
        if plan is None:
            return None
        return plan

    @delete("/{plan_id:int}", status_code=200)
    async def delete_weight_plan(
        self,
        plan_id: int,
        request: Request,
        router_dependency: Generator[Session, None, None],
    ) -> dict | None:
        """
        Delete a weight plan.
        """
        db = next(router_dependency)
        result = delete_weight_plan_impl(db, plan_id)
        logger.info(f"Delete weight plan: {result}")
        return result

    @get("/expected")
    async def get_weight_plan_expected(
        self,
        router_dependency: Generator[Session, None, None],
        request: Request,
        start: float,
        end: float,
        plan_id: int | None = None,
    ) -> WeightExpectedRangeResponse | None:
        """
        Get expected weights for a date range aligned to the active plan.
        """
        db = next(router_dependency)
        result = get_expected_weights_impl(db, start, end, plan_id)
        logger.info(f"Get weight plan expected range [{start}, {end}]: {len(result.points) if result else 0} points")
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


# ===================================================
# Sleep Controller
# ===================================================

class SleepController(Controller):
    path = "/sleep"

    @get("/{sleep_id:int}")
    async def get_sleep(
        self,
        sleep_id: int,
        router_dependency: Generator[Session, None, None],
        request: Request,
    ) -> SleepResponse:
        """Get a sleep record."""
        db = next(router_dependency)
        sleep = read_sleep_impl(db, sleep_id)
        logger.info(f"Get sleep: {sleep}")
        if sleep is None:
            return None
        return sleep

    @get()
    async def get_sleep_list(
        self,
        router_dependency: Generator[Session, None, None],
        skip: int = 0,
        limit: int = -1,
        start: float = None,
        end: float = None,
    ) -> list[SleepResponse]:
        """Get sleep record list."""
        db = next(router_dependency)
        sleeps = read_sleeps_impl(db, skip, limit, None, start, end)
        return sleeps

    @post()
    async def create_sleep(
        self,
        data: SleepCreateRequest,
        request: Request,
        router_dependency: Generator[Session, None, None],
    ) -> SleepResponse:
        """Create a new sleep record."""
        db = next(router_dependency)
        sleep = create_sleep_impl(db, data)
        logger.info(f"Create sleep: {sleep}")
        return sleep


# ===================================================
# Sleep Schedule Controller
# ===================================================

class SleepScheduleController(Controller):
    path = "/sleep-schedule"

    @get()
    async def get_sleep_schedule_goal(
        self,
        router_dependency: Generator[Session, None, None],
        request: Request,
        date: str = None,
    ) -> SleepScheduleGoalResponse | None:
        """Get sleep schedule goal for a date (default today)."""
        db = next(router_dependency)
        target_date = _parse_date(date) or date.today()
        goal = read_sleep_schedule_goal_impl(db, target_date)
        logger.info(f"Get sleep schedule goal: {goal}")
        return goal

    @post()
    async def create_or_update_sleep_schedule_goal(
        self,
        data: SleepScheduleGoalCreateRequest,
        request: Request,
        router_dependency: Generator[Session, None, None],
    ) -> SleepScheduleGoalResponse:
        """Create or update sleep schedule goal."""
        db = next(router_dependency)
        goal = upsert_sleep_schedule_goal_impl(db, data)
        logger.info(f"Upsert sleep schedule goal: {goal}")
        return goal


# ===================================================
# Medication Controller
# ===================================================

class MedicationController(Controller):
    path = "/medication"

    @get()
    async def get_medication_list(
        self,
        router_dependency: Generator[Session, None, None],
        date: str = None,
        taken: bool = None,
        skip: int = 0,
        limit: int = -1,
    ) -> list[MedicationResponse]:
        """Get medication list, optionally filtered by date and taken status."""
        db = next(router_dependency)
        target_date = _parse_date(date)
        medications = read_medications_impl(db, skip, limit, target_date, taken)
        return medications

    @post()
    async def create_medication(
        self,
        data: MedicationCreateRequest,
        request: Request,
        router_dependency: Generator[Session, None, None],
    ) -> MedicationResponse:
        """Create a new medication record."""
        db = next(router_dependency)
        medication = create_medication_impl(db, data)
        logger.info(f"Create medication: {medication}")
        return medication

    @put("/{medication_id:int}")
    async def update_medication(
        self,
        medication_id: int,
        data: MedicationUpdateRequest,
        request: Request,
        router_dependency: Generator[Session, None, None],
    ) -> MedicationResponse:
        """Update medication taken status."""
        db = next(router_dependency)
        medication = update_medication_impl(db, medication_id, data)
        logger.info(f"Update medication: {medication}")
        if medication is None:
            return None
        return medication

    @get("/today")
    async def get_medication_today(
        self,
        router_dependency: Generator[Session, None, None],
        request: Request,
        date: str = None,
    ) -> MedicationTodayDto:
        """Get today's medication list and compliance."""
        db = next(router_dependency)
        target_date = _parse_date(date) or date.today()
        result = medication_today_impl(db, target_date)
        logger.info(f"Get medication today: {result}")
        return result

    @get("/stats")
    async def get_medication_stats(
        self,
        router_dependency: Generator[Session, None, None],
        request: Request,
        days: int = 7,
        end_date: str = None,
    ) -> MedicationStatsDto:
        """Get medication compliance stats for the last N days."""
        db = next(router_dependency)
        end = _parse_date(end_date) or date.today()
        result = medication_stats_impl(db, days, end)
        logger.info(f"Get medication stats: {result}")
        return result


# ===================================================
# Diet Controller
# ===================================================

class DietController(Controller):
    path = "/diet"

    @get()
    async def get_diet_list(
        self,
        router_dependency: Generator[Session, None, None],
        date: str = None,
        meal_type: str = None,
        skip: int = 0,
        limit: int = -1,
    ) -> list[DietResponse]:
        """Get diet records, optionally filtered by date and meal type."""
        db = next(router_dependency)
        target_date = _parse_date(date)
        meal = None
        if meal_type:
            try:
                from sail_server.application.dto.health import MealType
                meal = MealType(meal_type)
            except ValueError:
                pass
        diets = read_diets_impl(db, skip, limit, target_date, meal)
        return diets

    @post()
    async def create_diet(
        self,
        data: DietCreateRequest,
        request: Request,
        router_dependency: Generator[Session, None, None],
    ) -> DietResponse:
        """Create a new diet record."""
        db = next(router_dependency)
        diet = create_diet_impl(db, data)
        logger.info(f"Create diet: {diet}")
        return diet

    @get("/summary")
    async def get_diet_summary(
        self,
        router_dependency: Generator[Session, None, None],
        date: str = None,
    ) -> DietSummaryDto:
        """Get daily diet summary with nutrition goals."""
        db = next(router_dependency)
        target_date = _parse_date(date) or date.today()
        result = diet_summary_impl(db, target_date)
        logger.info(f"Get diet summary: {result}")
        return result

    @post("/goal")
    async def create_or_update_nutrition_goal(
        self,
        data: NutritionGoalCreateRequest,
        request: Request,
        router_dependency: Generator[Session, None, None],
    ) -> NutritionGoalResponse:
        """Create or update daily nutrition goal."""
        db = next(router_dependency)
        goal = upsert_nutrition_goal_impl(db, data)
        logger.info(f"Upsert nutrition goal: {goal}")
        return goal

    @get("/goal")
    async def get_nutrition_goal(
        self,
        router_dependency: Generator[Session, None, None],
        date: str = None,
    ) -> NutritionGoalResponse | None:
        """Get nutrition goal for a date."""
        db = next(router_dependency)
        target_date = _parse_date(date) or date.today()
        goal = read_nutrition_goal_impl(db, target_date)
        logger.info(f"Get nutrition goal: {goal}")
        return goal


# ===================================================
# Health Dashboard Controller
# ===================================================

class HealthDashboardController(Controller):
    path = "/dashboard"

    @get()
    async def get_dashboard(
        self,
        router_dependency: Generator[Session, None, None],
        request: Request,
        date: str = None,
    ) -> HealthDashboardResponse:
        """Get health dashboard overview for a date."""
        db = next(router_dependency)
        target_date = _parse_date(date) or date.today()
        result = health_dashboard_impl(db, target_date)
        logger.info(f"Get health dashboard: {result}")
        return result


def _parse_date(date_str: str | None) -> date | None:
    if not date_str:
        return None
    try:
        return datetime.strptime(date_str, "%Y-%m-%d").date()
    except ValueError:
        return None
