# -*- coding: utf-8 -*-
# @file client.py
# @brief Generic OpenCode-compatible async HTTP / SSE client
# @author sailing-innocent
# @date 2026-05-31
# @version 2.0
# ---------------------------------
"""sail.opencode.client — Generic OpenCode-compatible async HTTP / SSE client.

Supports arbitrary service names via the ``name`` parameter, useful when
wrapping forks (codemaker, kimix, etc.) that share the same opencode API.
"""

from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, AsyncIterator, Callable, Dict, List, Optional

import httpx

logger = logging.getLogger(__name__)


# ── Data Models ───────────────────────────────────────────────────


class MessagePartType(str, Enum):
    TEXT = "text"
    TOOL = "tool"
    REASONING = "reasoning"
    STEP_START = "step-start"
    STEP_FINISH = "step-finish"
    TOOL_CALL = "tool_call"
    TOOL_RESULT = "tool_result"
    IMAGE = "image"
    FILE = "file"
    UNKNOWN = "unknown"


@dataclass
class MessagePart:
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
    id: str
    role: str
    parts: List[MessagePart] = field(default_factory=list)
    created_at: Optional[str] = None

    @property
    def text_content(self) -> str:
        return "".join(
            p.text for p in self.parts
            if p.type == MessagePartType.TEXT and p.text
        )

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Message":
        info = data.get("info", {})
        return cls(
            id=info.get("id", ""),
            role=info.get("role", "assistant"),
            parts=[MessagePart.from_dict(p) for p in data.get("parts", [])],
            created_at=info.get("createdAt"),
        )


@dataclass
class Session:
    id: str
    title: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    parent_id: Optional[str] = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Session":
        return cls(
            id=data.get("id", ""),
            title=data.get("title"),
            created_at=data.get("createdAt"),
            updated_at=data.get("updatedAt"),
            parent_id=data.get("parentID"),
        )


@dataclass
class SSEEvent:
    """Parsed Server-Sent Event."""

    event: str = ""
    data: str = ""
    id: Optional[str] = None

    def json(self) -> Any:
        if not self.data:
            return None
        try:
            return json.loads(self.data)
        except json.JSONDecodeError:
            return None

    @property
    def is_reconnect(self) -> bool:
        return self.event == "__reconnected__"


# ── Sync helpers ──────────────────────────────────────────────────


def check_health_sync(
    port: int,
    host: str = "127.0.0.1",
    timeout: float = 3.0,
) -> bool:
    """Synchronous health check for use in sync contexts (e.g. subprocess polling)."""
    try:
        with httpx.Client(
            timeout=httpx.Timeout(timeout),
            trust_env=False,
        ) as c:
            resp = c.get(f"http://{host}:{port}/global/health")
            return bool(resp.json().get("healthy", False))
    except Exception:
        return False


def abort_session_sync(
    session_id: str,
    port: int,
    host: str = "127.0.0.1",
    timeout: float = 10.0,
) -> bool:
    """Synchronous session abort for sync callbacks."""
    try:
        with httpx.Client(
            timeout=httpx.Timeout(timeout),
            trust_env=False,
        ) as c:
            resp = c.post(f"http://{host}:{port}/session/{session_id}/abort")
            return resp.status_code == 200
    except Exception:
        return False


# ── Async Client ──────────────────────────────────────────────────


class OpencodeAsyncClient:
    """Generic async OpenCode-compatible client with SSE support.

    Args:
        host: Server hostname.
        port: Server port.
        timeout: Default HTTP timeout.
        name: Service name used in log messages (e.g. ``"opencode"``, ``"codemaker"``).
    """

    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 4096,
        timeout: float = 30.0,
        name: str = "opencode",
    ) -> None:
        self.host = host
        self.port = port
        self.name = name
        self._base_url = f"http://{host}:{port}"
        self._client = httpx.AsyncClient(
            timeout=httpx.Timeout(timeout),
            trust_env=False,
        )

    async def close(self) -> None:
        await self._client.aclose()

    async def __aenter__(self) -> "OpencodeAsyncClient":
        return self

    async def __aexit__(self, *args: Any) -> bool:
        await self.close()
        return False

    # ── Health ────────────────────────────────────────────────────

    async def health_check(self) -> bool:
        try:
            resp = await self._client.get(f"{self._base_url}/global/health")
            data = resp.json()
            healthy = data.get("healthy", False)
            if not healthy:
                logger.warning(
                    "[%s] health_check: healthy=False, response=%s", self.name, data
                )
            return bool(healthy)
        except httpx.ConnectError as exc:
            logger.warning(
                "[%s] health_check: cannot connect %s — %s",
                self.name,
                self._base_url,
                exc,
            )
            return False
        except Exception as exc:
            logger.warning(
                "[%s] health_check: %s: %s", self.name, type(exc).__name__, exc
            )
            return False

    # ── Session CRUD ──────────────────────────────────────────────

    async def create_session(self, title: Optional[str] = None) -> Session:
        body = {"title": title} if title else {}
        resp = await self._client.post(f"{self._base_url}/session", json=body)
        resp.raise_for_status()
        return Session.from_dict(resp.json())

    async def get_session(self, session_id: str) -> Session:
        resp = await self._client.get(f"{self._base_url}/session/{session_id}")
        resp.raise_for_status()
        return Session.from_dict(resp.json())

    async def delete_session(self, session_id: str) -> bool:
        resp = await self._client.delete(f"{self._base_url}/session/{session_id}")
        return resp.status_code == 200

    async def list_sessions(self) -> List[Session]:
        resp = await self._client.get(f"{self._base_url}/session")
        resp.raise_for_status()
        return [Session.from_dict(s) for s in resp.json()]

    async def get_messages(
        self, session_id: str, limit: int = 10
    ) -> List[Message]:
        resp = await self._client.get(
            f"{self._base_url}/session/{session_id}/message",
            params={"limit": limit},
        )
        resp.raise_for_status()
        return [Message.from_dict(m) for m in resp.json()]

    async def get_session_transcript(
        self, session_id: str, limit: int = 0
    ) -> List[Dict[str, Any]]:
        """Fetch full message transcript (with parts) for archiving."""
        params: Dict[str, Any] = {}
        if limit > 0:
            params["limit"] = limit
        resp = await self._client.get(
            f"{self._base_url}/session/{session_id}/message",
            params=params,
        )
        resp.raise_for_status()
        raw = resp.json()
        if raw and isinstance(raw[0], dict) and "info" in raw[0]:
            return raw
        return [{"info": m, "parts": []} for m in raw]

    async def get_session_children(self, session_id: str) -> List[Dict[str, Any]]:
        resp = await self._client.get(
            f"{self._base_url}/session/{session_id}/children"
        )
        resp.raise_for_status()
        raw = resp.json()
        return raw if isinstance(raw, list) else []

    async def get_session_status(self) -> Dict[str, Any]:
        resp = await self._client.get(f"{self._base_url}/session/status")
        resp.raise_for_status()
        return resp.json()

    # ── Messaging ─────────────────────────────────────────────────

    async def send_prompt_async(
        self,
        session_id: str,
        text: str,
        agent: Optional[str] = None,
        model: Optional[str] = None,
    ) -> bool:
        body: Dict[str, Any] = {"parts": [{"type": "text", "text": text}]}
        if agent:
            body["agent"] = agent
        if model:
            body["model"] = model
        resp = await self._client.post(
            f"{self._base_url}/session/{session_id}/prompt_async", json=body
        )
        return resp.status_code == 204

    async def send_message(
        self,
        session_id: str,
        text: str,
        agent: Optional[str] = None,
        model: Optional[str] = None,
        timeout: float = 600.0,
    ) -> Message:
        body: Dict[str, Any] = {"parts": [{"type": "text", "text": text}]}
        if agent:
            body["agent"] = agent
        if model:
            body["model"] = model
        resp = await self._client.post(
            f"{self._base_url}/session/{session_id}/message",
            json=body,
            timeout=httpx.Timeout(timeout, read=timeout),
        )
        resp.raise_for_status()
        return Message.from_dict(resp.json())

    async def abort_session(self, session_id: str) -> bool:
        resp = await self._client.post(
            f"{self._base_url}/session/{session_id}/abort"
        )
        return resp.status_code == 200

    # ── Agent / Config / Permission ───────────────────────────────

    async def list_agents(self) -> List[Dict[str, Any]]:
        resp = await self._client.get(f"{self._base_url}/agent")
        resp.raise_for_status()
        return resp.json()

    async def get_config(self) -> Dict[str, Any]:
        resp = await self._client.get(f"{self._base_url}/config")
        resp.raise_for_status()
        return resp.json()

    async def update_config(self, patch: Dict[str, Any]) -> Dict[str, Any]:
        resp = await self._client.patch(f"{self._base_url}/config", json=patch)
        resp.raise_for_status()
        return resp.json()

    async def respond_permission(
        self,
        session_id: str,
        permission_id: str,
        response: str = "always",
        remember: bool = True,
    ) -> bool:
        """Respond to a permission request.

        Modern opencode-compatible servers use ``once`` / ``always`` / ``reject``.
        Legacy ``allow`` / ``deny`` values are mapped automatically.
        """
        reply = response
        if response == "allow":
            reply = "always" if remember else "once"
        elif response == "deny":
            reply = "reject"
        if reply not in {"once", "always", "reject"}:
            reply = "always"

        resp = await self._client.post(
            f"{self._base_url}/permission/{permission_id}/reply",
            json={"reply": reply},
        )
        if resp.status_code == 200:
            return True
        if resp.status_code not in {404, 405}:
            resp.raise_for_status()
            return False

        legacy_resp = await self._client.post(
            f"{self._base_url}/session/{session_id}/permissions/{permission_id}",
            json={"response": reply},
        )
        if legacy_resp.status_code == 200:
            return True
        legacy_resp.raise_for_status()
        return False

    # ── SSE Streaming ─────────────────────────────────────────────

    async def stream_events(
        self,
        session_id: str,
        timeout: float = 14400.0,
    ) -> AsyncIterator[SSEEvent]:
        """Stream raw SSE events from the global ``/event`` endpoint."""
        url = f"{self._base_url}/event"
        stream_client = httpx.AsyncClient(
            timeout=httpx.Timeout(timeout, connect=10.0, read=timeout),
            trust_env=False,
        )
        response_ctx = None
        try:
            response_ctx = stream_client.stream("GET", url)
            response = await response_ctx.__aenter__()
            response.raise_for_status()
            async for event in _parse_sse_stream(response):
                yield event
        except (asyncio.CancelledError, GeneratorExit):
            return
        finally:
            if response_ctx is not None:
                try:
                    await response_ctx.__aexit__(None, None, None)
                except Exception:
                    pass
            try:
                await stream_client.aclose()
            except Exception:
                pass

    async def stream_events_robust(
        self,
        session_id: str,
        timeout: float = 14400.0,
        max_reconnects: int = 5,
        reconnect_delay: float = 2.0,
        on_reconnect: Optional[Callable[[int], None]] = None,
    ) -> AsyncIterator[SSEEvent]:
        """SSE stream with automatic reconnect."""
        reconnects = 0
        while reconnects <= max_reconnects:
            try:
                async for event in self.stream_events(session_id, timeout):
                    reconnects = 0
                    yield event
                return
            except (
                httpx.ReadError,
                httpx.RemoteProtocolError,
                httpx.ConnectError,
                httpx.ReadTimeout,
            ) as exc:
                reconnects += 1
                if reconnects > max_reconnects:
                    logger.error(
                        "[%s] Max reconnects reached for session %s: %s",
                        self.name,
                        session_id[:16],
                        exc,
                    )
                    raise
                logger.warning(
                    "[%s] Reconnecting session %s (%d/%d): %s",
                    self.name,
                    session_id[:16],
                    reconnects,
                    max_reconnects,
                    exc,
                )
                if on_reconnect:
                    on_reconnect(reconnects)
                await asyncio.sleep(reconnect_delay * reconnects)
                yield SSEEvent(event="__reconnected__", data=str(reconnects))


# Backward-compatible alias
OpenCodeAsyncClient = OpencodeAsyncClient


# ── SSE Stream Parser (internal) ──────────────────────────────────


async def _parse_sse_stream(
    response: httpx.Response,
) -> AsyncIterator[SSEEvent]:
    """Parse an HTTP response body into a stream of SSEEvents."""
    current = SSEEvent()
    data_lines: List[str] = []

    async for raw_line in response.aiter_lines():
        line = raw_line.rstrip("\r\n")

        if not line:
            if data_lines or current.event:
                current.data = "\n".join(data_lines)
                yield current
                current = SSEEvent()
                data_lines = []
            continue

        if line.startswith(":"):
            continue  # SSE comment / heartbeat

        if ":" in line:
            field_name, _, value = line.partition(":")
            value = value.lstrip(" ")
        else:
            field_name = line
            value = ""

        if field_name == "event":
            current.event = value
        elif field_name == "data":
            data_lines.append(value)
        elif field_name == "id":
            current.id = value

    if data_lines or current.event:
        current.data = "\n".join(data_lines)
        yield current
