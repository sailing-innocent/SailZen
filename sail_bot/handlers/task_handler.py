# -*- coding: utf-8 -*-
# @file task_handler.py
# @brief Task execution handler
# @author sailing-innocent
# @date 2026-04-06
# @version 1.0
# ---------------------------------
"""Task execution handler for sending tasks to OpenCode.

This module handles the complex task execution flow including:
- Starting workspace if needed
- Creating and submitting async tasks
- Progress updates via card
- Result/error handling
"""

import time
import threading
from pathlib import Path
from typing import List, Optional

from sail_bot.handlers.base import BaseHandler, HandlerContext
from sail_bot.context import ConversationContext
from sail_bot.card_renderer import CardRenderer
from sail_bot.async_task_manager import task_manager
from sail_bot.task_logger import task_logger
from sail_bot.long_output_handler import LongOutputHandler, handle_long_output


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
        from sail_bot.session_manager import resolve_path

        # Resolve workspace path
        if not path:
            running = [
                s
                for s in self.ctx.session_mgr.list_sessions()
                if s.process_status == "running"
            ]
            if not running:
                card = CardRenderer.error(
                    "未找到会话",
                    "没有正在运行的 OpenCode 会话。\n请先启动一个，例如：启动 sailzen",
                )
                self.ctx.messaging.reply_card(message_id, card)
                return

            if len(running) == 1:
                path = running[0].path
            elif ctx.active_workspace:
                path = ctx.active_workspace
            else:
                names = [Path(s.path).name for s in running]
                self.ctx.messaging.reply_text(
                    message_id,
                    "有多个会话运行中：" + ", ".join(names) + "\n请指定工作区",
                )
                return

        # Start operation tracking
        op_id = self.ctx.op_tracker.start(path, task_text[:60], timeout=14400.0)  # 4 hours

        # Create progress card with cancel button
        progress_card = CardRenderer.progress(
            title="🚀 任务已提交",
            description=f"正在初始化...\n\n**任务:** {task_text[:100]}{'...' if len(task_text) > 100 else ''}",
            show_cancel_button=True,
            cancel_action_data={"action": "cancel_task", "task_id": op_id},
        )
        prog_mid = self.ctx.messaging.reply_card(
            message_id, progress_card, "progress", {"op_id": op_id, "path": path}
        )

        def do_async_task() -> None:
            """Execute task asynchronously."""
            from sail_bot.async_task_manager import TaskStep

            # Ensure workspace is running
            ok, session, start_msg = self.ctx.session_mgr.ensure_running(path, chat_id)
            if not ok:
                self.ctx.op_tracker.finish(op_id)
                err_card = CardRenderer.error("启动失败", start_msg, context_path=path)
                if prog_mid:
                    self.ctx.messaging.update_card(prog_mid, err_card)
                return

            ctx.mode = "coding"
            ctx.active_workspace = session.path
            ctx.clear_pending()  # Clear any pending confirmation
            self.ctx.save_contexts()

            if not task_text:
                self.ctx.op_tracker.finish(op_id)
                card = CardRenderer.result(
                    "就绪",
                    "OpenCode 已就绪，请描述你的任务。",
                    success=True,
                    context_path=path,
                )
                if prog_mid:
                    self.ctx.messaging.update_card(prog_mid, card)
                return

            # Get or create OpenCode session
            sess_id = self.ctx.session_mgr.get_or_create_opencode_session(path)
            if not sess_id:
                self.ctx.op_tracker.finish(op_id)
                err_card = CardRenderer.error(
                    "会话创建失败",
                    "无法创建 OpenCode 会话，请检查服务状态。",
                    context_path=path,
                )
                if prog_mid:
                    self.ctx.messaging.update_card(prog_mid, err_card)
                return

            start_time = time.time()
            last_card_update = start_time
            all_steps: List[TaskStep] = []
            current_task = None

            def on_step(step: TaskStep):
                """Step update callback."""
                nonlocal last_card_update
                all_steps.append(step)

                # Update card every 5 seconds (avoid Feishu rate limits & mobile flicker)
                current_time = time.time()
                if current_time - last_card_update < 5.0:
                    return

                last_card_update = current_time
                elapsed = int(current_time - start_time)

                # Build progress description
                recent_steps = all_steps[-5:]
                step_descriptions = []

                for s in recent_steps:
                    if s.step_type == "tool_call":
                        tool_name = s.metadata.get("tool", "unknown")
                        step_descriptions.append(f"🔧 调用: {tool_name}")
                    elif s.step_type == "tool_result":
                        step_descriptions.append("✅ 工具完成")
                    elif s.step_type == "thinking":
                        text = (
                            s.content[:80] + "..." if len(s.content) > 80 else s.content
                        )
                        step_descriptions.append(f"💭 {text}")

                progress_text = (
                    "\n".join(step_descriptions) if step_descriptions else "正在处理..."
                )

                progress_card = CardRenderer.progress(
                    title=f"⏳ 执行中 ({elapsed}s)",
                    description=f"**任务:** {task_text[:60]}...\n\n**进度:**\n{progress_text}\n\n*正在等待OpenCode响应...*",
                    show_cancel_button=True,
                    cancel_action_data={
                        "action": "cancel_task",
                        "task_id": current_task.task_id if current_task else op_id,
                    },
                )
                if prog_mid:
                    self.ctx.messaging.update_card(prog_mid, progress_card)

            def on_complete(result: str):
                """Completion callback with long output support."""
                self.ctx.op_tracker.finish(op_id)
                elapsed = int(time.time() - start_time)

                tool_calls = len([s for s in all_steps if s.step_type == "tool_call"])

                # Use long output handler for better handling of large results
                handler = LongOutputHandler(self.ctx.messaging)
                strategy, output = handler.process(
                    title=f"任务完成 ({elapsed}s)",
                    content=result,
                    chat_id=chat_id,
                    success=True,
                    context_path=path,
                )

                # Handle different output types
                if strategy == "paginate":
                    # Multiple cards - first replaces progress card, rest are new
                    cards = output
                    for i, card in enumerate(cards):
                        if i == 0 and prog_mid:
                            self.ctx.messaging.update_card(prog_mid, card)
                        else:
                            self.ctx.messaging.send_card(chat_id, card)
                else:
                    # Single card
                    card = output
                    if prog_mid:
                        self.ctx.messaging.update_card(prog_mid, card)
                    else:
                        self.ctx.messaging.send_card(chat_id, card)

                ctx.push("bot", f"任务完成（{elapsed}s，{tool_calls}次工具调用，策略：{strategy}）")

            def on_error(error_msg: str):
                """Error callback."""
                self.ctx.op_tracker.finish(op_id)

                # Build partial result from recent steps
                partial_steps = []
                for s in all_steps[-3:]:
                    if s.step_type == "thinking":
                        partial_steps.append(s.content[:100])

                partial_text = "\n".join(partial_steps) if partial_steps else ""

                error_card = CardRenderer.error(
                    title="❌ 任务执行出错",
                    error_message=f"{error_msg}\n\n**已执行步骤:**\n{partial_text[:300] if partial_text else '（无）'}",
                    context_path=path,
                )

                if prog_mid:
                    self.ctx.messaging.update_card(prog_mid, error_card)
                else:
                    self.ctx.messaging.send_card(chat_id, error_card)

                ctx.push("bot", f"任务出错: {error_msg[:50]}")

            # Submit async task
            from sail_bot.log_formatter import task as log_task, task_progress
            log_task(f"Submitting for session {sess_id[:16]}...")
            task = task_manager.submit_task(
                session_id=sess_id,
                port=session.port,
                text=task_text,
                workspace_path=path,
                on_step=on_step,
                on_complete=on_complete,
                on_error=on_error,
            )
            current_task = task
            task_progress(task.task_id, "started", f"session={sess_id[:16]}...")

            # Update card with correct task_id for cancellation
            # This ensures the cancel button works with the real task ID
            task_desc = (
                f"**任务:** {task_text[:100]}{'...' if len(task_text) > 100 else ''}"
            )
            initial_card = CardRenderer.progress(
                title="🚀 任务已开始",
                description=f"正在执行...\n\n{task_desc}",
                show_cancel_button=True,
                cancel_action_data={"action": "cancel_task", "task_id": task.task_id},
            )
            if prog_mid:
                self.ctx.messaging.update_card(prog_mid, initial_card)

        threading.Thread(target=do_async_task, daemon=True).start()
