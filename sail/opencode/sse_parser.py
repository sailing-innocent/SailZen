# -*- coding: utf-8 -*-
# @file sse_parser.py
# @brief Unified SSE event parser (opencode native + simplified format B)
# @author sailing-innocent
# @date 2026-05-31
# @version 2.0
# ---------------------------------
"""sail.opencode.sse_parser — SSE event parser supporting opencode-native
(format A) and simplified (format B) events."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, Optional

from sail.opencode.client import SSEEvent

logger = logging.getLogger(__name__)


class EventType(str, Enum):
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


@dataclass
class ParsedEvent:
    type: EventType = EventType.UNKNOWN
    text: str = ""
    delta: str = ""
    tool_name: str = ""
    tool_status: str = ""
    tool_input: str = ""
    tool_output: str = ""
    tool_error: str = ""
    tool_call_id: str = ""
    tool_title: str = ""
    permission_id: str = ""
    finished: bool = False
    cost: float = 0.0
    created_at: float = 0.0
    tokens: Dict[str, Any] = field(default_factory=dict)
    raw: Dict[str, Any] = field(default_factory=dict)

    def is_terminal(self) -> bool:
        if self.type == EventType.SESSION_IDLE:
            return True
        if self.type == EventType.STEP_FINISH:
            return self.text not in ("tool-calls", "tool_calls")
        return False


def parse_event(event: SSEEvent, session_id: str = "") -> ParsedEvent:
    if logger.isEnabledFor(logging.DEBUG):
        preview = event.data[:500] if event.data else "<empty>"
        logger.debug(
            "[RAW SSE] event=%s id=%s data=%s", event.event, event.id or "-", preview
        )

    if event.event == "__reconnected__":
        parsed = ParsedEvent(
            type=EventType.RECONNECTED,
            text=f"SSE reconnected (attempt {event.data})",
        )
        logger.debug("[PARSED] type=%s text=%s", parsed.type.value, parsed.text)
        return parsed

    data = event.json()
    if not data:
        logger.debug("[PARSED] type=SKIP reason=empty_json")
        return ParsedEvent(type=EventType.SKIP)

    event_type: str = data.get("type", "")

    if event_type in ("server.connected", "server.heartbeat"):
        logger.debug("[PARSED] type=SKIP reason=global_filter event_type=%s", event_type)
        return ParsedEvent(type=EventType.SKIP)

    if session_id and not _matches_session(data, session_id):
        logger.debug("[PARSED] type=SKIP reason=session_mismatch event_type=%s", event_type)
        return ParsedEvent(type=EventType.SKIP)

    # ── Format A: opencode native ─────────────────────────────────
    if event_type == "message.part.updated":
        parsed = _parse_part_updated(data)
        _log_parsed(parsed, event_type)
        return parsed

    if event_type in (
        "message.updated",
        "message.created",
        "session.updated",
        "session.created",
        "session.diff",
    ):
        if event_type in ("message.updated", "message.created"):
            props = data.get("properties", {})
            info = props.get("info", {}) if props else {}
            if not info:
                info = data.get("info", {})
            role = info.get("role", "")
            model_id = info.get("modelID", "")
            provider_id = info.get("providerID", "")
            agent = info.get("agent", "")
            finish = info.get("finish", "")
            cost = info.get("cost", 0)
            if role == "assistant" and (model_id or agent):
                logger.info(
                    "[SSE] %s: role=%s agent=%s provider=%s model=%s finish=%s cost=$%.4f",
                    event_type,
                    role,
                    agent or "?",
                    provider_id or "?",
                    model_id or "?",
                    finish or "-",
                    float(cost or 0),
                )
        else:
            logger.debug("[PARSED] type=SKIP reason=ignored_event event_type=%s", event_type)
        return ParsedEvent(type=EventType.SKIP)

    if event_type == "message.part.delta":
        parsed = _parse_part_delta(data)
        _log_parsed(parsed, event_type)
        return parsed

    if event_type in ("session.idle", "session.status"):
        parsed = _parse_session_status(data, event_type)
        _log_parsed(parsed, event_type)
        return parsed

    if event_type in ("session.permission", "permission", "permission.asked"):
        props = data.get("properties", {})
        perm_id = (
            data.get("id", data.get("permissionID", ""))
            or props.get("id", props.get("permissionID", ""))
        )
        parsed = ParsedEvent(
            type=EventType.PERMISSION,
            permission_id=perm_id,
            raw=data,
        )
        _log_parsed(parsed, event_type)
        return parsed

    # ── Format B: simplified events ───────────────────────────────
    parsed = _parse_simple_event(data, event_type)
    _log_parsed(parsed, event_type)
    return parsed


def _log_parsed(parsed: ParsedEvent, event_type: str) -> None:
    if not logger.isEnabledFor(logging.DEBUG):
        return
    parts = [f"type={parsed.type.value}", f"sse_type={event_type}"]
    if parsed.delta:
        preview = parsed.delta[:80].replace("\n", "\\n")
        parts.append(f"delta={preview!r}")
    if parsed.tool_name:
        parts.append(f"tool={parsed.tool_name}")
    if parsed.tool_status:
        parts.append(f"status={parsed.tool_status}")
    if parsed.finished:
        parts.append("finished=True")
    logger.debug("[PARSED] %s", "  ".join(parts))


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
        call_id = part.get("callID", part.get("id", ""))
        tool_input = ""
        if isinstance(state.get("input"), dict):
            tool_input = json.dumps(state["input"], ensure_ascii=False)
        elif isinstance(state.get("input"), str):
            tool_input = state["input"]

        if tool_name in ("permission", "question", "ask"):
            if status in ("pending", "running"):
                return ParsedEvent(
                    type=EventType.PERMISSION,
                    tool_name=tool_name,
                    tool_status=status,
                    tool_title=title,
                    permission_id=state.get("id", "") or part.get("id", ""),
                    raw=data,
                )

        return ParsedEvent(
            type=EventType.TOOL,
            tool_name=tool_name,
            tool_status=status,
            tool_title=title,
            tool_call_id=call_id,
            tool_input=tool_input,
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
        msg_info = props.get("message", {}) or {}
        model_id = msg_info.get("modelID", "")
        provider_id = msg_info.get("providerID", "")
        agent = msg_info.get("agent", "")
        if model_id or agent:
            logger.info(
                "[SSE] step-start: agent=%s provider=%s model=%s",
                agent or "?",
                provider_id or "?",
                model_id or "?",
            )
        else:
            logger.info("[SSE] step-start")
        return ParsedEvent(type=EventType.STEP_START, raw=data)

    if part_type == "step-finish":
        reason = part.get("reason", "")
        cost = part.get("cost", 0.0) or 0.0
        tokens = part.get("tokens", {}) or {}
        finished = reason not in ("tool-calls", "tool_calls")
        _fmt_tokens = (
            f"in={tokens.get('input', 0)} out={tokens.get('output', 0)} "
            f"cache_r={tokens.get('cache', {}).get('read', 0)} "
            f"cache_w={tokens.get('cache', {}).get('write', 0)}"
        )
        logger.info(
            "[SSE] step-finish: reason=%r terminal=%s cost=$%.4f tokens=[%s]",
            reason,
            finished,
            float(cost),
            _fmt_tokens,
        )
        return ParsedEvent(
            type=EventType.STEP_FINISH,
            text=reason,
            finished=finished,
            cost=float(cost),
            tokens=tokens,
            raw=data,
        )

    if part_type == "retry":
        attempt = part.get("attempt", "?")
        err = part.get("error", {}) or {}
        err_msg = err.get("data", {}).get("message", "") or err.get("message", "") or str(err)
        logger.info("[SSE] retry: attempt=%s error=%s", attempt, err_msg[:120])
        return ParsedEvent(type=EventType.SKIP, raw=data)

    if part_type == "agent":
        agent_name = part.get("name", "?")
        logger.info("[SSE] agent: name=%s", agent_name)
        return ParsedEvent(type=EventType.SKIP, raw=data)

    if part_type == "subtask":
        desc = part.get("description", "")
        agent = part.get("agent", "?")
        logger.info("[SSE] subtask: agent=%s description=%s", agent, desc[:80])
        return ParsedEvent(type=EventType.SKIP, raw=data)

    if part_type == "compaction":
        auto = part.get("auto", False)
        overflow = part.get("overflow", False)
        logger.info("[SSE] compaction: auto=%s overflow=%s", auto, overflow)
        return ParsedEvent(type=EventType.SKIP, raw=data)

    if part_type == "patch":
        files = part.get("files", [])
        logger.info("[SSE] patch: %d file(s) changed: %s", len(files), files[:5])
        return ParsedEvent(type=EventType.SKIP, raw=data)

    if part_type == "snapshot":
        logger.debug("[SSE] snapshot part (skipped)")
        return ParsedEvent(type=EventType.SKIP, raw=data)

    if part_type:
        logger.warning("[SSE] unknown part_type=%r in message.part.updated", part_type)
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
        logger.info(
            "[SSE] session.status: status_type=%r — %s",
            status_type,
            "→ SESSION_IDLE" if status_type == "idle" else "skip (non-idle)",
        )
        if status_type != "idle":
            return ParsedEvent(type=EventType.SKIP)

    elif event_type == "session.idle":
        logger.info("[SSE] session.idle received → SESSION_IDLE")

    return ParsedEvent(
        type=EventType.SESSION_IDLE,
        finished=True,
        raw=data,
    )


def _parse_simple_event(data: Dict[str, Any], event_type: str) -> ParsedEvent:
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


def _matches_session(data: Dict[str, Any], session_id: str) -> bool:
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
