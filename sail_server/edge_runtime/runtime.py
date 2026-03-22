from datetime import datetime, timezone
from typing import Any

from sail_server.control_plane.sync_contract import SyncEnvelope, SyncMessageType
from sail_server.edge_runtime.client import ControlPlaneClient
from sail_server.edge_runtime.config import EdgeRuntimeConfig
from sail_server.edge_runtime.executor import LocalExecutionAgent
from sail_server.edge_runtime.queue import EdgeLocalQueue


class EdgeRuntime:
    def __init__(self, config: EdgeRuntimeConfig):
        self.config = config
        self.client = ControlPlaneClient(config)
        self.queue_policy = None
        if not config.offline_mode:
            try:
                self.queue_policy = self.client.get_queue_policy()
            except Exception:
                self.queue_policy = None
        max_items = self.queue_policy.max_buffered_items if self.queue_policy else 500
        self.queue = EdgeLocalQueue(config.queue_path, max_items=max_items)
        self.ack_cursor = 0
        self.executor = LocalExecutionAgent()

    def capabilities(self) -> dict[str, Any]:
        return {
            "feishu_long_connection": True,
            "workspace_count": len(self.config.projects),
            "project_slugs": [project.slug for project in self.config.projects],
            "opencode_local_control": True,
            "safe_commands": sorted(self.executor.allowed_commands),
        }

    def register_or_heartbeat(self) -> None:
        if self.config.offline_mode:
            return
        self.sync_workspace_inventory()
        result = self.client.send_heartbeat(
            capabilities=self.capabilities(),
            queue_depth=self.queue.stats().pending_count,
            ack_cursor=self.ack_cursor,
        )
        self.ack_cursor = max(self.ack_cursor, result.get("ack_cursor", 0))
        replay_response = self.client.replay_events(self.ack_cursor)
        self.ack_cursor = max(self.ack_cursor, replay_response.next_cursor)

    def normalize_text_message(
        self,
        message_id: str,
        chat_id: str,
        sender_open_id: str,
        text: str,
        chat_type: str,
        mentions: list[dict[str, Any]] | None = None,
    ) -> SyncEnvelope:
        normalized_text = text.strip()
        payload = {
            "source": "feishu",
            "chat_id": chat_id,
            "sender_open_id": sender_open_id,
            "chat_type": chat_type,
            "mentions": mentions or [],
            "raw_text": text,
            "normalized_text": normalized_text,
            "received_at": datetime.now(timezone.utc).isoformat(),
        }
        envelope = SyncEnvelope(
            message_type=SyncMessageType.INBOUND_MESSAGE,
            message_id=message_id,
            idempotency_key=self.client.make_idempotency_key(
                SyncMessageType.INBOUND_MESSAGE, message_id, payload
            ),
            edge_node_key=self.config.edge_node_key,
            created_at=datetime.now(timezone.utc).isoformat(),
            payload=payload,
        )
        return envelope

    def forward_message(self, envelope: SyncEnvelope) -> dict[str, Any]:
        replay_window_seconds = (
            self.queue_policy.replay_window_seconds if self.queue_policy else 3600
        )
        self.queue.enqueue(envelope, replay_window_seconds)
        if self.config.offline_mode:
            return {"accepted": False, "delivery_status": "offline-buffered"}

        response = self.client.send_envelope(envelope)
        if response.delivery_status in {"accepted", "duplicate"}:
            self.queue.acknowledge(envelope.idempotency_key)
            self.ack_cursor = max(self.ack_cursor, response.ack_cursor)
        else:
            self.queue.mark_retry(envelope.idempotency_key)
        return response.model_dump(mode="json")

    def replay_pending(self) -> list[dict[str, Any]]:
        if self.config.offline_mode:
            return []
        results = []
        for item in self.queue.list_pending():
            response = self.client.send_envelope(item.envelope)
            if response.delivery_status in {"accepted", "duplicate"}:
                self.queue.acknowledge(item.envelope.idempotency_key)
                self.ack_cursor = max(self.ack_cursor, response.ack_cursor)
            else:
                self.queue.mark_retry(item.envelope.idempotency_key)
            results.append(response.model_dump(mode="json"))
        return results

    def close(self) -> None:
        self.client.close()

    def sync_workspace_inventory(self) -> list[dict[str, Any]]:
        inventory = self.executor.inventory_from_projects(self.config.projects)
        if self.config.offline_mode:
            return inventory
        for item in inventory:
            self.client.upsert_workspace(item)
        return inventory

    def ensure_workspace_session(
        self, workspace_slug: str, local_path: str
    ) -> dict[str, Any]:
        session = self.executor.ensure_session(workspace_slug, local_path)
        payload = self.executor.observed_state_payload(session.session_key)
        if not self.config.offline_mode:
            self.client.upsert_session(
                {
                    "session_key": session.session_key,
                    "workspace_slug": workspace_slug,
                    "edge_node_key": self.config.edge_node_key,
                    "status": session.status,
                    "desired_state": payload["desired_state"],
                    "observed_state": payload["observed_state"],
                    "local_url": session.local_url,
                    "local_path": session.local_path,
                    "process_info": payload["process_info"],
                    "diagnostics": payload["diagnostics"],
                    "last_error": session.last_error,
                }
            )
        return payload

    def run_local_command(
        self, workspace_slug: str, local_path: str, command_name: str
    ) -> tuple[bool, dict[str, Any]]:
        self.ensure_workspace_session(workspace_slug, local_path)
        session_key = f"sess_{workspace_slug}"
        ok, payload = self.executor.safe_execute(command_name, session_key)
        sync_payload = self.executor.observed_state_payload(session_key)
        if not self.config.offline_mode:
            self.client.sync_session_state(sync_payload)
        return ok, payload
