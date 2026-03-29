# -*- coding: utf-8 -*-
# @file brain.py
# @brief LLM驱动的意图识别大脑
# @author sailing-innocent
# @date 2026-03-25
# @version 1.0
# ---------------------------------
"""LLM-driven intent recognizer for the Feishu bot.

Converts raw user text + conversation context into a structured ActionPlan.
Falls back to deterministic keyword matching when LLM is unavailable.
"""

import ast
import asyncio
import json
import os
import re
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from context import ConversationContext, PendingConfirmation
from session_manager import extract_path_from_text, resolve_path


@dataclass
class ActionPlan:
    """Structured action plan from intent recognition."""

    action: str
    params: Dict[str, Any] = field(default_factory=dict)
    confirm_required: bool = False
    confirm_summary: str = ""
    reply: str = ""


# Fallback action mappings for deterministic mode
_BRAIN_FALLBACK_ACTIONS = {
    "帮助": ("show_help", {}),
    "help": ("show_help", {}),
    "状态": ("show_status", {}),
    "status": ("show_status", {}),
    "导入小说": ("import_text", {}),
    "导入文本": ("import_text", {}),
    "import text": ("import_text", {}),
    "import novel": ("import_text", {}),
}

# Confirmation word sets
_CONFIRM_WORDS = frozenset(
    [
        "确认",
        "确定",
        "是",
        "yes",
        "ok",
        "好",
        "好的",
        "执行",
        "继续",
        "confirm",
        "y",
    ]
)
_CANCEL_WORDS = frozenset(
    [
        "取消",
        "算了",
        "不",
        "no",
        "cancel",
        "停",
        "别",
        "n",
    ]
)

# LLM system prompt template
_BRAIN_SYSTEM = """你是飞书机器人，帮用户控制OpenCode开发环境。理解自然语言（可能有错别字），返回JSON行动计划。

上下文：mode={mode}, workspace={active_workspace}, projects={projects}
历史：{history}

用户：{user_text}

返回JSON：
{{"action":"...","params":{{}},"confirm_required":false,"confirm_summary":"","reply":"","reasoning":""}}

actions: start_workspace|stop_workspace|send_task|import_text|show_status|show_help|chat|clarify
import_text: 用户想导入小说/文本到系统。params需要file_name(文件名)和可选的title(标题)、author(作者)。books目录下的txt文件可以导入。
规则：stop_workspace需确认；长消息或破坏性操作需确认；import_text不需确认
注意：推断用户意图，只返回JSON"""


def _make_gateway(
    config_provider: Optional[str] = None, config_api_key: Optional[str] = None
):
    """Build a minimal LLMGateway from environment variables or config."""
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    try:
        from sail_server.utils.llm.gateway import LLMGateway
        from sail_server.utils.llm.providers import ProviderConfig
        from sail_server.utils.llm.available_providers import (
            DEFAULT_LLM_PROVIDER,
            DEFAULT_LLM_MODEL,
            DEFAULT_LLM_CONFIG,
        )

        provider_env_keys = {
            "moonshot": "MOONSHOT_API_KEY",
            "openai": "OPENAI_API_KEY",
            "google": "GOOGLE_API_KEY",
            "deepseek": "DEEPSEEK_API_KEY",
            "anthropic": "ANTHROPIC_API_KEY",
        }

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

        for pname, env_key in provider_env_keys.items():
            if pname in registered:
                continue
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


class BotBrain:
    """LLM-driven intent recognizer for the Feishu bot."""

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
            print("[BotBrain] No LLM API key found — falling back to keyword dispatch")

    def think(self, text: str, ctx: ConversationContext) -> ActionPlan:
        """Main entry: text + context → ActionPlan."""
        if self._gw:
            try:
                return asyncio.run(self._think_llm(text, ctx))
            except Exception as exc:
                print(f"[BotBrain] LLM call failed, using fallback: {exc}")
        return self._think_deterministic(text, ctx)

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
        from sail_server.utils.llm.gateway import LLMExecutionConfig

        start_time = time.time()
        slugs = [p.get("slug", p.get("label", "")) for p in self.projects]
        prompt = _BRAIN_SYSTEM.format(
            mode=ctx.mode,
            active_workspace=ctx.active_workspace or "None",
            projects=", ".join(slugs) if slugs else "None",
            history=ctx.history_text() or "(无历史)",
            user_text=text,
        )

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
            timeout=30,
        )

        for attempt in range(max_retries + 1):
            try:
                result = await self._gw.execute(prompt, config)
                raw = result.content.strip()
                elapsed = time.time() - start_time

                if not raw:
                    print(
                        f"{chat_prefix}[LLM] WARNING: Empty response (attempt {attempt + 1}/{max_retries + 1})"
                    )
                    if attempt < max_retries:
                        print(f"{chat_prefix}[LLM] Retrying in 1s...")
                        await asyncio.sleep(1)
                        continue
                    else:
                        raise Exception("LLM returned empty response after all retries")

                print(
                    f"{chat_prefix}[LLM] Response ({elapsed:.2f}s, {len(raw)} chars, attempt {attempt + 1}):"
                )
                print(f"{raw[:800]}{'...' if len(raw) > 800 else ''}")

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
                if attempt < max_retries:
                    print(
                        f"{chat_prefix}[LLM] Attempt {attempt + 1} failed after {elapsed:.2f}s: {exc}"
                    )
                    print(f"{chat_prefix}[LLM] Retrying...")
                    await asyncio.sleep(1)
                    continue
                else:
                    print(
                        f"{chat_prefix}[LLM] ERROR after {elapsed:.2f}s (all {max_retries + 1} attempts failed): {type(exc).__name__}: {exc}"
                    )
                    import traceback

                    traceback.print_exc()
                    raise

    def _parse_llm_json(self, raw: str, chat_id: Optional[str] = None) -> dict:
        """Parse JSON from LLM response with robust error handling."""
        chat_prefix = f"[{chat_id}] " if chat_id else ""

        try:
            return json.loads(raw)
        except json.JSONDecodeError as e:
            print(f"{chat_prefix}[LLM] JSON parse failed (attempt 1): {e}")

        cleaned = raw
        cleaned = re.sub(r"\bTrue\b", "true", cleaned)
        cleaned = re.sub(r"\bFalse\b", "false", cleaned)
        cleaned = re.sub(r"\bNone\b", "null", cleaned)

        try:
            result = json.loads(cleaned)
            print(f"{chat_prefix}[LLM] JSON parsed after boolean fix")
            return result
        except json.JSONDecodeError as e:
            print(
                f"{chat_prefix}[LLM] JSON parse failed (attempt 2 after boolean fix): {e}"
            )

        try:
            result = ast.literal_eval(cleaned)
            if isinstance(result, dict):
                print(f"{chat_prefix}[LLM] Parsed with ast.literal_eval")
                return result
        except (ValueError, SyntaxError) as e:
            print(f"{chat_prefix}[LLM] ast.literal_eval failed: {e}")

        try:
            pattern = r'["\']?action["\']?\s*[:=]\s*["\']([^"\']+)["\']'
            action_match = re.search(pattern, cleaned, re.IGNORECASE)
            if action_match:
                print(
                    f"{chat_prefix}[LLM] Extracted action via regex: {action_match.group(1)}"
                )
                return {"action": action_match.group(1)}
        except Exception as e:
            print(f"{chat_prefix}[LLM] Regex extraction failed: {e}")

        print(f"{chat_prefix}[LLM] All parsing attempts failed. Raw: {raw[:300]}")
        return {"action": "chat", "reply": "抱歉，我处理请求时遇到了技术问题。"}

    def _think_deterministic(self, text: str, ctx: ConversationContext) -> ActionPlan:
        """Fallback deterministic intent recognition using keyword matching."""
        t = text.lower().strip()

        for kw, (action, params) in _BRAIN_FALLBACK_ACTIONS.items():
            if kw in t:
                return ActionPlan(action=action, params=params)

        # Quick workspace switch commands
        switch_keywords = [
            "使用",
            "进入",
            "切换到",
            "切到",
            "use",
            "switch to",
            "enter",
        ]
        if any(k in t for k in switch_keywords):
            path = extract_path_from_text(text, self.projects)
            if path:
                ctx.mode = "coding"
                ctx.active_workspace = path
                return ActionPlan(
                    action="chat",
                    reply=f"已切换到工作区：{Path(path).name}\n现在可以直接发送指令给这个工作区。",
                )

        if any(k in t for k in ["start", "启动", "开启", "打开", "open"]):
            path = extract_path_from_text(text, self.projects)
            return ActionPlan(action="start_workspace", params={"path": path})

        if any(k in t for k in ["导入", "import"]) and any(
            k in t for k in ["小说", "文本", "txt", "text", "novel", "书"]
        ):
            file_name = self._extract_file_name(text)
            return ActionPlan(action="import_text", params={"file_name": file_name})

        if any(k in t for k in ["stop", "停止", "关闭", "结束", "kill"]):
            path = extract_path_from_text(text, self.projects)
            return ActionPlan(
                action="stop_workspace",
                params={"path": path},
                confirm_required=True,
                confirm_summary=f"停止 {'所有会话' if not path else path}",
            )

        if ctx.mode == "coding" and ctx.active_workspace:
            return ActionPlan(
                action="send_task", params={"task": text, "path": ctx.active_workspace}
            )

        if any(
            k in t
            for k in [
                "code",
                "写",
                "实现",
                "帮我",
                "task",
                "任务",
                "帮",
                "修",
                "fix",
                "add",
                "implement",
            ]
        ):
            path = extract_path_from_text(text, self.projects)
            return ActionPlan(action="send_task", params={"task": text, "path": path})

        return ActionPlan(
            action="chat",
            reply=(
                "我理解你说的可能是一个开发任务，但我需要知道目标工作区。\n"
                "可以说：'启动 sailzen' 或 '使用 sailzen' 或 '进入 ~/projects/myapp'"
            ),
        )

    def _extract_file_name(self, text: str) -> Optional[str]:
        """Extract a .txt file name from user text."""
        match = re.search(r"[\w\u4e00-\u9fff\-\.]+\.txt", text)
        if match:
            return match.group()
        for quote_char in ["《", "》", '"', '"', '"', "'"]:
            text = text.replace(quote_char, '"')
        match = re.search(r'"([^"]+)"', text)
        if match:
            return match.group(1)
        return None
