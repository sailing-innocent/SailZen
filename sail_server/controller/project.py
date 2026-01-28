# -*- coding: utf-8 -*-
# @file life.py
# @brief Life Controller
# @author sailing-innocent
# @date 2025-08-24
# @version 1.0
# ---------------------------------
from __future__ import annotations
from litestar.dto import DataclassDTO
from litestar.dto.config import DTOConfig
from litestar import Controller, delete, get, post, put, Request, Response
from litestar.exceptions import NotFoundException

from sail_server.data.project import ProjectData, MissionData
from sail_server.model.project import (
    create_project_impl,
    get_project_impl,
    get_projects_impl,
    update_project_impl,
    delete_project_impl,
    create_mission_impl,
    get_mission_impl,
    get_missions_impl,
    update_mission_impl,
    delete_mission_impl,
    pending_mission_impl,
    ready_mission_impl,
    doing_mission_impl,
    done_mission_impl,
    cancel_mission_impl,
    postpone_mission_impl,
    get_upcoming_missions_impl,
    get_overdue_missions_impl,
)
from sqlalchemy.orm import Session
from typing import Generator, List, Optional


class ProjectDataWriteDTO(DataclassDTO[ProjectData]):
    config = DTOConfig(
        include={"name", "description", "start_time", "end_time"},
    )


class ProjectDataUpdateDTO(DataclassDTO[ProjectData]):
    config = DTOConfig(
        include={"name", "description", "start_time", "end_time"},
    )


class ProjectDataReadDTO(DataclassDTO[ProjectData]):
    config = DTOConfig(exclude={"ctime", "mtime"})


class ProjectController(Controller):
    dto = ProjectDataWriteDTO
    return_dto = ProjectDataReadDTO
    path = "/project"

    @get("")
    async def get_projects(
        self,
        router_dependency: Generator[Session, None, None],
        request: Request,
        skip: int = 0,
        limit: int = -1
    ) -> List[ProjectData]:
        db = next(router_dependency)
        projects = get_projects_impl(db, skip, limit)
        request.logger.info(f"Get projects: {len(projects)}")
        return projects

    @get("/{project_id:int}")
    async def get_project(
        self,
        project_id: int,
        router_dependency: Generator[Session, None, None],
        request: Request,
    ) -> ProjectData:
        """
        Get a project by its ID.
        """
        db = next(router_dependency)
        project = get_project_impl(db, project_id)
        request.logger.info(f"Get project {project_id}: {project}")
        if not project:
            raise NotFoundException(detail=f"Project with ID {project_id} not found")
        return project

    @post("/")
    async def create_project(
        self,
        data: ProjectData,
        router_dependency: Generator[Session, None, None],
        request: Request,
    ) -> ProjectData:
        """
        Create a new project.
        """
        db = next(router_dependency)
        project = create_project_impl(db, data)
        request.logger.info(f"Created project: {project.name}")
        return project

    @put("/{project_id:int}")
    async def update_project(
        self,
        project_id: int,
        data: ProjectData,
        router_dependency: Generator[Session, None, None],
        request: Request,
    ) -> ProjectData:
        """
        Update a project by its ID.
        """
        db = next(router_dependency)
        project = update_project_impl(db, project_id, data)
        request.logger.info(f"Updated project {project_id}: {project}")
        if not project:
            raise NotFoundException(detail=f"Project with ID {project_id} not found")
        return project

    @delete("/{project_id:int}", status_code=200)
    async def delete_project(
        self,
        project_id: int,
        router_dependency: Generator[Session, None, None],
        request: Request,
    ) -> ProjectData:
        """
        Delete a project by its ID.
        """
        db = next(router_dependency)
        project = delete_project_impl(db, project_id)
        request.logger.info(f"Deleted project {project_id}")
        if not project:
            raise NotFoundException(detail=f"Project with ID {project_id} not found")
        return project


class MissionDataWriteDTO(DataclassDTO[MissionData]):
    config = DTOConfig(
        include={"name", "description", "parent_id", "project_id", "ddl"},
    )


class MissionDataUpdateDTO(DataclassDTO[MissionData]):
    config = DTOConfig(
        include={"name", "description", "parent_id", "project_id", "ddl"},
    )


class MissionDataReadDTO(DataclassDTO[MissionData]):
    config = DTOConfig(exclude={"ctime", "mtime"})


class MissionController(Controller):
    dto = MissionDataWriteDTO
    return_dto = MissionDataReadDTO
    path = "/mission"

    @get()
    async def get_missions(
        self,
        router_dependency: Generator[Session, None, None],
        request: Request,
        skip: int = 0,
        limit: int = -1,
        parent_id: Optional[int] = None,
        project_id: Optional[int] = None,
    ) -> List[MissionData]:
        """
        Get all missions with optional filtering by parent_id and project_id.
        """
        db = next(router_dependency)
        missions = get_missions_impl(db, skip, limit, parent_id, project_id)
        request.logger.info(f"Get missions: {len(missions)}")
        return missions

    @get("/{mission_id:int}")
    async def get_mission(
        self,
        mission_id: int,
        router_dependency: Generator[Session, None, None],
        request: Request,
    ) -> MissionData:
        """
        Get a mission by its ID.
        """
        db = next(router_dependency)
        mission = get_mission_impl(db, mission_id)
        request.logger.info(f"Get mission {mission_id}: {mission}")
        if not mission:
            raise NotFoundException(detail=f"Mission with ID {mission_id} not found")
        return mission

    @post("/")
    async def create_mission(
        self,
        data: MissionData,
        router_dependency: Generator[Session, None, None],
        request: Request,
    ) -> MissionData:
        """
        Create a new mission.
        """
        db = next(router_dependency)
        mission = create_mission_impl(db, data)
        request.logger.info(f"Created mission: {mission.name}")
        return mission

    @put("/{mission_id:int}")
    async def update_mission(
        self,
        mission_id: int,
        data: MissionData,
        router_dependency: Generator[Session, None, None],
        request: Request,
    ) -> MissionData:
        """
        Update a mission by its ID.
        """
        db = next(router_dependency)
        mission = update_mission_impl(db, mission_id, data)
        request.logger.info(f"Updated mission {mission_id}: {mission}")
        if not mission:
            raise NotFoundException(detail=f"Mission with ID {mission_id} not found")
        return mission

    @delete("/{mission_id:int}", status_code=200)
    async def delete_mission(
        self,
        mission_id: int,
        router_dependency: Generator[Session, None, None],
        request: Request,
    ) -> MissionData:
        """
        Delete a mission by its ID.
        """
        db = next(router_dependency)
        mission = delete_mission_impl(db, mission_id)
        request.logger.info(f"Deleted mission {mission_id}")
        if not mission:
            raise NotFoundException(detail=f"Mission with ID {mission_id} not found")
        return mission

    # ------------------------------------------------
    # Mission State Transition APIs
    # ------------------------------------------------
    @post("/{mission_id:int}/pending", status_code=200)
    async def pending_mission(
        self,
        mission_id: int,
        router_dependency: Generator[Session, None, None],
        request: Request,
    ) -> MissionData:
        """Set mission state to PENDING."""
        db = next(router_dependency)
        mission = pending_mission_impl(db, mission_id)
        request.logger.info(f"Mission {mission_id} set to PENDING")
        if not mission:
            raise NotFoundException(detail=f"Mission with ID {mission_id} not found")
        return mission

    @post("/{mission_id:int}/ready", status_code=200)
    async def ready_mission(
        self,
        mission_id: int,
        router_dependency: Generator[Session, None, None],
        request: Request,
    ) -> MissionData:
        """Set mission state to READY."""
        db = next(router_dependency)
        mission = ready_mission_impl(db, mission_id)
        request.logger.info(f"Mission {mission_id} set to READY")
        if not mission:
            raise NotFoundException(detail=f"Mission with ID {mission_id} not found")
        return mission

    @post("/{mission_id:int}/doing", status_code=200)
    async def doing_mission(
        self,
        mission_id: int,
        router_dependency: Generator[Session, None, None],
        request: Request,
    ) -> MissionData:
        """Set mission state to DOING (start working)."""
        db = next(router_dependency)
        mission = doing_mission_impl(db, mission_id)
        request.logger.info(f"Mission {mission_id} set to DOING")
        if not mission:
            raise NotFoundException(detail=f"Mission with ID {mission_id} not found")
        return mission

    @post("/{mission_id:int}/done", status_code=200)
    async def done_mission(
        self,
        mission_id: int,
        router_dependency: Generator[Session, None, None],
        request: Request,
    ) -> MissionData:
        """Set mission state to DONE (complete mission)."""
        db = next(router_dependency)
        mission = done_mission_impl(db, mission_id)
        request.logger.info(f"Mission {mission_id} set to DONE")
        if not mission:
            raise NotFoundException(detail=f"Mission with ID {mission_id} not found")
        return mission

    @post("/{mission_id:int}/cancel", status_code=200)
    async def cancel_mission(
        self,
        mission_id: int,
        router_dependency: Generator[Session, None, None],
        request: Request,
    ) -> MissionData:
        """Set mission state to CANCELED."""
        db = next(router_dependency)
        mission = cancel_mission_impl(db, mission_id)
        request.logger.info(f"Mission {mission_id} set to CANCELED")
        if not mission:
            raise NotFoundException(detail=f"Mission with ID {mission_id} not found")
        return mission

    @post("/{mission_id:int}/postpone", status_code=200)
    async def postpone_mission(
        self,
        mission_id: int,
        router_dependency: Generator[Session, None, None],
        request: Request,
        days: int = 7,
    ) -> MissionData:
        """Postpone mission deadline by specified days."""
        db = next(router_dependency)
        mission = postpone_mission_impl(db, mission_id, days)
        request.logger.info(f"Mission {mission_id} postponed by {days} days")
        if not mission:
            raise NotFoundException(detail=f"Mission with ID {mission_id} not found")
        return mission

    # ------------------------------------------------
    # Mission Reminder APIs
    # ------------------------------------------------
    @get("/upcoming")
    async def get_upcoming_missions(
        self,
        router_dependency: Generator[Session, None, None],
        request: Request,
        hours: int = 24,
    ) -> List[MissionData]:
        """Get missions with deadlines within specified hours."""
        db = next(router_dependency)
        missions = get_upcoming_missions_impl(db, hours)
        request.logger.info(f"Found {len(missions)} upcoming missions within {hours}h")
        return missions

    @get("/overdue")
    async def get_overdue_missions(
        self,
        router_dependency: Generator[Session, None, None],
        request: Request,
    ) -> List[MissionData]:
        """Get all overdue missions (past deadline, not done/canceled)."""
        db = next(router_dependency)
        missions = get_overdue_missions_impl(db)
        request.logger.info(f"Found {len(missions)} overdue missions")
        return missions
