# -*- coding: utf-8 -*-
# @file sse_printer.py
# @brief SSE event terminal visualizer + external callback adapter
# @author sailing-innocent
# @date 2026-05-31
# @version 2.0
# ---------------------------------
"""sail.opencode.sse_printer — Structured SSE event printer.

Compatible with any opencode-compatible server."""

from __future__ import annotations

import json
import re
import sys
import time
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

from dataclasses import dataclass
from sail.opencode.sse_parser import EventType, ParsedEvent


# ── Callback interface ────────────────────────────────────────────


@dataclass
class PrinterCallbacks:
    on_tool: Optional[Callable[..., None]] = None
    on_text: Optional[Callable[..., None]] = None
    on_finish: Optional[Callable[..., None]] = None
    on_permission: Optional[Callable[..., None]] = None


# ── ANSI colors ───────────────────────────────────────────────────


class AnsiColor:
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
        return re.sub(r"\033\[[0-9;]*m", "", text)

    @staticmethod
    def enable_windows_ansi() -> None:
        if sys.platform != "win32":
            return
        try:
            import ctypes

            kernel32 = ctypes.windll.kernel32  # type: ignore[attr-defined]
            kernel32.SetConsoleMode(kernel32.GetStdHandle(-11), 7)
        except Exception:
            pass


C = AnsiColor


# ── Helpers ───────────────────────────────────────────────────────


def _ts() -> str:
    return datetime.now().strftime("%H:%M:%S.%f")[:-3]


def _truncate(text: str, max_len: int = 80) -> str:
    if len(text) <= max_len:
        return text
    return text[: max_len - 3] + "..."


def format_tool_table(tool_calls: List[Dict[str, Any]]) -> str:
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


# ── Stats ─────────────────────────────────────────────────────────


class SSEStats:
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


# ── Printer ───────────────────────────────────────────────────────


class SSEPrinter:
    def __init__(
        self,
        verbose: bool = False,
        log_file: Optional[str] = None,
        session_id: str = "",
        callbacks: Optional[PrinterCallbacks] = None,
        on_tool: Optional[Callable[..., None]] = None,
        on_text: Optional[Callable[..., None]] = None,
        on_finish: Optional[Callable[..., None]] = None,
        on_permission: Optional[Callable[..., None]] = None,
    ) -> None:
        self.verbose = verbose
        self.session_id = session_id
        self.stats = SSEStats()
        self.finished = False
        self.finish_reason = ""
        self.accumulated_text = ""
        self._in_text_block = False
        self._log_fh = None

        cb = callbacks or PrinterCallbacks()
        self._on_tool = cb.on_tool or on_tool
        self._on_text = cb.on_text or on_text
        self._on_finish = cb.on_finish or on_finish
        self._on_permission = cb.on_permission or on_permission

        AnsiColor.enable_windows_ansi()

        if log_file:
            self._log_fh = open(log_file, "a", encoding="utf-8")
            self._log_raw("=" * 60)
            self._log_raw(f"SSE session started at {datetime.now().isoformat()}")

    def close(self) -> None:
        if self._log_fh:
            self._log_fh.close()
            self._log_fh = None

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

    def handle_event(self, parsed: ParsedEvent) -> None:
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

        if self._on_text:
            try:
                self._on_text(txt, self.stats.text_chars)
            except Exception:
                pass

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

        if self._on_tool:
            try:
                self._on_tool(tool_name, status, title)
            except Exception:
                pass

    def _handle_permission(self, parsed: ParsedEvent, t: str) -> None:
        perm_id = parsed.permission_id
        self.stats.permissions.append({"id": perm_id, "time": t, "data": parsed.raw})
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
        if self._on_permission:
            try:
                self._on_permission(perm_id, parsed.raw)
            except Exception:
                pass

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
            if self._on_finish:
                try:
                    self._on_finish(reason, self.stats.step_cost, self.stats.step_tokens)
                except Exception:
                    pass
        else:
            self._print_line(
                f"  {C.GRAY}[{t}]{C.RESET} "
                f"{C.YELLOW}🔄 step-finish{C.RESET} "
                f"{C.DIM}(reason={reason} → 等待工具执行{token_info}){C.RESET}"
            )

    def print_summary(self, session_id: str = "") -> None:
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
                preview = preview[:500] + f"... ({len(self.accumulated_text)}c total)"
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

    def get_summary_text(self) -> str:
        s = self.stats
        lines = [
            f"📊 任务摘要 ({s.elapsed_str()})",
            f"  文本: {s.text_chars:,} 字符, {s.text_lines:,} 行",
            f"  工具: {len(s.tool_calls)} 次调用",
        ]
        if s.step_cost:
            lines.append(f"  成本: ${s.step_cost:.4f}")
        if s.errors:
            lines.append(f"  错误: {len(s.errors)} 个")
        if s.step_finish_reason:
            lines.append(f"  完成: {s.step_finish_reason}")
        return "\n".join(lines)
