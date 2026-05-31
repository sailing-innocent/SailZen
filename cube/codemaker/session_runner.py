"""High-level codemaker task entry point.

``run_task`` is intentionally thin. Session lifecycle, prompt sending,
stream processing, permission approval, and fallbacks live in injected
services plus ``SessionStateMachine``.
"""

from __future__ import annotations

from typing import Callable, Optional

from cube.codemaker.client import CodemakerAsyncClient
from cube.codemaker.session_dependencies import (
    SessionRunDependencies,
    default_dependencies,
)
from cube.codemaker.session_models import (
    DEFAULT_AGENT_NAME,
    DEFAULT_MAX_RECONNECTS,
    DEFAULT_SSE_TIMEOUT,
    TaskResult,
    TaskRunConfig,
)
from cube.codemaker.session_state_machine import SessionStateMachine
from cube.codemaker.sse_parser import ParsedEvent


async def run_task(
    prompt: str,
    port: int = 4096,
    host: str = "127.0.0.1",
    config: Optional[TaskRunConfig] = None,
    on_event: Optional[Callable[[ParsedEvent], None]] = None,
    on_progress: Optional[Callable[[str], None]] = None,
    label: str = "task",
    dependencies: Optional[SessionRunDependencies] = None,
) -> TaskResult:
    """Run one codemaker prompt and wait for completion.

    Args:
        prompt: Prompt text sent to codemaker.
        port: Codemaker service port when ``config`` is not provided.
        host: Codemaker service host when ``config`` is not provided.
        config: Optional run config. Defaults keep previous public behavior.
        on_event: Optional parsed SSE observer.
        on_progress: Optional throttled progress callback.
        label: Log label for this run.
        dependencies: Optional injected handlers/services.

    Returns:
        ``TaskResult`` with final text, stats, and failure info.
    """
    cfg = config or TaskRunConfig(host=host, port=port)
    if config is None:
        cfg.host = host
        cfg.port = port

    deps = dependencies or default_dependencies(
        on_event=on_event,
        on_progress=on_progress,
    )
    if dependencies is not None:
        if on_event is not None:
            deps.on_event = on_event
        if on_progress is not None:
            deps.on_progress = on_progress

    async with CodemakerAsyncClient(host=cfg.host, port=cfg.port) as client:
        machine = SessionStateMachine(
            client=client,
            prompt=prompt,
            cfg=cfg,
            deps=deps,
            label=label,
        )
        return await machine.run()


__all__ = [
    "DEFAULT_AGENT_NAME",
    "DEFAULT_MAX_RECONNECTS",
    "DEFAULT_SSE_TIMEOUT",
    "SessionRunDependencies",
    "SessionStateMachine",
    "TaskResult",
    "TaskRunConfig",
    "default_dependencies",
    "run_task",
]
