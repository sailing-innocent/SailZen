# -*- coding: utf-8 -*-
# @file project.py
# @brief Project Pydantic DTOs
# @author sailing-innocent
# @date 2026-03-01
# @version 1.0
# ---------------------------------

"""
项目模块 Pydantic DTOs

原位置: sail_server/data/project.py
"""

from datetime import datetime
from typing import Optional, List

from pydantic import BaseModel, Field, ConfigDict


# ============================================================================
# Project DTOs
# ============================================================================

class ProjectBase(BaseModel):
    """项目基础信息"""
    model_config = ConfigDict(from_attributes=True)
    
    name: str = Field(description="项目名称")
    description: str = Field(default="", description="项目描述")
    state: int = Field(default=0, description="项目状态")
    start_time_qbw: int = Field(description="开始时间(QBW格式)")
    end_time_qbw: int = Field(description="结束时间(QBW格式)")


class ProjectCreateRequest(BaseModel):
    """创建项目请求"""
    model_config = ConfigDict(from_attributes=True)
    
    name: str = Field(description="项目名称")
    description: str = Field(default="", description="项目描述")
    start_time_qbw: Optional[int] = Field(default=None, description="开始时间(QBW格式)")
    end_time_qbw: Optional[int] = Field(default=None, description="结束时间(QBW格式)")


class ProjectUpdateRequest(BaseModel):
    """更新项目请求"""
    model_config = ConfigDict(from_attributes=True)
    
    name: Optional[str] = Field(default=None, description="项目名称")
    description: Optional[str] = Field(default=None, description="项目描述")
    state: Optional[int] = Field(default=None, description="项目状态")
    start_time_qbw: Optional[int] = Field(default=None, description="开始时间(QBW格式)")
    end_time_qbw: Optional[int] = Field(default=None, description="结束时间(QBW格式)")


class ProjectResponse(ProjectBase):
    """项目响应"""
    id: int = Field(description="项目ID")
    ctime: datetime = Field(description="创建时间")
    mtime: datetime = Field(description="修改时间")


class ProjectListResponse(BaseModel):
    """项目列表响应"""
    projects: List[ProjectResponse]
    total: int


# ============================================================================
# Mission DTOs
# ============================================================================

class MissionBase(BaseModel):
    """任务基础信息"""
    model_config = ConfigDict(from_attributes=True)
    
    name: str = Field(description="任务名称")
    description: str = Field(default="", description="任务描述")
    parent_id: Optional[int] = Field(default=None, description="父任务ID")
    project_id: Optional[int] = Field(default=None, description="所属项目ID")
    state: int = Field(default=0, description="任务状态")
    ddl: Optional[datetime] = Field(default=None, description="截止时间")


class MissionCreateRequest(BaseModel):
    """创建任务请求"""
    model_config = ConfigDict(from_attributes=True)
    
    name: str = Field(description="任务名称")
    description: str = Field(default="", description="任务描述")
    parent_id: Optional[int] = Field(default=None, description="父任务ID")
    project_id: Optional[int] = Field(default=None, description="所属项目ID")
    ddl: Optional[datetime] = Field(default=None, description="截止时间")


class MissionUpdateRequest(BaseModel):
    """更新任务请求"""
    model_config = ConfigDict(from_attributes=True)
    
    name: Optional[str] = Field(default=None, description="任务名称")
    description: Optional[str] = Field(default=None, description="任务描述")
    state: Optional[int] = Field(default=None, description="任务状态")
    ddl: Optional[datetime] = Field(default=None, description="截止时间")


class MissionResponse(MissionBase):
    """任务响应"""
    id: int = Field(description="任务ID")
    lft: Optional[int] = Field(default=None, description="左值(树形结构)")
    rgt: Optional[int] = Field(default=None, description="右值(树形结构)")
    tree_id: Optional[int] = Field(default=None, description="树ID")
    ctime: datetime = Field(description="创建时间")
    mtime: datetime = Field(description="修改时间")


class MissionListResponse(BaseModel):
    """任务列表响应"""
    missions: List[MissionResponse]
    total: int


class MissionTreeResponse(BaseModel):
    """任务树响应"""
    missions: List[MissionResponse]
    total: int
