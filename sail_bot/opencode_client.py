#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# @file opencode_client.py
# @brief OpenCode Server API Client - Async + SSE support
# @author sailing-innocent
# @date 2026-04-07
# @version 4.0
# ---------------------------------
"""OpenCode Server API Client with SSE event stream support.

Provides both synchronous (for simple operations) and async (for task execution)
access to the OpenCode server APIs.  The key improvement is using Server-Sent
Events (SSE) via GET /session/:id/events instead of polling for task progress.
"""

import asyncio
import json
import logging
import httpx
from dataclasses import dataclass, field
from typing import Any, AsyncIterator, Callable, Dict, List, Optional
from enum import Enum

logger = logging.getLogger("opencode_client")


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

class MessagePartType(str, Enum):
    """Types of message parts in OpenCode."""

    TEXT = "text"
    TOOL = "tool"
    REASONING = "reasoning"
    STEP_START = "step-start"
    STEP_FINISH = "step-finish"
    # Legacy / compat
    TOOL_CALL = "tool_call"
    TOOL_RESULT = "tool_result"
    IMAGE = "image"
    FILE = "file"
    UNKNOWN = "unknown"


@dataclass
class MessagePart:
    """A part of a message."""

    type: MessagePartType
    text: Optional[str] = None
    tool_name: Optional[str] = None
    tool_status: Optional[str] = None
    tool_state: Optional[Dict[str, Any]] = None
    reason: Optional[str] = None
    cost: Optional[float] = None
    tokens: Optional[Dict[str, Any]] = None
    raw_data: Optional[Dict[str, Any]] = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MessagePart":
        """Create MessagePart from API response dict."""
        part_type = data.get("type", "text")
        try:
            msg_type = MessagePartType(part_type)
        except ValueError:
            return cls(type=MessagePartType.UNKNOWN, raw_data=data)

        part = cls(type=msg_type)
        if msg_type == MessagePartType.TEXT:
            part.text = data.get("text")
        elif msg_type == MessagePartType.TOOL:
            part.tool_name = data.get("tool")
            state = data.get("state", {})
            part.tool_status = state.get("status")
            part.tool_state = state
        elif msg_type == MessagePartType.REASONING:
            part.text = data.get("text")
        elif msg_type == MessagePartType.STEP_FINISH:
            part.reason = data.get("reason")
            part.cost = data.get("cost")
            part.tokens = data.get("tokens")
        elif msg_type == MessagePartType.UNKNOWN:
            part.raw_data = data
        return part


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


# ---------------------------------------------------------------------------
# SSE Event
# ---------------------------------------------------------------------------

@dataclass
class SSEEvent:
    """A parsed Server-Sent Event."""

    event: str = ""     # event type (e.g. "message.updated", "session.completed")
    data: str = ""      # raw data payload
    id: Optional[str] = None

    def json(self) -> Any:
        """Parse data as JSON. Returns None on failure."""
        if not self.data:
            return None
        try:
            return json.loads(self.data)
        except json.JSONDecodeError:
            return None


# ---------------------------------------------------------------------------
# Synchronous client (for simple operations: health, session CRUD)
# ---------------------------------------------------------------------------

class OpenCodeSessionClient:
    """Simple, reliable OpenCode Server API client (synchronous).

    Use this for quick operations: health checks, session create/delete, etc.
    For task execution with progress, use OpenCodeAsyncClient instead.
    """

    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 4096,
        timeout: float = 30.0,
    ):
        self.host = host
        self.port = port
        self._base_url = f"http://{host}:{port}"
        self._client = httpx.Client(
            timeout=httpx.Timeout(timeout),
        )

    def _request(self, method: str, path: str, **kwargs) -> httpx.Response:
        url = f"{self._base_url}{path}"
        return self._client.request(method, url, **kwargs)

    def _json_request(self, method: str, path: str, **kwargs) -> Any:
        response = self._request(method, path, **kwargs)
        response.raise_for_status()
        return response.json()

    # -- Health ---------------------------------------------------------------

    def health_check(self) -> Dict[str, Any]:
        return self._json_request("GET", "/global/health")

    def is_healthy(self) -> bool:
        try:
            result = self.health_check()
            return result.get("healthy", False)
        except Exception:
            return False

    # -- Session CRUD ---------------------------------------------------------

    def create_session(self, title: Optional[str] = None) -> Session:
        body = {}
        if title:
            body["title"] = title
        data = self._json_request("POST", "/session", json=body)
        return Session.from_dict(data)

    def get_session(self, session_id: str) -> Session:
        data = self._json_request("GET", f"/session/{session_id}")
        return Session.from_dict(data)

    def delete_session(self, session_id: str) -> bool:
        response = self._request("DELETE", f"/session/{session_id}")
        return response.status_code == 200

    def list_sessions(self) -> List[Session]:
        data = self._json_request("GET", "/session")
        return [Session.from_dict(s) for s in data]

    # -- Session status -------------------------------------------------------

    def get_session_status(self) -> Dict[str, Any]:
        """Get status of all sessions. Returns {session_id: {type: 'busy'|...}}."""
        return self._json_request("GET", "/session/status")

    # -- Messages (synchronous, for simple use) --------------------------------

    def send_message(
        self,
        session_id: str,
        text: str,
        timeout: Optional[float] = None,
    ) -> Message:
        """Send a message and wait for complete response (blocking)."""
        body = {"parts": [{"type": "text", "text": text}]}
        client = self._client
        if timeout:
            client = httpx.Client(timeout=httpx.Timeout(timeout, read=timeout))
        try:
            url = f"{self._base_url}/session/{session_id}/message"
            response = client.post(url, json=body)
            response.raise_for_status()
            return Message.from_dict(response.json())
        finally:
            if timeout:
                client.close()

    def get_messages(self, session_id: str, limit: int = 50) -> List[Message]:
        data = self._json_request(
            "GET", f"/session/{session_id}/message", params={"limit": limit}
        )
        return [Message.from_dict(m) for m in data]

    # -- Async prompt (fire-and-forget) ----------------------------------------

    def send_prompt_async(self, session_id: str, text: str) -> bool:
        """Send prompt asynchronously. Returns True if accepted (HTTP 204)."""
        body = {"parts": [{"type": "text", "text": text}]}
        response = self._request(
            "POST", f"/session/{session_id}/prompt_async", json=body
        )
        return response.status_code == 204

    def abort_session(self, session_id: str) -> bool:
        """Abort the currently running generation in a session."""
        response = self._request("POST", f"/session/{session_id}/abort")
        return response.status_code == 200

    # -- Commands --------------------------------------------------------------

    def execute_command(
        self,
        session_id: str,
        command: str,
        arguments: Optional[List[str]] = None,
    ) -> Message:
        body = {"command": command, "arguments": arguments or []}
        data = self._json_request(
            "POST", f"/session/{session_id}/command", json=body
        )
        return Message.from_dict(data)

    def list_commands(self) -> List[Dict[str, Any]]:
        return self._json_request("GET", "/command")

    # -- File ops --------------------------------------------------------------

    def read_file(self, path: str) -> Dict[str, Any]:
        return self._json_request("GET", "/file/content", params={"path": path})

    def list_files(self, path: str = ".") -> List[Dict[str, Any]]:
        return self._json_request("GET", "/file", params={"path": path})

    # -- Lifecycle -------------------------------------------------------------

    def close(self) -> None:
        self._client.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
        return False


# ---------------------------------------------------------------------------
# Async client with SSE event stream
# ---------------------------------------------------------------------------

class OpenCodeAsyncClient:
    """Async OpenCode client with SSE event stream support.

    This is the recommended client for task execution.  It uses
    ``GET /session/:id/events`` (Server-Sent Events) to receive real-time
    updates instead of polling, dramatically reducing latency and load.

    Usage::

        async with OpenCodeAsyncClient(port=4096) as client:
            ok = await client.send_prompt_async(session_id, "write a function")
            async for event in client.stream_events(session_id):
                print(event.event, event.data)
    """

    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 4096,
        timeout: float = 30.0,
    ):
        self.host = host
        self.port = port
        self._base_url = f"http://{host}:{port}"
        self._client = httpx.AsyncClient(
            timeout=httpx.Timeout(timeout),
        )

    async def close(self) -> None:
        await self._client.aclose()

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()
        return False

    # -- Convenience wrappers (async) ------------------------------------------

    async def health_check(self) -> bool:
        try:
            resp = await self._client.get(f"{self._base_url}/global/health")
            return resp.json().get("healthy", False)
        except Exception:
            return False

    async def create_session(self, title: Optional[str] = None) -> Session:
        body = {"title": title} if title else {}
        resp = await self._client.post(f"{self._base_url}/session", json=body)
        resp.raise_for_status()
        return Session.from_dict(resp.json())

    async def get_session(self, session_id: str) -> Session:
        resp = await self._client.get(f"{self._base_url}/session/{session_id}")
        resp.raise_for_status()
        return Session.from_dict(resp.json())

    async def get_messages(self, session_id: str, limit: int = 10) -> List[Message]:
        resp = await self._client.get(
            f"{self._base_url}/session/{session_id}/message",
            params={"limit": limit},
        )
        resp.raise_for_status()
        return [Message.from_dict(m) for m in resp.json()]

    async def get_session_status(self) -> Dict[str, Any]:
        resp = await self._client.get(f"{self._base_url}/session/status")
        resp.raise_for_status()
        return resp.json()

    # -- Async prompt ----------------------------------------------------------

    async def send_prompt_async(self, session_id: str, text: str) -> bool:
        """Send prompt asynchronously. Returns True if accepted (HTTP 204)."""
        body = {"parts": [{"type": "text", "text": text}]}
        resp = await self._client.post(
            f"{self._base_url}/session/{session_id}/prompt_async",
            json=body,
        )
        return resp.status_code == 204

    async def send_message_async(
        self, session_id: str, text: str
    ) -> Message:
        """Send a synchronous message (blocks until AI finishes)."""
        body = {"parts": [{"type": "text", "text": text}]}
        resp = await self._client.post(
            f"{self._base_url}/session/{session_id}/message",
            json=body,
            timeout=httpx.Timeout(600.0, read=600.0),
        )
        resp.raise_for_status()
        return Message.from_dict(resp.json())

    async def abort_session(self, session_id: str) -> bool:
        """Abort the currently running generation."""
        resp = await self._client.post(
            f"{self._base_url}/session/{session_id}/abort"
        )
        return resp.status_code == 200

    # -- SSE Event Stream (core improvement) ------------------------------------

    async def stream_events(
        self,
        session_id: str,
        timeout: float = 3600.0,
    ) -> AsyncIterator[SSEEvent]:
        """Stream Server-Sent Events from an OpenCode session.

        This connects to ``GET /event`` (global event stream) and yields parsed
        SSE events in real-time. The connection stays open until:
        - The server closes it (task finished)
        - The timeout is reached
        - The caller breaks out of the loop

        Note: OpenCode uses a global event stream at /event, not per-session.
        Events are filtered by sessionID in the event data.

        Yields:
            SSEEvent objects with .event (type) and .data (payload)
        """
        url = f"{self._base_url}/event"
        # Use a dedicated client with streaming timeout
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(timeout, connect=10.0, read=timeout)
        ) as stream_client:
            async with stream_client.stream("GET", url) as response:
                response.raise_for_status()
                async for event in _parse_sse_stream(response):
                    yield event

    async def stream_events_robust(
        self,
        session_id: str,
        timeout: float = 3600.0,
        max_reconnects: int = 5,
        reconnect_delay: float = 2.0,
        on_reconnect: Optional[Callable[[int], None]] = None,
    ) -> AsyncIterator[SSEEvent]:
        """SSE stream with automatic reconnection on transient errors.

        Same as stream_events() but retries on connection errors. Yields
        a synthetic ``SSEEvent(event="__reconnected__")`` after each
        successful reconnection so callers can react.

        Note: The session_id parameter is used for event filtering in the
        consumer, not for the HTTP endpoint. OpenCode uses a global /event
        stream that includes events for all sessions.
        """
        reconnects = 0
        while reconnects <= max_reconnects:
            try:
                async for event in self.stream_events(session_id, timeout):
                    reconnects = 0  # reset on successful event
                    yield event
                # Stream ended normally (server closed connection)
                return
            except (httpx.ReadError, httpx.RemoteProtocolError,
                    httpx.ConnectError, httpx.ReadTimeout) as exc:
                reconnects += 1
                if reconnects > max_reconnects:
                    logger.error(
                        "[SSE] Max reconnects (%d) reached for session %s: %s",
                        max_reconnects, session_id[:16], exc,
                    )
                    raise
                logger.warning(
                    "[SSE] Connection lost for session %s (attempt %d/%d): %s",
                    session_id[:16], reconnects, max_reconnects, exc,
                )
                if on_reconnect:
                    on_reconnect(reconnects)
                await asyncio.sleep(reconnect_delay * reconnects)
                yield SSEEvent(event="__reconnected__", data=str(reconnects))


# ---------------------------------------------------------------------------
# SSE parser helper
# ---------------------------------------------------------------------------

async def _parse_sse_stream(
    response: httpx.Response,
) -> AsyncIterator[SSEEvent]:
    """Parse a raw HTTP response as an SSE stream.

    SSE format::

        event: <type>
        data: <payload>
        id: <optional id>
        <blank line>
    """
    current = SSEEvent()
    data_lines: List[str] = []

    async for raw_line in response.aiter_lines():
        line = raw_line.rstrip("\r\n")

        if not line:
            # Blank line = end of event
            if data_lines or current.event:
                current.data = "\n".join(data_lines)
                yield current
                current = SSEEvent()
                data_lines = []
            continue

        if line.startswith(":"):
            # SSE comment, skip
            continue

        if ":" in line:
            field, _, value = line.partition(":")
            value = value.lstrip(" ")  # single leading space is optional
        else:
            field = line
            value = ""

        if field == "event":
            current.event = value
        elif field == "data":
            data_lines.append(value)
        elif field == "id":
            current.id = value
        # ignore unknown fields per spec

    # Yield any trailing event without final blank line
    if data_lines or current.event:
        current.data = "\n".join(data_lines)
        yield current
