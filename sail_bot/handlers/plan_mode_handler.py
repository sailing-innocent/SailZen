# -*- coding: utf-8 -*-
# @file plan_mode_handler.py
# @brief Plan mode handler for collaborative planning in Feishu
# @author sailing-innocent
# @date 2026-06-16
# @version 1.0
# ---------------------------------
"""Plan mode handler for collaborative long-task planning.

Coordinates plan drafting, review, revision, approval, and execution using a
Feishu document as the single source of truth.
"""

import asyncio
import hashlib
import logging
import threading
from typing import Optional

from sail_bot.handlers.base import BaseHandler, HandlerContext
from sail_bot.context import ConversationContext, PlanModeState
from sail.feishu_card_kit.renderer import CardRenderer
from sail_bot.planner import PlanDocStore, PlannerClient, PlanRunner

logger = logging.getLogger(__name__)

_MAX_PLAN_DOC_CHARS = 100_000


class PlanModeHandler(BaseHandler):
    """Handler for plan mode operations."""

    def __init__(self, ctx: HandlerContext):
        super().__init__(ctx)
        self._doc_store = PlanDocStore(fallback_to_local=True)

    # ------------------------------------------------------------------
    # Entry points
    # ------------------------------------------------------------------

    def enter(
        self,
        chat_id: str,
        message_id: str,
        ctx: ConversationContext,
        requirement: str,
    ) -> None:
        """Enter plan mode and start drafting a plan."""
        requirement = (requirement or "").strip()
        if not requirement:
            self.ctx.messaging.reply_text(
                message_id,
                "请描述你想要制定的计划，例如：\n• 帮我规划一下健康管理重构\n• 制定一个项目上线计划",
            )
            return

        # If already in a plan mode session, treat as a new revision request
        if ctx.mode == "planning" and ctx.plan_state:
            self.revise(chat_id, message_id, ctx, requirement)
            return

        # Inform user when switching from an active coding workspace
        if ctx.mode == "coding" and ctx.active_workspace:
            self.ctx.messaging.reply_text(
                message_id,
                f"已暂停当前工作区 **{ctx.active_workspace}**，进入计划模式。"
                "计划批准执行后将自动切回该工作区。",
            )

        ctx.mode = "planning"
        ctx.plan_state = PlanModeState(
            status="draft",
            requirement=requirement,
        )
        self.ctx.save_contexts()

        # Show thinking card
        thinking_card = CardRenderer.progress(
            title="正在制定计划",
            description=f"正在理解需求并生成计划文档…\n\n**需求：** {requirement[:120]}{'...' if len(requirement) > 120 else ''}",
        )
        thinking_mid = self.ctx.messaging.reply_card(
            message_id, thinking_card, "plan_thinking", {"chat_id": chat_id}
        )

        def do_enter() -> None:
            try:
                loop = asyncio.new_event_loop()
                try:
                    loop.run_until_complete(
                        self._enter_async(chat_id, message_id, ctx, requirement, thinking_mid)
                    )
                finally:
                    loop.close()
            except Exception as exc:
                logger.error("PlanModeHandler.enter failed: %s", exc, exc_info=True)
                error_card = CardRenderer.error(
                    "进入计划模式失败", str(exc)[:400]
                )
                self.ctx.messaging.update_card(thinking_mid, error_card)

        threading.Thread(target=do_enter, daemon=True).start()

    async def _enter_async(
        self,
        chat_id: str,
        message_id: str,
        ctx: ConversationContext,
        requirement: str,
        thinking_mid: Optional[str],
    ) -> None:
        planner = PlannerClient(self.ctx.brain)
        plan_content = await planner.generate_plan(requirement)

        title = _extract_title(plan_content) or f"Plan: {requirement[:40]}"
        ctx.plan_state.plan_title = title
        ctx.plan_state.touch()
        self.ctx.save_contexts()

        doc_token, doc_url = await self._doc_store.create(
            title=title,
            initial_content=plan_content,
            chat_id=chat_id,
        )
        ctx.plan_state.doc_token = doc_token
        ctx.plan_state.doc_url = doc_url
        ctx.plan_state.status = "review"
        ctx.plan_state.last_content_hash = _content_hash(plan_content)
        ctx.plan_state.plan_revision += 1
        ctx.plan_state.touch()
        self.ctx.save_contexts()

        review_card = CardRenderer.plan_review(
            title=title,
            requirement=requirement,
            doc_url=doc_url,
            preview_steps=_preview_steps(plan_content),
        )
        if thinking_mid:
            self.ctx.messaging.update_card(thinking_mid, review_card)
            self.ctx.messaging.card_tracker.register(
                thinking_mid, "plan_review", {"chat_id": chat_id}
            )
        else:
            self.ctx.messaging.reply_card(
                message_id, review_card, "plan_review", {"chat_id": chat_id}
            )

    def revise(
        self,
        chat_id: str,
        message_id: str,
        ctx: ConversationContext,
        feedback: str,
    ) -> None:
        """Revise the current plan based on user feedback."""
        if not ctx.plan_state or not ctx.plan_state.doc_token:
            self.ctx.messaging.reply_text(
                message_id, "当前没有正在进行的计划，请先输入「帮我做个计划」开始。"
            )
            return

        ctx.plan_state.status = "revising"
        ctx.plan_state.touch()
        self.ctx.save_contexts()

        revising_card = CardRenderer.plan_revising(
            doc_url=ctx.plan_state.doc_url or "",
        )
        revising_mid = self.ctx.messaging.reply_card(
            message_id, revising_card, "plan_revising", {"chat_id": chat_id}
        )

        def do_revise() -> None:
            try:
                loop = asyncio.new_event_loop()
                try:
                    loop.run_until_complete(
                        self._revise_async(
                            chat_id, message_id, ctx, feedback, revising_mid
                        )
                    )
                finally:
                    loop.close()
            except Exception as exc:
                logger.error("PlanModeHandler.revise failed: %s", exc, exc_info=True)
                error_card = CardRenderer.error("修订计划失败", str(exc)[:400])
                self.ctx.messaging.update_card(revising_mid, error_card)

        threading.Thread(target=do_revise, daemon=True).start()

    async def _revise_async(
        self,
        chat_id: str,
        message_id: str,
        ctx: ConversationContext,
        feedback: str,
        revising_mid: Optional[str],
    ) -> None:
        current = await self._doc_store.fetch(ctx.plan_state.doc_token)
        planner = PlannerClient(self.ctx.brain)
        revised = await planner.revise_plan(
            ctx.plan_state.requirement, feedback, current
        )
        revised = _truncate_plan(revised)

        await self._doc_store.update(
            ctx.plan_state.doc_token,
            command="overwrite",
            content=revised,
        )

        ctx.plan_state.status = "review"
        ctx.plan_state.last_content_hash = _content_hash(revised)
        ctx.plan_state.plan_revision += 1
        ctx.plan_state.touch()
        self.ctx.save_contexts()

        review_card = CardRenderer.plan_review(
            title=ctx.plan_state.plan_title,
            requirement=ctx.plan_state.requirement,
            doc_url=ctx.plan_state.doc_url or "",
            preview_steps=_preview_steps(revised),
        )
        if revising_mid:
            self.ctx.messaging.update_card(revising_mid, review_card)
            self.ctx.messaging.card_tracker.register(
                revising_mid, "plan_review", {"chat_id": chat_id}
            )
        else:
            self.ctx.messaging.reply_card(
                message_id, review_card, "plan_review", {"chat_id": chat_id}
            )

    def approve(
        self,
        chat_id: str,
        message_id: str,
        ctx: ConversationContext,
        path: Optional[str] = None,
    ) -> None:
        """Approve the plan and start execution."""
        if not ctx.plan_state or not ctx.plan_state.doc_token:
            self.ctx.messaging.reply_text(message_id, "当前没有可执行的计划。")
            return

        ctx.plan_state.status = "approved"
        ctx.plan_state.touch()
        self.ctx.save_contexts()

        def do_execute() -> None:
            try:
                loop = asyncio.new_event_loop()
                try:
                    loop.run_until_complete(
                        self._execute_async(chat_id, message_id, ctx, path)
                    )
                finally:
                    loop.close()
            except Exception as exc:
                logger.error("PlanModeHandler.approve failed: %s", exc, exc_info=True)
                error_card = CardRenderer.error("执行计划失败", str(exc)[:400])
                self.ctx.messaging.reply_card(message_id, error_card)

        threading.Thread(target=do_execute, daemon=True).start()

    async def _execute_async(
        self,
        chat_id: str,
        message_id: str,
        ctx: ConversationContext,
        path: Optional[str],
    ) -> None:
        plan_content = await self._doc_store.fetch(ctx.plan_state.doc_token)
        if not plan_content:
            raise RuntimeError("无法读取计划文档内容")

        # Resolve workspace path
        resolved_path = path or ctx.plan_state.workspace_path or ctx.active_workspace

        # Update state to executing before dispatch
        ctx.plan_state.status = "executing"
        ctx.plan_state.workspace_path = resolved_path
        ctx.plan_state.touch()
        self.ctx.save_contexts()

        runner = PlanRunner(self.ctx)
        runner.execute(chat_id, message_id, ctx, plan_content, path=resolved_path)

        # Note: PlanRunner dispatches to TaskHandler, which creates its own
        # real-time progress card.  Future enhancements can parse STEP_DONE
        # markers from the agent output to update a dedicated plan_executing
        # card tied to the plan steps.

    def cancel(
        self,
        chat_id: str,
        message_id: str,
        ctx: ConversationContext,
    ) -> None:
        """Cancel plan mode."""
        if ctx.plan_state:
            ctx.plan_state.status = "cancelled"
            ctx.plan_state.touch()
        ctx.mode = "idle"
        ctx.clear_pending()
        self.ctx.save_contexts()

        card = CardRenderer.plan_cancelled()
        self.ctx.messaging.reply_card(message_id, card, "plan_cancelled", {"chat_id": chat_id})

    def handle_message_in_plan_mode(
        self,
        text: str,
        chat_id: str,
        message_id: str,
        ctx: ConversationContext,
    ) -> bool:
        """Route a user message received while in planning mode.

        Returns True if the message was handled as a plan-mode message.
        """
        if ctx.mode != "planning" or not ctx.plan_state:
            return False

        t = text.strip().lower()

        # Approval triggers
        if t in {"批准", "执行", "开始执行", "确认", "approve", "execute", "go", "ok"}:
            self.approve(chat_id, message_id, ctx)
            return True

        # Cancel triggers
        if t in {"取消", "退出", "exit", "quit", "cancel", "不做了"}:
            self.cancel(chat_id, message_id, ctx)
            return True

        # Direct doc update signal
        if t in {"已更新", "更新好了", "改好了", "done"}:
            self._check_doc_update_and_show_review(chat_id, message_id, ctx)
            return True

        # Treat as revision feedback
        self.revise(chat_id, message_id, ctx, text)
        return True

    def _check_doc_update_and_show_review(
        self,
        chat_id: str,
        message_id: str,
        ctx: ConversationContext,
    ) -> None:
        if not ctx.plan_state or not ctx.plan_state.doc_token:
            return

        def do_check() -> None:
            try:
                loop = asyncio.new_event_loop()
                try:
                    loop.run_until_complete(
                        self._check_doc_update_async(chat_id, message_id, ctx)
                    )
                finally:
                    loop.close()
            except Exception as exc:
                logger.error("PlanModeHandler._check_doc_update failed: %s", exc, exc_info=True)
                self.ctx.messaging.reply_text(
                    message_id, f"读取文档失败: {exc}"
                )

        threading.Thread(target=do_check, daemon=True).start()

    async def _check_doc_update_async(
        self,
        chat_id: str,
        message_id: str,
        ctx: ConversationContext,
    ) -> None:
        content = await self._doc_store.fetch(ctx.plan_state.doc_token)
        new_hash = _content_hash(content)
        changed = new_hash != ctx.plan_state.last_content_hash
        ctx.plan_state.last_content_hash = new_hash
        ctx.plan_state.status = "review"
        ctx.plan_state.touch()
        self.ctx.save_contexts()

        if changed:
            card = CardRenderer.plan_review(
                title=ctx.plan_state.plan_title,
                requirement=ctx.plan_state.requirement,
                doc_url=ctx.plan_state.doc_url or "",
                preview_steps=_preview_steps(content),
            )
            self.ctx.messaging.reply_card(
                message_id, card, "plan_review", {"chat_id": chat_id}
            )
        else:
            self.ctx.messaging.reply_text(
                message_id,
                "文档内容没有变化。请直接编辑文档或回复修改意见。",
            )

    # ------------------------------------------------------------------
    # Recovery helpers
    # ------------------------------------------------------------------

    def resume_on_message(
        self,
        chat_id: str,
        message_id: str,
        ctx: ConversationContext,
    ) -> bool:
        """If a persisted plan session exists, prompt the user to resume.

        Returns True if a plan session was found and a resume prompt sent.
        """
        if ctx.mode != "planning" or not ctx.plan_state:
            return False
        if ctx.plan_state.status in {"draft", "review", "revising", "approved"}:
            card = CardRenderer.result(
                title="计划会话恢复",
                content=(
                    f"你有一个未完成的计划：**{ctx.plan_state.plan_title or '未命名计划'}**\n\n"
                    f"文档链接：{ctx.plan_state.doc_url or '本地文档'}\n\n"
                    "你可以：\n"
                    "• 回复「批准」开始执行\n"
                    "• 回复修改意见继续修订\n"
                    "• 回复「取消」退出计划模式"
                ),
                success=True,
            )
            self.ctx.messaging.reply_card(
                message_id, card, "plan_resume", {"chat_id": chat_id}
            )
            return True
        return False


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _extract_title(content: str) -> str:
    """Extract title from XML <title> tag or first markdown H1."""
    import re

    # Prefer XML <title> tag
    m = re.search(r"<title>([^<]+)</title>", content)
    if m:
        return m.group(1).strip()
    m = re.search(r"^#\s+(.+)$", content, re.MULTILINE)
    return m.group(1).strip() if m else ""


def _preview_steps(content: str, max_steps: int = 5) -> list:
    from sail_bot.planner.plan_parser import PlanParser

    return PlanParser.preview_steps(content, max_steps=max_steps)


def _content_hash(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()[:16]


def _truncate_plan(content: str, max_chars: int = _MAX_PLAN_DOC_CHARS) -> str:
    if len(content) <= max_chars:
        return content
    return content[:max_chars] + "\n\n（内容已截断至最大限制）"
