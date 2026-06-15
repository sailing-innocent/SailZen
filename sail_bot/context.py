# -*- coding: utf-8 -*-
# @file context.py
# @brief Conversation context and state management
# @author sailing-innocent
# @date 2026-04-06
# @version 1.1
# ---------------------------------
"""Per-chat conversation context and state for the Feishu bot.

This module holds dataclasses that represent the state of an ongoing
conversation, including generic action plans, pending confirmations,
image generation state, and plan mode state.
"""

from collections import deque
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, Literal
from datetime import datetime

_HISTORY_WINDOW = 6

_CONFIRM_WORDS = {"是", "是的", "确认", "确定", "y", "yes", "ok", "好", "行", "可以", "没错", "对", "对的"}
_CANCEL_WORDS = {"否", "不是", "取消", "不", "n", "no", "算了", "别", "不要", "拒绝"}

PLAN_STATUSES = Literal["draft", "review", "revising", "approved", "executing", "done", "cancelled"]

# ---------------------------------------------------------------------------
# Conversation context
# ---------------------------------------------------------------------------
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
class ImageGenState:
    """图片生成工作流状态"""

    last_image_path: Optional[str] = None
    last_prompt: Optional[str] = None


@dataclass
class PendingConfirmation:
    action: str
    params: Dict[str, Any]
    summary: str
    expires_at: datetime

    def is_expired(self) -> bool:
        """Check if the pending confirmation has expired."""
        return datetime.now() > self.expires_at


@dataclass
class PlanModeState:
    """Plan mode state for a chat.

    Tracks the lifecycle of a collaborative plan document, from initial
    drafting through review, revision, approval, and execution.
    """

    status: Literal[
        "draft", "review", "revising", "approved", "executing", "done", "cancelled"
    ] = "draft"
    requirement: str = ""
    doc_token: Optional[str] = None
    doc_url: Optional[str] = None
    planner_session_id: Optional[str] = None
    executor_session_id: Optional[str] = None
    workspace_path: Optional[str] = None
    plan_revision: int = 0
    plan_title: str = ""
    last_content_hash: Optional[str] = None
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())

    def touch(self) -> None:
        """Update the updated_at timestamp."""
        self.updated_at = datetime.now().isoformat()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status,
            "requirement": self.requirement,
            "doc_token": self.doc_token,
            "doc_url": self.doc_url,
            "planner_session_id": self.planner_session_id,
            "executor_session_id": self.executor_session_id,
            "workspace_path": self.workspace_path,
            "plan_revision": self.plan_revision,
            "plan_title": self.plan_title,
            "last_content_hash": self.last_content_hash,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PlanModeState":
        return cls(
            status=data.get("status", "draft"),
            requirement=data.get("requirement", ""),
            doc_token=data.get("doc_token"),
            doc_url=data.get("doc_url"),
            planner_session_id=data.get("planner_session_id"),
            executor_session_id=data.get("executor_session_id"),
            workspace_path=data.get("workspace_path"),
            plan_revision=data.get("plan_revision", 0),
            plan_title=data.get("plan_title", ""),
            last_content_hash=data.get("last_content_hash"),
            created_at=data.get("created_at", datetime.now().isoformat()),
            updated_at=data.get("updated_at", datetime.now().isoformat()),
        )


@dataclass
class ConversationContext:
    """Per-chat conversation state."""

    chat_id: str
    history: deque = field(default_factory=lambda: deque(maxlen=_HISTORY_WINDOW))
    mode: str = "idle"  # idle | coding | image_gen | planning
    active_workspace: Optional[str] = None
    pending: Optional[PendingConfirmation] = None
    image_gen: Optional[ImageGenState] = None
    plan_state: Optional[PlanModeState] = None

    def push(self, role: str, text: str) -> None:
        self.history.append(TurnRecord(role=role, text=text))

    def history_text(self) -> str:
        lines = []
        for t in self.history:
            prefix = "User" if t.role == "user" else "Bot"
            lines.append(f"{prefix}: {t.text}")
        return "\n".join(lines)

    def is_pending_expired(self) -> bool:
        return self.pending is not None and self.pending.is_expired()

    def clear_pending(self) -> None:
        self.pending = None

    def to_dict(self) -> Dict[str, Any]:
        """Serialize context to dict for persistence (excludes history and pending)."""
        data: Dict[str, Any] = {
            "chat_id": self.chat_id,
            "mode": self.mode,
            "active_workspace": self.active_workspace,
        }
        if self.image_gen:
            data["image_gen"] = {
                "last_image_path": self.image_gen.last_image_path,
                "last_prompt": self.image_gen.last_prompt,
            }
        if self.plan_state:
            data["plan_state"] = self.plan_state.to_dict()
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ConversationContext":
        """Deserialize context from dict."""
        ctx = cls(
            chat_id=data.get("chat_id", ""),
            mode=data.get("mode", "idle"),
            active_workspace=data.get("active_workspace"),
        )
        ig = data.get("image_gen")
        if ig:
            ctx.image_gen = ImageGenState(
                last_image_path=ig.get("last_image_path"),
                last_prompt=ig.get("last_prompt"),
            )
        ps = data.get("plan_state")
        if ps:
            ctx.plan_state = PlanModeState.from_dict(ps)
        return ctx
