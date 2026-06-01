# -*- coding: utf-8 -*-
# @file session_handlers.py
# @brief Event handlers for the session state machine.
# @author sailing-innocent
# @date 2026-05-31
# @version 1.0
# ---------------------------------

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List

from sail.opencode.client import OpencodeAsyncClient
from sail.opencode.session_dependencies import SessionRunDependencies
from sail.opencode.session_models import PROGRESS_THROTTLE_SEC, TaskRunConfig
from sail.opencode.sse_parser import EventType, ParsedEvent

logger = logging.getLogger(__name__)


@dataclass
class SessionAccumulator:
    text: str = ""
    tool_calls: List[Dict[str, Any]] = field(default_factory=list)
    permissions_granted: int = 0
    steps: int = 0
    cost: float = 0.0
    tokens: Dict[str, Any] = field(default_factory=dict)
    finish_reason: str = ""
    last_progress_push: float = 0.0

    def push_progress(self, deps: SessionRunDependencies, message: str) -> None:
        if not deps.on_progress:
            return
        now = time.time()
        if now - self.last_progress_push < PROGRESS_THROTTLE_SEC:
            return
        self.last_progress_push = now
        try:
            deps.on_progress(message)
        except Exception:
            logger.debug("progress callback failed", exc_info=True)


class EventHandler:
    async def handle(
        self,
        event: ParsedEvent,
        state: SessionAccumulator,
        machine: "SessionStateMachineProtocol",
    ) -> bool:
        raise NotImplementedError


class SessionStateMachineProtocol:
    client: OpencodeAsyncClient
    session_id: str
    cfg: TaskRunConfig
    deps: SessionRunDependencies
    label: str
    started_at: float


class TextHandler(EventHandler):
    async def handle(
        self,
        event: ParsedEvent,
        state: SessionAccumulator,
        machine: SessionStateMachineProtocol,
    ) -> bool:
        delta = event.delta or event.text
        if delta:
            state.text += delta
            state.push_progress(machine.deps, f"输出文本 ({len(state.text)}c)")
        return False


class ToolHandler(EventHandler):
    async def handle(
        self,
        event: ParsedEvent,
        state: SessionAccumulator,
        machine: SessionStateMachineProtocol,
    ) -> bool:
        state.tool_calls.append({
            "name": event.tool_name,
            "status": event.tool_status,
            "title": event.tool_title,
            "time": time.time() - machine.started_at,
        })
        title = event.tool_title or event.tool_name
        if title:
            state.push_progress(machine.deps, f"工具: {title}")
        logger.debug(
            "[%s] 工具: %s -> %s",
            machine.label,
            event.tool_name,
            event.tool_status,
        )
        return False


class ReasoningHandler(EventHandler):
    async def handle(
        self,
        event: ParsedEvent,
        state: SessionAccumulator,
        machine: SessionStateMachineProtocol,
    ) -> bool:
        if event.text:
            state.push_progress(machine.deps, f"思考: {event.text[:60]}")
        return False


class PermissionHandler(EventHandler):
    async def handle(
        self,
        event: ParsedEvent,
        state: SessionAccumulator,
        machine: SessionStateMachineProtocol,
    ) -> bool:
        if not machine.cfg.auto_approve_permissions:
            return False
        state.permissions_granted += 1
        asyncio.create_task(
            machine.deps.permission_responder.approve(
                machine.client,
                machine.session_id,
                event.permission_id,
                machine.label,
            )
        )
        return False


class StepStartHandler(EventHandler):
    async def handle(
        self,
        event: ParsedEvent,
        state: SessionAccumulator,
        machine: SessionStateMachineProtocol,
    ) -> bool:
        state.steps += 1
        state.push_progress(machine.deps, f"step #{state.steps}")
        return False


class StepFinishHandler(EventHandler):
    async def handle(
        self,
        event: ParsedEvent,
        state: SessionAccumulator,
        machine: SessionStateMachineProtocol,
    ) -> bool:
        state.cost += event.cost
        if event.tokens:
            state.tokens = event.tokens
        if event.is_terminal():
            state.finish_reason = event.text or "step-finish"
            logger.info(
                "[%s] terminal step-finish observed reason=%s cost=%.4f",
                machine.label,
                state.finish_reason,
                state.cost,
            )
            return bool(getattr(machine.cfg, "finish_on_terminal_step", True))
        return False


class SessionIdleHandler(EventHandler):
    async def handle(
        self,
        event: ParsedEvent,
        state: SessionAccumulator,
        machine: SessionStateMachineProtocol,
    ) -> bool:
        state.finish_reason = "session_idle"
        logger.info("[%s] session idle observed", machine.label)
        return bool(getattr(machine.cfg, "finish_on_session_idle", True))


DEFAULT_EVENT_HANDLERS: Dict[EventType, EventHandler] = {
    EventType.TEXT: TextHandler(),
    EventType.TEXT_DELTA: TextHandler(),
    EventType.TOOL: ToolHandler(),
    EventType.REASONING: ReasoningHandler(),
    EventType.PERMISSION: PermissionHandler(),
    EventType.STEP_START: StepStartHandler(),
    EventType.STEP_FINISH: StepFinishHandler(),
    EventType.SESSION_IDLE: SessionIdleHandler(),
}
