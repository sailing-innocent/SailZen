from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import func
from sqlalchemy.orm import Session

from sail_server.control_plane.dao import (
    EdgeNodeDAO,
    OpenCodeSessionDAO,
    RemoteWorkspaceDAO,
    SessionActionDAO,
    SessionEventDAO,
)
from sail_server.control_plane.models import (
    EdgeNode,
    OpenCodeSession,
    RemoteWorkspace,
    SessionEvent,
)
from sail_server.control_plane.sync_contract import (
    DeliveryStatus,
    EdgeQueuePolicy,
    SessionDesiredObservedState,
    SyncEnvelope,
)


DEFAULT_EDGE_QUEUE_POLICY = EdgeQueuePolicy()


class ControlPlaneSyncService:
    def __init__(self, db: Session):
        self.db = db
        self.edge_nodes = EdgeNodeDAO(db)
        self.sessions = OpenCodeSessionDAO(db)
        self.workspaces = RemoteWorkspaceDAO(db)
        self.actions = SessionActionDAO(db)
        self.events = SessionEventDAO(db)

    def _next_sequence_id(self) -> int:
        current = self.db.query(func.max(SessionEvent.sequence_id)).scalar()
        return int(current or 0) + 1

    def accept_envelope(self, envelope: SyncEnvelope) -> tuple[SessionEvent, bool]:
        existing = self.events.filter_by(
            idempotency_key=envelope.idempotency_key, limit=1
        )
        if existing:
            return existing[0], True

        session_id = None
        if envelope.session_key:
            session_matches = self.sessions.filter_by(
                session_key=envelope.session_key, limit=1
            )
            if session_matches:
                session_id = session_matches[0].id

        event = SessionEvent(
            event_key=f"evt_{uuid4().hex}",
            sequence_id=self._next_sequence_id(),
            session_id=session_id,
            event_type=envelope.message_type.value,
            event_source="edge",
            idempotency_key=envelope.idempotency_key,
            event_payload=envelope.model_dump(mode="json"),
        )
        return self.events.create(event), False

    def upsert_edge_node_heartbeat(
        self,
        edge_node_key: str,
        host_name: str,
        runtime_version: str | None,
        capabilities: dict,
        ack_cursor: int,
    ) -> EdgeNode:
        matches = self.edge_nodes.filter_by(node_key=edge_node_key, limit=1)
        now = datetime.now(timezone.utc)
        if matches:
            return self.edge_nodes.update(
                matches[0].id,
                {
                    "host_name": host_name,
                    "runtime_version": runtime_version,
                    "capabilities": capabilities,
                    "ack_cursor": ack_cursor,
                    "status": "online",
                    "last_heartbeat_at": now,
                },
            )

        edge_node = EdgeNode(
            node_key=edge_node_key,
            display_name=edge_node_key,
            host_name=host_name,
            runtime_version=runtime_version,
            capabilities=capabilities,
            ack_cursor=ack_cursor,
            status="online",
            last_heartbeat_at=now,
        )
        return self.edge_nodes.create(edge_node)

    def update_session_observed_state(self, state: SessionDesiredObservedState):
        matches = self.sessions.filter_by(session_key=state.session_key, limit=1)
        if not matches:
            return None
        return self.sessions.update(
            matches[0].id,
            {
                "desired_state": state.desired_state.value,
                "observed_state": state.observed_state.value,
                "status": state.observed_state.value,
                "branch_name": state.branch_name,
                "local_url": state.local_url,
                "local_path": state.local_path,
                "last_error": state.last_error,
                "process_info": state.process_info,
                "diagnostics": state.diagnostics,
                "last_heartbeat_at": datetime.now(timezone.utc),
            },
        )

    def upsert_workspace(self, payload: dict) -> RemoteWorkspace:
        matches = self.workspaces.filter_by(slug=payload["slug"], limit=1)
        update_data = {
            "name": payload["name"],
            "local_path": payload["local_path"],
            "policy_profile": payload.get("policy_profile", "default"),
            "labels": payload.get("labels", {}),
            "is_enabled": payload.get("is_enabled", True),
            "inventory_source": payload.get("inventory_source", "edge-config"),
        }
        if matches:
            return self.workspaces.update(matches[0].id, update_data)
        workspace = RemoteWorkspace(slug=payload["slug"], **update_data)
        return self.workspaces.create(workspace)

    def upsert_session(self, payload: dict) -> OpenCodeSession:
        workspace_matches = self.workspaces.filter_by(
            slug=payload["workspace_slug"], limit=1
        )
        edge_matches = self.edge_nodes.filter_by(
            node_key=payload["edge_node_key"], limit=1
        )
        if not workspace_matches:
            raise ValueError(f"Workspace not found: {payload['workspace_slug']}")
        edge_node_id = edge_matches[0].id if edge_matches else None
        update_data = {
            "workspace_id": workspace_matches[0].id,
            "edge_node_id": edge_node_id,
            "status": payload.get("status", "stopped"),
            "desired_state": payload.get("desired_state", "stopped"),
            "observed_state": payload.get("observed_state", "unknown"),
            "local_url": payload.get("local_url"),
            "local_path": payload.get("local_path"),
            "process_info": payload.get("process_info", {}),
            "diagnostics": payload.get("diagnostics", {}),
            "last_error": payload.get("last_error"),
            "last_heartbeat_at": datetime.now(timezone.utc),
        }
        matches = self.sessions.filter_by(session_key=payload["session_key"], limit=1)
        if matches:
            return self.sessions.update(matches[0].id, update_data)
        session = OpenCodeSession(session_key=payload["session_key"], **update_data)
        return self.sessions.create(session)

    def acknowledge_action(self, action_key: str, detail: str | None, acked: bool):
        matches = self.actions.filter_by(action_key=action_key, limit=1)
        if not matches:
            return None
        current_result = matches[0].result_payload or {}
        if detail:
            current_result = {**current_result, "detail": detail}
        return self.actions.update(
            matches[0].id,
            {
                "edge_ack_status": DeliveryStatus.ACKED.value
                if acked
                else DeliveryStatus.FAILED.value,
                "edge_ack_at": datetime.now(timezone.utc),
                "result_payload": current_result,
            },
        )

    def replay_events(
        self, edge_node_key: str, cursor: int, limit: int = 100
    ) -> tuple[int, list[SyncEnvelope]]:
        event_rows = (
            self.db.query(SessionEvent)
            .filter(SessionEvent.sequence_id > cursor)
            .order_by(SessionEvent.sequence_id.asc())
            .limit(limit)
            .all()
        )
        envelopes: list[SyncEnvelope] = []
        next_cursor = cursor
        for event in event_rows:
            payload = event.event_payload or {}
            envelopes.append(SyncEnvelope.model_validate(payload))
            if event.sequence_id and event.sequence_id > next_cursor:
                next_cursor = event.sequence_id

        node_matches = self.edge_nodes.filter_by(node_key=edge_node_key, limit=1)
        if node_matches:
            self.edge_nodes.update(node_matches[0].id, {"ack_cursor": next_cursor})
        return next_cursor, envelopes
