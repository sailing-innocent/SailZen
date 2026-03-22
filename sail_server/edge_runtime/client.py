from datetime import datetime, timezone
from typing import Any
import hashlib
import json

import httpx

from sail_server.application.dto.control_plane_sync import (
    EdgeHeartbeatRequest,
    ReplayEventsResponse,
    SessionStateSyncRequest,
    SyncEnvelopeRequest,
    SyncEnvelopeResponse,
)
from sail_server.control_plane.sync_contract import (
    EdgeQueuePolicy,
    SyncEnvelope,
    SyncMessageType,
)
from sail_server.edge_runtime.config import EdgeRuntimeConfig


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class ControlPlaneClient:
    def __init__(self, config: EdgeRuntimeConfig):
        self.config = config
        self._client = httpx.Client(timeout=config.request_timeout_seconds)

    def build_headers(self) -> dict[str, str]:
        headers = {"X-Edge-Node-Key": self.config.edge_node_key}
        if self.config.edge_secret:
            headers["X-Edge-Secret"] = self.config.edge_secret
        return headers

    def is_available(self) -> bool:
        try:
            self.get_queue_policy()
            return True
        except httpx.HTTPError:
            return False

    def get_queue_policy(self) -> EdgeQueuePolicy:
        response = self._client.get(
            f"{self.config.control_plane_url}/sync/queue-policy",
            headers=self.build_headers(),
        )
        response.raise_for_status()
        return EdgeQueuePolicy.model_validate(response.json())

    def send_heartbeat(
        self, capabilities: dict[str, object], queue_depth: int, ack_cursor: int
    ) -> dict[str, Any]:
        payload = EdgeHeartbeatRequest(
            edge_node_key=self.config.edge_node_key,
            host_name=self.config.host_name,
            runtime_version=self.config.runtime_version,
            capabilities=capabilities,
            queue_depth=queue_depth,
            last_ack_cursor=ack_cursor,
            sent_at=utc_now_iso(),
        )
        response = self._client.post(
            f"{self.config.control_plane_url}/sync/heartbeats",
            json=payload.model_dump(mode="json"),
            headers=self.build_headers(),
        )
        response.raise_for_status()
        return response.json()

    def send_envelope(self, envelope: SyncEnvelope) -> SyncEnvelopeResponse:
        response = self._client.post(
            f"{self.config.control_plane_url}/sync/envelopes",
            json=SyncEnvelopeRequest.model_validate(envelope).model_dump(mode="json"),
            headers=self.build_headers(),
        )
        response.raise_for_status()
        return SyncEnvelopeResponse.model_validate(response.json())

    def close(self) -> None:
        self._client.close()

    def replay_events(self, cursor: int) -> ReplayEventsResponse:
        response = self._client.get(
            f"{self.config.control_plane_url}/sync/replay/{self.config.edge_node_key}",
            params={"cursor": cursor, "limit": 100},
            headers=self.build_headers(),
        )
        response.raise_for_status()
        return ReplayEventsResponse.model_validate(response.json())

    def upsert_workspace(self, workspace_payload: dict[str, Any]) -> dict[str, Any]:
        response = self._client.post(
            f"{self.config.control_plane_url}/workspaces/upsert",
            json=workspace_payload,
            headers=self.build_headers(),
        )
        response.raise_for_status()
        return response.json()

    def upsert_session(self, session_payload: dict[str, Any]) -> dict[str, Any]:
        response = self._client.post(
            f"{self.config.control_plane_url}/sessions/upsert",
            json=session_payload,
            headers=self.build_headers(),
        )
        response.raise_for_status()
        return response.json()

    def sync_session_state(self, session_payload: dict[str, Any]) -> dict[str, Any]:
        response = self._client.post(
            f"{self.config.control_plane_url}/sync/session-state",
            json=SessionStateSyncRequest.model_validate(session_payload).model_dump(
                mode="json"
            ),
            headers=self.build_headers(),
        )
        response.raise_for_status()
        return response.json()

    def make_idempotency_key(
        self, message_type: SyncMessageType, message_id: str, payload: dict[str, Any]
    ) -> str:
        payload_hash = hashlib.sha256(
            json.dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8")
        ).hexdigest()[:16]
        return f"{self.config.edge_node_key}:{message_type.value}:{message_id}:{payload_hash}"
