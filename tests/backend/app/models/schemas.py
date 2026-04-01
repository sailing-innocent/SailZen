from pydantic import BaseModel
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

    model_config = {"from_attributes": True}


class PipelineRunOut(BaseModel):
    id: int
    pipeline_id: str
    pipeline_name: str
    params: dict[str, Any]
    status: str
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None
    node_runs: list[NodeRunOut] = []

    model_config = {"from_attributes": True}
