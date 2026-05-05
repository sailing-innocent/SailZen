# -*- coding: utf-8 -*-
# @file sse_parser.py
# @brief SSE 事件统一解析器
# @author sailing-innocent
# @date 2026-04-25
# @version 1.0
# ---------------------------------
"""sail.opencode.sse_parser — SSE 事件统一解析器。

将 OpenCode /event 端点推送的原始 SSEEvent 解码为
结构化的 ParsedEvent，兼容 opencode 原生格式和简化格式。

格式 A — opencode 原生格式
    message.part.updated  → type = text | tool | reasoning | step-start | step-finish
    message.part.delta    → type = text_delta
    session.idle          → type = session_idle

格式 B — 简化格式
    text / reasoning / tool / step-start / step-finish

会话过滤
    /event 是全局端点，传入 session_id 后自动过滤非本 session 的事件。

使用示例::

    async for raw_event in client.stream_events_robust(session_id):
        parsed = parse_event(raw_event, session_id)
        if parsed.type == EventType.TEXT:
            print(parsed.delta, end="", flush=True)
        elif parsed.type == EventType.SESSION_IDLE:
            break
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, Optional

from sail.opencode.client import SSEEvent


# ── 事件类型枚举 ──────────────────────────────────────────────────


class EventType(str, Enum):
    """解析后的事件类型。"""

    TEXT = "text"
    TEXT_DELTA = "text_delta"
    REASONING = "reasoning"
    TOOL = "tool"
    PERMISSION = "permission"
    STEP_START = "step-start"
    STEP_FINISH = "step-finish"
    SESSION_IDLE = "session_idle"
    RECONNECTED = "reconnected"
    SKIP = "skip"
    UNKNOWN = "unknown"


# ── 结构化解析结果 ────────────────────────────────────────────────


@dataclass
class ParsedEvent:
    """SSE 事件的结构化解析结果。"""

    type: EventType = EventType.UNKNOWN
    text: str = ""
    delta: str = ""
    tool_name: str = ""
    tool_status: str = ""
    tool_title: str = ""
    permission_id: str = ""
    finished: bool = False
    cost: float = 0.0
    tokens: Dict[str, Any] = field(default_factory=dict)
    raw: Dict[str, Any] = field(default_factory=dict)

    def is_terminal(self) -> bool:
        """是否是最终完成事件。"""
        if self.type == EventType.SESSION_IDLE:
            return True
        if self.type == EventType.STEP_FINISH:
            return self.text not in ("tool-calls", "tool_calls")
        return False


# ── 主解析函数 ────────────────────────────────────────────────────


def parse_event(event: SSEEvent, session_id: str = "") -> ParsedEvent:
    """将原始 SSEEvent 解析为 ParsedEvent。

    兼容 opencode 原生格式 A 和简化格式 B。

    Args:
        event:      原始 SSE 事件
        session_id: 当前会话 ID，用于过滤。传空字符串则不过滤。

    Returns:
        ParsedEvent，type == EventType.SKIP 时可安全忽略。
    """
    # ── 重连哨兵 ──────────────────────────────────────────────────
    if event.event == "__reconnected__":
        return ParsedEvent(
            type=EventType.RECONNECTED,
            text=f"SSE reconnected (attempt {event.data})",
        )

    data = event.json()
    if not data:
        return ParsedEvent(type=EventType.SKIP)

    event_type: str = data.get("type", "")

    # ── 全局事件过滤 ──────────────────────────────────────────────
    if event_type in ("server.connected", "server.heartbeat"):
        return ParsedEvent(type=EventType.SKIP)

    # ── Session 过滤 ──────────────────────────────────────────────
    if session_id and not _matches_session(data, session_id):
        return ParsedEvent(type=EventType.SKIP)

    # ── 格式 A: opencode 原生事件 ─────────────────────────────────
    if event_type == "message.part.updated":
        return _parse_part_updated(data)

    if event_type in (
        "message.updated",
        "message.created",
        "session.updated",
        "session.created",
        "session.diff",
    ):
        return ParsedEvent(type=EventType.SKIP)

    if event_type == "message.part.delta":
        return _parse_part_delta(data)

    if event_type in ("session.idle", "session.status"):
        return _parse_session_status(data, event_type)

    if event_type in ("session.permission", "permission"):
        perm_id = data.get("id", data.get("permissionID", ""))
        return ParsedEvent(
            type=EventType.PERMISSION,
            permission_id=perm_id,
            raw=data,
        )

    # ── 格式 B: 简化事件 ──────────────────────────────────────────
    return _parse_simple_event(data, event_type)


# ── 格式 A 解析器 ──────────────────────────────────────────────────


def _parse_part_updated(data: Dict[str, Any]) -> ParsedEvent:
    props = data.get("properties", {})
    part = props.get("part", {})
    delta = props.get("delta", "")
    part_type = part.get("type", "")

    if part_type == "text":
        return ParsedEvent(
            type=EventType.TEXT,
            delta=delta,
            text=part.get("text", ""),
            raw=data,
        )

    if part_type == "tool":
        state = part.get("state", {})
        tool_name = part.get("tool", "unknown")
        status = state.get("status", "")
        title = state.get("title", tool_name)

        if tool_name in ("permission", "question", "ask"):
            if status in ("pending", "running"):
                return ParsedEvent(
                    type=EventType.PERMISSION,
                    tool_name=tool_name,
                    tool_status=status,
                    tool_title=title,
                    permission_id=state.get("id", ""),
                    raw=data,
                )

        return ParsedEvent(
            type=EventType.TOOL,
            tool_name=tool_name,
            tool_status=status,
            tool_title=title,
            raw=data,
        )

    if part_type == "reasoning":
        return ParsedEvent(
            type=EventType.REASONING,
            text=part.get("text", ""),
            delta=delta,
            raw=data,
        )

    if part_type == "step-start":
        return ParsedEvent(type=EventType.STEP_START, raw=data)

    if part_type == "step-finish":
        reason = part.get("reason", "")
        cost = part.get("cost", 0.0) or 0.0
        tokens = part.get("tokens", {}) or {}
        finished = reason not in ("tool-calls", "tool_calls")
        return ParsedEvent(
            type=EventType.STEP_FINISH,
            text=reason,
            finished=finished,
            cost=float(cost),
            tokens=tokens,
            raw=data,
        )

    return ParsedEvent(type=EventType.SKIP)


def _parse_part_delta(data: Dict[str, Any]) -> ParsedEvent:
    props = data.get("properties", {})
    delta = props.get("delta", "")
    field_name = props.get("field", "")

    if delta and field_name in ("text", "reasoning"):
        return ParsedEvent(
            type=EventType.TEXT_DELTA,
            delta=delta,
            text=delta,
            raw=data,
        )
    return ParsedEvent(type=EventType.SKIP)


def _parse_session_status(data: Dict[str, Any], event_type: str) -> ParsedEvent:
    if event_type == "session.status":
        props = data.get("properties", {})
        status = props.get("status", {})
        status_type = status.get("type", "") if isinstance(status, dict) else ""
        if status_type != "idle":
            return ParsedEvent(type=EventType.SKIP)

    return ParsedEvent(
        type=EventType.SESSION_IDLE,
        finished=True,
        raw=data,
    )


# ── 格式 B 解析器 ──────────────────────────────────────────────────


def _parse_simple_event(
    data: Dict[str, Any], event_type: str
) -> ParsedEvent:
    if event_type == "text":
        txt = data.get("text", "")
        return ParsedEvent(type=EventType.TEXT, text=txt, delta=txt, raw=data)

    if event_type == "reasoning":
        return ParsedEvent(
            type=EventType.REASONING,
            text=data.get("text", ""),
            raw=data,
        )

    if event_type == "tool":
        state = data.get("state", {})
        tool_name = data.get("tool", "")
        status = state.get("status", "")
        title = state.get("title", tool_name)

        if tool_name in ("permission", "question", "ask"):
            if status in ("pending", "running"):
                return ParsedEvent(
                    type=EventType.PERMISSION,
                    tool_name=tool_name,
                    tool_status=status,
                    tool_title=title,
                    permission_id=state.get("id", ""),
                    raw=data,
                )

        return ParsedEvent(
            type=EventType.TOOL,
            tool_name=tool_name,
            tool_status=status,
            tool_title=title,
            raw=data,
        )

    if event_type == "step-start":
        return ParsedEvent(type=EventType.STEP_START, raw=data)

    if event_type == "step-finish":
        reason = data.get("reason", "")
        cost = data.get("cost", 0.0) or 0.0
        tokens = data.get("tokens", {}) or {}
        finished = reason not in ("tool-calls", "tool_calls")
        return ParsedEvent(
            type=EventType.STEP_FINISH,
            text=reason,
            finished=finished,
            cost=float(cost),
            tokens=tokens,
            raw=data,
        )

    return ParsedEvent(type=EventType.UNKNOWN, raw=data)


# ── 会话匹配 ──────────────────────────────────────────────────────


def _matches_session(data: Dict[str, Any], session_id: str) -> bool:
    """检查 SSE 事件是否属于指定 session。"""
    props = data.get("properties", {})
    sid: Optional[str] = (
        props.get("sessionID")
        or props.get("session_id")
        or data.get("sessionID")
    )
    if not sid:
        info = props.get("info", {}) if props else {}
        sid = info.get("sessionID")

    return not sid or sid == session_id
