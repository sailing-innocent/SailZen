# -*- coding: utf-8 -*-
# @file task_handler.py
# @brief Task execution handler (v2.0 - uses sail.opencode)
# @author sailing-innocent
# @date 2026-04-25
# @version 2.0
# ---------------------------------
"""Task execution handler for sending tasks to Agent runtime.

v2.0: 使用 sail.opencode.SessionRunner 替代旧的 async_task_manager。
整个执行流程:
1. 确认工作区进程已运行 (process_mgr)
2. 获取/创建 agent session
3. 通过 SessionRunner 发送 prompt 并监听 SSE 流
4. 实时更新飞书卡片进度
5. 完成后展示结果（支持长输出分页）
"""

import asyncio
import logging
import time
import threading
from pathlib import Path
from typing import Optional

from sail_bot.handlers.base import BaseHandler, HandlerContext

from sail_bot.context import ConversationContext
from feishu_card_kit.renderer import CardRenderer
from sail_bot.task_logger import task_logger
from sail_bot.long_output_handler import LongOutputHandler

from sail.opencode import (
    SessionRunner,
    PrinterCallbacks,
    RunResult,
    extract_path_from_text,
)
from sail.opencode.sse_parser import EventType, ParsedEvent

logger = logging.getLogger(__name__)


class TaskHandler(BaseHandler):
    """Handler for executing tasks in OpenCode."""

    def handle(
        self,
        chat_id: str,
        message_id: str,
        ctx: ConversationContext,
        task_text: str,
        path: Optional[str] = None,
    ) -> None:
        """Execute a task in the specified workspace.

        Args:
            chat_id: Target chat ID
            message_id: Message to reply to
            ctx: Conversation context
            task_text: The task description
            path: Workspace path (optional, will auto-detect if not provided)
        """
        # Resolve workspace path
        if not path:
            running = [
                p for p in self.ctx.process_mgr.list_processes()
                if p.status.value == "running"
            ]
            if not running:
                card = CardRenderer.error(
                    "未找到会话",
                    "没有正在运行的 Agent 会话。\n请先启动一个，例如：启动 sailzen",
                )
                self.ctx.messaging.reply_card(message_id, card)
                return

            if len(running) == 1:
                path = running[0].path
            elif ctx.active_workspace:
                path = ctx.active_workspace
            else:
                names = [Path(p.path).name for p in running]
                self.ctx.messaging.reply_text(
                    message_id,
                    "有多个会话运行中：" + ", ".join(names) + "\n请指定工作区",
                )
                return

        # Start operation tracking
        op_id = self.ctx.op_tracker.start(path, task_text[:60], timeout=14400.0)  # 4 hours

        # Create progress card
        progress_card = CardRenderer.progress(
            title="🚀 任务已提交",
            description=f"正在初始化...\n\n**任务:** {task_text[:100]}{'...' if len(task_text) > 100 else ''}",
            show_cancel_button=True,
            cancel_action_data={"action": "cancel_task", "task_id": op_id},
        )
        prog_mid = self.ctx.messaging.reply_card(
            message_id, progress_card, "progress", {"op_id": op_id, "path": path}
        )

        # Launch async execution in a background thread
        def do_async_task() -> None:
            loop = asyncio.new_event_loop()
            try:
                loop.run_until_complete(
                    self._execute_task(chat_id, ctx, task_text, path, op_id, prog_mid)
                )
            except Exception as exc:
                logger.error("[TaskHandler] Async execution error: %s", exc, exc_info=True)
                self.ctx.op_tracker.finish(op_id)
                err_card = CardRenderer.error("执行异常", str(exc), context_path=path)
                if prog_mid:
                    self.ctx.messaging.update_card(prog_mid, err_card)
            finally:
                loop.close()

        threading.Thread(target=do_async_task, daemon=True).start()

    async def _execute_task(
        self,
        chat_id: str,
        ctx: ConversationContext,
        task_text: str,
        path: str,
        op_id: str,
        prog_mid: Optional[str],
    ) -> None:
        """Core async task execution."""

        # 1) Ensure workspace process is running
        ok, proc, start_msg = await self.ctx.process_mgr.ensure_running_async(path, chat_id)
        if not ok:
            self.ctx.op_tracker.finish(op_id)
            err_card = CardRenderer.error("启动失败", start_msg, context_path=path)
            if prog_mid:
                self.ctx.messaging.update_card(prog_mid, err_card)
            return

        ctx.mode = "coding"
        ctx.active_workspace = proc.path
        ctx.clear_pending()
        self.ctx.save_contexts()

        if not task_text:
            self.ctx.op_tracker.finish(op_id)
            card = CardRenderer.result(
                "就绪", "Agent 已就绪，请描述你的任务。",
                success=True, context_path=path,
            )
            if prog_mid:
                self.ctx.messaging.update_card(prog_mid, card)
            return

        # 2) Get or create OpenCode API session
        sess_id = self.ctx.process_mgr.get_or_create_api_session(path)
        if not sess_id:
            self.ctx.op_tracker.finish(op_id)
            err_card = CardRenderer.error(
                "会话创建失败",
                "无法创建 Agent 会话，请检查服务状态。",
                context_path=path,
            )
            if prog_mid:
                self.ctx.messaging.update_card(prog_mid, err_card)
            return

        # 3) Build real-time progress callbacks
        start_time = time.time()
        last_card_update = start_time
        tool_count = 0
        step_descriptions = []

        def on_tool(tool_name: str, status: str, content: str) -> None:
            nonlocal tool_count, last_card_update
            tool_count += 1
            icon = {"pending": "⏳", "running": "⚙️", "completed": "✅", "error": "❌"}.get(status, "🔧")
            step_descriptions.append(f"{icon} {tool_name}")
            if len(step_descriptions) > 5:
                step_descriptions.pop(0)

            # Throttle card updates (every 5s)
            now = time.time()
            if now - last_card_update < 5.0:
                return
            last_card_update = now
            elapsed = int(now - start_time)

            progress_card = CardRenderer.progress(
                title=f"⏳ 执行中 ({elapsed}s)",
                description=(
                    f"**任务:** {task_text[:60]}...\n\n"
                    f"**进度 ({tool_count} 次工具调用):**\n"
                    + "\n".join(step_descriptions[-5:])
                ),
                show_cancel_button=True,
                cancel_action_data={"action": "cancel_task", "task_id": op_id},
            )
            if prog_mid:
                self.ctx.messaging.update_card(prog_mid, progress_card)

        def on_text(text: str) -> None:
            pass  # Text accumulation handled by SessionRunner internally

        def on_finish(summary: str) -> None:
            pass  # Final result handled below after runner.run() returns

        callbacks = PrinterCallbacks(
            on_tool=on_tool,
            on_text=on_text,
            on_finish=on_finish,
        )

        # 4) Run the prompt via SessionRunner
        runner = SessionRunner(
            port=proc.port,
            verbose=True,
            printer_callbacks=callbacks,
        )

        # Register cancel callback so CardActionHandler can cancel via op_id
        self.ctx.op_tracker.register_cancel_callback(op_id, runner.cancel)

        try:
            result = await runner.run(
                prompt=task_text,
                session_id=sess_id,
                timeout=14400.0,
            )
        finally:
            await runner.close()

        # 5) Handle result
        self.ctx.op_tracker.finish(op_id)
        elapsed = int(time.time() - start_time)

        if result.success:
            self._handle_success(chat_id, ctx, path, prog_mid, result, elapsed, task_text)
        elif result.was_cancelled:
            cancel_card = CardRenderer.result(
                "任务已取消",
                f"任务在 {elapsed}s 后被取消。\n{result.as_brief(200)}",
                success=False, context_path=path,
            )
            if prog_mid:
                self.ctx.messaging.update_card(prog_mid, cancel_card)
        else:
            self._handle_error(chat_id, ctx, path, prog_mid, result, elapsed)

    def _handle_success(
        self,
        chat_id: str,
        ctx: ConversationContext,
        path: str,
        prog_mid: Optional[str],
        result: RunResult,
        elapsed: int,
        task_text: str,
    ) -> None:
        """Handle successful task completion."""
        handler = LongOutputHandler(self.ctx.messaging)
        strategy, output = handler.process(
            title=f"任务完成 ({elapsed}s)",
            content=result.full_text or result.summary or "（任务已完成）",
            chat_id=chat_id,
            success=True,
            context_path=path,
        )

        if strategy == "paginate":
            cards = output
            for i, card in enumerate(cards):
                if i == 0 and prog_mid:
                    self.ctx.messaging.update_card(prog_mid, card)
                else:
                    self.ctx.messaging.send_card(chat_id, card)
        else:
            card = output
            if prog_mid:
                self.ctx.messaging.update_card(prog_mid, card)
            else:
                self.ctx.messaging.send_card(chat_id, card)

        tool_count = len(result.tool_calls)
        ctx.push("bot", f"任务完成（{elapsed}s，{tool_count}次工具调用，策略：{strategy}）")

    def _handle_error(
        self,
        chat_id: str,
        ctx: ConversationContext,
        path: str,
        prog_mid: Optional[str],
        result: RunResult,
        elapsed: int,
    ) -> None:
        """Handle task error."""
        partial = result.as_brief(300)
        error_card = CardRenderer.error(
            title="❌ 任务执行出错",
            error_message=f"{result.error or '未知错误'}\n\n{partial}",
            context_path=path,
        )
        if prog_mid:
            self.ctx.messaging.update_card(prog_mid, error_card)
        else:
            self.ctx.messaging.send_card(chat_id, error_card)

        ctx.push("bot", f"任务出错: {(result.error or '')[:50]}")
