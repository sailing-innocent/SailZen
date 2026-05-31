# -*- coding: utf-8 -*-
# @file store.py
# @brief In-memory session/message store for the dummy server.
# @author sailing-innocent
# @date 2026-05-31
# @version 1.0
# ---------------------------------

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class StoredMessage:
    id: str
    role: str
    parts: List[Dict[str, Any]] = field(default_factory=list)
    created_at: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "info": {
                "id": self.id,
                "role": self.role,
                "createdAt": self.created_at,
            },
            "parts": self.parts,
        }


@dataclass
class StoredSession:
    id: str
    title: Optional[str] = None
    created_at: str = ""
    updated_at: str = ""
    parent_id: Optional[str] = None
    messages: List[StoredMessage] = field(default_factory=list)
    status: str = "idle"  # idle | busy

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "createdAt": self.created_at,
            "updatedAt": self.updated_at,
            "parentID": self.parent_id,
        }


class OpencodeStore:
    """Thread-safe in-memory store (asyncio-safe because GIL + single event loop)."""

    def __init__(self) -> None:
        self._sessions: Dict[str, StoredSession] = {}
        self._config: Dict[str, Any] = {"default_agent": "Sisyphus"}

    # ── Sessions ──────────────────────────────────────────────────

    def create_session(self, title: Optional[str] = None) -> StoredSession:
        sid = str(uuid.uuid4())
        now = _iso_now()
        sess = StoredSession(
            id=sid,
            title=title or "Untitled",
            created_at=now,
            updated_at=now,
        )
        self._sessions[sid] = sess
        return sess

    def get_session(self, session_id: str) -> Optional[StoredSession]:
        return self._sessions.get(session_id)

    def delete_session(self, session_id: str) -> bool:
        return self._sessions.pop(session_id, None) is not None

    def list_sessions(self) -> List[StoredSession]:
        return list(self._sessions.values())

    def get_session_status(self) -> Dict[str, Any]:
        return {
            sid: {"type": sess.status}
            for sid, sess in self._sessions.items()
        }

    # ── Messages ──────────────────────────────────────────────────

    def add_message(
        self,
        session_id: str,
        role: str,
        parts: List[Dict[str, Any]],
    ) -> StoredMessage:
        sess = self._sessions[session_id]
        msg = StoredMessage(
            id=str(uuid.uuid4()),
            role=role,
            parts=parts,
            created_at=_iso_now(),
        )
        sess.messages.append(msg)
        sess.updated_at = _iso_now()
        return msg

    def get_messages(
        self, session_id: str, limit: int = 10
    ) -> List[StoredMessage]:
        sess = self._sessions.get(session_id)
        if not sess:
            return []
        msgs = list(reversed(sess.messages))
        if limit > 0:
            msgs = msgs[:limit]
        return list(reversed(msgs))

    def get_children(self, session_id: str) -> List[Dict[str, Any]]:
        return [
            s.to_dict()
            for s in self._sessions.values()
            if s.parent_id == session_id
        ]

    def set_session_status(self, session_id: str, status: str) -> None:
        sess = self._sessions.get(session_id)
        if sess:
            sess.status = status

    # ── Config ────────────────────────────────────────────────────

    def get_config(self) -> Dict[str, Any]:
        return dict(self._config)

    def patch_config(self, patch: Dict[str, Any]) -> Dict[str, Any]:
        self._config.update(patch)
        return dict(self._config)

    # ── Agents ────────────────────────────────────────────────────

    def list_agents(self) -> List[Dict[str, Any]]:
        return [{"name": self._config.get("default_agent", "Sisyphus")}]


# ── Helpers ───────────────────────────────────────────────────────


def _iso_now() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).isoformat()
