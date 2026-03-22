# -*- coding: utf-8 -*-
# @file intent_router.py
# @brief LLM-backed intent router for Feishu commands
# @author sailing-innocent
# @date 2026-03-22
# @version 1.0
# ---------------------------------
"""Intent routing layer for the Feishu remote control system.

This module provides an LLM-backed intent router that transforms raw user
input into structured action plans with confidence, risk level, and
clarification state. It also provides deterministic fallback handlers
for when LLM routing is unavailable.
"""

import json
import re
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from enum import Enum, auto

from sail_server.utils.llm.gateway import LLMGateway, LLMExecutionConfig
from sail_server.utils.llm.available_providers import (
    DEFAULT_LLM_PROVIDER,
    DEFAULT_LLM_MODEL,
    DEFAULT_LLM_CONFIG,
)


class RiskLevel(Enum):
    """Risk levels for actions."""

    SAFE = "safe"  # Read-only operations
    LOW = "low"  # Non-destructive changes
    MEDIUM = "medium"  # Moderate impact
    HIGH = "high"  # Destructive operations
    CRITICAL = "critical"  # Irreversible/high-stakes


class IntentCategory(Enum):
    """Categories of user intent."""

    SESSION_CONTROL = "session_control"  # start, stop, restart, recover
    CODE_REQUEST = "code_request"  # code generation, refactoring
    MONITORING = "monitoring"  # status, logs, health
    RECOVERY = "recovery"  # retry, resume, rollback
    NAVIGATION = "navigation"  # list, select, help
    GIT_OPERATION = "git_operation"  # git commands
    UNKNOWN = "unknown"


@dataclass
class IntentPlan:
    """Structured intent plan output from the router.

    This is the primary output of intent routing, representing a
    validated, structured action plan ready for execution or confirmation.
    """

    intent_type: str
    target_workspace: Optional[str]
    target_session: Optional[str]
    requested_action: str
    parameters: Dict[str, Any] = field(default_factory=dict)
    risk_level: RiskLevel = RiskLevel.SAFE
    confidence: float = 0.0  # 0.0 to 1.0
    clarification_needed: bool = False
    clarification_prompt: Optional[str] = None
    requires_confirmation: bool = False
    normalized_draft: Optional[str] = None  # Operator-visible cleaned text
    raw_input: str = ""  # Original input for audit

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "intent_type": self.intent_type,
            "target_workspace": self.target_workspace,
            "target_session": self.target_session,
            "requested_action": self.requested_action,
            "parameters": self.parameters,
            "risk_level": self.risk_level.value,
            "confidence": self.confidence,
            "clarification_needed": self.clarification_needed,
            "clarification_prompt": self.clarification_prompt,
            "requires_confirmation": self.requires_confirmation,
            "normalized_draft": self.normalized_draft,
            "raw_input": self.raw_input,
        }


@dataclass
class NormalizationDraft:
    """Normalization draft for messy/speech-derived text.

    Represents a cleaned, structured version of user input with
    uncertainty markers for operator review.
    """

    cleaned_text: str
    intent_summary: str
    target_workspace: Optional[str]
    target_session: Optional[str]
    action_description: str
    uncertain_tokens: List[str] = field(default_factory=list)
    unresolved_slots: List[str] = field(default_factory=list)
    confidence: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "cleaned_text": self.cleaned_text,
            "intent_summary": self.intent_summary,
            "target_workspace": self.target_workspace,
            "target_session": self.target_session,
            "action_description": self.action_description,
            "uncertain_tokens": self.uncertain_tokens,
            "unresolved_slots": self.unresolved_slots,
            "confidence": self.confidence,
        }


class IntentRouter:
    """LLM-backed intent router for remote development commands.

    Transforms raw user input into structured intent plans with:
    - Template-based normalization for messy text
    - Confidence scoring
    - Risk classification
    - Clarification detection
    - Deterministic fallback for common/safe actions
    """

    # Risk classification for actions
    ACTION_RISKS = {
        "status": RiskLevel.SAFE,
        "list": RiskLevel.SAFE,
        "view": RiskLevel.SAFE,
        "help": RiskLevel.SAFE,
        "start_session": RiskLevel.LOW,
        "restart_session": RiskLevel.MEDIUM,
        "code_request": RiskLevel.LOW,
        "stop_session": RiskLevel.MEDIUM,
        "git_status": RiskLevel.SAFE,
        "git_pull": RiskLevel.MEDIUM,
        "git_commit": RiskLevel.MEDIUM,
        "git_push": RiskLevel.HIGH,
        "recover_session": RiskLevel.MEDIUM,
        "force_stop": RiskLevel.HIGH,
        "delete_workspace": RiskLevel.CRITICAL,
    }

    # Actions that always require confirmation
    CONFIRMATION_REQUIRED = {
        "git_push",
        "force_stop",
        "delete_workspace",
        "reset_session",
    }

    def __init__(
        self,
        llm_gateway: Optional[LLMGateway] = None,
        enable_llm_routing: bool = True,
        confidence_threshold: float = 0.7,
    ):
        """Initialize the intent router.

        Args:
            llm_gateway: LLM gateway instance (created if None)
            enable_llm_routing: Whether to use LLM for routing
            confidence_threshold: Minimum confidence for auto-execution
        """
        self.llm_gateway = llm_gateway or LLMGateway()
        self.enable_llm_routing = enable_llm_routing
        self.confidence_threshold = confidence_threshold

    async def route(
        self, text: str, sender_id: str, context: Optional[Dict] = None
    ) -> IntentPlan:
        """Route user input to an intent plan.

        This is the main entry point for intent routing. It attempts
        LLM-based routing first, then falls back to deterministic
        handlers if needed.

        Args:
            text: User input text
            sender_id: User identifier
            context: Optional context (workspaces, sessions, etc.)

        Returns:
            Structured intent plan
        """
        context = context or {}

        # Try deterministic routing first for efficiency
        deterministic_plan = self._try_deterministic_route(text)
        if deterministic_plan:
            return deterministic_plan

        # Use LLM routing for complex/natural language inputs
        if self.enable_llm_routing:
            try:
                return await self._route_with_llm(text, sender_id, context)
            except Exception as e:
                # Fall back to clarification on LLM failure
                return IntentPlan(
                    intent_type="unknown",
                    target_workspace=None,
                    target_session=None,
                    requested_action="unknown",
                    confidence=0.0,
                    clarification_needed=True,
                    clarification_prompt="抱歉，我没能理解您的请求。请尝试使用更清晰的指令，或从菜单中选择操作。",
                    raw_input=text,
                )

        # No routing possible
        return IntentPlan(
            intent_type="unknown",
            target_workspace=None,
            target_session=None,
            requested_action="unknown",
            confidence=0.0,
            clarification_needed=True,
            clarification_prompt="我不太明白您的意思。可用指令：查看状态、启动会话、停止会话、代码请求等。",
            raw_input=text,
        )

    async def normalize_text(
        self, text: str, is_voice_input: bool = False
    ) -> NormalizationDraft:
        """Normalize messy/voice-derived text into structured draft.

        Args:
            text: Raw input text
            is_voice_input: Whether text came from speech-to-text

        Returns:
            Normalized draft with uncertainty markers
        """
        # For MVP-2: Simple rule-based normalization
        # In production, this would use LLM-based normalization

        # Clean up text
        cleaned = self._clean_text(text, is_voice_input)

        # Extract potential workspace/session references
        workspace = self._extract_workspace_reference(cleaned)
        session = self._extract_session_reference(cleaned)

        # Detect uncertain tokens (simplified heuristic)
        uncertain = []
        if is_voice_input:
            # Mark potential transcription errors
            uncertain = self._detect_speech_errors(cleaned)

        # Generate intent summary
        intent_summary = self._generate_intent_summary(cleaned)
        action_desc = self._generate_action_description(cleaned)

        # Calculate confidence based on cleanup quality
        confidence = self._calculate_normalization_confidence(
            text, cleaned, is_voice_input
        )

        return NormalizationDraft(
            cleaned_text=cleaned,
            intent_summary=intent_summary,
            target_workspace=workspace,
            target_session=session,
            action_description=action_desc,
            uncertain_tokens=uncertain,
            confidence=confidence,
        )

    def _try_deterministic_route(self, text: str) -> Optional[IntentPlan]:
        """Try to route using deterministic patterns.

        Handles common commands without LLM overhead.

        NOTE: Slash commands (e.g., /start) are intentionally NOT supported
        as they require switching to symbol keyboard on mobile, creating poor UX.
        Use natural language or card buttons instead.
        """
        text_lower = text.lower().strip()

        # Simple keyword matching for common intents
        patterns = [
            (r"^(status|状态|查看状态|系统状态)", "monitoring", "status"),
            (r"^(help|帮助|怎么用|指令)", "navigation", "help"),
            (r"^(list|列表|工作区|项目列表)", "navigation", "list_workspaces"),
            (r"^(home|主页|首页|返回)", "navigation", "home"),
        ]

        for pattern, intent_type, action in patterns:
            if re.search(pattern, text_lower):
                return IntentPlan(
                    intent_type=intent_type,
                    target_workspace=None,
                    target_session=None,
                    requested_action=action,
                    confidence=0.9,
                    risk_level=self.ACTION_RISKS.get(action, RiskLevel.SAFE),
                    requires_confirmation=action in self.CONFIRMATION_REQUIRED,
                    raw_input=text,
                )

        # Session control patterns (Chinese)
        if any(kw in text_lower for kw in ["启动", "start", "开启", "打开"]):
            workspace = self._extract_workspace_reference(text)
            return IntentPlan(
                intent_type="session_control",
                target_workspace=workspace,
                target_session=None,
                requested_action="start_session",
                parameters={"workspace": workspace},
                confidence=0.8,
                risk_level=RiskLevel.LOW,
                raw_input=text,
            )

        if any(kw in text_lower for kw in ["停止", "stop", "关闭", "结束"]):
            return IntentPlan(
                intent_type="session_control",
                target_workspace=None,
                target_session=None,
                requested_action="stop_session",
                confidence=0.8,
                risk_level=RiskLevel.MEDIUM,
                requires_confirmation=True,
                raw_input=text,
            )

        if any(kw in text_lower for kw in ["重启", "restart", "重新启动"]):
            return IntentPlan(
                intent_type="session_control",
                target_workspace=None,
                target_session=None,
                requested_action="restart_session",
                confidence=0.8,
                risk_level=RiskLevel.MEDIUM,
                requires_confirmation=True,
                raw_input=text,
            )

        return None

    async def _route_with_llm(
        self, text: str, sender_id: str, context: Dict[str, Any]
    ) -> IntentPlan:
        """Route using LLM-based intent classification."""
        # Build prompt for intent classification
        prompt = self._build_intent_prompt(text, context)

        # Execute LLM call
        config = LLMExecutionConfig(
            provider=DEFAULT_LLM_PROVIDER,
            model=DEFAULT_LLM_MODEL,
            temperature=DEFAULT_LLM_CONFIG["temperature"],
            max_tokens=DEFAULT_LLM_CONFIG["max_tokens"],
            system_prompt=self._get_system_prompt(),
        )

        result = await self.llm_gateway.execute(prompt, config)

        # Parse LLM response
        try:
            parsed = json.loads(result.content)
            return self._llm_response_to_plan(parsed, text)
        except json.JSONDecodeError:
            # LLM didn't return valid JSON, return clarification
            return IntentPlan(
                intent_type="unknown",
                target_workspace=None,
                target_session=None,
                requested_action="unknown",
                confidence=0.0,
                clarification_needed=True,
                clarification_prompt="抱歉，我没理解您的请求。请重新描述或使用简单指令。",
                raw_input=text,
            )

    def _build_intent_prompt(self, text: str, context: Dict) -> str:
        """Build the intent classification prompt."""
        workspaces = context.get("workspaces", [])
        active_sessions = context.get("active_sessions", [])

        prompt = f"""Analyze this user request for a remote development control system:

User input: "{text}"

Available workspaces: {json.dumps([w.get("name") for w in workspaces], ensure_ascii=False)}
Active sessions: {json.dumps([s.get("id") for s in active_sessions])}

Classify the intent and return a JSON object with:
- intent_type: one of [session_control, code_request, monitoring, recovery, navigation, git_operation, unknown]
- requested_action: specific action name
- target_workspace: workspace name if specified, else null
- target_session: session id if specified, else null
- parameters: additional parameters as dict
- confidence: 0.0 to 1.0
- risk_level: one of [safe, low, medium, high, critical]
- requires_confirmation: true/false
- clarification_needed: true if unclear
- clarification_prompt: question to ask if clarification needed

Response (JSON only):"""

        return prompt

    def _get_system_prompt(self) -> str:
        """Get the system prompt for intent classification."""
        return """You are an intent classifier for a remote development control system.
Your task is to analyze user requests and classify them into structured intents.

Be conservative with risk classification:
- SAFE: read-only operations (status, list, view)
- LOW: non-destructive changes (start session, code request)
- MEDIUM: state changes (stop, restart, git pull)
- HIGH: destructive operations (git push, force operations)
- CRITICAL: irreversible operations (delete, reset)

Always return valid JSON. Be precise and conservative."""

    def _llm_response_to_plan(self, parsed: Dict, raw_input: str) -> IntentPlan:
        """Convert LLM response to IntentPlan."""
        action = parsed.get("requested_action", "unknown")

        return IntentPlan(
            intent_type=parsed.get("intent_type", "unknown"),
            target_workspace=parsed.get("target_workspace"),
            target_session=parsed.get("target_session"),
            requested_action=action,
            parameters=parsed.get("parameters", {}),
            risk_level=RiskLevel(parsed.get("risk_level", "safe")),
            confidence=parsed.get("confidence", 0.0),
            clarification_needed=parsed.get("clarification_needed", False),
            clarification_prompt=parsed.get("clarification_prompt"),
            requires_confirmation=parsed.get("requires_confirmation", False)
            or action in self.CONFIRMATION_REQUIRED,
            raw_input=raw_input,
        )

    # Helper methods for text normalization

    def _clean_text(self, text: str, is_voice: bool) -> str:
        """Clean and normalize text."""
        # Remove extra whitespace
        cleaned = " ".join(text.split())

        if is_voice:
            # Remove common filler words (Chinese)
            fillers = ["那个", "这个", "然后", "就是", "嗯", "啊", "呃"]
            for filler in fillers:
                cleaned = cleaned.replace(filler, " ")

            # Normalize punctuation
            cleaned = cleaned.replace("。。", "。")
            cleaned = cleaned.replace("。。", "。")
            cleaned = cleaned.replace("，，", "，")

        return " ".join(cleaned.split())  # Re-normalize whitespace

    def _extract_workspace_reference(self, text: str) -> Optional[str]:
        """Extract workspace name from text."""
        # Simple pattern matching for workspace references
        patterns = [
            r"在\s*([^\s]+)\s*(?:项目|工作区|workspace)?",
            r"(?:打开|启动|查看)\s*([^\s]+)",
            r"workspace[\s:]+([^\s]+)",
        ]

        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(1)

        return None

    def _extract_session_reference(self, text: str) -> Optional[str]:
        """Extract session reference from text."""
        # Match session IDs or references
        patterns = [
            r"session[\s:]+([^\s]+)",
            r"会话[\s:]+([^\s]+)",
        ]

        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(1)

        return None

    def _detect_speech_errors(self, text: str) -> List[str]:
        """Detect potential speech-to-text errors."""
        uncertain = []

        # Words that look like homophones or transcription errors
        # This is a simplified heuristic
        patterns = [
            r"\b\w{10,}\b",  # Very long words (likely compound errors)
            r"\d+[a-zA-Z]+\d*",  # Mixed alphanumeric that isn't standard
        ]

        for pattern in patterns:
            for match in re.finditer(pattern, text):
                uncertain.append(match.group())

        return uncertain

    def _generate_intent_summary(self, text: str) -> str:
        """Generate a brief intent summary."""
        # Simple heuristic-based summary
        if any(kw in text for kw in ["启动", "start", "打开", "开启"]):
            return "启动会话"
        elif any(kw in text for kw in ["停止", "stop", "关闭", "结束"]):
            return "停止会话"
        elif any(kw in text for kw in ["状态", "status", "查看", "信息"]):
            return "查看状态"
        elif any(kw in text for kw in ["代码", "code", "写", "生成"]):
            return "代码请求"
        else:
            return "未知意图"

    def _generate_action_description(self, text: str) -> str:
        """Generate a human-readable action description."""
        summary = self._generate_intent_summary(text)
        workspace = self._extract_workspace_reference(text)

        if workspace:
            return f"{summary} (目标: {workspace})"
        return summary

    def _calculate_normalization_confidence(
        self, raw: str, cleaned: str, is_voice: bool
    ) -> float:
        """Calculate confidence score for normalization."""
        confidence = 0.8  # Base confidence

        if is_voice:
            # Voice input reduces confidence
            confidence -= 0.1

            # Check for excessive filler removal
            reduction_ratio = len(cleaned) / max(len(raw), 1)
            if reduction_ratio < 0.5:
                confidence -= 0.2  # Too much was removed

        # Check for ambiguity
        if len(cleaned) < 5:
            confidence -= 0.2  # Very short

        # Ensure confidence is in valid range
        return max(0.0, min(1.0, confidence))


# Global router instance
_router: Optional[IntentRouter] = None


def get_intent_router() -> IntentRouter:
    """Get or create the global intent router instance."""
    global _router
    if _router is None:
        _router = IntentRouter()
    return _router
