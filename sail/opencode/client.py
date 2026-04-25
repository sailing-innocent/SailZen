# -*- coding: utf-8 -*-
# @file client.py
# @brief OpenCode (opencode) 异步 HTTP / SSE 客户端
# @author sailing-innocent
# @date 2026-04-25
# @version 1.0
# ---------------------------------
"""sail.opencode.client — OpenCode 异步 HTTP / SSE 客户端。

**只提供异步客户端 OpenCodeAsyncClient**。

进程管理中需要同步健康检查的场景（如 subprocess.Popen 等待启动），
请使用模块级辅助函数 check_health_sync(port)。

SSE 格式说明
-----------
OpenCode 的 /event 全局端点推送两种格式:

格式 A (opencode 原生):
    message.part.updated  — 文本/工具/推理部分更新
    message.part.delta    — 增量文本
    session.idle          — 任务完成

格式 B (简化格式):
    text / reasoning / tool / step-start / step-finish

两种格式均由 sail.opencode.sse_parser.parse_event 统一解码。
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


# ── 同步辅助函数（无需创建客户端对象）────────────────────────────


def check_health_sync(
    port: int,
    host: str = "127.0.0.1",
    timeout: float = 3.0,
) -> bool:
    """同步健康检查，用于进程管理等同步上下文。"""
    try:
        with httpx.Client(timeout=httpx.Timeout(timeout)) as c:
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
    """同步中止 session，适用于无法使用 async 的回调中。"""
    try:
        with httpx.Client(timeout=httpx.Timeout(timeout)) as c:
            resp = c.post(f"http://{host}:{port}/session/{session_id}/abort")
            return resp.status_code == 200
    except Exception:
        return False


# ── Async Client ──────────────────────────────────────────────────


class OpenCodeAsyncClient:
    """异步 OpenCode 客户端，内置 SSE 事件流支持。

    推荐用于所有任务执行和实时进度监听。

    Example::

        async with OpenCodeAsyncClient(port=4096) as client:
            sess = await client.create_session("My Task")
            ok = await client.send_prompt_async(sess.id, "write tests")
            async for event in client.stream_events_robust(sess.id):
                parsed = parse_event(event, sess.id)
                if parsed.type == EventType.TEXT:
                    print(parsed.delta, end="", flush=True)
    """

    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 4096,
        timeout: float = 30.0,
    ) -> None:
        self.host = host
        self.port = port
        self._base_url = f"http://{host}:{port}"
        self._client = httpx.AsyncClient(timeout=httpx.Timeout(timeout))

    async def close(self) -> None:
        await self._client.aclose()

    async def __aenter__(self) -> "OpenCodeAsyncClient":
        return self

    async def __aexit__(self, *args: Any) -> bool:
        await self.close()
        return False

    # ── Health ────────────────────────────────────────────────────

    async def health_check(self) -> bool:
        """异步健康检查。"""
        try:
            resp = await self._client.get(f"{self._base_url}/global/health")
            data = resp.json()
            healthy = data.get("healthy", False)
            if not healthy:
                logger.warning(
                    "[OpenCode] health_check: healthy=False, response=%s", data
                )
            return bool(healthy)
        except httpx.ConnectError as exc:
            logger.warning(
                "[OpenCode] health_check: 无法连接 %s — %s", self._base_url, exc
            )
            return False
        except Exception as exc:
            logger.warning(
                "[OpenCode] health_check: %s: %s", type(exc).__name__, exc
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
        """Fire-and-forget prompt (HTTP 204)。"""
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
        """发送消息并等待响应（阻塞直到 LLM 回复）。"""
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

    async def respond_permission(
        self,
        session_id: str,
        permission_id: str,
        response: str = "allow",
        remember: bool = True,
    ) -> bool:
        """响应权限请求 (allow / deny)。"""
        body = {"response": response, "remember": remember}
        resp = await self._client.post(
            f"{self._base_url}/session/{session_id}/permissions/{permission_id}",
            json=body,
        )
        return resp.status_code == 200

    # ── SSE Streaming ─────────────────────────────────────────────

    async def stream_events(
        self,
        session_id: str,
        timeout: float = 14400.0,
    ) -> AsyncIterator[SSEEvent]:
        """从全局 /event 端点流式读取 SSE 事件。

        注意: /event 是全局端点，会推送所有 session 的事件。
        配合 sse_parser.parse_event(event, session_id) 过滤。
        """
        url = f"{self._base_url}/event"
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
        timeout: float = 14400.0,
        max_reconnects: int = 5,
        reconnect_delay: float = 2.0,
        on_reconnect: Optional[Callable[[int], None]] = None,
    ) -> AsyncIterator[SSEEvent]:
        """带自动重连的 SSE 事件流。

        断线时自动重连，每次重连前产生一个
        ``SSEEvent(event="__reconnected__")`` 哨兵事件。
        """
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
                        "[SSE] Max reconnects reached for session %s: %s",
                        session_id[:16], exc,
                    )
                    raise
                logger.warning(
                    "[SSE] Reconnecting session %s (%d/%d): %s",
                    session_id[:16], reconnects, max_reconnects, exc,
                )
                if on_reconnect:
                    on_reconnect(reconnects)
                await asyncio.sleep(reconnect_delay * reconnects)
                yield SSEEvent(event="__reconnected__", data=str(reconnects))


# ── SSE Stream Parser (internal) ──────────────────────────────────


async def _parse_sse_stream(
    response: httpx.Response,
) -> AsyncIterator[SSEEvent]:
    """将 HTTP 响应体解析为 SSEEvent 流（内部使用）。"""
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
            continue  # SSE 注释行（心跳）

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
