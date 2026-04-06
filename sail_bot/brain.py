# -*- coding: utf-8 -*-
# @file brain.py
# @brief Bot brain with LLM intent recognition
# @author sailing-innocent
# @date 2026-04-06
# @version 1.1
# ---------------------------------
"""Bot brain with LLM-driven intent recognition.

This module provides the BotBrain class for converting user text
into structured ActionPlan objects using LLM or deterministic matching.
"""

from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List, Tuple
import asyncio
import re
import json
import os
import time
import ast

# FIX: Move imports to top level
from sail_server.utils.llm.gateway import LLMGateway, LLMExecutionConfig
from sail_server.utils.llm.providers import ProviderConfig
from sail_server.utils.llm.available_providers import (
    DEFAULT_LLM_PROVIDER,
    DEFAULT_LLM_MODEL,
    DEFAULT_LLM_CONFIG,
)

from sail_bot.context import (
    ConversationContext,
    ActionPlan,
    PendingConfirmation,
    _CONFIRM_WORDS,
    _CANCEL_WORDS,
)
from sail_bot.card_renderer import CardRenderer
from sail_bot.session_manager import extract_path_from_text


# 这是什么傻逼实现
def _make_gateway(
    config_provider: Optional[str] = None, config_api_key: Optional[str] = None
):
    """Build a minimal LLMGateway from environment variables or config.

    Args:
        config_provider: Optional provider name from config file (e.g., "moonshot")
        config_api_key: Optional API key from config file
    """
    try:
        provider_env_keys = {
            "moonshot": "MOONSHOT_API_KEY",
            "openai": "OPENAI_API_KEY",
            "google": "GOOGLE_API_KEY",
            "deepseek": "DEEPSEEK_API_KEY",
            "anthropic": "ANTHROPIC_API_KEY",
        }

        # Default models for each provider
        default_models = {
            "moonshot": DEFAULT_LLM_MODEL
            if DEFAULT_LLM_PROVIDER == "moonshot"
            else "kimi-k2.5",
            "openai": os.environ.get("OPENAI_MODEL", "gpt-4o-mini"),
            "google": os.environ.get("GOOGLE_MODEL", "gemini-2.0-flash"),
            "deepseek": os.environ.get("DEEPSEEK_MODEL", "deepseek-chat"),
            "anthropic": os.environ.get("ANTHROPIC_MODEL", "claude-3-haiku-20240307"),
        }

        gw = LLMGateway()
        registered = []

        # First, check if config file has explicit provider + api_key
        if config_provider and config_api_key:
            provider = config_provider.lower()
            if provider in provider_env_keys:
                model = default_models.get(provider, "")
                cfg = ProviderConfig(
                    provider_name=provider,
                    model=model,
                    api_key=config_api_key,
                    api_base=os.environ.get(f"{provider.upper()}_API_BASE"),
                )
                gw.register_provider(provider, cfg)
                registered.append(provider)
                print(f"[BotBrain] Registered provider from config: {provider}")

        # Then check environment variables for other providers
        for pname, env_key in provider_env_keys.items():
            if pname in registered:
                continue  # Skip if already registered from config
            key = os.environ.get(env_key, "")
            if key:
                cfg = ProviderConfig(
                    provider_name=pname,
                    model=default_models[pname],
                    api_key=key,
                    api_base=os.environ.get(f"{pname.upper()}_API_BASE"),
                )
                gw.register_provider(pname, cfg)
                registered.append(pname)

        if not registered:
            return None, None, None
        primary = (
            DEFAULT_LLM_PROVIDER
            if DEFAULT_LLM_PROVIDER in registered
            else registered[0]
        )
        model = default_models.get(primary, "")
        temp = float(DEFAULT_LLM_CONFIG.get("temperature", 0.7))
        return gw, primary, (model, temp)

    except Exception as exc:
        print(f"[BotBrain] Gateway init failed: {exc}")
        return None, None, None


# ---------------------------------------------------------------------------
# LLM-driven brain
# ---------------------------------------------------------------------------

_BRAIN_SYSTEM = """你是飞书机器人，帮用户控制OpenCode开发环境。理解自然语言（可能有错别字），返回JSON行动计划。

上下文：mode={mode}, workspace={active_workspace}, projects={projects}
历史：{history}

用户：{user_text}

返回JSON：
{{"action":"...","params":{{}},"confirm_required":false,"confirm_summary":"","reply":"","reasoning":""}}

actions: start_workspace|stop_workspace|send_task|show_status|show_help|chat|clarify
规则：stop_workspace需确认；长消息或破坏性操作需确认
注意：推断用户意图，只返回JSON"""

_BRAIN_FALLBACK_ACTIONS = {
    "帮助": ("show_help", {}),
    "help": ("show_help", {}),
    "状态": ("show_status", {}),
    "status": ("show_status", {}),
    # Phase 0: Self-update commands
    "更新": (
        "self_update",
        {"trigger_source": "manual", "reason": "User requested update"},
    ),
    "更新bot": (
        "self_update",
        {"trigger_source": "manual", "reason": "User requested bot update"},
    ),
    "更新 bots": (
        "self_update",
        {"trigger_source": "manual", "reason": "User requested bot update"},
    ),
    "update": (
        "self_update",
        {"trigger_source": "manual", "reason": "User requested update"},
    ),
    "update bot": (
        "self_update",
        {"trigger_source": "manual", "reason": "User requested bot update"},
    ),
    "升级": (
        "self_update",
        {"trigger_source": "manual", "reason": "User requested upgrade"},
    ),
    "升级bot": (
        "self_update",
        {"trigger_source": "manual", "reason": "User requested bot upgrade"},
    ),
    "restart": (
        "self_update",
        {"trigger_source": "manual", "reason": "User requested restart"},
    ),
    "restart bot": (
        "self_update",
        {"trigger_source": "manual", "reason": "User requested bot restart"},
    ),
    "重启": (
        "self_update",
        {"trigger_source": "manual", "reason": "User requested restart"},
    ),
    "重启bot": (
        "self_update",
        {"trigger_source": "manual", "reason": "User requested bot restart"},
    ),
    "自更新": (
        "self_update",
        {"trigger_source": "manual", "reason": "User requested self-update"},
    ),
}


class BotBrain:
    """LLM-driven intent recognizer for the Feishu bot.

    Converts raw user text + conversation context into a structured ActionPlan.
    Falls back to deterministic keyword matching when LLM is unavailable.
    """

    _CONFIRM_TTL = timedelta(minutes=5)

    def __init__(
        self,
        projects: List[Dict[str, str]],
        llm_provider: Optional[str] = None,
        llm_api_key: Optional[str] = None,
    ):
        self.projects = projects
        self._gw, self._provider, self._model_cfg = _make_gateway(
            llm_provider, llm_api_key
        )
        if self._gw:
            m, _ = self._model_cfg
            print(f"[BotBrain] LLM ready: {self._provider}/{m}")
        else:
            print("[BotBrain] No LLM API key found — keyword-only mode")

    def think(self, text: str, ctx: ConversationContext) -> ActionPlan:
        """Main entry: text + context → ActionPlan.

        渐进式意图识别策略:
        Level 1: 快速 regex/关键词匹配 (可靠、快速)
        Level 2: LLM 语义理解 (复杂意图)
        Level 3: 优雅降级到通用 chat
        """
        # Level 1: 先尝试确定性匹配
        plan = self._think_deterministic(text, ctx)
        if plan.action != "chat":
            # 确定性匹配成功，直接返回
            print(f"[BotBrain] Level 1 (regex) matched: {plan.action}")
            return plan

        # Level 2: 简单匹配失败，且用户可能说了复杂内容，尝试 LLM
        if self._gw:
            try:
                plan = asyncio.run(self._think_llm(text, ctx))
                if plan.action != "chat":
                    print(f"[BotBrain] Level 2 (LLM) matched: {plan.action}")
                    return plan
                # LLM 返回 chat，说明它也没理解，继续降级
            except Exception as exc:
                print(f"[BotBrain] LLM failed: {exc}")

        # Level 3: 优雅降级 - 返回通用 chat
        print(f"[BotBrain] Level 3 (fallback to chat)")
        return self._create_fallback_plan(text, ctx)

    def _create_fallback_plan(self, text: str, ctx: ConversationContext) -> ActionPlan:
        """创建优雅降级的 chat 响应。"""
        # 根据当前状态提供更智能的提示
        if ctx.mode == "coding" and ctx.active_workspace:
            return ActionPlan(
                action="send_task",
                params={"task": text, "path": ctx.active_workspace},
            )

        return ActionPlan(
            action="chat",
            reply=(
                "我可以帮你控制 OpenCode 开发环境。试试这些指令：\n"
                "• 打开 sailzen\n"
                "• 启动 ~/projects/myapp\n"
                "• 查看状态\n"
                "• 帮我写代码...\n\n"
                "或者直接描述你需要做什么。"
            ),
        )

    def build_confirmation(
        self,
        action: str,
        params: Dict[str, Any],
        summary: str,
        ctx: ConversationContext,
    ) -> PendingConfirmation:
        return PendingConfirmation(
            action=action,
            params=params,
            summary=summary,
            expires_at=datetime.now() + self._CONFIRM_TTL,
        )

    def check_confirmation_reply(self, text: str) -> Optional[bool]:
        """Return True=confirmed, False=cancelled, None=unrelated."""
        t = text.strip().lower()
        if t in _CONFIRM_WORDS:
            return True
        if t in _CANCEL_WORDS:
            return False
        return None

    async def _think_llm(
        self,
        text: str,
        ctx: ConversationContext,
        chat_id: Optional[str] = None,
        max_retries: int = 2,
    ) -> ActionPlan:
        # FIX: Import moved to top level
        start_time = time.time()
        slugs = [p.get("slug", p.get("label", "")) for p in self.projects]
        prompt = _BRAIN_SYSTEM.format(
            mode=ctx.mode,
            active_workspace=ctx.active_workspace or "None",
            projects=", ".join(slugs) if slugs else "None",
            history=ctx.history_text() or "(无历史)",
            user_text=text,
        )

        # Log the prompt for debugging
        chat_prefix = f"[{chat_id}] " if chat_id else ""
        print(f"\n{'=' * 60}")
        print(f"{chat_prefix}[LLM] Prompt ({len(prompt)} chars):")
        print(f"{prompt[:500]}{'...' if len(prompt) > 500 else ''}")
        print(f"{'=' * 60}")

        model, temp = self._model_cfg
        config = LLMExecutionConfig(
            provider=self._provider,
            model=model,
            temperature=temp,
            max_tokens=512,
            enable_caching=False,
            timeout=30,  # 设置30秒超时，避免长时间等待
        )

        last_error = None
        # 重试循环
        for attempt in range(max_retries + 1):
            try:
                result = await self._gw.execute(prompt, config)
                raw = result.content.strip()
                elapsed = time.time() - start_time

                # 检查空响应
                if not raw:
                    print(
                        f"{chat_prefix}[LLM] WARNING: Empty response (attempt {attempt + 1}/{max_retries + 1})"
                    )
                    if attempt < max_retries:
                        print(f"{chat_prefix}[LLM] Retrying in 1s...")
                        await asyncio.sleep(1)
                        continue
                    else:
                        # 所有重试后仍空，优雅降级
                        return ActionPlan(action="chat")

                # Log the raw response
                print(
                    f"{chat_prefix}[LLM] Response ({elapsed:.2f}s, {len(raw)} chars, attempt {attempt + 1}):"
                )
                print(f"{raw[:800]}{'...' if len(raw) > 800 else ''}")

                # Clean up markdown code blocks
                raw_cleaned = re.sub(r"^```(?:json)?\s*", "", raw)
                raw_cleaned = re.sub(r"\s*```$", "", raw_cleaned)

                data = self._parse_llm_json(raw_cleaned, chat_id=chat_id)

                action = data.get("action", "chat")
                print(f"{chat_prefix}[LLM] Parsed action: {action}")

                return ActionPlan(
                    action=action,
                    params=data.get("params", {}),
                    confirm_required=bool(data.get("confirm_required", False)),
                    confirm_summary=data.get("confirm_summary", ""),
                    reply=data.get("reply", ""),
                )

            except Exception as exc:
                elapsed = time.time() - start_time
                last_error = exc
                if attempt < max_retries:
                    print(
                        f"{chat_prefix}[LLM] Attempt {attempt + 1} failed after {elapsed:.2f}s: {exc}"
                    )
                    print(f"{chat_prefix}[LLM] Retrying...")
                    await asyncio.sleep(1)
                    continue
                else:
                    print(
                        f"{chat_prefix}[LLM] All {max_retries + 1} attempts failed after {elapsed:.2f}s"
                    )
                    # 不抛出异常，返回 chat action 让上层优雅降级
                    return ActionPlan(action="chat")

    async def think_with_feedback(
        self,
        text: str,
        ctx: ConversationContext,
        chat_id: str,
        message_id: str,
        agent: "FeishuBotAgent",  # noqa: F821
        use_thinking_card: bool = True,
    ) -> Tuple[ActionPlan, Optional[str]]:
        """Think with UX feedback - returns (ActionPlan, thinking_card_message_id or None).

        渐进式识别流程:
        1. 先尝试 regex 匹配 (不显示 thinking card)
        2. regex 失败才显示 thinking card 并调用 LLM
        3. LLM 失败优雅降级
        """
        # Level 1: 先尝试确定性匹配 (不显示 thinking card)
        plan = self._think_deterministic(text, ctx)
        if plan.action != "chat":
            print(f"[BotBrain] Level 1 matched (no LLM needed): {plan.action}")
            return plan, None

        # Level 2: 需要 LLM，显示 thinking card
        if use_thinking_card and self._gw:
            thinking_card = CardRenderer.progress(
                "正在理解你的意图", "AI正在分析中，请稍候..."
            )
            thinking_mid = agent._reply_card(
                message_id, thinking_card, "thinking", {"user_text": text[:50]}
            )
        else:
            thinking_mid = None

        try:
            if self._gw:
                plan = await self._think_llm(text, ctx, chat_id=chat_id)
                if plan.action != "chat":
                    print(f"[BotBrain] Level 2 matched (LLM): {plan.action}")
                    return plan, thinking_mid
                # LLM 返回 chat，说明它也没理解
                print(f"[BotBrain] Level 2 (LLM) returned chat, falling back")

            # 没有 LLM 或 LLM 也没理解，优雅降级
            plan = self._create_fallback_plan(text, ctx)
            return plan, thinking_mid

        except Exception as exc:
            print(f"[{chat_id}] LLM failed: {exc}")
            # 更新 thinking card 显示降级
            if thinking_mid:
                fallback_card = CardRenderer.result(
                    "已切换到备用模式",
                    "AI理解遇到了问题，正在使用备用模式为你服务。",
                    success=True,
                )
                agent._update_card(thinking_mid, fallback_card)
            # 返回降级 plan
            plan = self._create_fallback_plan(text, ctx)
            return plan, thinking_mid

    def _parse_llm_json(self, raw: str, chat_id: Optional[str] = None) -> dict:
        """Parse JSON from LLM response with robust error handling.

        LLMs often return malformed JSON with:
        - Single quotes instead of double quotes
        - Trailing commas
        - Missing quotes around property names
        - Python-style True/False/None instead of true/false/null
        """
        # FIX: Import moved to top level
        chat_prefix = f"[{chat_id}] " if chat_id else ""

        # Try standard JSON parsing first
        try:
            return json.loads(raw)
        except json.JSONDecodeError as e:
            print(f"{chat_prefix}[LLM] JSON parse failed (attempt 1): {e}")

        # Fix common LLM JSON issues
        cleaned = raw

        # Replace Python-style booleans and None with JSON equivalents
        cleaned = re.sub(r"\bTrue\b", "true", cleaned)
        cleaned = re.sub(r"\bFalse\b", "false", cleaned)
        cleaned = re.sub(r"\bNone\b", "null", cleaned)

        # Try JSON parsing again after boolean fixes
        try:
            result = json.loads(cleaned)
            print(f"{chat_prefix}[LLM] JSON parsed after boolean fix")
            return result
        except json.JSONDecodeError as e:
            print(
                f"{chat_prefix}[LLM] JSON parse failed (attempt 2 after boolean fix): {e}"
            )

        # Try to use ast.literal_eval as a fallback for Python dict-like structures
        try:
            # This handles single quotes and other Python syntax
            result = ast.literal_eval(cleaned)
            if isinstance(result, dict):
                print(f"{chat_prefix}[LLM] Parsed with ast.literal_eval")
                return result
        except (ValueError, SyntaxError) as e:
            print(f"{chat_prefix}[LLM] ast.literal_eval failed: {e}")

        # Last resort: try to extract JSON-like structure with regex
        # Look for key-value pairs and reconstruct
        try:
            # Simple pattern to extract action and other fields
            pattern = r'["\']?action["\']?\s*[:=]\s*["\']([^"\']+)["\']'
            action_match = re.search(pattern, cleaned, re.IGNORECASE)
            if action_match:
                print(
                    f"{chat_prefix}[LLM] Extracted action via regex: {action_match.group(1)}"
                )
                return {"action": action_match.group(1)}
        except Exception as e:
            print(f"{chat_prefix}[LLM] Regex extraction failed: {e}")

        # If all parsing fails, return a default action (graceful degradation)
        print(f"{chat_prefix}[LLM] All parsing attempts failed. Raw: {raw[:300]}")
        return {"action": "chat"}

    def _think_deterministic(self, text: str, ctx: ConversationContext) -> ActionPlan:
        """确定性意图识别 - 基于当前状态进行不同的处理逻辑。

        状态1 - 不在工作区（idle）:
            正常执行三级意图匹配（关键词 → LLM → 降级）

        状态2 - 在工作区（coding）:
            绝大部分消息直接转发给OpenCode
            只有以感叹号开头的消息才在Bot层执行控制指令
        """
        t = text.lower().strip()

        # === 状态2：在工作区 ===
        if ctx.mode == "coding" and ctx.active_workspace:
            # 感叹号开头的消息 -> 在Bot层执行控制指令（去掉感叹号后的内容）
            if t.startswith("!") or t.startswith("！"):
                cmd_text = text.lstrip("!！").strip()
                cmd_lower = cmd_text.lower()

                # 在感叹号模式下，解析控制指令
                # 完全匹配精确指令
                for kw, (action, params) in _BRAIN_FALLBACK_ACTIONS.items():
                    if cmd_lower == kw:
                        return ActionPlan(action=action, params=params)

                # 状态查询指令（!状态 或 !status）
                if cmd_lower in ["状态", "status", "s"]:
                    return ActionPlan(action="show_status", params={})

                # 解析工作区控制指令（启动、停止、切换等）
                if any(
                    k in cmd_lower for k in ["启动", "打开", "开启", "start", "open"]
                ):
                    path = extract_path_from_text(cmd_text, self.projects)
                    return ActionPlan(action="start_workspace", params={"path": path})

                if any(
                    k in cmd_lower for k in ["停止", "关闭", "结束", "stop", "kill"]
                ):
                    path = extract_path_from_text(cmd_text, self.projects)
                    return ActionPlan(
                        action="stop_workspace",
                        params={"path": path},
                        confirm_required=True,
                        confirm_summary=f"停止 {'所有会话' if not path else path}",
                    )

                if any(
                    k in cmd_lower for k in ["切换", "使用", "进入", "switch", "use"]
                ):
                    path = extract_path_from_text(cmd_text, self.projects)
                    if path:
                        return ActionPlan(
                            action="switch_workspace", params={"path": path}
                        )

                # 感叹号开头但不认识的指令 -> 提示用户
                return ActionPlan(
                    action="chat",
                    reply=f"未知的控制指令: {cmd_text}\n\n可用的控制指令:\n• !状态 / !status / !s - 查看当前状态\n• !启动 <项目> - 启动工作区\n• !停止 - 停止工作区\n• !切换 <项目> - 切换工作区\n• !帮助 / !help - 显示帮助",
                )

            # 非感叹号开头的消息 -> 直接转发给OpenCode
            return ActionPlan(
                action="send_task", params={"task": text, "path": ctx.active_workspace}
            )

        # === 状态1：不在工作区（idle）===
        # Level 1: 精确匹配（完全匹配，无歧义）
        for kw, (action, params) in _BRAIN_FALLBACK_ACTIONS.items():
            if t == kw:
                return ActionPlan(action=action, params=params)

        # 启动指令（进入coding模式）
        if any(k in t for k in ["start", "启动", "开启", "打开", "open"]):
            path = extract_path_from_text(text, self.projects)
            if path:
                return ActionPlan(action="start_workspace", params={"path": path})

        # 停止指令
        if any(k in t for k in ["stop", "停止", "关闭", "结束", "kill"]):
            path = extract_path_from_text(text, self.projects)
            return ActionPlan(
                action="stop_workspace",
                params={"path": path},
                confirm_required=True,
                confirm_summary=f"停止 {'所有会话' if not path else path}",
            )

        # 切换工作区指令
        if any(
            k in t
            for k in ["使用", "进入", "切换到", "切到", "use", "switch to", "enter"]
        ):
            path = extract_path_from_text(text, self.projects)
            if path:
                return ActionPlan(action="switch_workspace", params={"path": path})

        # 返回 chat action 表示需要 LLM 处理（Level 2）
        return ActionPlan(action="chat")
