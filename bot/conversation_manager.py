# -*- coding: utf-8 -*-
# @file conversation_manager.py
# @brief Conversation state management for Feishu Bot - OpenCode interaction
# @author sailing-innocent
# @date 2026-03-29
# @version 1.0
# ---------------------------------
"""Conversation management for human-friendly OpenCode interaction.

This module provides:
- Session lifecycle management (start/pause/resume/end)
- Conversation history tracking with pagination
- Progressive message display for long responses
- Detailed conversation inspection

Key Features:
1. No truncation: Full conversation history is saved
2. Human-friendly: Summary view with option to see details
3. Session control: Start, pause, resume, end sessions explicitly
4. Progressive disclosure: Show summary first, expand for details
"""

import json
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


class ConversationStatus(Enum):
    """Status of a conversation session."""

    IDLE = "idle"  # Not started yet
    ACTIVE = "active"  # Currently active
    PAUSED = "paused"  # Paused by user
    COMPLETED = "completed"  # Completed normally
    ERROR = "error"  # Error state


@dataclass
class Message:
    """A single message in the conversation."""

    role: str  # 'user' or 'assistant'
    content: str
    timestamp: float = field(default_factory=time.time)
    message_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "role": self.role,
            "content": self.content,
            "timestamp": self.timestamp,
            "message_id": self.message_id,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Message":
        return cls(
            role=data["role"],
            content=data["content"],
            timestamp=data.get("timestamp", time.time()),
            message_id=data.get("message_id", str(uuid.uuid4())[:8]),
            metadata=data.get("metadata", {}),
        )


@dataclass
class ConversationSession:
    """A conversation session between user and OpenCode."""

    session_id: str
    workspace_path: str
    chat_id: str
    status: ConversationStatus = ConversationStatus.IDLE
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    opencode_session_id: Optional[str] = None
    messages: List[Message] = field(default_factory=list)
    summary: str = ""  # Brief summary of the conversation
    current_task: str = ""  # Current task description

    def add_message(
        self, role: str, content: str, metadata: Optional[Dict] = None
    ) -> Message:
        """Add a message to the conversation."""
        msg = Message(
            role=role,
            content=content,
            metadata=metadata or {},
        )
        self.messages.append(msg)
        self.updated_at = time.time()
        return msg

    def get_messages(self, limit: Optional[int] = None) -> List[Message]:
        """Get messages, optionally limited to last N."""
        if limit:
            return self.messages[-limit:]
        return self.messages.copy()

    def get_message_count(self) -> int:
        """Get total message count."""
        return len(self.messages)

    def get_last_message(self) -> Optional[Message]:
        """Get the last message."""
        return self.messages[-1] if self.messages else None

    def get_user_messages(self) -> List[Message]:
        """Get all user messages."""
        return [m for m in self.messages if m.role == "user"]

    def get_assistant_messages(self) -> List[Message]:
        """Get all assistant messages."""
        return [m for m in self.messages if m.role == "assistant"]

    def get_conversation_text(self, max_messages: Optional[int] = None) -> str:
        """Get full conversation text for context."""
        messages = self.messages
        if max_messages:
            messages = messages[-max_messages:]

        lines = []
        for msg in messages:
            prefix = "User" if msg.role == "user" else "Assistant"
            lines.append(f"{prefix}: {msg.content}")
        return "\n\n".join(lines)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "session_id": self.session_id,
            "workspace_path": self.workspace_path,
            "chat_id": self.chat_id,
            "status": self.status.value,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "opencode_session_id": self.opencode_session_id,
            "messages": [m.to_dict() for m in self.messages],
            "summary": self.summary,
            "current_task": self.current_task,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ConversationSession":
        session = cls(
            session_id=data["session_id"],
            workspace_path=data["workspace_path"],
            chat_id=data["chat_id"],
            status=ConversationStatus(data.get("status", "idle")),
            created_at=data.get("created_at", time.time()),
            updated_at=data.get("updated_at", time.time()),
            opencode_session_id=data.get("opencode_session_id"),
            summary=data.get("summary", ""),
            current_task=data.get("current_task", ""),
        )
        session.messages = [Message.from_dict(m) for m in data.get("messages", [])]
        return session

    def get_summary_stats(self) -> Dict[str, Any]:
        """Get conversation statistics."""
        user_msgs = self.get_user_messages()
        assistant_msgs = self.get_assistant_messages()

        return {
            "total_messages": len(self.messages),
            "user_messages": len(user_msgs),
            "assistant_messages": len(assistant_msgs),
            "duration_minutes": (self.updated_at - self.created_at) / 60,
            "status": self.status.value,
        }


class ConversationManager:
    """Manages multiple conversation sessions."""

    def __init__(self, storage_path: Optional[Path] = None):
        """Initialize conversation manager.

        Args:
            storage_path: Path to store conversation history
        """
        self.storage_path = storage_path or (
            Path.home() / ".config" / "feishu-agent" / "conversations.json"
        )
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)

        self._sessions: Dict[str, ConversationSession] = {}
        self._chat_sessions: Dict[str, str] = {}  # chat_id -> session_id

        self._load_sessions()

    def create_session(
        self,
        workspace_path: str,
        chat_id: str,
        task: Optional[str] = None,
    ) -> ConversationSession:
        """Create a new conversation session.

        Args:
            workspace_path: Workspace path for this session
            chat_id: Feishu chat ID
            task: Initial task description

        Returns:
            New conversation session
        """
        session_id = f"conv_{int(time.time())}_{uuid.uuid4().hex[:6]}"

        session = ConversationSession(
            session_id=session_id,
            workspace_path=workspace_path,
            chat_id=chat_id,
            status=ConversationStatus.IDLE,
            current_task=task or "",
        )

        self._sessions[session_id] = session
        self._chat_sessions[chat_id] = session_id
        self._save_sessions()

        return session

    def get_session(self, session_id: str) -> Optional[ConversationSession]:
        """Get a session by ID."""
        return self._sessions.get(session_id)

    def get_active_session(self, chat_id: str) -> Optional[ConversationSession]:
        """Get the active session for a chat."""
        session_id = self._chat_sessions.get(chat_id)
        if session_id:
            session = self._sessions.get(session_id)
            if session and session.status in (
                ConversationStatus.IDLE,
                ConversationStatus.ACTIVE,
            ):
                return session
        return None

    def start_session(
        self, session_id: str, opencode_session_id: Optional[str] = None
    ) -> bool:
        """Start a conversation session.

        Args:
            session_id: Session ID
            opencode_session_id: OpenCode session ID if available

        Returns:
            True if started successfully
        """
        session = self._sessions.get(session_id)
        if not session:
            return False

        session.status = ConversationStatus.ACTIVE
        if opencode_session_id:
            session.opencode_session_id = opencode_session_id
        session.updated_at = time.time()

        self._save_sessions()
        return True

    def pause_session(self, session_id: str) -> bool:
        """Pause a conversation session."""
        session = self._sessions.get(session_id)
        if not session:
            return False

        session.status = ConversationStatus.PAUSED
        session.updated_at = time.time()
        self._save_sessions()
        return True

    def resume_session(self, session_id: str) -> bool:
        """Resume a paused conversation session."""
        session = self._sessions.get(session_id)
        if not session:
            return False

        session.status = ConversationStatus.ACTIVE
        session.updated_at = time.time()
        self._save_sessions()
        return True

    def end_session(self, session_id: str, completed: bool = True) -> bool:
        """End a conversation session.

        Args:
            session_id: Session ID
            completed: Whether completed normally (True) or with error (False)
        """
        session = self._sessions.get(session_id)
        if not session:
            return False

        session.status = (
            ConversationStatus.COMPLETED if completed else ConversationStatus.ERROR
        )
        session.updated_at = time.time()

        # Remove from active chat mapping
        if session.chat_id in self._chat_sessions:
            del self._chat_sessions[session.chat_id]

        self._save_sessions()
        return True

    def add_user_message(
        self,
        session_id: str,
        content: str,
        metadata: Optional[Dict] = None,
    ) -> Optional[Message]:
        """Add a user message to a session."""
        session = self._sessions.get(session_id)
        if not session:
            return None

        msg = session.add_message("user", content, metadata)
        self._save_sessions()
        return msg

    def add_assistant_message(
        self,
        session_id: str,
        content: str,
        metadata: Optional[Dict] = None,
    ) -> Optional[Message]:
        """Add an assistant message to a session."""
        session = self._sessions.get(session_id)
        if not session:
            return None

        msg = session.add_message("assistant", content, metadata)
        self._save_sessions()
        return msg

    def update_summary(self, session_id: str, summary: str) -> bool:
        """Update conversation summary."""
        session = self._sessions.get(session_id)
        if not session:
            return False

        session.summary = summary
        session.updated_at = time.time()
        self._save_sessions()
        return True

    def update_task(self, session_id: str, task: str) -> bool:
        """Update current task."""
        session = self._sessions.get(session_id)
        if not session:
            return False

        session.current_task = task
        session.updated_at = time.time()
        self._save_sessions()
        return True

    def get_session_history(
        self,
        session_id: str,
        page: int = 1,
        page_size: int = 10,
    ) -> Tuple[List[Message], int]:
        """Get paginated session history.

        Args:
            session_id: Session ID
            page: Page number (1-indexed)
            page_size: Items per page

        Returns:
            Tuple of (messages for page, total pages)
        """
        session = self._sessions.get(session_id)
        if not session:
            return [], 0

        messages = session.messages
        total = len(messages)
        total_pages = (total + page_size - 1) // page_size

        start = (page - 1) * page_size
        end = start + page_size

        return messages[start:end], total_pages

    def list_sessions(
        self,
        chat_id: Optional[str] = None,
        status: Optional[ConversationStatus] = None,
        limit: int = 20,
    ) -> List[ConversationSession]:
        """List conversation sessions.

        Args:
            chat_id: Filter by chat ID
            status: Filter by status
            limit: Maximum results

        Returns:
            List of sessions (newest first)
        """
        sessions = list(self._sessions.values())

        if chat_id:
            sessions = [s for s in sessions if s.chat_id == chat_id]

        if status:
            sessions = [s for s in sessions if s.status == status]

        # Sort by updated time (newest first)
        sessions.sort(key=lambda s: s.updated_at, reverse=True)

        return sessions[:limit]

    def get_recent_summary(self, chat_id: str, max_sessions: int = 5) -> str:
        """Get a summary of recent conversations.

        Args:
            chat_id: Chat ID
            max_sessions: Maximum sessions to include

        Returns:
            Formatted summary text
        """
        sessions = self.list_sessions(chat_id=chat_id, limit=max_sessions)

        if not sessions:
            return "暂无对话历史"

        lines = [f"最近 {len(sessions)} 个对话："]
        for i, session in enumerate(sessions, 1):
            stats = session.get_summary_stats()
            status_icon = {
                ConversationStatus.ACTIVE: "🟢",
                ConversationStatus.PAUSED: "⏸️",
                ConversationStatus.COMPLETED: "✅",
                ConversationStatus.ERROR: "❌",
                ConversationStatus.IDLE: "⚪",
            }.get(session.status, "⚪")

            lines.append(
                f"{i}. {status_icon} {session.workspace_path}\n"
                f"   任务: {session.current_task[:30]}{'...' if len(session.current_task) > 30 else ''}\n"
                f"   消息: {stats['user_messages']} 用户 / {stats['assistant_messages']} 助手\n"
                f"   时长: {stats['duration_minutes']:.1f} 分钟"
            )

        return "\n\n".join(lines)

    def _save_sessions(self) -> None:
        """Save sessions to disk."""
        try:
            data = {
                "sessions": {sid: s.to_dict() for sid, s in self._sessions.items()},
                "chat_sessions": self._chat_sessions,
            }
            with open(self.storage_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as exc:
            print(f"[ConversationManager] Failed to save: {exc}")

    def _load_sessions(self) -> None:
        """Load sessions from disk."""
        if not self.storage_path.exists():
            return

        try:
            with open(self.storage_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            for sid, sdata in data.get("sessions", {}).items():
                try:
                    self._sessions[sid] = ConversationSession.from_dict(sdata)
                except Exception as exc:
                    print(f"[ConversationManager] Failed to load session {sid}: {exc}")

            self._chat_sessions = data.get("chat_sessions", {})

        except Exception as exc:
            print(f"[ConversationManager] Failed to load: {exc}")

    def cleanup_old_sessions(self, max_age_hours: int = 168) -> int:
        """Clean up old completed/error sessions.

        Args:
            max_age_hours: Maximum age in hours

        Returns:
            Number of sessions cleaned
        """
        cutoff = time.time() - (max_age_hours * 3600)
        to_remove = []

        for sid, session in self._sessions.items():
            if session.status in (
                ConversationStatus.COMPLETED,
                ConversationStatus.ERROR,
            ):
                if session.updated_at < cutoff:
                    to_remove.append(sid)

        for sid in to_remove:
            del self._sessions[sid]

        if to_remove:
            self._save_sessions()

        return len(to_remove)


# Global instance
_conversation_manager: Optional[ConversationManager] = None


def get_conversation_manager(
    storage_path: Optional[Path] = None,
) -> ConversationManager:
    """Get or create global conversation manager."""
    global _conversation_manager
    if _conversation_manager is None:
        _conversation_manager = ConversationManager(storage_path)
    return _conversation_manager
