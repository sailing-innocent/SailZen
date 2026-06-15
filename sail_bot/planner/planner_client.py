# -*- coding: utf-8 -*-
# @file planner_client.py
# @brief Planner client for generating and revising plans
# @author sailing-innocent
# @date 2026-06-16
# @version 1.0
# ---------------------------------
"""Planner client for plan mode.

Generates and revises plan content using the configured LLM gateway.  The
produced plan is written to the plan document store (`PlanDocStore`).
"""

import logging
from typing import Optional

from sail.llm.gateway import LLMExecutionConfig

logger = logging.getLogger(__name__)

_PLANNER_SYSTEM = """你是一位任务规划专家。请根据用户需求制定详细可执行计划。

计划文档必须包含以下章节：
1. 目标
2. 背景
3. 执行步骤（编号列表，每步包含：步骤标题、具体操作、预期输出）
4. 风险与回退方案
5. 预计耗时

要求：
- 步骤要具体、可验证、可执行
- 每步说明控制在 2-4 句话
- 使用 Markdown 格式输出，便于写入飞书文档
- 直接输出文档内容，不要有多余解释
"""

_REVISE_SYSTEM = """你是一位任务规划专家。用户已对现有计划提出修改意见，请据此修订计划文档。

请读取当前计划，根据用户意见进行修改，保持原有章节结构：
1. 目标
2. 背景
3. 执行步骤（编号列表）
4. 风险与回退方案
5. 预计耗时

只输出修订后的完整 Markdown 文档内容，不要有多余解释。
"""


class PlannerClient:
    """Client that produces plan content via LLM."""

    def __init__(self, brain: "BotBrain"):  # noqa: F821
        self._brain = brain

    async def generate_plan(self, requirement: str, existing_plan: str = "") -> str:
        """Generate a plan markdown document for the given requirement."""
        if existing_plan:
            prompt = (
                f"{_PLANNER_SYSTEM}\n\n"
                f"当前已有如下计划草案，请基于用户需求重新整理并完善：\n\n"
                f"---\n{existing_plan}\n---\n\n"
                f"用户需求：{requirement}\n\n"
                f"请输出完整计划文档："
            )
        else:
            prompt = (
                f"{_PLANNER_SYSTEM}\n\n"
                f"用户需求：{requirement}\n\n"
                f"请输出完整计划文档："
            )
        return await self._call_llm(prompt)

    async def revise_plan(self, requirement: str, feedback: str, current_plan: str) -> str:
        """Revise an existing plan based on user feedback."""
        prompt = (
            f"{_REVISE_SYSTEM}\n\n"
            f"原始需求：{requirement}\n\n"
            f"用户修改意见：{feedback}\n\n"
            f"当前计划文档：\n\n---\n{current_plan}\n---\n\n"
            f"请输出修订后的完整计划文档："
        )
        return await self._call_llm(prompt)

    async def _call_llm(self, prompt: str) -> str:
        """Call the LLM gateway via BotBrain."""
        gw = getattr(self._brain, "_gw", None)
        model_cfg = getattr(self._brain, "_model_cfg", None)
        provider = getattr(self._brain, "_provider", None)
        if not gw or not model_cfg or not provider:
            raise RuntimeError("LLM gateway not available for planner")

        model, temp = model_cfg
        config = LLMExecutionConfig(
            provider=provider,
            model=model,
            temperature=temp,
            max_tokens=4000,
            enable_caching=False,
            timeout=120,
        )
        result = await gw.execute(prompt, config)
        text = result.content.strip() if result.content else ""
        # Strip markdown code fences if present
        if text.startswith("```"):
            text = text[text.find("\n") + 1 :]
            if text.endswith("```"):
                text = text[: text.rfind("```")].strip()
        return text
