# -*- coding: utf-8 -*-
# @file project.py
# @brief The Project Model
# @author sailing-innocent
# @date 2025-02-03
# @version 2.0
# ---------------------------------

from datetime import datetime, timedelta
from typing import List, Optional

from sail_server.infrastructure.orm.project import (
    Project,
    Mission,
)
from sail_server.application.dto.project import (
    ProjectCreateRequest,
    ProjectUpdateRequest,
    ProjectResponse,
    MissionCreateRequest,
    MissionUpdateRequest,
    MissionResponse,
    ProjectState,
    MissionState,
)
from sail_server.utils.time_utils import QuarterBiWeekTime


def clean_all_impl(db):
    db.query(Project).delete()
    db.commit()


# ------------------------------------------------
# Project Management
# ------------------------------------------------


def _project_to_response(project: Project) -> ProjectResponse:
    """Convert Project ORM model to ProjectResponse DTO."""
    return ProjectResponse(
        id=project.id,
        name=project.name,
        description=project.description,
        state=project.state,
        start_time_qbw=project.start_time_qbw,
        end_time_qbw=project.end_time_qbw,
        timespan_id=project.timespan_id,
        energy_budget=project.energy_budget or 0,
        priority=project.priority or 0,
        tags=project.tags or [],
        ctime=project.ctime,
        mtime=project.mtime,
    )


def create_project_impl(db, project_create: ProjectCreateRequest) -> ProjectResponse:
    """Create a new project from ProjectCreateRequest."""
    now = QuarterBiWeekTime.now()
    project = Project(
        name=project_create.name,
        description=project_create.description,
        state=ProjectState.INVALID,
        start_time_qbw=project_create.start_time_qbw
        if project_create.start_time_qbw is not None
        else now,
        end_time_qbw=project_create.end_time_qbw
        if project_create.end_time_qbw is not None
        else now + 1,
        timespan_id=project_create.timespan_id,
        energy_budget=project_create.energy_budget or 0,
        priority=project_create.priority or 0,
        tags=project_create.tags or [],
    )
    db.add(project)
    db.commit()
    db.refresh(project)
    return _project_to_response(project)


def change_project_state_impl(
    db, project_id: int, change_func: callable
) -> Optional[ProjectResponse]:
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        return None
    new_state = ProjectState(project.state)
    change_func(new_state)
    project.state = new_state.get_state()
    db.commit()
    db.refresh(project)
    return _project_to_response(project)


def valid_project_impl(db, project_id: int) -> Optional[ProjectResponse]:
    return change_project_state_impl(db, project_id, lambda state: state.valid())


def prepare_project_impl(db, project_id: int) -> Optional[ProjectResponse]:
    return change_project_state_impl(db, project_id, lambda state: state.prepare())


def tracking_project_impl(db, project_id: int) -> Optional[ProjectResponse]:
    return change_project_state_impl(db, project_id, lambda state: state.tracking())


def pending_project_impl(db, project_id: int) -> Optional[ProjectResponse]:
    return change_project_state_impl(db, project_id, lambda state: state.pending())


def restore_project_impl(db, project_id: int) -> Optional[ProjectResponse]:
    return change_project_state_impl(db, project_id, lambda state: state.restore())


def done_project_impl(db, project_id: int) -> Optional[ProjectResponse]:
    return change_project_state_impl(db, project_id, lambda state: state.done())


def cancel_project_impl(db, project_id: int) -> Optional[ProjectResponse]:
    return change_project_state_impl(db, project_id, lambda state: state.cancel())


def get_project_impl(db, project_id: int) -> Optional[ProjectResponse]:
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        return None
    return _project_to_response(project)


def get_projects_impl(db, skip: int = 0, limit: int = -1) -> List[ProjectResponse]:
    query = db.query(Project)
    if skip > 0:
        query = query.offset(skip)
    if limit > 0:
        query = query.limit(limit)

    projects = query.all()
    return [_project_to_response(project) for project in projects]


def update_project_impl(
    db, project_id: int, project_update: ProjectUpdateRequest
) -> Optional[ProjectResponse]:
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        return None

    # Update only provided fields
    if project_update.name is not None:
        project.name = project_update.name
    if project_update.description is not None:
        project.description = project_update.description
    if project_update.state is not None:
        project.state = project_update.state
    if project_update.start_time_qbw is not None:
        project.start_time_qbw = project_update.start_time_qbw
    if project_update.end_time_qbw is not None:
        project.end_time_qbw = project_update.end_time_qbw
    if project_update.timespan_id is not None:
        project.timespan_id = project_update.timespan_id
    if project_update.energy_budget is not None:
        project.energy_budget = project_update.energy_budget
    if project_update.priority is not None:
        project.priority = project_update.priority
    if project_update.tags is not None:
        project.tags = list(project_update.tags)

    project.mtime = datetime.now()
    db.commit()
    db.refresh(project)
    return _project_to_response(project)


def delete_project_impl(db, project_id: int) -> Optional[ProjectResponse]:
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        return None
    # 先删除关联的所有 missions（避免外键约束违反）
    db.query(Mission).filter(Mission.project_id == project_id).delete()
    # 再删除 project
    db.delete(project)
    db.commit()
    return _project_to_response(project)


# ------------------------------------------------
# Mission Management
# ------------------------------------------------


def _mission_to_response(mission: Mission) -> MissionResponse:
    """Convert Mission ORM model to MissionResponse DTO."""
    return MissionResponse(
        id=mission.id,
        name=mission.name,
        description=mission.description,
        parent_id=mission.parent_id,
        project_id=mission.project_id,
        state=mission.state,
        ddl=mission.ddl,
        planned_minutes=mission.planned_minutes or 0,
        actual_minutes=mission.actual_minutes or 0,
        energy_cost=mission.energy_cost or 0,
        day_id=mission.day_id,
        milestone_id=mission.milestone_id,
        health_constraint=mission.health_constraint or "normal",
        lft=mission.lft,
        rgt=mission.rgt,
        tree_id=mission.tree_id,
        ctime=mission.ctime,
        mtime=mission.mtime,
    )


def create_mission_impl(db, mission_create: MissionCreateRequest) -> MissionResponse:
    """Create a new mission from MissionCreateRequest."""
    mission = Mission(
        name=mission_create.name,
        description=mission_create.description,
        parent_id=mission_create.parent_id,
        project_id=mission_create.project_id,
        state=MissionState.PENDING,
        ddl=mission_create.ddl,
        planned_minutes=mission_create.planned_minutes or 0,
        actual_minutes=mission_create.actual_minutes or 0,
        energy_cost=mission_create.energy_cost or 0,
        day_id=mission_create.day_id,
        milestone_id=mission_create.milestone_id,
        health_constraint=mission_create.health_constraint or "normal",
    )
    db.add(mission)
    db.commit()
    db.refresh(mission)
    return _mission_to_response(mission)


def change_mission_state_impl(
    db, mission_id: int, change_func: callable
) -> Optional[MissionResponse]:
    mission = db.query(Mission).filter(Mission.id == mission_id).first()
    if not mission:
        return None
    new_state = MissionState(mission.state)
    change_func(new_state)

    mission.state = new_state.get_state()
    db.commit()
    db.refresh(mission)
    return _mission_to_response(mission)


def pending_mission_impl(db, mission_id: int) -> Optional[MissionResponse]:
    return change_mission_state_impl(db, mission_id, lambda state: state.pending())


def ready_mission_impl(db, mission_id: int) -> Optional[MissionResponse]:
    return change_mission_state_impl(db, mission_id, lambda state: state.ready())


def doing_mission_impl(db, mission_id: int) -> Optional[MissionResponse]:
    return change_mission_state_impl(db, mission_id, lambda state: state.doing())


def done_mission_impl(db, mission_id: int) -> Optional[MissionResponse]:
    return change_mission_state_impl(db, mission_id, lambda state: state.done())


def cancel_mission_impl(db, mission_id: int) -> Optional[MissionResponse]:
    return change_mission_state_impl(db, mission_id, lambda state: state.cancel())


def get_mission_impl(db, mission_id: int) -> Optional[MissionResponse]:
    mission = db.query(Mission).filter(Mission.id == mission_id).first()
    if not mission:
        return None
    return _mission_to_response(mission)


def get_missions_impl(
    db, skip: int = 0, limit: int = -1, parent_id: int = None, project_id: int = None
) -> List[MissionResponse]:
    query = db.query(Mission)

    if parent_id is not None:
        query = query.filter(Mission.parent_id == parent_id)

    if project_id is not None:
        query = query.filter(Mission.project_id == project_id)

    if skip > 0:
        query = query.offset(skip)
    if limit > 0:
        query = query.limit(limit)

    missions = query.all()
    return [_mission_to_response(mission) for mission in missions]


def update_mission_impl(
    db, mission_id: int, mission_update: MissionUpdateRequest
) -> Optional[MissionResponse]:
    mission = db.query(Mission).filter(Mission.id == mission_id).first()
    if not mission:
        return None

    # Update only provided fields
    if mission_update.name is not None:
        mission.name = mission_update.name
    if mission_update.description is not None:
        mission.description = mission_update.description
    if mission_update.state is not None:
        mission.state = mission_update.state
    if mission_update.ddl is not None:
        mission.ddl = mission_update.ddl
    if mission_update.planned_minutes is not None:
        mission.planned_minutes = mission_update.planned_minutes
    if mission_update.actual_minutes is not None:
        mission.actual_minutes = mission_update.actual_minutes
    if mission_update.energy_cost is not None:
        mission.energy_cost = mission_update.energy_cost
    if mission_update.day_id is not None:
        mission.day_id = mission_update.day_id
    if mission_update.milestone_id is not None:
        mission.milestone_id = mission_update.milestone_id
    if mission_update.health_constraint is not None:
        mission.health_constraint = mission_update.health_constraint

    mission.mtime = datetime.now()
    db.commit()
    db.refresh(mission)
    return _mission_to_response(mission)


def delete_mission_impl(db, mission_id: int) -> Optional[MissionResponse]:
    mission = db.query(Mission).filter(Mission.id == mission_id).first()
    if not mission:
        return None
    db.delete(mission)
    db.commit()
    return _mission_to_response(mission)


# ------------------------------------------------
# Mission State Transition (Simplified)
# ------------------------------------------------
# For the basic task loop, we simplify state transitions:
# Any state can transition to any other state for flexibility


def postpone_mission_impl(
    db, mission_id: int, days: int = 7
) -> Optional[MissionResponse]:
    """Postpone mission deadline by specified days."""
    mission = db.query(Mission).filter(Mission.id == mission_id).first()
    if not mission:
        return None
    if mission.ddl:
        mission.ddl = mission.ddl + timedelta(days=days)
    else:
        mission.ddl = datetime.now() + timedelta(days=days)
    mission.mtime = datetime.now()
    db.commit()
    db.refresh(mission)
    return _mission_to_response(mission)


# ------------------------------------------------
# Mission Reminder Queries
# ------------------------------------------------


def get_upcoming_missions_impl(db, hours: int = 24) -> List[MissionResponse]:
    """Get missions with deadlines within specified hours that are not done/canceled."""
    now = datetime.now()
    deadline_threshold = now + timedelta(hours=hours)

    missions = (
        db.query(Mission)
        .filter(
            Mission.ddl >= now,
            Mission.ddl <= deadline_threshold,
            Mission.state.notin_([MissionState.DONE, MissionState.CANCELED]),
        )
        .order_by(Mission.ddl.asc())
        .all()
    )

    return [_mission_to_response(m) for m in missions]


def get_overdue_missions_impl(db) -> List[MissionResponse]:
    """Get all overdue missions (past deadline, not done/canceled)."""
    now = datetime.now()

    missions = (
        db.query(Mission)
        .filter(
            Mission.ddl < now,
            Mission.state.notin_([MissionState.DONE, MissionState.CANCELED]),
        )
        .order_by(Mission.ddl.asc())
        .all()
    )

    return [_mission_to_response(m) for m in missions]
