# -*- coding: utf-8 -*-
# @file health.py
# @brief Health Pydantic DTOs
# @author sailing-innocent
# @date 2026-03-01
# @version 1.0
# ---------------------------------

"""
健康模块 Pydantic DTOs

原位置: sail_server/data/health.py
"""

from datetime import datetime, date
from enum import Enum
from typing import Optional, List

from pydantic import BaseModel, Field, ConfigDict, field_serializer


# ============================================================================
# Weight DTOs
# ============================================================================


class WeightBase(BaseModel):
    """体重记录基础信息"""

    model_config = ConfigDict(from_attributes=True)

    value: float = Field(description="体重值 (kg)")
    tag: str = Field(default="raw", description="记录标签")
    description: Optional[str] = Field(default="", description="记录描述")


class WeightCreateRequest(WeightBase):
    """创建体重记录请求"""

    htime: Optional[float] = Field(default=None, description="发生时间戳")


class WeightResponse(WeightBase):
    """体重记录响应"""

    id: int = Field(description="记录ID")
    htime: Optional[float] = Field(default=None, description="发生时间戳")


class WeightListResponse(BaseModel):
    """体重记录列表响应"""

    weights: List[WeightResponse]
    total: int


# ============================================================================
# BodySize DTOs
# ============================================================================


class BodySizeBase(BaseModel):
    """身体尺寸基础信息"""

    model_config = ConfigDict(from_attributes=True)

    waist: float = Field(description="腰围 (cm)")
    hip: float = Field(description="臀围 (cm)")
    chest: float = Field(description="胸围 (cm)")
    tag: str = Field(default="daily", description="记录标签")


class BodySizeCreateRequest(BodySizeBase):
    """创建身体尺寸记录请求"""

    htime: Optional[float] = Field(default=None, description="发生时间戳")


class BodySizeResponse(BodySizeBase):
    """身体尺寸记录响应"""

    id: int = Field(description="记录ID")
    htime: float = Field(description="发生时间戳")


class BodySizeListResponse(BaseModel):
    """身体尺寸记录列表响应"""

    body_sizes: List[BodySizeResponse]
    total: int


# ============================================================================
# Exercise DTOs
# ============================================================================


class ExerciseBase(BaseModel):
    """运动记录基础信息"""

    model_config = ConfigDict(from_attributes=True)

    description: str = Field(default="", description="运动描述")


class ExerciseCreateRequest(ExerciseBase):
    """创建运动记录请求"""

    htime: Optional[float] = Field(default=None, description="发生时间戳")


class ExerciseResponse(ExerciseBase):
    """运动记录响应"""

    id: int = Field(description="记录ID")
    htime: float = Field(description="发生时间戳")


class ExerciseListResponse(BaseModel):
    """运动记录列表响应"""

    exercises: List[ExerciseResponse]
    total: int


# ============================================================================
# WeightPlan DTOs
# ============================================================================


class WeightPlanCurveType(str, Enum):
    """体重计划目标曲线类型"""

    LINEAR = "linear"
    POLYNOMIAL = "polynomial"
    EXPONENTIAL = "exponential"


class WeightPlanBase(BaseModel):
    """体重计划基础信息"""

    model_config = ConfigDict(from_attributes=True)

    target_weight: str = Field(description="目标体重 (kg)")
    initial_weight: Optional[str] = Field(
        default=None, description="起始体重 (kg)，None 则自动取 start_time 后第一次记录"
    )
    curve_type: WeightPlanCurveType = Field(
        default=WeightPlanCurveType.LINEAR, description="目标曲线类型"
    )
    description: str = Field(default="", description="计划描述")


class WeightPlanCreateRequest(WeightPlanBase):
    """创建体重计划请求"""

    start_time: Optional[datetime] = Field(default=None, description="计划开始时间")
    target_time: Optional[datetime] = Field(default=None, description="计划目标时间")
    notify_enabled: bool = Field(default=False, description="是否启用 Rhythm 提醒")
    notify_time: Optional[str] = Field(
        default="08:30", pattern=r"^\d{2}:\d{2}$", description="提醒时间 HH:MM"
    )
    feedback_enabled: bool = Field(
        default=False, description="记录体重时是否同步 Rhythm 打卡"
    )


class WeightPlanUpdateRequest(WeightPlanBase):
    """更新体重计划请求"""

    start_time: Optional[datetime] = Field(default=None, description="计划开始时间")
    target_time: Optional[datetime] = Field(default=None, description="计划目标时间")
    notify_enabled: bool = Field(default=False, description="是否启用 Rhythm 提醒")
    notify_time: Optional[str] = Field(
        default="08:30", pattern=r"^\d{2}:\d{2}$", description="提醒时间 HH:MM"
    )
    feedback_enabled: bool = Field(
        default=False, description="记录体重时是否同步 Rhythm 打卡"
    )


class WeightPlanResponse(WeightPlanBase):
    """体重计划响应"""

    id: int = Field(description="计划ID")
    start_time: datetime = Field(description="计划开始时间")
    target_time: datetime = Field(description="计划目标时间")
    created_at: datetime = Field(description="创建时间")
    notify_enabled: bool = Field(description="是否启用 Rhythm 提醒")
    notify_time: Optional[str] = Field(description="提醒时间 HH:MM")
    feedback_enabled: bool = Field(description="记录体重时是否同步 Rhythm 打卡")
    rhythm_affair_id: Optional[int] = Field(
        default=None, description="关联 Rhythm 事务 ID"
    )

    @field_serializer("start_time", "target_time", "created_at")
    def serialize_datetime(self, value: datetime) -> float:
        return value.timestamp()


class WeightExpectedPoint(BaseModel):
    """按日期范围返回的预期体重单点"""

    htime: float = Field(description="当天 00:00:00 时间戳（秒）")
    expected_weight: float = Field(description="预期体重 (kg)")


class WeightExpectedRangeResponse(BaseModel):
    """按日期范围返回的预期体重响应"""

    plan: WeightPlanResponse = Field(description="当前活跃计划")
    points: List[WeightExpectedPoint] = Field(description="区间内每一天的预期体重")


class WeightPlanListResponse(BaseModel):
    """体重计划列表响应"""

    weight_plans: List[WeightPlanResponse]
    total: int


# ============================================================================
# Sleep DTOs
# ============================================================================


class SleepBase(BaseModel):
    """睡眠记录基础信息"""

    model_config = ConfigDict(from_attributes=True)

    hours: float = Field(description="睡眠时长(小时)")
    quality: int = Field(default=3, description="睡眠质量 1-5")
    description: Optional[str] = Field(default="", description="描述")


class SleepCreateRequest(SleepBase):
    """创建睡眠记录请求"""

    day_id: Optional[int] = Field(default=None, description="自然日ID")
    htime: Optional[float] = Field(default=None, description="发生时间戳")


class SleepResponse(SleepBase):
    """睡眠记录响应"""

    id: int = Field(description="记录ID")
    day_id: Optional[int] = Field(default=None, description="自然日ID")
    htime: Optional[float] = Field(default=None, description="发生时间戳")


class SleepListResponse(BaseModel):
    """睡眠记录列表响应"""

    sleeps: List[SleepResponse]
    total: int


# ============================================================================
# Energy Level DTOs
# ============================================================================


class EnergyLevelBase(BaseModel):
    """精力评分基础信息"""

    model_config = ConfigDict(from_attributes=True)

    score: int = Field(description="精力评分 1-5")
    description: Optional[str] = Field(default="", description="描述")


class EnergyLevelCreateRequest(EnergyLevelBase):
    """创建精力评分请求"""

    day_id: Optional[int] = Field(default=None, description="自然日ID")
    htime: Optional[float] = Field(default=None, description="发生时间戳")


class EnergyLevelResponse(EnergyLevelBase):
    """精力评分响应"""

    id: int = Field(description="记录ID")
    day_id: Optional[int] = Field(default=None, description="自然日ID")
    htime: Optional[float] = Field(default=None, description="发生时间戳")


class EnergyLevelListResponse(BaseModel):
    """精力评分列表响应"""

    energy_levels: List[EnergyLevelResponse]
    total: int


# ============================================================================
# Mood DTOs
# ============================================================================


class MoodBase(BaseModel):
    """情绪评分基础信息"""

    model_config = ConfigDict(from_attributes=True)

    score: int = Field(description="情绪评分 1-5")
    description: Optional[str] = Field(default="", description="描述")


class MoodCreateRequest(MoodBase):
    """创建情绪评分请求"""

    day_id: Optional[int] = Field(default=None, description="自然日ID")
    htime: Optional[float] = Field(default=None, description="发生时间戳")


class MoodResponse(MoodBase):
    """情绪评分响应"""

    id: int = Field(description="记录ID")
    day_id: Optional[int] = Field(default=None, description="自然日ID")
    htime: Optional[float] = Field(default=None, description="发生时间戳")


class MoodListResponse(BaseModel):
    """情绪评分列表响应"""

    moods: List[MoodResponse]
    total: int


# ============================================================================
# HealthSignal DTOs
# ============================================================================


class HealthSignalBase(BaseModel):
    """统一健康信号基础信息"""

    model_config = ConfigDict(from_attributes=True)

    signal_type: str = Field(description="信号类型")
    ref_id: int = Field(description="关联记录ID")
    day_id: Optional[int] = Field(default=None, description="自然日ID")
    htime: Optional[float] = Field(default=None, description="发生时间戳")
    value_json: Optional[dict] = Field(default_factory=dict, description="原始值")
    score: Optional[int] = Field(default=None, description="标准化分数")


class HealthSignalCreateRequest(HealthSignalBase):
    """创建健康信号请求"""

    pass


class HealthSignalResponse(HealthSignalBase):
    """健康信号响应"""

    id: int = Field(description="信号ID")


class HealthSignalListResponse(BaseModel):
    """健康信号列表响应"""

    health_signals: List[HealthSignalResponse]
    total: int
