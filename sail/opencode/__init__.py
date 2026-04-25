# -*- coding: utf-8 -*-
# @file __init__.py
# @brief sail.opencode — OpenCode/CodeMaker 基础设施层
# @author sailing-innocent
# @date 2026-04-25
# @version 1.0
# ---------------------------------
"""sail.opencode — OpenCode/CodeMaker 异步客户端基础设施包。

这是一个纯基础设施层，不依赖 sail_bot 的任何组件。
上层（如 sail_bot）通过导入本包来与 opencode serve 交互。

公共 API:
    # 底层客户端
    from sail.opencode import OpenCodeAsyncClient, SSEEvent, Session

    # SSE 解析
    from sail.opencode import parse_event, ParsedEvent, EventType

    # 可视化 / 回调
    from sail.opencode import SSEPrinter, PrinterCallbacks

    # 进程管理
    from sail.opencode import OpenCodeProcessManager, ManagedProcess, ProcessStatus

    # 高层级执行
    from sail.opencode import SessionRunner, RunResult, run_prompt
"""

from sail.opencode.client import (
    OpenCodeAsyncClient,
    SSEEvent,
    Session,
    check_health_sync,
)
from sail.opencode.sse_parser import (
    EventType,
    MessagePart,
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
)
from sail.opencode.session_runner import (
    RunResult,
    SessionRunner,
    run_prompt,
)

__all__ = [
    # client
    "OpenCodeAsyncClient",
    "SSEEvent",
    "Session",
    "check_health_sync",
    # sse_parser
    "EventType",
    "MessagePart",
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
    # session_runner
    "RunResult",
    "SessionRunner",
    "run_prompt",
]
