# -*- coding: utf-8 -*-
# @file health.py
# @brief The Health Data Storage
# @author sailing-innocent
# @date 2025-04-21
# @version 1.0
# ---------------------------------

from sqlalchemy import Column, Integer, String, TIMESTAMP, func
from .orm import ORMBase
from dataclasses import dataclass, field
from datetime import datetime


# The Raw Weight Data
class Weight(ORMBase):
    __tablename__ = "weights"
    id = Column(Integer, primary_key=True)
    value = Column(String)  # float in kg
    htime = Column(TIMESTAMP, server_default=func.current_timestamp())  # happen time
    tag = Column(
        String, default="daily"
    )  # tag for the weight record, e.g. raw, daily, weekly, monthly, yearly (calculated from raw data)
    description = Column(String, default="")  # description of the weight record


@dataclass
class WeightData:
    """
    The Weight Data
    """

    value: float
    htime: float = field(default_factory=lambda: datetime.now().timestamp())
    id: int = field(default=-1)
    tag: str = field(default="raw")
    description: str = field(default="")


class BodySize(ORMBase):
    __tablename__ = "body_size"
    id = Column(Integer, primary_key=True)
    waist = Column(String)  # waist circumference in cm
    hip = Column(String)  # hip circumference in cm
    chest = Column(String)  # chest circumference in cm
    tag = Column(
        String, default="daily"
    )  # tag for the body size record, e.g. daily, weekly, monthly, yearly (calculated from raw data)
    htime = Column(TIMESTAMP, server_default=func.current_timestamp())  # happen time


@dataclass
class BodySizeData:
    """
    The Body Size Data
    """

    waist: float
    hip: float
    chest: float
    tag: str = field(default="daily")
    id: int = field(default=-1)
    htime: float = field(default_factory=lambda: datetime.now().timestamp())


# The Exercise Record Data
class Exercise(ORMBase):
    __tablename__ = "exercises"
    id = Column(Integer, primary_key=True)
    htime = Column(TIMESTAMP, server_default=func.current_timestamp())  # happen time
    description = Column(String, default="")  # natural language description


@dataclass
class ExerciseData:
    """
    The Exercise Data
    """

    htime: float = field(default_factory=lambda: datetime.now().timestamp())
    id: int = field(default=-1)
    description: str = field(default="")


# The Weight Plan Data
class WeightPlan(ORMBase):
    __tablename__ = "weight_plans"
    id = Column(Integer, primary_key=True)
    target_weight = Column(String)  # target weight value in kg
    start_time = Column(
        TIMESTAMP, server_default=func.current_timestamp()
    )  # plan start time
    target_time = Column(TIMESTAMP)  # plan target time
    description = Column(String, default="")  # plan description
    created_at = Column(TIMESTAMP, server_default=func.current_timestamp())


@dataclass
class WeightPlanData:
    """
    The Weight Plan Data
    """

    target_weight: float = field(default=0.0)
    start_time: float = field(default_factory=lambda: datetime.now().timestamp())
    target_time: float = field(default_factory=lambda: datetime.now().timestamp())
    id: int = field(default=-1)
    description: str = field(default="")
    created_at: float = field(default_factory=lambda: datetime.now().timestamp())


@dataclass
class WeightAnalysisResult:
    """
    Weight Trend Analysis Result
    """

    model_type: str = "linear"  # 'linear', 'polynomial', etc.
    slope: float = 0.0  # weight change per day (kg/day)
    intercept: float = 0.0  # initial weight
    r_squared: float = 0.0  # goodness of fit
    current_weight: float = 0.0
    current_trend: str = "stable"  # 'decreasing', 'stable', 'increasing'
    predicted_weights: list = field(default_factory=list)  # list of {htime, value}


@dataclass
class WeightPredictionPoint:
    """
    Single weight prediction point
    """

    htime: float = 0.0
    value: float = 0.0
    is_actual: bool = True  # True for actual data, False for predicted


@dataclass
class WeightPlanProgress:
    """
    Weight Plan Progress with daily predictions
    """

    plan: WeightPlanData = field(default_factory=WeightPlanData)
    control_rate: float = 0.0  # 0-100, how well the plan is being followed
    current_weight: float = 0.0
    expected_current_weight: float = 0.0  # what weight should be according to plan
    daily_predictions: list = field(
        default_factory=list
    )  # list of {htime, expected_weight, actual_weight}
    is_on_track: bool = True  # whether current weight is within expected range


@dataclass
class WeightRecordWithStatus:
    """
    Weight record with comparison status against plan
    """

    id: int = -1
    value: float = 0.0
    htime: float = 0.0
    expected_value: float = 0.0  # expected weight at this time
    status: str = "normal"  # 'above' (red), 'below' (green), 'normal' (blue)
    diff: float = 0.0  # difference from expected (positive = above, negative = below)
