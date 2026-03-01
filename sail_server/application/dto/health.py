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

from datetime import datetime
from typing import Optional, List

from pydantic import BaseModel, Field, ConfigDict


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

class WeightPlanBase(BaseModel):
    """体重计划基础信息"""
    model_config = ConfigDict(from_attributes=True)
    
    target_weight: str = Field(description="目标体重 (kg)")
    description: str = Field(default="", description="计划描述")


class WeightPlanCreateRequest(WeightPlanBase):
    """创建体重计划请求"""
    start_time: Optional[datetime] = Field(default=None, description="计划开始时间")
    target_time: Optional[datetime] = Field(default=None, description="计划目标时间")


class WeightPlanResponse(WeightPlanBase):
    """体重计划响应"""
    id: int = Field(description="计划ID")
    start_time: datetime = Field(description="计划开始时间")
    target_time: datetime = Field(description="计划目标时间")
    created_at: datetime = Field(description="创建时间")


class WeightPlanListResponse(BaseModel):
    """体重计划列表响应"""
    weight_plans: List[WeightPlanResponse]
    total: int
