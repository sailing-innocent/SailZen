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
# Project State Classes
# ============================================================================

class ProjectState:
    """项目状态管理类"""
    INVALID = 0   # 无效
    VALID = 1     # 有效
    PREPARE = 2   # 准备中
    TRACKING = 3  # 跟踪中
    PENDING = 4   # 挂起
    DONE = 5      # 完成
    CANCELED = 6  # 取消

    STATE_MAP = {
        INVALID: "无效",
        VALID: "有效",
        PREPARE: "准备中",
        TRACKING: "跟踪中",
        PENDING: "挂起",
        DONE: "完成",
        CANCELED: "取消",
    }

    def __init__(self, state: int):
        self.state = state

    def get_state(self) -> int:
        return self.state

    def valid(self):
        self.state = self.VALID

    def prepare(self):
        self.state = self.PREPARE

    def tracking(self):
        self.state = self.TRACKING

    def pending(self):
        self.state = self.PENDING

    def done(self):
        self.state = self.DONE

    def cancel(self):
        self.state = self.CANCELED

    def restore(self):
        self.state = self.VALID

    def __str__(self):
        return self.STATE_MAP.get(self.state, "未知")


class MissionState:
    """任务状态管理类"""
    PENDING = 0   # 待处理
    READY = 1     # 就绪
    DOING = 2     # 进行中
    DONE = 3      # 完成
    CANCELED = 4  # 取消

    STATE_MAP = {
        PENDING: "待处理",
        READY: "就绪",
        DOING: "进行中",
        DONE: "完成",
        CANCELED: "取消",
    }

    def __init__(self, state: int):
        self.state = state

    def get_state(self) -> int:
        return self.state

    def pending(self):
        self.state = self.PENDING

    def ready(self):
        self.state = self.READY

    def doing(self):
        self.state = self.DOING

    def done(self):
        self.state = self.DONE

    def cancel(self):
        self.state = self.CANCELED

    def __str__(self):
        return self.STATE_MAP.get(self.state, "未知")


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
