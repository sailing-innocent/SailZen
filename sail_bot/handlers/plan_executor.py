# -*- coding: utf-8 -*-
# @file plan_executor.py
# @brief Plan execution coordinator
# @author sailing-innocent
# @date 2026-04-08
# @version 2.0
# ---------------------------------
"""Plan execution coordinator.

Routes ActionPlans to specific handlers via an action registry.
New actions can be added by registering an entry in _ACTION_REGISTRY.
"""

import logging
import threading
from typing import Optional, Callable, Dict

from sail_bot.handlers.base import BaseHandler, HandlerContext
from sail_bot.context import ActionPlan, ConversationContext
from sail.feishu_card_kit.renderer import CardRenderer

logger = logging.getLogger(__name__)


class PlanExecutor(BaseHandler):
    """Executor for ActionPlans.

    Uses a registry dict to dispatch actions to handlers, making it trivial
    to add new actions without modifying the execute() method.
    """

    def __init__(self, ctx: HandlerContext):
        super().__init__(ctx)
        from sail_bot.handlers.command_handlers import HelpHandler, StatusHandler
        from sail_bot.handlers.workspace_handlers import (
            StartWorkspaceHandler,
            StopWorkspaceHandler,
            SwitchWorkspaceHandler,
            WorkspaceDashboardHandler,
        )
        from sail_bot.handlers.task_handler import TaskHandler
        from sail_bot.handlers.self_update_handler import SelfUpdateHandler
        from sail_bot.handlers.image_gen_handler import ImageGenHandler

        self._help = HelpHandler(ctx)
        self._status = StatusHandler(ctx)
        self._start = StartWorkspaceHandler(ctx)
        self._stop = StopWorkspaceHandler(ctx)
        self._switch = SwitchWorkspaceHandler(ctx)
        self._dashboard = WorkspaceDashboardHandler(ctx)
        self._task = TaskHandler(ctx)
        self._update = SelfUpdateHandler(ctx)
        self._image_gen = ImageGenHandler(ctx)

        self._registry: Dict[str, tuple[Callable, str]] = {
            "show_help": (self._exec_help, "显示帮助信息"),
            "show_status": (self._exec_status, "状态已显示"),
            "show_workspace_dashboard": (self._exec_dashboard, "显示工作区面板"),
            "switch_workspace": (self._exec_switch, "切换工作区"),
            "start_workspace": (self._exec_start, "启动工作区"),
            "stop_workspace": (self._exec_stop, "停止工作区"),
            "send_task": (self._exec_task, "发送任务"),
            "self_update": (self._exec_self_update, "自更新"),
            "confirm_self_update": (
                self._exec_confirmed_self_update,
                "正在执行自更新...",
            ),
            "enter_image_gen": (self._exec_enter_image_gen, "进入图片生成模式"),
            "generate_image": (self._exec_generate_image, "生成图片"),
            "edit_image": (self._exec_edit_image, "编辑图片"),
            "save_image": (self._exec_save_image, "保存图片"),
            "exit_image_gen": (self._exec_exit_image_gen, "退出图片生成模式"),
        }

    def execute(
        self,
        plan: ActionPlan,
        chat_id: str,
        message_id: str,
        ctx: ConversationContext,
        thinking_mid: Optional[str] = None,
    ) -> None:
        """Execute an ActionPlan by dispatching to the registered handler."""
        entry = self._registry.get(plan.action)
        if entry:
            handler_fn, log_msg = entry
            handler_fn(plan, chat_id, message_id, ctx)
            ctx.push("bot", log_msg)
        else:
            logger.warning("Unknown action: %s", plan.action)
            self.ctx.messaging.reply_text(message_id, f"未知动作: {plan.action}")

    def _exec_help(
        self, plan: ActionPlan, chat_id: str, mid: str, ctx: ConversationContext
    ) -> None:
        self._help.handle(chat_id, mid)

    def _exec_status(
        self, plan: ActionPlan, chat_id: str, mid: str, ctx: ConversationContext
    ) -> None:
        self._status.handle(chat_id, mid, ctx)

    def _exec_dashboard(
        self, plan: ActionPlan, chat_id: str, mid: str, ctx: ConversationContext
    ) -> None:
        self._dashboard.handle(chat_id, mid)

    def _exec_switch(
        self, plan: ActionPlan, chat_id: str, mid: str, ctx: ConversationContext
    ) -> None:
        path = plan.params.get("path")
        if path:
            self._switch.handle(chat_id, mid, ctx, path)
        else:
            self.ctx.messaging.reply_text(mid, "请指定工作区路径")

    def _exec_start(
        self, plan: ActionPlan, chat_id: str, mid: str, ctx: ConversationContext
    ) -> None:
        self._start.handle(
            chat_id,
            mid,
            ctx,
            path=plan.params.get("path"),
            project_slug=plan.params.get("project"),
        )

    def _exec_stop(
        self, plan: ActionPlan, chat_id: str, mid: str, ctx: ConversationContext
    ) -> None:
        self._stop.handle(chat_id, mid, ctx, path=plan.params.get("path"))

    def _exec_task(
        self, plan: ActionPlan, chat_id: str, mid: str, ctx: ConversationContext
    ) -> None:
        self._task.handle(
            chat_id,
            mid,
            ctx,
            plan.params.get("task", ""),
            path=plan.params.get("path"),
        )

    def _exec_self_update(
        self, plan: ActionPlan, chat_id: str, mid: str, ctx: ConversationContext
    ) -> None:
        trigger = plan.params.get("trigger_source", "manual")
        reason = plan.params.get("reason", "User requested update")
        self._update.handle(chat_id, mid, ctx, reason=f"[{trigger}] {reason}")

    def _exec_confirmed_self_update(
        self, plan: ActionPlan, chat_id: str, mid: str, ctx: ConversationContext
    ) -> None:
        trigger_source = plan.params.get("trigger_source", "manual")
        reason = plan.params.get("reason", "User confirmed update")

        # Save pending update context BEFORE starting the update
        from sail_bot.self_update_orchestrator import SelfUpdateOrchestrator

        SelfUpdateOrchestrator.save_pending_update(
            chat_id=chat_id,
            reason=f"[{trigger_source}] {reason}",
        )

        def do_self_update():
            result = self.ctx.request_self_update(
                reason=f"[{trigger_source}] {reason} (by {chat_id})",
            )
            if result and result.get("success"):
                card = CardRenderer.result(
                    "更新已启动",
                    f"Bot 即将退出并由 watcher 重启。",
                    success=True,
                )
                self.ctx.messaging.send_card(chat_id, card)
            else:
                # Clear pending update on failure
                SelfUpdateOrchestrator.load_and_clear_pending_update()
                err = result.get("error", "Unknown error") if result else "No response"
                card = CardRenderer.result("更新失败", err, success=False)
                self.ctx.messaging.send_card(chat_id, card)

        threading.Thread(target=do_self_update, daemon=True).start()
        self.ctx.messaging.reply_text(mid, "正在启动更新，请稍候...")

    def _exec_enter_image_gen(
        self, plan: ActionPlan, chat_id: str, mid: str, ctx: ConversationContext
    ) -> None:
        self._image_gen.handle_enter(chat_id, mid, ctx)

    def _exec_generate_image(
        self, plan: ActionPlan, chat_id: str, mid: str, ctx: ConversationContext
    ) -> None:
        self._image_gen.handle_generate(plan, chat_id, mid, ctx)

    def _exec_edit_image(
        self, plan: ActionPlan, chat_id: str, mid: str, ctx: ConversationContext
    ) -> None:
        self._image_gen.handle_edit(plan, chat_id, mid, ctx)

    def _exec_save_image(
        self, plan: ActionPlan, chat_id: str, mid: str, ctx: ConversationContext
    ) -> None:
        self._image_gen.handle_save(plan, chat_id, mid, ctx)

    def _exec_exit_image_gen(
        self, plan: ActionPlan, chat_id: str, mid: str, ctx: ConversationContext
    ) -> None:
        self._image_gen.handle_exit(chat_id, mid, ctx)
