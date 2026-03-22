from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


class SyncMessageType(str, Enum):
    INBOUND_MESSAGE = "inbound_message"
    ACTION_ACK = "action_ack"
    HEARTBEAT = "heartbeat"
    OBSERVED_STATE = "observed_state"
    OUTBOUND_DELIVERY_ACK = "outbound_delivery_ack"


class DeliveryStatus(str, Enum):
    PENDING = "pending"
    ACKED = "acked"
    FAILED = "failed"


class DesiredSessionState(str, Enum):
    STOPPED = "stopped"
    RUNNING = "running"
    RESTARTING = "restarting"
    RECOVERING = "recovering"


class ObservedSessionState(str, Enum):
    UNKNOWN = "unknown"
    STOPPED = "stopped"
    STARTING = "starting"
    RUNNING = "running"
    UNHEALTHY = "unhealthy"
    CRASHED = "crashed"


class EdgeQueuePolicy(BaseModel):
    max_buffered_items: int = 500
    max_retry_attempts: int = 5
    replay_window_seconds: int = 3600
    heartbeat_interval_seconds: int = 15
    delivery_retry_backoff_seconds: list[int] = Field(
        default_factory=lambda: [5, 15, 60, 180, 300]
    )


class SyncEnvelope(BaseModel):
    message_type: SyncMessageType
    message_id: str
    idempotency_key: str
    edge_node_key: str
    thread_key: Optional[str] = None
    action_key: Optional[str] = None
    session_key: Optional[str] = None
    workspace_slug: Optional[str] = None
    created_at: str
    attempt_count: int = 1
    replayed: bool = False
    payload: dict[str, Any] = Field(default_factory=dict)


class SessionDesiredObservedState(BaseModel):
    session_key: str
    workspace_slug: str
    desired_state: DesiredSessionState
    observed_state: ObservedSessionState
    health_status: str = "unknown"
    branch_name: Optional[str] = None
    local_url: Optional[str] = None
    local_path: Optional[str] = None
    last_error: Optional[str] = None
    process_info: dict[str, Any] = Field(default_factory=dict)
    diagnostics: dict[str, Any] = Field(default_factory=dict)
    observed_at: str


class EdgeHeartbeatPayload(BaseModel):
    edge_node_key: str
    host_name: str
    runtime_version: Optional[str] = None
    capabilities: dict[str, Any] = Field(default_factory=dict)
    queue_depth: int = 0
    last_ack_cursor: int = 0
    sent_at: str


class ActionAckPayload(BaseModel):
    action_key: str
    delivery_status: DeliveryStatus
    ack_cursor: int = 0
    detail: Optional[str] = None
    sent_at: str


class OutboundDeliveryAckPayload(BaseModel):
    message_id: str
    delivery_status: DeliveryStatus
    ack_cursor: int = 0
    provider_message_id: Optional[str] = None
    detail: Optional[str] = None
    sent_at: str


class EdgeQueueItem(BaseModel):
    envelope: SyncEnvelope
    retry_count: int = 0
    next_retry_at: Optional[str] = None
    expires_at: Optional[str] = None
