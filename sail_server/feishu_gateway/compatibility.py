# -*- coding: utf-8 -*-
# @file compatibility.py
# @brief Compatibility and rollout controls for migration
# @author sailing-innocent
# @date 2026-03-22
# @version 1.0
# ---------------------------------
"""Compatibility and rollout controls for the Feishu gateway migration.

This module provides:
- Feature flags for staged rollout
- Shadow mode for testing
- Compatibility fallbacks
- Rollback mechanisms
"""

from typing import Dict, Any, Optional, Callable
from dataclasses import dataclass, field
from enum import Enum


class FeatureFlag(Enum):
    """Feature flags for staged rollout."""

    CARD_RENDERING = "card_rendering"
    INTENT_ROUTING = "intent_routing"
    DESKTOP_RECONCILIATION = "desktop_reconciliation"
    CONFIRMATION_GATING = "confirmation_gating"
    VOICE_NORMALIZATION = "voice_normalization"
    LLM_FALLBACK = "llm_fallback"


class RollbackMode(Enum):
    """Rollback modes."""

    FULL = "full"  # Full new system with cards and natural language
    HYBRID = "hybrid"  # New system with simplified text fallback
    DEGRADED = "degraded"  # Minimal functionality mode (emergency only)


@dataclass
class FeatureConfig:
    """Configuration for a feature flag."""

    enabled: bool = False
    shadow_mode: bool = False  # Log but don't execute
    rollout_percentage: int = 0  # 0-100
    allowed_senders: Optional[list] = None  # None = all


class CompatibilityLayer:
    """Compatibility layer for migration and rollout.

    Manages feature flags, shadow mode, and rollback behavior.
    """

    def __init__(self):
        """Initialize the compatibility layer."""
        # Feature flag configurations
        self._features: Dict[FeatureFlag, FeatureConfig] = {
            flag: FeatureConfig() for flag in FeatureFlag
        }

        # Current rollback mode
        self._rollback_mode = RollbackMode.FULL

        # Legacy command handler (for fallback)
        self._legacy_handler: Optional[Callable] = None

        # Shadow mode callbacks
        self._shadow_callbacks: list = []

    def configure_feature(
        self,
        flag: FeatureFlag,
        enabled: Optional[bool] = None,
        shadow_mode: Optional[bool] = None,
        rollout_percentage: Optional[int] = None,
    ) -> None:
        """Configure a feature flag.

        Args:
            flag: Feature to configure
            enabled: Whether feature is enabled
            shadow_mode: Whether to run in shadow mode
            rollout_percentage: Percentage of traffic (0-100)
        """
        config = self._features[flag]

        if enabled is not None:
            config.enabled = enabled

        if shadow_mode is not None:
            config.shadow_mode = shadow_mode

        if rollout_percentage is not None:
            config.rollout_percentage = max(0, min(100, rollout_percentage))

    def is_feature_enabled(
        self, flag: FeatureFlag, sender_id: Optional[str] = None
    ) -> bool:
        """Check if a feature is enabled for a user.

        Args:
            flag: Feature to check
            sender_id: Optional sender for percentage rollout

        Returns:
            True if enabled
        """
        config = self._features[flag]

        # Check if feature is enabled
        if not config.enabled:
            return False

        # Check allowed senders
        if config.allowed_senders is not None:
            if sender_id not in config.allowed_senders:
                return False

        # Check percentage rollout
        if config.rollout_percentage < 100 and sender_id:
            # Deterministic hash of sender_id
            import hashlib

            hash_val = int(hashlib.md5(sender_id.encode()).hexdigest(), 16)
            user_percentile = hash_val % 100

            if user_percentile >= config.rollout_percentage:
                return False

        return True

    def is_shadow_mode(self, flag: FeatureFlag) -> bool:
        """Check if feature is in shadow mode."""
        return self._features[flag].shadow_mode

    def set_rollback_mode(self, mode: RollbackMode) -> None:
        """Set the rollback mode.

        Args:
            mode: Rollback mode to use
        """
        self._rollback_mode = mode

        if mode == RollbackMode.DEGRADED:
            # Disable all new features in degraded mode
            for flag in FeatureFlag:
                self._features[flag].enabled = False

    def get_rollback_mode(self) -> RollbackMode:
        """Get current rollback mode."""
        return self._rollback_mode

    def should_use_text_fallback(self) -> bool:
        """Check if we should use simplified text fallback."""
        return self._rollback_mode in [RollbackMode.DEGRADED, RollbackMode.HYBRID]

    def register_legacy_handler(self, handler: Callable) -> None:
        """Register the legacy command handler for fallback."""
        self._legacy_handler = handler

    def get_legacy_handler(self) -> Optional[Callable]:
        """Get the legacy command handler."""
        return self._legacy_handler

    def register_shadow_callback(self, callback: Callable) -> None:
        """Register a callback for shadow mode events.

        Callback receives: (feature_flag, input_data, new_result, legacy_result)
        """
        self._shadow_callbacks.append(callback)

    async def execute_with_shadow(
        self,
        flag: FeatureFlag,
        new_handler: Callable,
        legacy_handler: Callable,
        *args,
        **kwargs,
    ) -> Any:
        """Execute with shadow mode comparison.

        In shadow mode, both handlers are called but only legacy result is used.
        Differences are logged for analysis.

        Args:
            flag: Feature flag
            new_handler: New implementation
            legacy_handler: Legacy implementation
            *args, **kwargs: Arguments to pass to handlers

        Returns:
            Result (legacy in shadow mode, new if not)
        """
        # Always call legacy handler
        legacy_result = await legacy_handler(*args, **kwargs)

        # Call new handler in shadow mode or if enabled
        if self.is_shadow_mode(flag) or self.is_feature_enabled(flag):
            try:
                new_result = await new_handler(*args, **kwargs)

                # Log differences in shadow mode
                if self.is_shadow_mode(flag):
                    if new_result != legacy_result:
                        for callback in self._shadow_callbacks:
                            try:
                                callback(flag, args, new_result, legacy_result)
                            except Exception as e:
                                print(f"Shadow callback error: {e}")

                # Return new result if not in shadow mode and enabled
                if not self.is_shadow_mode(flag) and self.is_feature_enabled(flag):
                    return new_result

            except Exception as e:
                # Log error but don't fail
                print(f"Shadow mode error for {flag.value}: {e}")

        return legacy_result

    def get_feature_status(self) -> Dict[str, Any]:
        """Get status of all features."""
        return {
            flag.value: {
                "enabled": config.enabled,
                "shadow_mode": config.shadow_mode,
                "rollout_percentage": config.rollout_percentage,
            }
            for flag, config in self._features.items()
        }

    def enable_all_features(self) -> None:
        """Enable all features (for testing)."""
        for flag in FeatureFlag:
            self._features[flag].enabled = True
            self._features[flag].shadow_mode = False
            self._features[flag].rollout_percentage = 100

    def disable_all_features(self) -> None:
        """Disable all new features (rollback to legacy)."""
        for flag in FeatureFlag:
            self._features[flag].enabled = False
            self._features[flag].shadow_mode = False


# Default configuration for different rollout stages
ROLLOUT_CONFIGS = {
    "mvp2_alpha": {
        FeatureFlag.CARD_RENDERING: {
            "enabled": True,
            "shadow_mode": False,
            "rollout_percentage": 10,
        },
        FeatureFlag.INTENT_ROUTING: {
            "enabled": True,
            "shadow_mode": True,
            "rollout_percentage": 100,
        },
        FeatureFlag.CONFIRMATION_GATING: {
            "enabled": True,
            "shadow_mode": False,
            "rollout_percentage": 100,
        },
    },
    "mvp2_beta": {
        FeatureFlag.CARD_RENDERING: {
            "enabled": True,
            "shadow_mode": False,
            "rollout_percentage": 50,
        },
        FeatureFlag.INTENT_ROUTING: {
            "enabled": True,
            "shadow_mode": False,
            "rollout_percentage": 50,
        },
        FeatureFlag.DESKTOP_RECONCILIATION: {
            "enabled": True,
            "shadow_mode": True,
            "rollout_percentage": 100,
        },
        FeatureFlag.CONFIRMATION_GATING: {
            "enabled": True,
            "shadow_mode": False,
            "rollout_percentage": 100,
        },
    },
    "mvp2_ga": {
        FeatureFlag.CARD_RENDERING: {
            "enabled": True,
            "shadow_mode": False,
            "rollout_percentage": 100,
        },
        FeatureFlag.INTENT_ROUTING: {
            "enabled": True,
            "shadow_mode": False,
            "rollout_percentage": 100,
        },
        FeatureFlag.DESKTOP_RECONCILIATION: {
            "enabled": True,
            "shadow_mode": False,
            "rollout_percentage": 100,
        },
        FeatureFlag.CONFIRMATION_GATING: {
            "enabled": True,
            "shadow_mode": False,
            "rollout_percentage": 100,
        },
        FeatureFlag.VOICE_NORMALIZATION: {
            "enabled": True,
            "shadow_mode": False,
            "rollout_percentage": 100,
        },
    },
}


# Global compatibility layer instance
_compatibility: Optional[CompatibilityLayer] = None


def get_compatibility_layer() -> CompatibilityLayer:
    """Get or create the global compatibility layer."""
    global _compatibility
    if _compatibility is None:
        _compatibility = CompatibilityLayer()
    return _compatibility


def apply_rollout_config(config_name: str) -> None:
    """Apply a named rollout configuration.

    Args:
        config_name: One of "mvp2_alpha", "mvp2_beta", "mvp2_ga"
    """
    layer = get_compatibility_layer()
    config = ROLLOUT_CONFIGS.get(config_name, {})

    for flag, settings in config.items():
        layer.configure_feature(flag, **settings)
