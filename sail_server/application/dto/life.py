# -*- coding: utf-8 -*-
# @file life.py
# @brief Life Pydantic DTOs
# @author sailing-innocent
# @date 2026-03-01
# @version 1.0
# ---------------------------------

"""
生活服务模块 Pydantic DTOs

原位置: sail_server/data/life.py
"""

from datetime import date as date_type
from datetime import datetime
from enum import Enum
from typing import Optional, List, Dict, Any

from pydantic import BaseModel, Field, ConfigDict


# ============================================================================
# ServiceAccount DTOs
# ============================================================================


class ServiceAccountBase(BaseModel):
    """服务账户基础信息"""

    model_config = ConfigDict(from_attributes=True)
    name: str = Field(description="账户名称")
    entry: str = Field(description="入口网站/应用名称")
    username: str = Field(description="用户名")
    password: str = Field(description="密码")
    desp: str = Field(default="", description="账户描述")
    expire_time: int = Field(description="过期时间戳(秒)")


class ServiceAccountCreateRequest(ServiceAccountBase):
    """创建服务账户请求"""

    pass


class ServiceAccountUpdateRequest(BaseModel):
    """更新服务账户请求"""

    model_config = ConfigDict(from_attributes=True)

    name: Optional[str] = Field(default=None, description="账户名称")
    entry: Optional[str] = Field(default=None, description="入口网站/应用名称")
    username: Optional[str] = Field(default=None, description="用户名")
    password: Optional[str] = Field(default=None, description="密码")
    desp: Optional[str] = Field(default=None, description="账户描述")
    expire_time: Optional[int] = Field(default=None, description="过期时间戳(秒)")


class ServiceAccountResponse(ServiceAccountBase):
    """服务账户响应"""

    id: int = Field(description="账户ID")


class ServiceAccountListResponse(BaseModel):
    """服务账户列表响应"""

    accounts: list[ServiceAccountResponse]
    total: int


# ============================================================================
# TimeSpanClass Enum
# ============================================================================


class TimeSpanClass(str, Enum):
    """时间跨度类型枚举

    统一使用小写下划线命名，便于数据库存储与查询。
    """

    WEEK = "week"
    BIWEEK = "biweek"
    MONTH = "month"
    BIMONTH = "bimonth"
    QUARTER = "quarter"
    HYEAR = "hyear"
    YEAR = "year"
    FISCAL_MONTH = "fiscal_month"
    FISCAL_QUARTER = "fiscal_quarter"
    FISCAL_YEAR = "fiscal_year"
    CUSTOM = "custom"


# ============================================================================
# Day DTOs
# ============================================================================


class DayBase(BaseModel):
    """自然日基础信息"""

    model_config = ConfigDict(from_attributes=True)

    date: date_type = Field(description="自然日")
    ref: Dict[str, Any] = Field(default_factory=dict, description="扩展字段")


class DayCreateRequest(DayBase):
    """创建自然日请求"""

    pass


class DayUpdateRequest(BaseModel):
    """更新自然日请求"""

    model_config = ConfigDict(from_attributes=True)

    ref: Optional[Dict[str, Any]] = Field(default=None, description="扩展字段")


class DayResponse(DayBase):
    """自然日响应"""

    id: int = Field(description="自然日ID")
    created_at: Optional[datetime] = Field(default=None, description="创建时间")
    updated_at: Optional[datetime] = Field(default=None, description="更新时间")


class DayListResponse(BaseModel):
    """自然日列表响应"""

    days: List[DayResponse]
    total: int


# ============================================================================
# TimeSpan DTOs
# ============================================================================


class TimeSpanBase(BaseModel):
    """时间跨度基础信息"""

    model_config = ConfigDict(
        from_attributes=True, populate_by_name=True, serialize_by_alias=True
    )

    class_: TimeSpanClass = Field(
        description="时间跨度类型", alias="class", serialization_alias="class"
    )
    name: str = Field(description="规范化名称")
    start_day_id: int = Field(description="起始自然日ID")
    end_day_id: int = Field(description="结束自然日ID")
    child_span_ids: List[int] = Field(
        default_factory=list, description="一级子时间跨度ID列表"
    )
    ref: Dict[str, Any] = Field(default_factory=dict, description="扩展字段")


class TimeSpanCreateRequest(BaseModel):
    """创建时间跨度请求"""

    model_config = ConfigDict(
        from_attributes=True, populate_by_name=True, serialize_by_alias=True
    )

    class_: TimeSpanClass = Field(
        description="时间跨度类型", alias="class", serialization_alias="class"
    )
    name: str = Field(description="规范化名称")
    start_day_id: int = Field(description="起始自然日ID")
    end_day_id: int = Field(description="结束自然日ID")
    child_span_ids: List[int] = Field(
        default_factory=list, description="一级子时间跨度ID列表"
    )
    ref: Dict[str, Any] = Field(default_factory=dict, description="扩展字段")


class TimeSpanUpdateRequest(BaseModel):
    """更新时间跨度请求"""

    model_config = ConfigDict(
        from_attributes=True, populate_by_name=True, serialize_by_alias=True
    )

    class_: Optional[TimeSpanClass] = Field(
        default=None,
        description="时间跨度类型",
        alias="class",
        serialization_alias="class",
    )
    name: Optional[str] = Field(default=None, description="规范化名称")
    start_day_id: Optional[int] = Field(default=None, description="起始自然日ID")
    end_day_id: Optional[int] = Field(default=None, description="结束自然日ID")
    child_span_ids: Optional[List[int]] = Field(
        default=None, description="一级子时间跨度ID列表"
    )
    ref: Optional[Dict[str, Any]] = Field(default=None, description="扩展字段")


class TimeSpanResponse(TimeSpanBase):
    """时间跨度响应"""

    id: int = Field(description="时间跨度ID")
    created_at: Optional[datetime] = Field(default=None, description="创建时间")
    updated_at: Optional[datetime] = Field(default=None, description="更新时间")


class TimeSpanFilter(BaseModel):
    """时间跨度过滤条件"""

    model_config = ConfigDict(
        from_attributes=True, populate_by_name=True, serialize_by_alias=True
    )

    class_: Optional[TimeSpanClass] = Field(
        default=None,
        description="时间跨度类型",
        alias="class",
        serialization_alias="class",
    )
    name: Optional[str] = Field(default=None, description="规范化名称")
    start_date: Optional[date_type] = Field(default=None, description="起始日期")
    end_date: Optional[date_type] = Field(default=None, description="结束日期")


class TimeSpanListResponse(BaseModel):
    """时间跨度列表响应"""

    timespans: List[TimeSpanResponse]
    total: int
