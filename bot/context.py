# -*- coding: utf-8 -*-
# @file context.py
# @brief 对话上下文管理
# @author sailing-innocent
# @date 2026-03-25
# @version 1.0
# ---------------------------------
"""Conversation context management for Feishu bot.

Manages per-chat conversation state including:
- Message history
- Active workspace
- Pending confirmations
"""

from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Dict, Optional


@dataclass
class TurnRecord:
    """A single turn in the conversation."""

    role: str
    text: str
    ts: datetime = field(default_factory=datetime.now)


@dataclass
class PendingConfirmation:
    """A pending confirmation waiting for user response."""

    action: str
    params: Dict[str, Any]
    summary: str
    expires_at: datetime


_HISTORY_WINDOW = 6  # Number of turns to keep in history


@dataclass
class ConversationContext:
    """Per-chat conversation state."""

    chat_id: str
    history: deque = field(default_factory=lambda: deque(maxlen=_HISTORY_WINDOW))
    mode: str = "idle"
    active_workspace: Optional[str] = None
    pending: Optional[PendingConfirmation] = None

    def push(self, role: str, text: str) -> None:
        """Add a turn to the history."""
        self.history.append(TurnRecord(role=role, text=text))

    def history_text(self) -> str:
        """Get formatted history text."""
        lines = []
        for t in self.history:
            prefix = "User" if t.role == "user" else "Bot"
            lines.append(f"{prefix}: {t.text}")
        return "\n".join(lines)

    def is_pending_expired(self) -> bool:
        """Check if pending confirmation has expired."""
        return self.pending is not None and datetime.now() > self.pending.expires_at

    def clear_pending(self) -> None:
        """Clear pending confirmation."""
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


# Confirmation word sets
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


def check_confirmation_reply(text: str) -> Optional[bool]:
    """Check if text is a confirmation or cancellation response.

    Returns:
        True: confirmed
        False: cancelled
        None: unrelated
    """
    t = text.strip().lower()
    if t in _CONFIRM_WORDS:
        return True
    if t in _CANCEL_WORDS:
        return False
    return None
