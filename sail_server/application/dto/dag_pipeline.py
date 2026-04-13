# -*- coding: utf-8 -*-
# @file dag_pipeline.py
# @brief DAG Pipeline DTOs
# @author sailing-innocent
# @date 2026-04-13
# @version 1.0
# ---------------------------------

from pydantic import BaseModel, ConfigDict
from datetime import datetime
from typing import Any


class PipelineInfo(BaseModel):
    id: str
    name: str
    description: str
    params: list[dict[str, Any]]


class RunRequest(BaseModel):
    pipeline_id: str
    params: dict[str, Any] = {}


class NodeRunOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    node_id: str
    node_name: str
    node_type: str
    description: str
    depends_on: list[str]
    status: str
    logs: list[str]
    started_at: datetime | None
    finished_at: datetime | None
    duration: float | None
    is_dynamic: bool
    can_spawn: bool


class PipelineRunOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    pipeline_id: str
    pipeline_name: str
    params: dict[str, Any]
    status: str
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None
    node_runs: list[NodeRunOut] = []
