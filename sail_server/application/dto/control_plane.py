from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field


class RemoteWorkspaceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    slug: str
    name: str
    local_path: str
    policy_profile: str
    labels: dict[str, Any] = Field(default_factory=dict)
    is_enabled: bool
    inventory_source: str
    created_at: datetime
    updated_at: datetime


class EdgeNodeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    node_key: str
    display_name: str
    host_name: str
    runtime_version: Optional[str] = None
    capabilities: dict[str, Any] = Field(default_factory=dict)
    auth_mode: str
    ack_cursor: int
    status: str
    last_heartbeat_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime


class OpenCodeSessionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    session_key: str
    workspace_id: int
    edge_node_id: Optional[int] = None
    status: str
    desired_state: str
    observed_state: str
    branch_name: Optional[str] = None
    local_url: Optional[str] = None
    local_path: Optional[str] = None
    process_info: dict[str, Any] = Field(default_factory=dict)
    diagnostics: dict[str, Any] = Field(default_factory=dict)
    last_error: Optional[str] = None
    last_heartbeat_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime


class SessionActionCreateRequest(BaseModel):
    action_type: str
    initiator_id: str
    session_key: Optional[str] = None
    workspace_slug: Optional[str] = None
    risk_level: str = "safe-auto"
    confirmation_status: str = "not-required"
    payload: dict[str, Any] = Field(default_factory=dict)


class SessionActionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    action_key: str
    session_id: Optional[int] = None
    workspace_id: Optional[int] = None
    action_type: str
    initiator_id: str
    risk_level: str
    confirmation_status: str
    status: str
    edge_ack_status: str
    edge_ack_at: Optional[datetime] = None
    payload: dict[str, Any] = Field(default_factory=dict)
    result_payload: Optional[dict[str, Any]] = None
    created_at: datetime
    updated_at: datetime


class SessionEventResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    event_key: str
    sequence_id: int
    session_id: Optional[int] = None
    event_type: str
    event_source: str
    idempotency_key: str
    event_payload: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime


class InteractionThreadResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    thread_key: str
    platform: str
    chat_id: str
    sender_open_id: str
    active_workspace_slug: Optional[str] = None
    active_session_key: Optional[str] = None
    last_message_id: Optional[str] = None
    draft_payload: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime
