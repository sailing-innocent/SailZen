# -*- coding: utf-8 -*-
# @file session_dependencies.py
# @brief Dependency interfaces and default implementations for session runs.
# @author sailing-innocent
# @date 2026-05-31
# @version 1.0
# ---------------------------------

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Awaitable, Callable, Optional, Protocol, Union

from sail.opencode.client import OpencodeAsyncClient
from sail.opencode.sse_parser import ParsedEvent

logger = logging.getLogger(__name__)


class ProgressSink(Protocol):
    def __call__(self, message: str) -> None:
        ...


class EventSink(Protocol):
    def __call__(self, event: ParsedEvent) -> None:
        ...


class AgentResolver(Protocol):
    async def resolve(
        self,
        client: OpencodeAsyncClient,
        preferred: Optional[str],
        label: str,
    ) -> Optional[str]:
        ...


class PermissionResponder(Protocol):
    async def approve(
        self,
        client: OpencodeAsyncClient,
        session_id: str,
        permission_id: str,
        label: str,
    ) -> bool:
        ...


CompletionPredicate = Callable[[], Union[bool, Awaitable[bool]]]
ForegroundFinishPredicate = Callable[[], Union[bool, Awaitable[bool]]]


@dataclass
class SessionRunDependencies:
    """Injectable services used by the session state machine."""

    agent_resolver: AgentResolver
    permission_responder: PermissionResponder
    on_event: Optional[Callable[[ParsedEvent], None]] = None
    on_progress: Optional[Callable[[str], None]] = None
    is_complete: Optional[CompletionPredicate] = None
    can_finish_foreground: Optional[ForegroundFinishPredicate] = None


class DefaultAgentResolver:
    """Resolve requested agent name against server agent list."""

    async def resolve(
        self,
        client: OpencodeAsyncClient,
        preferred: Optional[str],
        label: str,
    ) -> Optional[str]:
        if not preferred:
            return None
        try:
            agents = await client.list_agents()
        except Exception as exc:
            logger.warning("[%s] list_agents 失败: %s", label, exc)
            return None

        names = [ag.get("name", "") or ag.get("id", "") for ag in agents]
        for name in names:
            if name == preferred:
                logger.info("[%s] 找到 agent: %s", label, name)
                return name
        for name in names:
            if preferred.lower() in name.lower():
                logger.info("[%s] 找到相似 agent: %s", label, name)
                return name

        logger.warning(
            "[%s] 未找到 agent %r，可用: %s，使用默认",
            label,
            preferred,
            names[:5],
        )
        return None


class DefaultPermissionResponder:
    """Approve explicit permission requests automatically."""

    async def approve(
        self,
        client: OpencodeAsyncClient,
        session_id: str,
        permission_id: str,
        label: str,
    ) -> bool:
        if not permission_id:
            logger.warning(
                "[%s] 收到权限事件但缺少 permission_id，跳过自动批准", label
            )
            return False
        try:
            ok = await client.respond_permission(
                session_id,
                permission_id,
                response="always",
            )
            logger.info(
                "[%s] 批准权限 %s -> %s",
                label,
                permission_id[:16],
                "ok" if ok else "failed",
            )
            return ok
        except Exception as exc:
            logger.warning("[%s] 权限 API 失败: %s", label, exc)
            return False


def default_dependencies(
    on_event: Optional[Callable[[ParsedEvent], None]] = None,
    on_progress: Optional[Callable[[str], None]] = None,
) -> SessionRunDependencies:
    return SessionRunDependencies(
        agent_resolver=DefaultAgentResolver(),
        permission_responder=DefaultPermissionResponder(),
        on_event=on_event,
        on_progress=on_progress,
    )
