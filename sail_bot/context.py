from collections import deque
from dataclasses import dataclass, field
from typing import Optional, Dict, Any
from .config import _HISTORY_WINDOW
from datetime import datetime


# ---------------------------------------------------------------------------
# Conversation context
# ---------------------------------------------------------------------------

_CONFIRM_WORDS = frozenset(
    [
        "确认",
        "确定",
        "是",
        "yes",
        "ok",
        "好",
        "好的",
        "执行",
        "继续",
        "confirm",
        "y",
    ]
)

_CANCEL_WORDS = frozenset(
    [
        "取消",
        "算了",
        "不",
        "no",
        "cancel",
        "停",
        "别",
        "n",
    ]
)


@dataclass
class ActionPlan:
    action: str
    params: Dict[str, Any] = field(default_factory=dict)
    confirm_required: bool = False
    confirm_summary: str = ""
    reply: str = ""


@dataclass
class TurnRecord:
    role: str
    text: str
    ts: datetime = field(default_factory=datetime.now)


@dataclass
class PendingConfirmation:
    action: str
    params: Dict[str, Any]
    summary: str
    expires_at: datetime


@dataclass
class ConversationContext:
    """Per-chat conversation state."""

    chat_id: str
    history: deque = field(default_factory=lambda: deque(maxlen=_HISTORY_WINDOW))
    mode: str = "idle"
    active_workspace: Optional[str] = None
    pending: Optional[PendingConfirmation] = None

    def push(self, role: str, text: str) -> None:
        self.history.append(TurnRecord(role=role, text=text))

    def history_text(self) -> str:
        lines = []
        for t in self.history:
            prefix = "User" if t.role == "user" else "Bot"
            lines.append(f"{prefix}: {t.text}")
        return "\n".join(lines)

    def is_pending_expired(self) -> bool:
        return self.pending is not None and datetime.now() > self.pending.expires_at

    def clear_pending(self) -> None:
        self.pending = None

    def to_dict(self) -> Dict[str, Any]:
        """Serialize context to dict for persistence (excludes history and pending)."""
        return {
            "chat_id": self.chat_id,
            "mode": self.mode,
            "active_workspace": self.active_workspace,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ConversationContext":
        """Deserialize context from dict."""
        ctx = cls(
            chat_id=data.get("chat_id", ""),
            mode=data.get("mode", "idle"),
            active_workspace=data.get("active_workspace"),
        )
        return ctx
