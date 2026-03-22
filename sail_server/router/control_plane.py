from uuid import uuid4

from litestar import Controller, Router, get, post
from litestar.di import Provide
from litestar.exceptions import NotFoundException, ValidationException
from sqlalchemy.orm import Session

from sail_server.application.dto.control_plane import (
    EdgeNodeResponse,
    InteractionThreadResponse,
    OpenCodeSessionResponse,
    RemoteWorkspaceResponse,
    SessionActionCreateRequest,
    SessionActionResponse,
    SessionEventResponse,
)
from sail_server.application.dto.control_plane_commands import (
    SessionUpsertRequest,
    WorkspaceUpsertRequest,
)
from sail_server.application.dto.control_plane_sync import (
    ActionAckRequest,
    EdgeHeartbeatRequest,
    EdgeQueuePolicyResponse,
    OutboundDeliveryAckRequest,
    ReplayEventsResponse,
    SessionStateSyncRequest,
    SyncEnvelopeRequest,
    SyncEnvelopeResponse,
)
from sail_server.control_plane.dao import (
    EdgeNodeDAO,
    InteractionThreadDAO,
    OpenCodeSessionDAO,
    RemoteWorkspaceDAO,
    SessionActionDAO,
    SessionEventDAO,
)
from sail_server.control_plane.db import get_control_plane_db_dependency
from sail_server.control_plane.models import SessionAction
from sail_server.control_plane.service import (
    DEFAULT_EDGE_QUEUE_POLICY,
    ControlPlaneSyncService,
)
from sail_server.control_plane.sync_contract import DeliveryStatus, SyncMessageType


class ControlPlaneController(Controller):
    path = "/control-plane"

    @get("/workspaces")
    async def list_workspaces(
        self, control_plane_db: Session
    ) -> list[RemoteWorkspaceResponse]:
        dao = RemoteWorkspaceDAO(control_plane_db)
        return [
            RemoteWorkspaceResponse.model_validate(item)
            for item in dao.get_all(limit=200)
        ]

    @get("/edge-nodes")
    async def list_edge_nodes(
        self, control_plane_db: Session
    ) -> list[EdgeNodeResponse]:
        dao = EdgeNodeDAO(control_plane_db)
        return [
            EdgeNodeResponse.model_validate(item) for item in dao.get_all(limit=200)
        ]

    @get("/sessions")
    async def list_sessions(
        self, control_plane_db: Session
    ) -> list[OpenCodeSessionResponse]:
        dao = OpenCodeSessionDAO(control_plane_db)
        return [
            OpenCodeSessionResponse.model_validate(item)
            for item in dao.get_all(limit=200)
        ]

    @get("/sessions/{session_key:str}")
    async def get_session(
        self, control_plane_db: Session, session_key: str
    ) -> OpenCodeSessionResponse:
        dao = OpenCodeSessionDAO(control_plane_db)
        sessions = dao.filter_by(session_key=session_key, limit=1)
        if not sessions:
            raise NotFoundException(f"Session not found: {session_key}")
        return OpenCodeSessionResponse.model_validate(sessions[0])

    @post("/workspaces/upsert")
    async def upsert_workspace(
        self, control_plane_db: Session, data: WorkspaceUpsertRequest
    ) -> RemoteWorkspaceResponse:
        service = ControlPlaneSyncService(control_plane_db)
        workspace = service.upsert_workspace(data.model_dump(mode="json"))
        return RemoteWorkspaceResponse.model_validate(workspace)

    @post("/sessions/upsert")
    async def upsert_session(
        self, control_plane_db: Session, data: SessionUpsertRequest
    ) -> OpenCodeSessionResponse:
        service = ControlPlaneSyncService(control_plane_db)
        session = service.upsert_session(data.model_dump(mode="json"))
        return OpenCodeSessionResponse.model_validate(session)

    @post("/actions")
    async def create_action(
        self, control_plane_db: Session, data: SessionActionCreateRequest
    ) -> SessionActionResponse:
        workspace_id = None
        session_id = None

        if data.workspace_slug:
            workspace_matches = RemoteWorkspaceDAO(control_plane_db).filter_by(
                slug=data.workspace_slug, limit=1
            )
            if not workspace_matches:
                raise ValidationException(f"Workspace not found: {data.workspace_slug}")
            workspace_id = workspace_matches[0].id

        if data.session_key:
            session_matches = OpenCodeSessionDAO(control_plane_db).filter_by(
                session_key=data.session_key, limit=1
            )
            if not session_matches:
                raise ValidationException(f"Session not found: {data.session_key}")
            session_id = session_matches[0].id

        action = SessionAction(
            action_key=f"act_{uuid4().hex}",
            session_id=session_id,
            workspace_id=workspace_id,
            action_type=data.action_type,
            initiator_id=data.initiator_id,
            risk_level=data.risk_level,
            confirmation_status=data.confirmation_status,
            payload=data.payload,
        )
        created = SessionActionDAO(control_plane_db).create(action)
        return SessionActionResponse.model_validate(created)

    @get("/actions")
    async def list_actions(
        self, control_plane_db: Session
    ) -> list[SessionActionResponse]:
        dao = SessionActionDAO(control_plane_db)
        return [
            SessionActionResponse.model_validate(item)
            for item in dao.get_all(limit=200)
        ]

    @get("/events")
    async def list_events(
        self, control_plane_db: Session
    ) -> list[SessionEventResponse]:
        dao = SessionEventDAO(control_plane_db)
        return [
            SessionEventResponse.model_validate(item) for item in dao.get_all(limit=200)
        ]

    @get("/threads")
    async def list_threads(
        self, control_plane_db: Session
    ) -> list[InteractionThreadResponse]:
        dao = InteractionThreadDAO(control_plane_db)
        return [
            InteractionThreadResponse.model_validate(item)
            for item in dao.get_all(limit=200)
        ]

    @post("/sync/envelopes")
    async def accept_sync_envelope(
        self, control_plane_db: Session, data: SyncEnvelopeRequest
    ) -> SyncEnvelopeResponse:
        service = ControlPlaneSyncService(control_plane_db)
        event, is_duplicate = service.accept_envelope(data)
        return SyncEnvelopeResponse(
            accepted=not is_duplicate,
            event_key=event.event_key,
            sequence_id=event.sequence_id,
            idempotency_key=event.idempotency_key,
            ack_cursor=event.sequence_id or 0,
            delivery_status="duplicate" if is_duplicate else "accepted",
        )

    @post("/sync/heartbeats")
    async def accept_heartbeat(
        self, control_plane_db: Session, data: EdgeHeartbeatRequest
    ) -> EdgeNodeResponse:
        service = ControlPlaneSyncService(control_plane_db)
        node = service.upsert_edge_node_heartbeat(
            data.edge_node_key,
            data.host_name,
            data.runtime_version,
            data.capabilities,
            data.last_ack_cursor,
        )
        return EdgeNodeResponse.model_validate(node)

    @post("/sync/session-state")
    async def sync_session_state(
        self, control_plane_db: Session, data: SessionStateSyncRequest
    ) -> OpenCodeSessionResponse:
        service = ControlPlaneSyncService(control_plane_db)
        session = service.update_session_observed_state(data)
        if not session:
            raise NotFoundException(f"Session not found: {data.session_key}")
        return OpenCodeSessionResponse.model_validate(session)

    @post("/sync/action-acks")
    async def acknowledge_action(
        self, control_plane_db: Session, data: ActionAckRequest
    ) -> SessionActionResponse:
        service = ControlPlaneSyncService(control_plane_db)
        action = service.acknowledge_action(
            data.action_key,
            data.detail,
            data.delivery_status == DeliveryStatus.ACKED,
        )
        if not action:
            raise NotFoundException(f"Action not found: {data.action_key}")
        return SessionActionResponse.model_validate(action)

    @post("/sync/outbound-acks")
    async def acknowledge_outbound_delivery(
        self, control_plane_db: Session, data: OutboundDeliveryAckRequest
    ) -> SyncEnvelopeResponse:
        envelope = SyncEnvelopeRequest(
            message_type=SyncMessageType.OUTBOUND_DELIVERY_ACK,
            message_id=data.message_id,
            idempotency_key=f"delivery:{data.message_id}:{data.ack_cursor}:{data.delivery_status.value}",
            edge_node_key="delivery-channel",
            created_at=data.sent_at,
            payload=data.model_dump(mode="json"),
        )
        service = ControlPlaneSyncService(control_plane_db)
        event, is_duplicate = service.accept_envelope(envelope)
        return SyncEnvelopeResponse(
            accepted=not is_duplicate,
            event_key=event.event_key,
            sequence_id=event.sequence_id,
            idempotency_key=event.idempotency_key,
            ack_cursor=event.sequence_id or 0,
            delivery_status="duplicate" if is_duplicate else "accepted",
        )

    @get("/sync/replay/{edge_node_key:str}")
    async def replay_events(
        self,
        control_plane_db: Session,
        edge_node_key: str,
        cursor: int = 0,
        limit: int = 100,
    ) -> ReplayEventsResponse:
        service = ControlPlaneSyncService(control_plane_db)
        next_cursor, events = service.replay_events(edge_node_key, cursor, limit)
        return ReplayEventsResponse(
            next_cursor=next_cursor,
            events=events,
            queue_policy=EdgeQueuePolicyResponse.model_validate(
                DEFAULT_EDGE_QUEUE_POLICY
            ),
        )

    @get("/sync/queue-policy")
    async def get_queue_policy(self) -> EdgeQueuePolicyResponse:
        return EdgeQueuePolicyResponse.model_validate(DEFAULT_EDGE_QUEUE_POLICY)


router = Router(
    path="/remote-dev",
    dependencies={"control_plane_db": Provide(get_control_plane_db_dependency)},
    route_handlers=[ControlPlaneController],
)
