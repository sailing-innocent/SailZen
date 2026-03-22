from typing import Any, Optional

from pydantic import BaseModel, Field


class WorkspaceUpsertRequest(BaseModel):
    slug: str
    name: str
    local_path: str
    policy_profile: str = "default"
    labels: dict[str, Any] = Field(default_factory=dict)
    is_enabled: bool = True
    inventory_source: str = "edge-config"


class SessionUpsertRequest(BaseModel):
    session_key: str
    workspace_slug: str
    edge_node_key: str
    status: str = "stopped"
    desired_state: str = "stopped"
    observed_state: str = "unknown"
    local_url: Optional[str] = None
    local_path: Optional[str] = None
    process_info: dict[str, Any] = Field(default_factory=dict)
    diagnostics: dict[str, Any] = Field(default_factory=dict)
    last_error: Optional[str] = None
