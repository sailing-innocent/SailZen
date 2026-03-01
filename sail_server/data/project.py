# -*- coding: utf-8 -*-
# @file project.py
# @brief The Project Data Storage
# @author sailing-innocent
# @date 2025-04-21
# @version 2.0
# ---------------------------------

"""
项目管理模块数据层

ORM 模型已从 infrastructure.orm.project 迁移
DTO 模型已从 application.dto.project 迁移

此文件保留向后兼容的导出、状态机枚举和遗留的 dataclass DTOs
（因为 controller 层仍使用 Litestar DataclassDTO）
"""

import json
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any

# 从 infrastructure.orm 导入 ORM 模型
from sail_server.infrastructure.orm.project import (
    Project,
    Mission,
)

# 从 application.dto 导入 Pydantic DTOs
from sail_server.application.dto.project import (
    ProjectBase,
    ProjectCreateRequest,
    ProjectUpdateRequest,
    ProjectResponse,
    ProjectListResponse,
    MissionBase,
    MissionCreateRequest,
    MissionUpdateRequest,
    MissionResponse,
    MissionListResponse,
    MissionTreeResponse,
)


# -----------------------------------------
# Project State Machine (保留在此，因为是业务逻辑)
# -----------------------------------------
class ProjectState:
    """项目状态机"""
    # Project State Machine
    # -----------------------------------------------------
    # INVALID -> VALID -> PREPARE -> TRACKING ---> DONE
    #                                  ^   |
    #                                  |   v
    #                                  PENDING---> CANCEL
    # ------------------------------------------------------
    # state enum
    INVALID = 0
    VALID = 1
    PREPARE = 2
    TRACKING = 3
    DONE = 4
    PENDING = 5
    CANCELED = 6
    _state = INVALID

    def __init__(self, state: int = INVALID):
        self._state = state

    def valid(self):
        self._state = self.VALID

    def prepare(self):
        if self._state == self.VALID:
            self._state = self.PREPARE
        else:
            raise ValueError("Invalid state for prepare")

    def tracking(self):
        if self._state == self.PREPARE:
            self._state = self.TRACKING
        else:
            raise ValueError("Invalid state for tracking")

    def pending(self):
        if self._state == self.TRACKING:
            self._state = self.PENDING
        else:
            raise ValueError("Invalid state for pending")

    def restore(self):
        if self._state == self.PENDING:
            self._state = self.TRACKING
        else:
            raise ValueError("Invalid state for restore")

    def done(self):
        if self._state == self.PENDING:
            self._state = self.DONE
        else:
            raise ValueError("Invalid state for done")

    def cancel(self):
        # no need to check state
        self._state = self.CANCELED

    def get_state(self) -> int:
        return self._state


# -----------------------------------------
# Mission State Machine (保留在此，因为是业务逻辑)
# -----------------------------------------
class MissionState:
    """任务状态机"""
    # Mission State Machine
    # -----------------------------------------------------
    # PENDING -> READY -> DOING ---> DONE
    #  ^                  |    |
    #  |                  |    v
    #  <------------------    CANCEL
    # ------------------------------------------------------
    PENDING = 0
    READY = 1
    DOING = 2
    DONE = 3
    CANCELED = 4

    def __init__(self, state: int = PENDING):
        self._state = state

    def pending(self):
        self._state = self.PENDING

    def ready(self):
        self._state = self.READY

    def doing(self):
        self._state = self.DOING

    def done(self):
        self._state = self.DONE

    def cancel(self):
        self._state = self.CANCELED

    def get_state(self) -> int:
        return self._state


# ============================================================================
# Legacy Dataclass DTOs (保留以兼容现有 controller)
# TODO: 迁移到 Pydantic DTOs 后删除
# ============================================================================

@dataclass
class ProjectData:
    """项目数据 (legacy dataclass)"""
    id: int = field(default=None)
    name: str = field(default="")
    description: str = field(default="")
    state: int = field(default_factory=lambda: ProjectState().get_state())
    start_time_qbw: int = field(
        default_factory=lambda: 0  # TODO: import QuarterBiWeekTime if needed
    )
    end_time_qbw: int = field(
        default_factory=lambda: 0  # TODO: import QuarterBiWeekTime if needed
    )
    ctime: datetime = field(default_factory=lambda: datetime.now())
    mtime: datetime = field(default_factory=lambda: datetime.now())

    @classmethod
    def read_from_orm(cls, orm: Project):
        return cls(
            id=orm.id,
            name=orm.name,
            description=orm.description,
            state=orm.state,
            start_time_qbw=orm.start_time_qbw,
            end_time_qbw=orm.end_time_qbw,
            ctime=orm.ctime,
            mtime=orm.mtime,
        )

    @classmethod
    def from_dict(cls, json_data: dict):
        return cls(
            id=json_data.get("id"),
            name=json_data.get("name"),
            description=json_data.get("description"),
            state=json_data.get("state"),
            start_time_qbw=json_data.get("start_time_qbw"),
            end_time_qbw=json_data.get("end_time_qbw"),
            ctime=json_data.get("ctime"),
            mtime=json_data.get("mtime"),
        )

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "state": self.state,
            "start_time_qbw": self.start_time_qbw,
            "end_time_qbw": self.end_time_qbw,
            "ctime": self.ctime,
            "mtime": self.mtime,
        }

    @classmethod
    def from_string(cls, project_str: str):
        return cls.from_dict(json.loads(project_str))

    def to_string(self):
        return json.dumps(self.to_dict())

    def create_project(self):
        return Project(
            name=self.name,
            description=self.description,
            start_time_qbw=self.start_time_qbw,
            end_time_qbw=self.end_time_qbw,
        )

    def update_project(self, project: Project):
        project.name = self.name
        project.description = self.description
        project.start_time_qbw = self.start_time_qbw
        project.end_time_qbw = self.end_time_qbw
        project.mtime = datetime.now()


@dataclass
class MissionData:
    """任务数据 (legacy dataclass)"""
    id: int = field(default=None)
    name: str = field(default="")
    description: str = field(default="")
    parent_id: int = field(default=0)
    project_id: int = field(default=0)
    state: int = field(default_factory=lambda: MissionState().get_state())
    ctime: datetime = field(default_factory=lambda: datetime.now())
    mtime: datetime = field(default_factory=lambda: datetime.now())
    ddl: datetime = field(
        default_factory=lambda: datetime.now() + timedelta(days=14)
    )

    @classmethod
    def read_from_orm(cls, orm: Mission):
        return cls(
            id=orm.id,
            name=orm.name,
            description=orm.description,
            parent_id=orm.parent_id,
            project_id=orm.project_id,
            state=orm.state,
            ctime=orm.ctime,
            mtime=orm.mtime,
            ddl=orm.ddl,
        )

    def create_mission(self):
        parent_id = self.parent_id if self.parent_id > 0 else None
        project_id = self.project_id if self.project_id > 0 else None
        return Mission(
            name=self.name,
            description=self.description,
            parent_id=parent_id,
            project_id=project_id,
            state=self.state,
            ddl=self.ddl,
        )

    @classmethod
    def from_dict(cls, json_data: dict):
        return cls(
            id=json_data.get("id"),
            name=json_data.get("name"),
            description=json_data.get("description"),
            parent_id=json_data.get("parent_id"),
            project_id=json_data.get("project_id"),
            state=json_data.get("state"),
            ctime=json_data.get("ctime"),
            mtime=json_data.get("mtime"),
            ddl=json_data.get("ddl"),
        )

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "parent_id": self.parent_id,
            "project_id": self.project_id,
            "state": self.state,
            "ctime": self.ctime,
            "mtime": self.mtime,
            "ddl": self.ddl,
        }


__all__ = [
    # State Machines
    "ProjectState",
    "MissionState",
    # ORM Models
    "Project",
    "Mission",
    # Pydantic DTOs
    "ProjectBase",
    "ProjectCreateRequest",
    "ProjectUpdateRequest",
    "ProjectResponse",
    "ProjectListResponse",
    "MissionBase",
    "MissionCreateRequest",
    "MissionUpdateRequest",
    "MissionResponse",
    "MissionListResponse",
    "MissionTreeResponse",
    # Legacy Dataclass DTOs
    "ProjectData",
    "MissionData",
]
