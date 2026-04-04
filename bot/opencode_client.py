#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# @file opencode_client.py
# @brief OpenCode Server API Client - Simplified reliable version
# @author sailing-innocent
# @date 2026-04-04
# @version 3.0
# ---------------------------------
"""OpenCode Server API Client - Reliable synchronous implementation.

This client provides simple, reliable access to the OpenCode server APIs.
"""

import json
import httpx
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from pathlib import Path
from enum import Enum


class MessagePartType(str, Enum):
    """Types of message parts in OpenCode."""

    TEXT = "text"
    TOOL_CALL = "tool_call"
    TOOL_RESULT = "tool_result"
    IMAGE = "image"
    FILE = "file"
    STEP_START = "step-start"
    STEP_END = "step-end"
    UNKNOWN = "unknown"


@dataclass
class MessagePart:
    """A part of a message."""

    type: MessagePartType
    text: Optional[str] = None
    tool_call: Optional[Dict[str, Any]] = None
    tool_result: Optional[Dict[str, Any]] = None
    raw_data: Optional[Dict[str, Any]] = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MessagePart":
        """Create MessagePart from API response dict."""
        part_type = data.get("type", "text")

        try:
            msg_type = MessagePartType(part_type)
        except ValueError:
            return cls(type=MessagePartType.UNKNOWN, raw_data=data)

        return cls(
            type=msg_type,
            text=data.get("text"),
            tool_call=data.get("tool_call"),
            tool_result=data.get("tool_result"),
            raw_data=data if msg_type == MessagePartType.UNKNOWN else None,
        )


@dataclass
class Message:
    """An OpenCode message."""

    id: str
    role: str
    parts: List[MessagePart] = field(default_factory=list)
    created_at: Optional[str] = None

    @property
    def text_content(self) -> str:
        """Extract all text content from message parts."""
        texts = []
        for part in self.parts:
            if part.type == MessagePartType.TEXT and part.text:
                texts.append(part.text)
        return "".join(texts)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Message":
        """Create Message from API response dict."""
        info = data.get("info", {})
        parts_data = data.get("parts", [])

        return cls(
            id=info.get("id", ""),
            role=info.get("role", "assistant"),
            parts=[MessagePart.from_dict(p) for p in parts_data],
            created_at=info.get("createdAt"),
        )


@dataclass
class Session:
    """An OpenCode session."""

    id: str
    title: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    parent_id: Optional[str] = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Session":
        """Create Session from API response dict."""
        return cls(
            id=data.get("id", ""),
            title=data.get("title"),
            created_at=data.get("createdAt"),
            updated_at=data.get("updatedAt"),
            parent_id=data.get("parentID"),
        )


class OpenCodeSessionClient:
    """Simple, reliable OpenCode Server API client.

    Example:
        client = OpenCodeSessionClient(port=4096)
        session = client.create_session(title="My Session")
        message = client.send_message(session.id, "Hello, write a function")
        print(message.text_content)
    """

    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 4096,
        timeout: float = 300.0,
    ):
        self.host = host
        self.port = port
        self._base_url = f"http://{host}:{port}"

        # HTTP client with long timeout for AI responses
        self._client = httpx.Client(
            timeout=httpx.Timeout(timeout, read=timeout),
        )

    def _request(self, method: str, path: str, **kwargs) -> httpx.Response:
        """Make an HTTP request to the OpenCode server."""
        url = f"{self._base_url}{path}"
        return self._client.request(method, url, **kwargs)

    def _json_request(self, method: str, path: str, **kwargs) -> Dict[str, Any]:
        """Make a JSON request and parse response."""
        response = self._request(method, path, **kwargs)
        response.raise_for_status()
        return response.json()

    # -----------------------------------------------------------------------
    # Health & Status
    # -----------------------------------------------------------------------

    def health_check(self) -> Dict[str, Any]:
        """Check server health."""
        return self._json_request("GET", "/global/health")

    def is_healthy(self) -> bool:
        """Quick health check."""
        try:
            result = self.health_check()
            return result.get("healthy", False)
        except Exception:
            return False

    # -----------------------------------------------------------------------
    # Session Management
    # -----------------------------------------------------------------------

    def create_session(self, title: Optional[str] = None) -> Session:
        """Create a new session."""
        body = {}
        if title:
            body["title"] = title
        data = self._json_request("POST", "/session", json=body)
        return Session.from_dict(data)

    def get_session(self, session_id: str) -> Session:
        """Get session details."""
        data = self._json_request("GET", f"/session/{session_id}")
        return Session.from_dict(data)

    def delete_session(self, session_id: str) -> bool:
        """Delete a session."""
        response = self._request("DELETE", f"/session/{session_id}")
        return response.status_code == 200

    def list_sessions(self) -> List[Session]:
        """List all sessions."""
        data = self._json_request("GET", "/session")
        return [Session.from_dict(s) for s in data]

    # -----------------------------------------------------------------------
    # Messages - Reliable Synchronous
    # -----------------------------------------------------------------------

    def send_message(
        self,
        session_id: str,
        text: str,
        timeout: Optional[float] = None,
    ) -> Message:
        """Send a message and wait for complete response.

        This uses the synchronous API which blocks until the AI finishes.
        It's reliable for long responses (up to 5 minutes or more).

        Args:
            session_id: Session ID
            text: Message text
            timeout: Request timeout override (default: client timeout)

        Returns:
            Complete response Message
        """
        body = {
            "parts": [{"type": "text", "text": text}],
        }

        print(
            f"[OpenCode] Sending message (timeout: {timeout or self._client.timeout.read}s)..."
        )

        data = self._json_request(
            "POST",
            f"/session/{session_id}/message",
            json=body,
        )

        msg = Message.from_dict(data)
        print(f"[OpenCode] Received response: {len(msg.text_content)} chars")
        return msg

    def get_messages(self, session_id: str, limit: int = 50) -> List[Message]:
        """Get messages in a session."""
        params = {"limit": limit}
        data = self._json_request(
            "GET", f"/session/{session_id}/message", params=params
        )
        return [Message.from_dict(m) for m in data]

    # -----------------------------------------------------------------------
    # Commands
    # -----------------------------------------------------------------------

    def execute_command(
        self,
        session_id: str,
        command: str,
        arguments: Optional[List[str]] = None,
    ) -> Message:
        """Execute a slash command."""
        body = {
            "command": command,
            "arguments": arguments or [],
        }
        data = self._json_request(
            "POST",
            f"/session/{session_id}/command",
            json=body,
        )
        return Message.from_dict(data)

    def list_commands(self) -> List[Dict[str, Any]]:
        """List all available commands."""
        return self._json_request("GET", "/command")

    # -----------------------------------------------------------------------
    # File Operations
    # -----------------------------------------------------------------------

    def read_file(self, path: str) -> Dict[str, Any]:
        """Read file content."""
        return self._json_request("GET", "/file/content", params={"path": path})

    def list_files(self, path: str = ".") -> List[Dict[str, Any]]:
        """List files and directories."""
        return self._json_request("GET", "/file", params={"path": path})

    # -----------------------------------------------------------------------
    # Context Management
    # -----------------------------------------------------------------------

    def close(self) -> None:
        """Close the HTTP client."""
        self._client.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
        return False


# Legacy compatibility
class OpenCodeWebClient(OpenCodeSessionClient):
    """Legacy client name for backward compatibility."""

    pass
