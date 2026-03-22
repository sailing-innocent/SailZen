# -*- coding: utf-8 -*-
# @file __init__.py
# @brief Feishu Gateway module
# @author sailing-innocent
# @date 2026-03-22
# @version 2.0
# ---------------------------------
"""Feishu Bot Gateway for OpenCode integration.

This module provides the Feishu interaction pipeline with normalized
event types for handling text, voice, mentions, and card actions.
"""

from .webhook import FeishuWebhookHandler
from .message_handler import MessageHandler
from .events import (
    normalize_feishu_event,
    FeishuEvent,
    TextEvent,
    VoiceEvent,
    MentionEvent,
    CardActionEvent,
    SystemEvent,
    EventType,
    SenderInfo,
    MentionInfo,
)
from .delivery import (
    FeishuDeliveryAdapter,
    DeliveryStatus,
    get_delivery_adapter,
    configure_delivery_adapter,
)
from .cards import (
    CardRenderer,
    CardTemplate,
)
from .intent_router import (
    IntentRouter,
    IntentPlan,
    NormalizationDraft,
    RiskLevel,
    IntentCategory,
    get_intent_router,
)
from .policy import (
    PolicyEngine,
    ActionTier,
    AuthorizationResult,
    AuthorizationCheck,
    ConfirmationRecord,
    AuditRecord,
    get_policy_engine,
    configure_policy_engine,
)
from .session_orchestrator import (
    SessionOrchestrator,
    Session,
    SessionTask,
    SessionEvent,
    SessionStatus,
    TaskStatus,
    get_session_orchestrator,
)
from .observability import (
    ObservabilityService,
    Alert,
    AlertSeverity,
    AlertType,
    HealthCheckResult,
    get_observability_service,
)
from .compatibility import (
    CompatibilityLayer,
    FeatureFlag,
    RollbackMode,
    FeatureConfig,
    get_compatibility_layer,
    apply_rollout_config,
    ROLLOUT_CONFIGS,
)

__all__ = [
    "FeishuWebhookHandler",
    "MessageHandler",
    "normalize_feishu_event",
    "FeishuEvent",
    "TextEvent",
    "VoiceEvent",
    "MentionEvent",
    "CardActionEvent",
    "SystemEvent",
    "EventType",
    "SenderInfo",
    "MentionInfo",
    "FeishuDeliveryAdapter",
    "DeliveryStatus",
    "get_delivery_adapter",
    "configure_delivery_adapter",
    "CardRenderer",
    "CardTemplate",
    "IntentRouter",
    "IntentPlan",
    "NormalizationDraft",
    "RiskLevel",
    "IntentCategory",
    "get_intent_router",
    "PolicyEngine",
    "ActionTier",
    "AuthorizationResult",
    "AuthorizationCheck",
    "ConfirmationRecord",
    "AuditRecord",
    "get_policy_engine",
    "configure_policy_engine",
    "SessionOrchestrator",
    "Session",
    "SessionTask",
    "SessionEvent",
    "SessionStatus",
    "TaskStatus",
    "get_session_orchestrator",
    "ObservabilityService",
    "Alert",
    "AlertSeverity",
    "AlertType",
    "HealthCheckResult",
    "get_observability_service",
    "CompatibilityLayer",
    "FeatureFlag",
    "RollbackMode",
    "FeatureConfig",
    "get_compatibility_layer",
    "apply_rollout_config",
    "ROLLOUT_CONFIGS",
]
