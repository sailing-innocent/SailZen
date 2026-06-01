# -*- coding: utf-8 -*-
# @file __init__.py
# @brief sail.opencode — OpenCode-compatible client infrastructure
# @author sailing-innocent
# @date 2026-05-31
# @version 2.0
# ---------------------------------
"""sail.opencode — OpenCode-compatible async client infrastructure.

Public API
----------
**Client**
    ``OpencodeAsyncClient`` (alias ``OpenCodeAsyncClient``)

**SSE parsing**
    ``parse_event``, ``ParsedEvent``, ``EventType``

**Visualization / callbacks**
    ``SSEPrinter``, ``PrinterCallbacks``

**Process management**
    ``OpenCodeProcessManager``, ``ManagedProcess``, ``ProcessStatus``,
    ``extract_path_from_text``, ``resolve_workspace_path``

**High-level execution (legacy simple)**
    ``SessionRunner``, ``RunResult``, ``run_prompt``

**High-level execution (DI-based)**
    ``run_task``, ``TaskResult``, ``TaskRunConfig``,
    ``SessionRunDependencies``, ``default_dependencies``,
    ``SessionStateMachine``

**Compatibility**
    ``CompatibilityReport``, ``check_cli_compatibility``
"""

from sail.opencode.client import (
    OpencodeAsyncClient,
    OpenCodeAsyncClient,  # backward-compatible alias
    SSEEvent,
    Session,
    Message,
    MessagePart,
    MessagePartType,
    check_health_sync,
    abort_session_sync,
)
from sail.opencode.sse_parser import (
    EventType,
    ParsedEvent,
    parse_event,
)
from sail.opencode.sse_printer import (
    PrinterCallbacks,
    SSEPrinter,
)
from sail.opencode.process_manager import (
    ManagedProcess,
    OpenCodeProcessManager,
    ProcessStatus,
    extract_path_from_text,
    resolve_workspace_path,
)
from sail.opencode.session_runner import (
    RunResult,
    SessionRunner,
    run_prompt,
    run_task,
    TaskResult,
    TaskRunConfig,
    SessionRunDependencies,
    default_dependencies,
    SessionStateMachine,
)
from sail.opencode.compatibility import (
    CompatibilityReport,
    check_cli_compatibility,
)

__all__ = [
    # client
    "OpencodeAsyncClient",
    "OpenCodeAsyncClient",
    "SSEEvent",
    "Session",
    "Message",
    "MessagePart",
    "MessagePartType",
    "check_health_sync",
    "abort_session_sync",
    # sse_parser
    "EventType",
    "ParsedEvent",
    "parse_event",
    # sse_printer
    "PrinterCallbacks",
    "SSEPrinter",
    # process_manager
    "ManagedProcess",
    "OpenCodeProcessManager",
    "ProcessStatus",
    "extract_path_from_text",
    "resolve_workspace_path",
    # session_runner (legacy + DI)
    "RunResult",
    "SessionRunner",
    "run_prompt",
    "run_task",
    "TaskResult",
    "TaskRunConfig",
    "SessionRunDependencies",
    "default_dependencies",
    "SessionStateMachine",
    # compatibility
    "CompatibilityReport",
    "check_cli_compatibility",
]
