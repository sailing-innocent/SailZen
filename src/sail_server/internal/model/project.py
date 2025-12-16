# -*- coding: utf-8 -*-
# @file necessity.py
# @brief The Necessity Model
# @author sailing-innocent
# @date 2025-02-03
# @version 1.0
# ---------------------------------

from pydantic import BaseModel
from internal.data.project import (
    Project,
    ProjectState,
    ProjectData,
    Mission,
    MissionState,
    MissionData,
)
from datetime import datetime
from utils.time_utils import QuarterBiWeekTime


def clean_all_impl(db):
    db.query(Project).delete()
    db.commit()


# ------------------------------------------------
# Project Management
# ------------------------------------------------


def create_project_impl(db, project_create: ProjectData):
    project = project_create.create_project()
    db.add(project)
    db.commit()
    db.refresh(project)
    return ProjectData.read_from_orm(project)


def change_project_state_impl(db, project_id: int, change_func: callable):
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        return None
    new_state = ProjectState(project.state)
    change_func(new_state)
    project.state = new_state.get_state()
    db.commit()
    db.refresh(project)
    return ProjectData.read_from_orm(project)


def valid_project_impl(db, project_id: int):
    return change_project_state_impl(db, project_id, lambda state: state.valid())


def prepare_project_impl(db, project_id: int):
    return change_project_state_impl(db, project_id, lambda state: state.prepare())


def tracking_project_impl(db, project_id: int):
    return change_project_state_impl(db, project_id, lambda state: state.tracking())


def pending_project_impl(db, project_id: int):
    return change_project_state_impl(db, project_id, lambda state: state.pending())


def restore_project_impl(db, project_id: int):
    return change_project_state_impl(db, project_id, lambda state: state.restore())


def done_project_impl(db, project_id: int):
    return change_project_state_impl(db, project_id, lambda state: state.done())


def cancel_project_impl(db, project_id: int):
    return change_project_state_impl(db, project_id, lambda state: state.cancel())


def get_project_impl(db, project_id: int):
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        return None
    return ProjectData.read_from_orm(project)


def get_projects_impl(db, skip: int = 0, limit: int = -1):
    query = db.query(Project)
    if skip > 0:
        query = query.offset(skip)
    if limit > 0:
        query = query.limit(limit)

    projects = query.all()
    return [ProjectData.read_from_orm(project) for project in projects]


def update_project_impl(db, project_id: int, project_update: ProjectData):
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        return None
    project_update.update_project(project)
    db.commit()
    db.refresh(project)
    return ProjectData.read_from_orm(project)


def delete_project_impl(db, project_id: int):
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        return None
    db.delete(project)
    db.commit()
    return ProjectData.read_from_orm(project)


# ------------------------------------------------
# Mission Management
# ------------------------------------------------


def create_mission_impl(db, mission_create: MissionData):
    mission = mission_create.create_mission()
    db.add(mission)
    db.commit()
    db.refresh(mission)
    return MissionData.read_from_orm(mission)


def change_mission_state_impl(db, mission_id: int, change_func: callable):
    mission = db.query(Mission).filter(Mission.id == mission_id).first()
    if not mission:
        return None
    new_state = MissionState(mission.state)
    change_func(new_state)

    mission.state = new_state.get_state()
    db.commit()
    db.refresh(mission)
    return MissionData.read_from_orm(mission)


def pending_mission_impl(db, mission_id: int):
    return change_mission_state_impl(db, mission_id, lambda state: state.pending())


def ready_mission_impl(db, mission_id: int):
    return change_mission_state_impl(db, mission_id, lambda state: state.ready())


def doing_mission_impl(db, mission_id: int):
    return change_mission_state_impl(db, mission_id, lambda state: state.doing())


def done_mission_impl(db, mission_id: int):
    return change_mission_state_impl(db, mission_id, lambda state: state.done())


def cancel_mission_impl(db, mission_id: int):
    return change_mission_state_impl(db, mission_id, lambda state: state.cancel())


def get_mission_impl(db, mission_id: int):
    mission = db.query(Mission).filter(Mission.id == mission_id).first()
    if not mission:
        return None
    return MissionData.read_from_orm(mission)


def get_missions_impl(
    db, skip: int = 0, limit: int = -1, parent_id: int = None, project_id: int = None
):
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
    return [MissionData.read_from_orm(mission) for mission in missions]


def update_mission_impl(db, mission_id: int, mission_update: MissionData):
    mission = db.query(Mission).filter(Mission.id == mission_id).first()
    if not mission:
        return None

    mission.name = mission_update.name
    mission.description = mission_update.description
    mission.parent_id = mission_update.parent_id
    mission.project_id = mission_update.project_id
    mission.ddl = mission_update.ddl
    mission.mtime = datetime.now()

    db.commit()
    db.refresh(mission)
    return MissionData.read_from_orm(mission)


def delete_mission_impl(db, mission_id: int):
    mission = db.query(Mission).filter(Mission.id == mission_id).first()
    if not mission:
        return None
    db.delete(mission)
    db.commit()
    return MissionData.read_from_orm(mission)
