# -*- coding: utf-8 -*-
# @file health.py
# @brief The Health Data Storage - Re-export module
# @author sailing-innocent
# @date 2025-04-21
# @version 3.0
# ---------------------------------

"""
健康管理模块数据层 - 重新导出模块

- ORM 模型从 infrastructure.orm.health 导入
- Pydantic DTOs 从 application.dto.health 导入
"""

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
]
