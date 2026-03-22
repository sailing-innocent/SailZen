from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from sail_server.control_plane.sync_contract import (
    ActionAckPayload,
    EdgeHeartbeatPayload,
    EdgeQueueItem,
    EdgeQueuePolicy,
    OutboundDeliveryAckPayload,
    SessionDesiredObservedState,
    SyncEnvelope,
)


class SyncEnvelopeRequest(SyncEnvelope):
    pass


class SyncEnvelopeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    accepted: bool = True
    event_key: str
    sequence_id: Optional[int] = None
    idempotency_key: str
    ack_cursor: int = 0
    delivery_status: str = "accepted"


class SessionStateSyncRequest(SessionDesiredObservedState):
    pass


class EdgeHeartbeatRequest(EdgeHeartbeatPayload):
    pass


class ActionAckRequest(ActionAckPayload):
    pass


class OutboundDeliveryAckRequest(OutboundDeliveryAckPayload):
    pass


class EdgeQueuePolicyResponse(EdgeQueuePolicy):
    pass


class EdgeQueueItemResponse(EdgeQueueItem):
    pass


class ReplayEventsResponse(BaseModel):
    next_cursor: int = 0
    events: list[SyncEnvelope] = Field(default_factory=list)
    queue_policy: EdgeQueuePolicyResponse
