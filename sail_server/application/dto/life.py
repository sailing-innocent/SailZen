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

from typing import Optional

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
