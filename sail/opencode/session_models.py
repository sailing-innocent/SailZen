# -*- coding: utf-8 -*-
# @file session_models.py
# @brief Task config and result data classes for DI-based session runs.
# @author sailing-innocent
# @date 2026-05-31
# @version 1.0
# ---------------------------------

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


DEFAULT_SSE_TIMEOUT = 14400.0
DEFAULT_MAX_RECONNECTS = 5
DEFAULT_AGENT_NAME = "Sisyphus"
PROGRESS_THROTTLE_SEC = 5.0


@dataclass
class TaskRunConfig:
    """Configuration for one opencode task run."""

    host: str = "127.0.0.1"
    port: int = 4096

    agent: Optional[str] = DEFAULT_AGENT_NAME
    model: Optional[str] = None

    session_id: Optional[str] = None
    session_title: str = ""

    sse_timeout: float = DEFAULT_SSE_TIMEOUT
    max_reconnects: int = DEFAULT_MAX_RECONNECTS

    auto_approve_permissions: bool = True
    auto_discover_agent: bool = True
    poll_fallback: bool = True
    finish_on_session_idle: bool = True
    finish_on_terminal_step: bool = True
    delayed_finish_heartbeat_sec: float = 300.0
    delayed_finish_max_heartbeats: int = 3
    delayed_finish_heartbeat_prompt: str = (
        "请继续推进当前任务，检查后台任务结果并在完成后写入最终 session_result.json。"
    )


@dataclass
class TaskResult:
    """Result returned by ``run_task``."""

    success: bool
    text: str = ""
    session_id: str = ""
    agent_used: Optional[str] = None
    tool_calls: List[Dict[str, Any]] = field(default_factory=list)
    permissions_granted: int = 0
    steps: int = 0
    elapsed_sec: float = 0.0
    cost: float = 0.0
    tokens: Dict[str, Any] = field(default_factory=dict)
    finish_reason: str = ""
    error: Optional[str] = None

    @classmethod
    def fail(
        cls,
        error: str,
        session_id: str = "",
        elapsed_sec: float = 0.0,
    ) -> "TaskResult":
        return cls(
            success=False,
            error=error,
            session_id=session_id,
            elapsed_sec=elapsed_sec,
        )
