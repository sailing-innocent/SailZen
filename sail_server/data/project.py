# -*- coding: utf-8 -*-
# @file project.py
# @brief The Project Data Storage
# @author sailing-innocent
# @date 2025-04-21
# @version 2.0
# ---------------------------------

"""
项目管理模块数据层

此模块重新导出以下内容:
- ORM 模型: Project, Mission (从 infrastructure.orm.project 导入)
- Pydantic DTOs: ProjectBase, ProjectCreateRequest, ProjectUpdateRequest, 
  ProjectResponse, ProjectListResponse, MissionBase, MissionCreateRequest,
  MissionUpdateRequest, MissionResponse, MissionListResponse, MissionTreeResponse
  (从 application.dto.project 导入)
- 状态机: ProjectState, MissionState (业务逻辑，定义在此模块)
"""

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
]
