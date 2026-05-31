"""cube.codemaker.sse_printer — SSE 事件终端可视化打印器。

从 scripts/debug_pick.py 中的 SSEPrinter/SSEStats 提炼为通用库组件，
可在任何需要展示 CodeMaker 实时进度的地方复用：

- 调试脚本 (scripts/debug_pick.py)
- 任务执行日志
- 批量 PICK 进度监控

特性
----
- 彩色终端输出（ANSI），自动兼容 Windows ANSI 模式
- verbose 模式：展开所有文本 / reasoning
- 非 verbose 模式：进度点号 + 里程碑行
- 自动处理文本流块（末尾换行）
- 可同步写入日志文件（自动去除 ANSI 代码）
- 完整统计摘要（耗时、字符数、工具调用表格、成本）
- 使用 ParsedEvent（cube.codemaker.sse_parser），而非原始 SSEEvent

使用示例
--------
::

    from cube.codemaker import CodemakerAsyncClient, parse_event, SSEPrinter
    from cube.codemaker.sse_parser import EventType

    async with CodemakerAsyncClient(port=4096) as client:
        printer = SSEPrinter(verbose=True, session_id=session_id)
        async for raw in client.stream_events_robust(session_id):
            parsed = parse_event(raw, session_id)
            printer.handle_event(parsed)
            if parsed.is_terminal():
                break
        printer.print_summary()
        printer.close()
"""

from __future__ import annotations

import json
import sys
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

from cube.codemaker.sse_parser import EventType, ParsedEvent


# ── ANSI 颜色 ─────────────────────────────────────────────────────


class AnsiColor:
    """ANSI 颜色代码。

    在 Windows 上调用 ``enable_windows_ansi()`` 以激活 VT 模式。
    """

    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN = "\033[36m"
    WHITE = "\033[37m"
    GRAY = "\033[90m"
    BG_RED = "\033[41m"
    BG_GREEN = "\033[42m"
    BG_YELLOW = "\033[43m"

    @staticmethod
    def strip(text: str) -> str:
        """移除 ANSI 转义码。"""
        import re

        return re.sub(r"\033\[[0-9;]*m", "", text)

    @staticmethod
    def enable_windows_ansi() -> None:
        """在 Windows 上启用 VT100 ANSI 转义支持（Python 3.12+ 已自动启用）。"""
        import sys

        if sys.platform != "win32":
            return
        try:
            import ctypes

            kernel32 = ctypes.windll.kernel32  # type: ignore[attr-defined]
            kernel32.SetConsoleMode(
                kernel32.GetStdHandle(-11), 7
            )  # ENABLE_VIRTUAL_TERMINAL_PROCESSING
        except Exception:
            pass


# 快捷别名（兼容旧代码）
C = AnsiColor


# ── 辅助函数 ──────────────────────────────────────────────────────


def _ts() -> str:
    """当前时间戳字符串 (HH:MM:SS.mmm)。"""
    return datetime.now().strftime("%H:%M:%S.%f")[:-3]


def _truncate(text: str, max_len: int = 80) -> str:
    """截断文本，超出部分用省略号。"""
    if len(text) <= max_len:
        return text
    return text[: max_len - 3] + "..."


def format_tool_table(tool_calls: List[Dict[str, Any]]) -> str:
    """将工具调用列表格式化为可读统计表格。

    Args:
        tool_calls: 工具调用记录列表，每项包含 name / status 字段

    Returns:
        多行格式化字符串
    """
    if not tool_calls:
        return "    (无工具调用)"

    lines = []
    tool_summary: Dict[str, Dict[str, int]] = {}
    for tc in tool_calls:
        name = tc.get("name", "?")
        status = tc.get("status", "?")
        if name not in tool_summary:
            tool_summary[name] = {}
        tool_summary[name][status] = tool_summary[name].get(status, 0) + 1

    lines.append(f"    {'工具名':<30s} {'调用情况'}")
    lines.append(f"    {'─' * 30} {'─' * 30}")
    for name, statuses in tool_summary.items():
        parts = [f"{status}×{cnt}" for status, cnt in statuses.items()]
        lines.append(f"    {name:<30s} {', '.join(parts)}")
    lines.append(f"    {'─' * 30} {'─' * 30}")
    lines.append(
        f"    总计: {len(tool_calls)} 次调用, {len(tool_summary)} 种工具"
    )
    return "\n".join(lines)


# ── SSE 统计累加器 ────────────────────────────────────────────────


class SSEStats:
    """累积 SSE 事件统计，用于摘要报告。"""

    def __init__(self) -> None:
        self.t0 = time.time()
        self.text_chars: int = 0
        self.text_lines: int = 0
        self.reasoning_chars: int = 0
        self.tool_calls: List[Dict[str, Any]] = []
        self.permissions: List[Dict[str, Any]] = []
        self.steps: int = 0
        self.step_finish_reason: str = ""
        self.step_cost: float = 0.0
        self.step_tokens: Dict[str, Any] = {}
        self.reconnects: int = 0
        self.unknown_events: int = 0
        self.event_count: int = 0
        self.last_tool_name: str = ""
        self.last_tool_status: str = ""
        self.errors: List[str] = []

    @property
    def elapsed(self) -> float:
        return time.time() - self.t0

    def elapsed_str(self) -> str:
        e = self.elapsed
        if e < 60:
            return f"{e:.1f}s"
        m, s = divmod(e, 60)
        return f"{int(m)}m{s:.0f}s"


# ── SSE 事件打印器 ────────────────────────────────────────────────


class SSEPrinter:
    """结构化 SSE 事件终端打印器。

    接收 ParsedEvent（来自 sse_parser.parse_event），
    以彩色格式输出到终端，并可选地写入日志文件。

    事件处理策略
    ------------
    - TEXT / TEXT_DELTA : 实时流式输出，带字符计数进度点
    - REASONING         : verbose 模式下展开，否则静默记录
    - TOOL              : 单行状态更新（pending → running → done）
    - PERMISSION        : 高亮警告框
    - STEP_START/FINISH : 里程碑标记行
    - SESSION_IDLE      : 完成标记
    - SKIP              : 静默忽略
    - UNKNOWN           : 折叠为摘要行

    Example::

        printer = SSEPrinter(verbose=True, log_file="debug.log", session_id=sess_id)
        async for raw_event in client.stream_events_robust(session_id):
            parsed = parse_event(raw_event, session_id)
            printer.handle_event(parsed)
            if parsed.is_terminal():
                break
        printer.print_summary(session_id)
        printer.close()
    """

    def __init__(
        self,
        verbose: bool = False,
        log_file: Optional[str] = None,
        session_id: str = "",
    ) -> None:
        self.verbose = verbose
        self.session_id = session_id
        self.stats = SSEStats()
        self.finished = False
        self.finish_reason = ""
        self.accumulated_text = ""
        self._in_text_block = False
        self._log_fh = None

        AnsiColor.enable_windows_ansi()

        if log_file:
            self._log_fh = open(log_file, "a", encoding="utf-8")
            self._log_raw("=" * 60)
            self._log_raw(
                f"SSE session started at {datetime.now().isoformat()}"
            )

    def close(self) -> None:
        """关闭日志文件句柄。"""
        if self._log_fh:
            self._log_fh.close()
            self._log_fh = None

    # ── 内部输出工具 ──────────────────────────────────────────────

    def _log_raw(self, text: str) -> None:
        if self._log_fh:
            self._log_fh.write(AnsiColor.strip(text) + "\n")
            self._log_fh.flush()

    def _end_text_block(self) -> None:
        if self._in_text_block:
            sys.stdout.write("\n")
            sys.stdout.flush()
            self._in_text_block = False

    def _print_line(self, line: str) -> None:
        self._end_text_block()
        print(line)
        self._log_raw(line)

    # ── 主入口 ────────────────────────────────────────────────────

    def handle_event(self, parsed: ParsedEvent) -> None:
        """处理单个已解析的 SSE 事件。"""
        self.stats.event_count += 1
        t = self.stats.elapsed_str()
        etype = parsed.type

        if etype == EventType.SKIP:
            return

        if etype == EventType.RECONNECTED:
            self.stats.reconnects += 1
            self._print_line(
                f"  {C.YELLOW}🔄 [{t}] SSE 重连 #{self.stats.reconnects}{C.RESET}"
            )
            return

        if etype in (EventType.TEXT, EventType.TEXT_DELTA):
            self._handle_text(parsed, t)
            return

        if etype == EventType.REASONING:
            self._handle_reasoning(parsed, t)
            return

        if etype == EventType.TOOL:
            self._handle_tool(parsed, t)
            return

        if etype == EventType.PERMISSION:
            self._handle_permission(parsed, t)
            return

        if etype == EventType.STEP_START:
            self.stats.steps += 1
            self._print_line(
                f"  {C.GRAY}[{t}]{C.RESET} "
                f"{C.BLUE}{C.BOLD}▶ step-start{C.RESET} "
                f"{C.DIM}(step #{self.stats.steps}){C.RESET}"
            )
            return

        if etype == EventType.STEP_FINISH:
            self._handle_step_finish(parsed, t)
            return

        if etype == EventType.SESSION_IDLE:
            if self._in_text_block:
                sys.stdout.write(
                    f" {C.DIM}({self.stats.text_chars}c){C.RESET}\n"
                )
                sys.stdout.flush()
                self._in_text_block = False
            self.finished = True
            self.finish_reason = "session_idle"
            self.stats.step_finish_reason = "session_idle"
            self._print_line(
                f"  {C.GRAY}[{t}]{C.RESET} "
                f"{C.GREEN}{C.BOLD}✅ session idle (任务完成){C.RESET}"
            )
            return

        # UNKNOWN
        self.stats.unknown_events += 1
        preview = json.dumps(parsed.raw, ensure_ascii=False) if parsed.raw else ""
        self._print_line(
            f"  {C.GRAY}[{t}]{C.RESET} "
            f"{C.DIM}📦 {etype}: {_truncate(preview, 100)}{C.RESET}"
        )

    # ── 事件类型处理器 ─────────────────────────────────────────────

    def _handle_text(self, parsed: ParsedEvent, t: str) -> None:
        txt = parsed.delta or parsed.text
        if not txt:
            return

        if parsed.delta:
            self.accumulated_text += parsed.delta
        elif parsed.text and not self.accumulated_text:
            self.accumulated_text = parsed.text

        self.stats.text_chars += len(txt)
        self.stats.text_lines += txt.count("\n")

        if self.verbose:
            if not self._in_text_block:
                sys.stdout.write(
                    f"  {C.GRAY}[{t}]{C.RESET} {C.DIM}📝 text:{C.RESET} "
                )
                self._in_text_block = True
            sys.stdout.write(txt)
            sys.stdout.flush()
        else:
            if not self._in_text_block:
                self._in_text_block = True
                sys.stdout.write(
                    f"  {C.GRAY}[{t}]{C.RESET} {C.DIM}📝 text streaming "
                )
                sys.stdout.flush()
            dots = self.stats.text_chars // 500
            prev_dots = (self.stats.text_chars - len(txt)) // 500
            if dots > prev_dots:
                sys.stdout.write("·")
                sys.stdout.flush()

        self._log_raw(
            f"  [text +{len(txt)}c] total={len(self.accumulated_text)}c"
            + (f" | {txt[:200]}" if self.verbose else "")
        )

    def _handle_reasoning(self, parsed: ParsedEvent, t: str) -> None:
        txt = parsed.text
        if not txt:
            return
        self.stats.reasoning_chars += len(txt)
        if self.verbose:
            if not self._in_text_block:
                sys.stdout.write(
                    f"  {C.GRAY}[{t}]{C.RESET} {C.GRAY}💭 reasoning:{C.RESET} "
                )
                self._in_text_block = True
            sys.stdout.write(f"{C.GRAY}{txt}{C.RESET}")
            sys.stdout.flush()
        self._log_raw(f"  [reasoning +{len(txt)}c] {txt[:200]}")

    def _handle_tool(self, parsed: ParsedEvent, t: str) -> None:
        tool_name = parsed.tool_name
        status = parsed.tool_status
        title = parsed.tool_title or tool_name
        error = parsed.raw.get("state", {}).get("error", "") if parsed.raw else ""

        self.stats.tool_calls.append(
            {"name": tool_name, "status": status, "time": t, "error": error}
        )
        self.stats.last_tool_name = tool_name
        self.stats.last_tool_status = status

        if status == "pending":
            icon, color = "⏳", C.GRAY
        elif status == "running":
            icon, color = "⚙️ ", C.CYAN
        elif status in ("completed", "done"):
            icon, color = "✅", C.GREEN
        elif status in ("error", "failed"):
            icon, color = "❌", C.RED
            if error:
                self.stats.errors.append(f"{tool_name}: {error}")
        else:
            icon, color = "🔧", C.WHITE

        line = (
            f"  {C.GRAY}[{t}]{C.RESET} "
            f"{icon} {color}{title}{C.RESET}"
            f" → {color}{status}{C.RESET}"
        )
        if error:
            line += f"  {C.RED}err: {_truncate(error, 60)}{C.RESET}"
        self._print_line(line)

    def _handle_permission(self, parsed: ParsedEvent, t: str) -> None:
        perm_id = parsed.permission_id
        self.stats.permissions.append(
            {"id": perm_id, "time": t, "data": parsed.raw}
        )
        self._print_line(
            f"  {C.GRAY}[{t}]{C.RESET} "
            f"{C.BG_YELLOW}{C.BOLD} 🔒 PERMISSION REQUEST {C.RESET} "
            f"id={C.YELLOW}{perm_id[:20] if perm_id else 'N/A'}{C.RESET}"
        )
        desc = (parsed.raw or {}).get(
            "description", (parsed.raw or {}).get("message", "")
        )
        if desc:
            self._print_line(
                f"         {C.YELLOW}→ {_truncate(desc, 120)}{C.RESET}"
            )

    def _handle_step_finish(self, parsed: ParsedEvent, t: str) -> None:
        reason = parsed.text
        cost = parsed.cost
        tokens = parsed.tokens
        is_terminal = parsed.is_terminal()

        if is_terminal and self._in_text_block:
            sys.stdout.write(f" {C.DIM}({self.stats.text_chars}c){C.RESET}\n")
            sys.stdout.flush()
            self._in_text_block = False

        if is_terminal:
            self.finished = True
            self.finish_reason = reason or "step-finish"
            self.stats.step_finish_reason = reason

        self.stats.step_cost += cost
        if tokens:
            self.stats.step_tokens = tokens

        token_info = ""
        if tokens:
            inp = tokens.get("input", tokens.get("prompt_tokens", 0))
            out = tokens.get("output", tokens.get("completion_tokens", 0))
            token_info = f", tokens: {inp}→{out}"

        if is_terminal:
            self._print_line(
                f"  {C.GRAY}[{t}]{C.RESET} "
                f"{C.GREEN}{C.BOLD}✅ step-finish{C.RESET} "
                f"{C.DIM}(reason={reason}, cost=${cost:.4f}{token_info}){C.RESET}"
            )
        else:
            self._print_line(
                f"  {C.GRAY}[{t}]{C.RESET} "
                f"{C.YELLOW}🔄 step-finish{C.RESET} "
                f"{C.DIM}(reason={reason} → 等待工具执行{token_info}){C.RESET}"
            )

    # ── 摘要打印 ──────────────────────────────────────────────────

    def print_summary(self, session_id: str = "") -> None:
        """打印 SSE 流的最终统计摘要。"""
        s = self.stats
        elapsed = s.elapsed_str()

        print()
        print(f"  {C.BOLD}{'═' * 56}{C.RESET}")
        print(f"  {C.BOLD}  📊 SSE 流统计摘要{C.RESET}")
        print(f"  {C.BOLD}{'═' * 56}{C.RESET}")

        sid = session_id or self.session_id
        if sid:
            print(f"    Session:      {sid[:24]}...")

        print(f"    总耗时:       {elapsed}")
        print(f"    事件总数:     {s.event_count}")
        print()

        print(f"  {C.CYAN}  📝 文本输出{C.RESET}")
        print(f"    字符数:       {s.text_chars:,}")
        print(f"    行数:         {s.text_lines:,}")
        if s.reasoning_chars:
            print(f"    推理字符:     {s.reasoning_chars:,}")

        if self.accumulated_text.strip():
            preview = self.accumulated_text.strip()
            if len(preview) > 500:
                preview = (
                    preview[:500] + f"... ({len(self.accumulated_text)}c total)"
                )
            print(f"    {'─' * 40}")
            for line in preview.split("\n"):
                print(f"    {C.DIM}{line}{C.RESET}")
            print(f"    {'─' * 40}")
        print()

        print(f"  {C.CYAN}  🔧 工具调用{C.RESET}")
        print(format_tool_table(s.tool_calls))
        print()

        if s.permissions:
            print(f"  {C.YELLOW}  🔒 权限请求: {len(s.permissions)} 次{C.RESET}")
            for p in s.permissions:
                print(
                    f"    [{p['time']}] id={p['id'][:20] if p['id'] else 'N/A'}"
                )
            print()

        if s.errors:
            print(f"  {C.RED}  ❌ 错误: {len(s.errors)} 个{C.RESET}")
            for err in s.errors[-5:]:
                print(f"    {C.RED}• {_truncate(err, 100)}{C.RESET}")
            print()

        if s.step_finish_reason:
            print(f"  {C.GREEN}  ✅ 完成{C.RESET}")
            print(f"    原因:         {s.step_finish_reason}")
            if s.step_cost:
                print(f"    成本:         ${s.step_cost:.4f}")
            if s.step_tokens:
                print(f"    Tokens:       {json.dumps(s.step_tokens)}")
            print()

        if s.reconnects:
            print(f"    SSE 重连:     {s.reconnects} 次")
        if s.unknown_events:
            print(f"    未知事件:     {s.unknown_events}")

        print(f"  {C.BOLD}{'═' * 56}{C.RESET}")
        print()

        self._log_raw(f"\n{'=' * 56}")
        self._log_raw(
            f"SSE Summary: elapsed={elapsed}, events={s.event_count}, "
            f"text={s.text_chars}c, tools={len(s.tool_calls)}, "
            f"permissions={len(s.permissions)}, errors={len(s.errors)}"
        )
