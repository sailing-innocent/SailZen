# -*- coding: utf-8 -*-
# @file health.py
# @brief The Health Data Storage
# @author sailing-innocent
# @date 2025-04-21
# @version 2.0
# ---------------------------------

"""
健康管理模块数据层

ORM 模型已从 infrastructure.orm.health 迁移
DTO 模型已从 application.dto.health 迁移

此文件保留向后兼容的导出和遗留的 dataclass DTOs
（因为 controller 层仍使用 Litestar DataclassDTO）
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import List

# 从 infrastructure.orm 导入 ORM 模型
from sail_server.infrastructure.orm.health import (
    Weight,
    BodySize,
    Exercise,
    WeightPlan,
)

# 从 application.dto 导入 Pydantic DTOs
from sail_server.application.dto.health import (
    WeightBase,
    WeightCreateRequest,
    WeightResponse,
    WeightListResponse,
    BodySizeBase,
    BodySizeCreateRequest,
    BodySizeResponse,
    BodySizeListResponse,
    ExerciseBase,
    ExerciseCreateRequest,
    ExerciseResponse,
    ExerciseListResponse,
    WeightPlanBase,
    WeightPlanCreateRequest,
    WeightPlanResponse,
    WeightPlanListResponse,
)


# ============================================================================
# Legacy Dataclass DTOs (保留以兼容现有 controller)
# TODO: 迁移到 Pydantic DTOs 后删除
# ============================================================================

@dataclass
class WeightData:
    """体重数据 (legacy dataclass)"""
    value: float
    htime: float = field(default_factory=lambda: datetime.now().timestamp())
    id: int = field(default=-1)
    tag: str = field(default="raw")
    description: str = field(default="")


@dataclass
class BodySizeData:
    """身体尺寸数据 (legacy dataclass)"""
    waist: float
    hip: float
    chest: float
    tag: str = field(default="daily")
    id: int = field(default=-1)
    htime: float = field(default_factory=lambda: datetime.now().timestamp())


@dataclass
class ExerciseData:
    """运动数据 (legacy dataclass)"""
    htime: float = field(default_factory=lambda: datetime.now().timestamp())
    id: int = field(default=-1)
    description: str = field(default="")


@dataclass
class WeightPlanData:
    """体重计划数据 (legacy dataclass)"""
    target_weight: float = field(default=0.0)
    start_time: float = field(default_factory=lambda: datetime.now().timestamp())
    target_time: float = field(default_factory=lambda: datetime.now().timestamp())
    id: int = field(default=-1)
    description: str = field(default="")
    created_at: float = field(default_factory=lambda: datetime.now().timestamp())


@dataclass
class WeightAnalysisResult:
    """体重趋势分析结果 (legacy dataclass)"""
    model_type: str = "linear"
    slope: float = 0.0
    intercept: float = 0.0
    r_squared: float = 0.0
    current_weight: float = 0.0
    current_trend: str = "stable"
    predicted_weights: list = field(default_factory=list)


@dataclass
class WeightPredictionPoint:
    """单一体重预测点 (legacy dataclass)"""
    htime: float = 0.0
    value: float = 0.0
    is_actual: bool = True


@dataclass
class WeightPlanProgress:
    """体重计划进度 (legacy dataclass)"""
    plan: WeightPlanData = field(default_factory=WeightPlanData)
    control_rate: float = 0.0
    current_weight: float = 0.0
    expected_current_weight: float = 0.0
    daily_predictions: list = field(default_factory=list)
    is_on_track: bool = True


@dataclass
class WeightRecordWithStatus:
    """带状态对比的体重记录 (legacy dataclass)"""
    id: int = -1
    value: float = 0.0
    htime: float = 0.0
    expected_value: float = 0.0
    status: str = "normal"
    diff: float = 0.0


__all__ = [
    # ORM Models
    "Weight",
    "BodySize",
    "Exercise",
    "WeightPlan",
    # Pydantic DTOs
    "WeightBase",
    "WeightCreateRequest",
    "WeightResponse",
    "WeightListResponse",
    "BodySizeBase",
    "BodySizeCreateRequest",
    "BodySizeResponse",
    "BodySizeListResponse",
    "ExerciseBase",
    "ExerciseCreateRequest",
    "ExerciseResponse",
    "ExerciseListResponse",
    "WeightPlanBase",
    "WeightPlanCreateRequest",
    "WeightPlanResponse",
    "WeightPlanListResponse",
    # Legacy Dataclass DTOs
    "WeightData",
    "BodySizeData",
    "ExerciseData",
    "WeightPlanData",
    "WeightAnalysisResult",
    "WeightPredictionPoint",
    "WeightPlanProgress",
    "WeightRecordWithStatus",
]
