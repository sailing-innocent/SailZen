# -*- coding: utf-8 -*-
# @file plan_runner.py
# @brief Execute approved plans in a workspace
# @author sailing-innocent
# @date 2026-06-16
# @version 1.0
# ---------------------------------
"""Execute approved plans by dispatching them to the active workspace.

`PlanRunner` takes an approved plan document and uses `TaskHandler` to run it
in an OpenCode workspace.  It also tracks progress by parsing `STEP_DONE:`
markers emitted by the executing agent.
"""

import asyncio
import logging
from typing import Optional

from sail_bot.context import ConversationContext
from sail_bot.planner.plan_parser import PlanParser, StructuredPlan

logger = logging.getLogger(__name__)

_EXECUTION_PROMPT = """请严格按照以下计划执行。每完成一个主要步骤，请在输出中明确标记：
STEP_DONE: <步骤编号>

如果遇到困难，请明确说明并请求用户决策。

---
{plan_content}
---
"""


class PlanRunner:
    """Run an approved plan in the active workspace."""

    def __init__(self, ctx: "HandlerContext"):  # noqa: F821
        self.ctx = ctx

    def execute(
        self,
        chat_id: str,
        message_id: str,
        ctx: ConversationContext,
        plan_content: str,
        path: Optional[str] = None,
    ) -> None:
        """Dispatch the approved plan to a workspace for execution."""
        from sail_bot.handlers.task_handler import TaskHandler

        task_text = _EXECUTION_PROMPT.format(plan_content=plan_content)
        task_handler = TaskHandler(self.ctx)
        task_handler.handle(chat_id, message_id, ctx, task_text, path=path)

    @staticmethod
    def parse_progress(plan_content: str, agent_output: str) -> StructuredPlan:
        """Update a structured plan with progress parsed from agent output."""
        plan = PlanParser.parse(plan_content)
        done_ids = set()
        for line in agent_output.splitlines():
            line = line.strip()
            if line.startswith("STEP_DONE:"):
                step_id = line[len("STEP_DONE:") :].strip()
                done_ids.add(step_id)

        for step in plan.steps:
            if step.step_id in done_ids:
                step.status = "done"
        return plan
