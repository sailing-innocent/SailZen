"""cube.codemaker.sse_parser — SSE 事件统一解析器。

将 CodeMaker (opencode) /event 端点推送的原始 SSEEvent 解码为
结构化的 ParsedEvent。仅支持 opencode-compatible 原生事件格式：

    message.part.updated  → type = text | tool | reasoning | step-start | step-finish
    message.part.delta    → type = text_delta
    session.idle          → type = session_idle   (任务完成)
    session.status        → type = session_idle   (若 status.type == "idle")

会话过滤
--------
/event 是全局端点，会推送 **所有** session 的事件。
传入 session_id 后，parse_event 会自动过滤不属于当前 session
的事件，并将其标记为 EventType.SKIP。

使用示例
--------
::

    async for raw_event in client.stream_events_robust(session_id):
        parsed = parse_event(raw_event, session_id)
        if parsed.type == EventType.TEXT:
            print(parsed.delta, end="", flush=True)
        elif parsed.type == EventType.SESSION_IDLE:
            print("\\n✅ 任务完成")
            break
        elif parsed.type == EventType.SKIP:
            continue
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, Optional

from cube.codemaker.client import SSEEvent

logger = logging.getLogger(__name__)


# ── 事件类型枚举 ──────────────────────────────────────────────────


class EventType(str, Enum):
    """解析后的事件类型。"""

    # 文本输出 (message.part.updated type=text)
    TEXT = "text"
    # 增量文本 (message.part.delta)
    TEXT_DELTA = "text_delta"
    # 推理思考 (message.part.updated type=reasoning)
    REASONING = "reasoning"
    # 工具调用 (message.part.updated type=tool)
    TOOL = "tool"
    # 权限请求 (permission/question 工具 pending/running 状态)
    PERMISSION = "permission"
    # 步骤开始 (message.part.updated type=step-start)
    STEP_START = "step-start"
    # 步骤结束 (message.part.updated type=step-finish)
    STEP_FINISH = "step-finish"
    # 任务完成 (session.idle / session.status type=idle)
    SESSION_IDLE = "session_idle"
    # SSE 重连哨兵事件
    RECONNECTED = "reconnected"
    # 跳过 (心跳 / 其他 session / 无关事件)
    SKIP = "skip"
    # 未知事件
    UNKNOWN = "unknown"


# ── 结构化解析结果 ────────────────────────────────────────────────


@dataclass
class ParsedEvent:
    """SSE 事件的结构化解析结果。

    所有字段均有默认值，调用方只需检查自己关心的字段。
    """

    # 事件类型
    type: EventType = EventType.UNKNOWN

    # 文本内容 (TEXT / TEXT_DELTA / REASONING / STEP_FINISH 的 reason)
    text: str = ""

    # 增量文本 (TEXT 的 delta 字段 / TEXT_DELTA)
    delta: str = ""

    # 工具相关 (TOOL / PERMISSION)
    tool_name: str = ""
    tool_status: str = ""
    tool_input: str = ""
    tool_output: str = ""
    tool_error: str = ""
    tool_call_id: str = ""
    tool_title: str = ""

    # 权限请求 ID (PERMISSION)
    permission_id: str = ""

    # 步骤完成标志
    finished: bool = False

    # 步骤成本 & tokens (STEP_FINISH / SESSION_IDLE)
    cost: float = 0.0
    created_at: float = 0.0
    tokens: Dict[str, Any] = field(default_factory=dict)

    # 原始 JSON 数据（调试用）
    raw: Dict[str, Any] = field(default_factory=dict)

    def is_terminal(self) -> bool:
        """是否是最终完成事件（不应再收到后续内容）。"""
        if self.type == EventType.SESSION_IDLE:
            return True
        if self.type == EventType.STEP_FINISH:
            # tool-calls reason 表示中间步骤，还会继续
            return self.text not in ("tool-calls", "tool_calls")
        return False


# ── 主解析函数 ────────────────────────────────────────────────────


def parse_event(event: SSEEvent, session_id: str = "") -> ParsedEvent:
    """将原始 SSEEvent 解析为 ParsedEvent。

    仅支持 opencode-compatible 原生事件格式。

    Args:
        event:      原始 SSE 事件（来自 CodemakerAsyncClient.stream_events）
        session_id: 当前会话 ID，用于过滤非本 session 的事件。
                    传空字符串则不过滤。

    Returns:
        ParsedEvent，type == EventType.SKIP 时可安全忽略。
    """
    # ── debug: 打印原始 SSE 事件 ──────────────────────────────────
    if logger.isEnabledFor(logging.DEBUG):
        raw_data_preview = event.data[:500] if event.data else "<empty>"
        logger.debug(
            "[RAW SSE] event=%s  id=%s  data=%s",
            event.event,
            event.id or "-",
            raw_data_preview,
        )

    # ── 重连哨兵 ──────────────────────────────────────────────────
    if event.event == "__reconnected__":
        parsed = ParsedEvent(
            type=EventType.RECONNECTED,
            text=f"SSE reconnected (attempt {event.data})",
        )
        logger.debug("[PARSED] type=%s  text=%s", parsed.type.value, parsed.text)
        return parsed

    data = event.json()
    if not data:
        logger.debug("[PARSED] type=SKIP  reason=empty_json")
        return ParsedEvent(type=EventType.SKIP)

    event_type: str = data.get("type", "")

    # ── 全局事件过滤 (心跳 / 服务器连接) ──────────────────────────
    if event_type in ("server.connected", "server.heartbeat"):
        logger.debug("[PARSED] type=SKIP  reason=global_filter  event_type=%s", event_type)
        return ParsedEvent(type=EventType.SKIP)

    # ── Session 过滤: 排除其他 session 的事件 ──────────────────────
    if session_id and not _matches_session(data, session_id):
        logger.debug("[PARSED] type=SKIP  reason=session_mismatch  event_type=%s", event_type)
        return ParsedEvent(type=EventType.SKIP)

    # ── opencode 原生事件 ───────────────────────────────────────────
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
        # message.updated / message.created 携带 providerID/modelID/agent，摘要打 INFO
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
                    event_type, role, agent or "?", provider_id or "?",
                    model_id or "?", finish or "-", float(cost or 0),
                )
        else:
            logger.debug("[PARSED] type=SKIP  reason=ignored_event  event_type=%s", event_type)
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
        perm_id = data.get("id", data.get("permissionID", "")) or props.get("id", props.get("permissionID", ""))
        parsed = ParsedEvent(
            type=EventType.PERMISSION,
            permission_id=perm_id,
            raw=data,
        )
        _log_parsed(parsed, event_type)
        return parsed

    # ── 未知/不支持事件 ───────────────────────────────────────────
    return ParsedEvent(type=EventType.UNKNOWN, raw=data)


# ── 会话匹配 ──────────────────────────────────────────────────────

def _log_parsed(parsed: ParsedEvent, event_type: str) -> None:
    """Debug 日志：打印解析后的事件摘要。"""
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
        call_id = part.get("callID", part.get("id", ""))
        tool_input = ""
        if isinstance(state.get("input"), dict):
            tool_input = json.dumps(state["input"], ensure_ascii=False)
        elif isinstance(state.get("input"), str):
            tool_input = state["input"]

        # permission/question 类工具 pending/running → 权限请求
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
        # step-start 携带当前使用的 model/provider 信息（在 message 的 info 里）
        # 从 properties 中的 message 字段提取（如果有）
        msg_info = props.get("message", {}) or {}
        model_id = msg_info.get("modelID", "")
        provider_id = msg_info.get("providerID", "")
        agent = msg_info.get("agent", "")
        if model_id or agent:
            logger.info(
                "[SSE] step-start: agent=%s provider=%s model=%s",
                agent or "?", provider_id or "?", model_id or "?",
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
            reason, finished, float(cost), _fmt_tokens,
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

    # 未知 part type → 跳过并打 warning 便于发现新事件
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



# ── 会话匹配 ──────────────────────────────────────────────────────


def _matches_session(data: Dict[str, Any], session_id: str) -> bool:
    """检查 SSE 事件是否属于指定 session。

    SSE /event 是全局端点，会推送所有 session 的事件。
    如果事件不携带 sessionID 字段，则放行（可能是全局事件）。
    """
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
