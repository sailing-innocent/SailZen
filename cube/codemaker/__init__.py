"""cube.codemaker — CubeClaw 的 LLM 智能基础设施。

这是整个项目与 CodeMaker (opencode fork) 交互的统一入口。

模块结构
--------
cube/codemaker/
├── __init__.py          本文件 — 公共 API 聚合 + 快速上手示例
├── client.py            HTTP / SSE 异步客户端 + 同步辅助函数
├── sse_parser.py        SSE 事件解析器 (格式A/B 统一解码)
├── sse_printer.py       终端可视化打印器 + 统计器
├── process_manager.py   codemaker serve 进程生命周期管理
├── session_models.py    任务配置与结果数据类
├── session_dependencies.py  可注入依赖默认实现
├── session_handlers.py  SSE 消息处理器
├── session_state_machine.py  session 交互状态机
└── session_runner.py    高层任务入口

核心数据流
----------
  用户请求
    → process_manager.CodemakerProcessManager.ensure_running()   # 确保进程在跑
    → client.CodemakerAsyncClient.create_session()               # 建立会话
    → session_runner.run_task()                                   # 发送 prompt
    → client.CodemakerAsyncClient.stream_events_robust()         # 监听 SSE
    → sse_parser.parse_event()                                    # 解析事件
    → sse_printer.SSEPrinter.handle_event()  (可选, 调试时)       # 可视化
    → 回调 / 返回最终文本

快速示例
--------
::

    import asyncio
    from cube.codemaker import run_task, ensure_running

    async def main():
        # 1. 确保 codemaker serve 在本地运行
        mgr, session, msg = await ensure_running("/path/to/workspace")
        print(msg)  # "已在端口 4096 运行"

        # 2. 执行任务，等待完成
        result = await run_task(
            port=session.port,
            prompt="写一个 Python hello world",
        )
        print(result.text)

    asyncio.run(main())

导出摘要
--------
客户端:
    CodemakerAsyncClient     异步 HTTP + SSE 客户端
    check_health_sync        同步健康检查（进程管理用）
    abort_session_sync       同步中止 session
    SSEEvent                 SSE 事件数据类

SSE 解析:
    parse_event              解析单个 SSE 事件 → ParsedEvent
    ParsedEvent              结构化 SSE 事件结果
    EventType                事件类型枚举

SSE 可视化:
    SSEPrinter               终端彩色打印器
    SSEStats                 统计累加器

进程管理:
    CodemakerProcessManager  进程生命周期管理
    ManagedProcess           进程状态数据类
    ProcessStatus            进程状态枚举

任务运行:
    run_task                 高层任务执行协程
    TaskResult               任务结果数据类
"""

from cube.codemaker.client import (
    CodemakerAsyncClient,
    check_health_sync,
    abort_session_sync,
    SSEEvent,
    Session,
    Message,
    MessagePart,
    MessagePartType,
)
from cube.codemaker.sse_parser import (
    parse_event,
    ParsedEvent,
    EventType,
)
from cube.codemaker.sse_printer import (
    SSEPrinter,
    SSEStats,
    AnsiColor,
    format_tool_table,
)
from cube.codemaker.process_manager import (
    CodemakerProcessManager,
    ManagedProcess,
    ProcessStatus,
)
from cube.codemaker.session_runner import (
    run_task,
    TaskResult,
    TaskRunConfig,
)

__all__ = [
    # client
    "CodemakerAsyncClient",
    "check_health_sync",
    "abort_session_sync",
    "SSEEvent",
    "Session",
    "Message",
    "MessagePart",
    "MessagePartType",
    # sse_parser
    "parse_event",
    "ParsedEvent",
    "EventType",
    # sse_printer
    "SSEPrinter",
    "SSEStats",
    "AnsiColor",
    "format_tool_table",
    # process_manager
    "CodemakerProcessManager",
    "ManagedProcess",
    "ProcessStatus",
    # session_runner
    "run_task",
    "TaskResult",
    "TaskRunConfig",
]
