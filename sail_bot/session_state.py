# -*- coding: utf-8 -*-
# @file session_state.py
# @brief Session state machine, progress feedback, risk classification for Feishu bot
# @author sailing-innocent
# @date 2026-03-24
# @version 1.0
# ---------------------------------

from __future__ import annotations

import json
import logging
import threading
import time
import uuid
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)

STATE_FILE = Path.home() / ".config" / "feishu-agent" / "session_states.json"

_MIN_CARD_UPDATE_INTERVAL = 3.0


# ---------------------------------------------------------------------------
# 2.1 SessionState Enum + Transition Validation
# ---------------------------------------------------------------------------


class SessionState(str, Enum):
    IDLE = "idle"
    STARTING = "starting"
    RUNNING = "running"
    STOPPING = "stopping"
    ERROR = "error"


_VALID_TRANSITIONS: Dict[SessionState, set] = {
    SessionState.IDLE: {SessionState.STARTING},
    SessionState.STARTING: {
        SessionState.RUNNING,
        SessionState.ERROR,
        SessionState.IDLE,
    },
    SessionState.RUNNING: {SessionState.STOPPING, SessionState.ERROR},
    SessionState.STOPPING: {SessionState.IDLE, SessionState.ERROR},
    SessionState.ERROR: {SessionState.STARTING, SessionState.IDLE},
}


def is_valid_transition(current: SessionState, next_state: SessionState) -> bool:
    return next_state in _VALID_TRANSITIONS.get(current, set())


# ---------------------------------------------------------------------------
# 2.1.4 / 3.3.1 State change event hooks
# ---------------------------------------------------------------------------


@dataclass
class SessionStateEntry:
    path: str
    state: SessionState = SessionState.IDLE
    port: Optional[int] = None
    pid: Optional[int] = None
    last_error: Optional[str] = None
    started_at: Optional[str] = None
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())
    activities: deque = field(default_factory=lambda: deque(maxlen=20))
    health_fail_count: int = 0
    chat_id: Optional[str] = None
    opencode_session_id: Optional[str] = None

    def add_activity(self, msg: str) -> None:
        ts = datetime.now().strftime("%H:%M:%S")
        self.activities.appendleft("[" + ts + "] " + msg)

    def recent_activities(self) -> List[str]:
        return list(self.activities)[:5]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "path": self.path,
            "state": self.state.value,
            "port": self.port,
            "pid": self.pid,
            "last_error": self.last_error,
            "started_at": self.started_at,
            "updated_at": self.updated_at,
            "chat_id": self.chat_id,
            "opencode_session_id": self.opencode_session_id,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SessionStateEntry":
        entry = cls(path=data["path"])
        raw = data.get("state", "idle")
        try:
            entry.state = SessionState(raw)
        except ValueError:
            entry.state = SessionState.IDLE
        entry.port = data.get("port")
        entry.pid = data.get("pid")
        entry.last_error = data.get("last_error")
        entry.started_at = data.get("started_at")
        entry.updated_at = data.get("updated_at", datetime.now().isoformat())
        entry.chat_id = data.get("chat_id")
        entry.opencode_session_id = data.get("opencode_session_id")
        return entry


StateChangeHook = Callable[[str, SessionState, SessionState, SessionStateEntry], None]


class SessionStateStore:
    def __init__(self) -> None:
        self._entries: Dict[str, SessionStateEntry] = {}
        self._lock = threading.Lock()
        self._hooks: List[StateChangeHook] = []
        self._last_save: float = 0.0

    def register_hook(self, hook: StateChangeHook) -> None:
        self._hooks.append(hook)

    def get(self, path: str) -> Optional[SessionStateEntry]:
        with self._lock:
            return self._entries.get(path)

    def get_or_create(
        self, path: str, chat_id: Optional[str] = None
    ) -> SessionStateEntry:
        with self._lock:
            if path not in self._entries:
                self._entries[path] = SessionStateEntry(path=path, chat_id=chat_id)
            return self._entries[path]

    def transition(self, path: str, next_state: SessionState, **kwargs: Any) -> bool:
        with self._lock:
            entry = self._entries.get(path)
            if entry is None:
                return False
            if not is_valid_transition(entry.state, next_state):
                logger.warning(
                    "Invalid transition %s->%s for %s", entry.state, next_state, path
                )
                return False
            prev = entry.state
            entry.state = next_state
            entry.updated_at = datetime.now().isoformat()
            for k, v in kwargs.items():
                if hasattr(entry, k):
                    setattr(entry, k, v)
            entry.add_activity(prev.value + " → " + next_state.value)
            self._save_state_locked()

        for hook in self._hooks:
            try:
                hook(path, prev, next_state, entry)
            except Exception as exc:
                logger.error("State hook error: %s", exc)
        return True

    def force_set(self, path: str, state: SessionState, **kwargs: Any) -> None:
        with self._lock:
            entry = self._entries.get(path)
            if entry is None:
                return
            entry.state = state
            entry.updated_at = datetime.now().isoformat()
            for k, v in kwargs.items():
                if hasattr(entry, k):
                    setattr(entry, k, v)
            self._save_state_locked()

    def all_entries(self) -> List[SessionStateEntry]:
        with self._lock:
            return list(self._entries.values())

    def remove(self, path: str) -> None:
        with self._lock:
            self._entries.pop(path, None)
            self._save_state_locked()

    def load_from_disk(self) -> None:
        if not STATE_FILE.exists():
            return
        try:
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            with self._lock:
                for item in data:
                    path = item.get("path", "")
                    if not path:
                        continue
                    entry = SessionStateEntry.from_dict(item)
                    self._entries[path] = entry
            logger.info(
                "[SessionState] Loaded %d session(s) from disk", len(self._entries)
            )
        except Exception as exc:
            logger.error("[SessionState] Failed to load: %s", exc)

    def _save_state_locked(self) -> None:
        now = time.time()
        if now - self._last_save < 1.0:
            return
        self._last_save = now
        try:
            STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
            data = [e.to_dict() for e in self._entries.values()]
            with open(STATE_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception as exc:
            logger.error("[SessionState] Failed to save: %s", exc)

    def save_to_disk(self) -> None:
        with self._lock:
            self._save_state_locked()


# ---------------------------------------------------------------------------
# 2.3 Health Monitoring
# ---------------------------------------------------------------------------


class SessionHealthMonitor:
    MAX_FAIL_COUNT = 3
    CHECK_INTERVAL = 30

    def __init__(
        self,
        store: SessionStateStore,
        health_check_fn: Callable[[str, int], bool],
        auto_restart: bool = False,
    ) -> None:
        self._store = store
        self._health_check_fn = health_check_fn
        self._auto_restart = auto_restart
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._history: deque = deque(maxlen=100)

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._monitor_loop, daemon=True, name="health-monitor"
        )
        self._thread.start()
        logger.info("[HealthMonitor] Started")

    def stop(self) -> None:
        self._stop_event.set()

    def _monitor_loop(self) -> None:
        while not self._stop_event.wait(self.CHECK_INTERVAL):
            for entry in self._store.all_entries():
                if entry.state != SessionState.RUNNING:
                    continue
                if entry.port is None:
                    continue
                try:
                    ok = self._health_check_fn(entry.path, entry.port)
                    ts = datetime.now().isoformat()
                    self._history.appendleft({"path": entry.path, "ts": ts, "ok": ok})
                    if ok:
                        entry.health_fail_count = 0
                    else:
                        entry.health_fail_count += 1
                        logger.warning(
                            "[Health] %s fail %d/%d",
                            entry.path,
                            entry.health_fail_count,
                            self.MAX_FAIL_COUNT,
                        )
                        if entry.health_fail_count >= self.MAX_FAIL_COUNT:
                            self._store.transition(
                                entry.path,
                                SessionState.ERROR,
                                last_error="Health check failed 3 times",
                            )
                            if self._auto_restart:
                                logger.info("[Health] Auto-restarting %s", entry.path)
                                self._store.transition(
                                    entry.path, SessionState.STARTING
                                )
                except Exception as exc:
                    logger.error("[Health] Check error for %s: %s", entry.path, exc)

    def recent_history(self) -> List[Dict[str, Any]]:
        return list(self._history)[:20]


# ---------------------------------------------------------------------------
# 3.1 / 3.2 Progress Feedback + Operation Tracking
# ---------------------------------------------------------------------------


@dataclass
class ActiveOperation:
    op_id: str
    path: str
    description: str
    started_at: float = field(default_factory=time.time)
    progress_pct: Optional[int] = None
    spinner_tick: int = 0
    timeout_seconds: float = 120.0
    warned: bool = False
    cancelled: bool = False
    progress_message_id: Optional[str] = None


class OperationTracker:
    LONG_OP_THRESHOLD = 1.0
    WARNING_THRESHOLD = 30.0

    def __init__(self) -> None:
        self._ops: Dict[str, ActiveOperation] = {}
        self._lock = threading.Lock()

    def start(self, path: str, description: str, timeout: float = 120.0) -> str:
        op_id = str(uuid.uuid4())[:8]
        with self._lock:
            self._ops[op_id] = ActiveOperation(
                op_id=op_id, path=path, description=description, timeout_seconds=timeout
            )
        return op_id

    def update_progress(self, op_id: str, pct: int) -> None:
        with self._lock:
            op = self._ops.get(op_id)
            if op:
                op.progress_pct = pct
                op.spinner_tick += 1

    def tick_spinner(self, op_id: str) -> None:
        with self._lock:
            op = self._ops.get(op_id)
            if op:
                op.spinner_tick += 1

    def finish(self, op_id: str) -> None:
        with self._lock:
            self._ops.pop(op_id, None)

    def cancel(self, op_id: str) -> None:
        with self._lock:
            op = self._ops.get(op_id)
            if op:
                op.cancelled = True

    def get(self, op_id: str) -> Optional[ActiveOperation]:
        with self._lock:
            return self._ops.get(op_id)

    def is_busy(self, path: str) -> Optional[ActiveOperation]:
        with self._lock:
            for op in self._ops.values():
                if op.path == path and not op.cancelled:
                    return op
        return None

    def elapsed(self, op_id: str) -> float:
        with self._lock:
            op = self._ops.get(op_id)
            return time.time() - op.started_at if op else 0.0

    def is_long(self, op_id: str) -> bool:
        return self.elapsed(op_id) >= self.LONG_OP_THRESHOLD

    def needs_timeout_warning(self, op_id: str) -> bool:
        with self._lock:
            op = self._ops.get(op_id)
            if op is None or op.warned:
                return False
            if time.time() - op.started_at >= self.WARNING_THRESHOLD:
                op.warned = True
                return True
        return False


# ---------------------------------------------------------------------------
# 4.1 Risk Level Classification
# ---------------------------------------------------------------------------


class RiskLevel(str, Enum):
    SAFE = "safe"
    GUARDED = "guarded"
    CONFIRM_REQUIRED = "confirm_required"


_ACTION_RISK: Dict[str, RiskLevel] = {
    "show_status": RiskLevel.SAFE,
    "show_help": RiskLevel.SAFE,
    "chat": RiskLevel.SAFE,
    "clarify": RiskLevel.SAFE,
    "start_workspace": RiskLevel.GUARDED,
    "send_task": RiskLevel.SAFE,
    "stop_workspace": RiskLevel.CONFIRM_REQUIRED,
    "switch_workspace": RiskLevel.CONFIRM_REQUIRED,
}

_DESTRUCTIVE_KEYWORDS = frozenset(
    [
        "删除",
        "delete",
        "drop",
        "reset",
        "覆盖",
        "overwrite",
        "清空",
        "truncate",
        "格式化",
        "format",
    ]
)


def classify_risk(
    action: str, task_text: str = "", has_running_session: bool = False
) -> RiskLevel:
    base = _ACTION_RISK.get(action, RiskLevel.SAFE)
    if action == "send_task":
        if any(kw in task_text.lower() for kw in _DESTRUCTIVE_KEYWORDS):
            return RiskLevel.CONFIRM_REQUIRED
        if len(task_text) > 200:
            return RiskLevel.GUARDED
    if action == "start_workspace" and has_running_session:
        return RiskLevel.SAFE
    return base


# ---------------------------------------------------------------------------
# 4.2 / 4.3 Pending Confirmation Management
# ---------------------------------------------------------------------------


@dataclass
class PendingAction:
    pending_id: str
    action: str
    params: Dict[str, Any]
    summary: str
    detail: str
    risk_level: RiskLevel
    created_at: float = field(default_factory=time.time)
    timeout_seconds: float = 300.0
    can_undo: bool = False
    bypass_count: int = 0

    def is_expired(self) -> bool:
        return time.time() - self.created_at > self.timeout_seconds

    def to_dict(self) -> Dict[str, Any]:
        return {
            "pending_id": self.pending_id,
            "action": self.action,
            "params": self.params,
            "summary": self.summary,
            "risk_level": self.risk_level.value,
        }


class ConfirmationManager:
    SESSION_BYPASS_THRESHOLD = 3

    def __init__(self) -> None:
        self._pending: Dict[str, PendingAction] = {}
        self._action_confirm_counts: Dict[str, int] = {}

    def create(
        self,
        action: str,
        params: Dict[str, Any],
        summary: str,
        detail: str = "",
        risk_level: RiskLevel = RiskLevel.CONFIRM_REQUIRED,
        can_undo: bool = False,
        timeout_seconds: float = 300.0,
    ) -> PendingAction:
        pid = str(uuid.uuid4())[:12]
        pending = PendingAction(
            pending_id=pid,
            action=action,
            params=params,
            summary=summary,
            detail=detail,
            risk_level=risk_level,
            timeout_seconds=timeout_seconds,
            can_undo=can_undo,
        )
        self._pending[pid] = pending
        return pending

    def consume(self, pending_id: str) -> Optional[PendingAction]:
        pending = self._pending.pop(pending_id, None)
        if pending and not pending.is_expired():
            key = pending.action
            self._action_confirm_counts[key] = (
                self._action_confirm_counts.get(key, 0) + 1
            )
            return pending
        return None

    def cancel(self, pending_id: str) -> bool:
        return self._pending.pop(pending_id, None) is not None

    def cleanup_expired(self) -> List[str]:
        expired = [pid for pid, p in self._pending.items() if p.is_expired()]
        for pid in expired:
            self._pending.pop(pid, None)
        return expired

    def should_bypass(self, action: str, force: bool = False) -> bool:
        if force:
            return True
        count = self._action_confirm_counts.get(action, 0)
        return count >= self.SESSION_BYPASS_THRESHOLD
