from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
import json

from sail_server.control_plane.sync_contract import EdgeQueueItem, SyncEnvelope


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class EdgeQueueStats:
    pending_count: int = 0


class EdgeLocalQueue:
    def __init__(self, queue_path: str, max_items: int = 500):
        self.queue_path = Path(queue_path)
        self.queue_path.parent.mkdir(parents=True, exist_ok=True)
        self.max_items = max_items
        self._items = self._load_items()

    def enqueue(self, envelope: SyncEnvelope, replay_window_seconds: int) -> None:
        item = EdgeQueueItem(
            envelope=envelope,
            retry_count=0,
            expires_at=(
                datetime.now(timezone.utc) + timedelta(seconds=replay_window_seconds)
            ).isoformat(),
        )
        self._items = [
            entry
            for entry in self._items
            if entry.envelope.idempotency_key != envelope.idempotency_key
        ]
        self._items.append(item)
        self._items = self._items[-self.max_items :]
        self._save_items()

    def acknowledge(self, idempotency_key: str) -> None:
        self._items = [
            entry
            for entry in self._items
            if entry.envelope.idempotency_key != idempotency_key
        ]
        self._save_items()

    def mark_retry(self, idempotency_key: str) -> None:
        for entry in self._items:
            if entry.envelope.idempotency_key == idempotency_key:
                entry.retry_count += 1
                entry.envelope.attempt_count += 1
        self._save_items()

    def list_pending(self) -> list[EdgeQueueItem]:
        now = datetime.now(timezone.utc)
        valid_items = []
        for entry in self._items:
            if entry.expires_at and datetime.fromisoformat(entry.expires_at) < now:
                continue
            valid_items.append(entry)
        self._items = valid_items
        self._save_items()
        return list(self._items)

    def stats(self) -> EdgeQueueStats:
        return EdgeQueueStats(pending_count=len(self._items))

    def _load_items(self) -> list[EdgeQueueItem]:
        if not self.queue_path.exists():
            return []
        with open(self.queue_path, "r", encoding="utf-8") as file:
            raw_items = json.load(file)
        return [EdgeQueueItem.model_validate(item) for item in raw_items]

    def _save_items(self) -> None:
        with open(self.queue_path, "w", encoding="utf-8") as file:
            json.dump(
                [item.model_dump(mode="json") for item in self._items],
                file,
                ensure_ascii=False,
                indent=2,
            )
