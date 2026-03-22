# -*- coding: utf-8 -*-
# @file policy.py
# @brief Policy, authorization, and governance for remote control
# @author sailing-innocent
# @date 2026-03-22
# @version 1.0
# ---------------------------------
"""Policy, authorization, and governance layer.

This module provides:
- Sender allowlists and workspace-scoped authorization
- Action classification into policy tiers
- Confirmation flow management with expiry
- Audit recording for sensitive actions
- Degraded-mode safety rules
"""

import time
from typing import Dict, Any, List, Optional, Set
from dataclasses import dataclass, field
from enum import Enum, auto
from datetime import datetime, timedelta

from .intent_router import IntentPlan, RiskLevel


class ActionTier(Enum):
    """Policy tiers for action classification."""

    SAFE_AUTO = "safe_auto"  # Read-only, no confirmation needed
    GUARDED_AUTO = "guarded_auto"  # Low-risk, auto with logging
    CONFIRM_REQUIRED = "confirm_required"  # Requires explicit confirmation
    BLOCKED = "blocked"  # Blocked by policy


class AuthorizationResult(Enum):
    """Result of authorization check."""

    ALLOWED = auto()
    DENIED = auto()
    CONFIRMATION_REQUIRED = auto()
    DEGRADED_BLOCKED = auto()


@dataclass
class AuthorizationCheck:
    """Result of an authorization check."""

    result: AuthorizationResult
    reason: str
    audit_log_id: Optional[str] = None
    requires_confirmation: bool = False
    confirmation_timeout_seconds: int = 300


@dataclass
class ConfirmationRecord:
    """Record of a pending confirmation."""

    confirmation_id: str
    plan: IntentPlan
    sender_id: str
    created_at: datetime
    expires_at: datetime
    status: str = "pending"  # pending, confirmed, cancelled, expired
    confirmed_at: Optional[datetime] = None
    confirmation_data: Optional[Dict[str, Any]] = None

    @property
    def is_expired(self) -> bool:
        """Check if confirmation has expired."""
        return datetime.now() > self.expires_at

    @property
    def is_pending(self) -> bool:
        """Check if confirmation is still pending."""
        return self.status == "pending" and not self.is_expired


@dataclass
class AuditRecord:
    """Audit record for sensitive actions."""

    record_id: str
    timestamp: datetime
    sender_id: str
    action_type: str
    workspace: Optional[str]
    session: Optional[str]
    risk_level: str
    result: str  # allowed, denied, confirmed, failed
    reason: str
    metadata: Dict[str, Any] = field(default_factory=dict)


class PolicyEngine:
    """Policy engine for remote control authorization and governance.

    Enforces authorization rules, manages confirmation flows,
    records audit trails, and handles degraded-mode safety.
    """

    # Action tier mapping (overrides risk level)
    ACTION_TIERS = {
        "status": ActionTier.SAFE_AUTO,
        "list_workspaces": ActionTier.SAFE_AUTO,
        "view_session": ActionTier.SAFE_AUTO,
        "help": ActionTier.SAFE_AUTO,
        "git_status": ActionTier.SAFE_AUTO,
        "start_session": ActionTier.GUARDED_AUTO,
        "code_request": ActionTier.GUARDED_AUTO,
        "restart_session": ActionTier.GUARDED_AUTO,
        "recover_session": ActionTier.GUARDED_AUTO,
        "stop_session": ActionTier.CONFIRM_REQUIRED,
        "git_pull": ActionTier.CONFIRM_REQUIRED,
        "git_commit": ActionTier.CONFIRM_REQUIRED,
        "git_push": ActionTier.CONFIRM_REQUIRED,
        "force_stop": ActionTier.CONFIRM_REQUIRED,
        "reset_session": ActionTier.CONFIRM_REQUIRED,
        "delete_workspace": ActionTier.CONFIRM_REQUIRED,
        "unknown": ActionTier.BLOCKED,
    }

    def __init__(
        self,
        allowed_senders: Optional[Set[str]] = None,
        workspace_permissions: Optional[Dict[str, Set[str]]] = None,
    ):
        """Initialize the policy engine.

        Args:
            allowed_senders: Set of allowed sender IDs (None = allow all)
            workspace_permissions: Map of workspace -> allowed senders
        """
        self.allowed_senders = allowed_senders
        self.workspace_permissions = workspace_permissions or {}

        # In-memory stores (should be Redis/database in production)
        self._pending_confirmations: Dict[str, ConfirmationRecord] = {}
        self._audit_log: List[AuditRecord] = []

        # Degraded mode flags
        self._llm_healthy = True
        self._edge_healthy = True
        self._server_healthy = True

    def check_authorization(
        self, plan: IntentPlan, sender_id: str
    ) -> AuthorizationCheck:
        """Check if action is authorized.

        Args:
            plan: The intent plan to check
            sender_id: ID of the requesting user

        Returns:
            Authorization check result
        """
        # Check sender allowlist
        if self.allowed_senders is not None:
            if sender_id not in self.allowed_senders:
                self._audit(plan, sender_id, "denied", "Sender not in allowlist")
                return AuthorizationCheck(
                    result=AuthorizationResult.DENIED,
                    reason="Sender not authorized",
                    audit_log_id=self._get_last_audit_id(),
                )

        # Check workspace permissions
        if plan.target_workspace:
            allowed = self.workspace_permissions.get(plan.target_workspace)
            if allowed and sender_id not in allowed:
                self._audit(plan, sender_id, "denied", "Workspace access denied")
                return AuthorizationCheck(
                    result=AuthorizationResult.DENIED,
                    reason=f"Not authorized for workspace: {plan.target_workspace}",
                    audit_log_id=self._get_last_audit_id(),
                )

        # Check action tier
        tier = self.ACTION_TIERS.get(plan.requested_action, ActionTier.CONFIRM_REQUIRED)

        if tier == ActionTier.BLOCKED:
            self._audit(plan, sender_id, "denied", "Action blocked by policy")
            return AuthorizationCheck(
                result=AuthorizationResult.DENIED,
                reason="Action not permitted",
                audit_log_id=self._get_last_audit_id(),
            )

        # Check degraded mode
        degraded_check = self._check_degraded_mode(plan, tier)
        if degraded_check:
            return degraded_check

        # Determine if confirmation is needed
        if tier == ActionTier.CONFIRM_REQUIRED or plan.requires_confirmation:
            return AuthorizationCheck(
                result=AuthorizationResult.CONFIRMATION_REQUIRED,
                reason="High-risk action requires confirmation",
                requires_confirmation=True,
                confirmation_timeout_seconds=300,
            )

        # Safe or guarded auto-allowed
        self._audit(plan, sender_id, "allowed", f"Auto-approved (tier: {tier.value})")
        return AuthorizationCheck(
            result=AuthorizationResult.ALLOWED,
            reason=f"Action authorized ({tier.value})",
            audit_log_id=self._get_last_audit_id(),
        )

    def create_confirmation(
        self, plan: IntentPlan, sender_id: str, timeout_seconds: int = 300
    ) -> ConfirmationRecord:
        """Create a pending confirmation record.

        Args:
            plan: The intent plan to confirm
            sender_id: User requesting the action
            timeout_seconds: Confirmation timeout

        Returns:
            Confirmation record
        """
        confirmation_id = f"cfm_{int(time.time() * 1000)}_{sender_id[:8]}"
        now = datetime.now()

        record = ConfirmationRecord(
            confirmation_id=confirmation_id,
            plan=plan,
            sender_id=sender_id,
            created_at=now,
            expires_at=now + timedelta(seconds=timeout_seconds),
        )

        self._pending_confirmations[confirmation_id] = record

        # Cleanup expired confirmations
        self._cleanup_expired_confirmations()

        return record

    def confirm_action(
        self, confirmation_id: str, sender_id: str, confirmed: bool = True
    ) -> Optional[IntentPlan]:
        """Confirm or cancel a pending action.

        Args:
            confirmation_id: ID of the confirmation
            sender_id: User confirming (must match original)
            confirmed: True to confirm, False to cancel

        Returns:
            The intent plan if confirmed, None otherwise
        """
        record = self._pending_confirmations.get(confirmation_id)

        if not record:
            return None

        if record.sender_id != sender_id:
            return None

        if not record.is_pending:
            return None

        if confirmed:
            record.status = "confirmed"
            record.confirmed_at = datetime.now()
            self._audit(
                record.plan, sender_id, "confirmed", f"Action confirmed by user"
            )
            return record.plan
        else:
            record.status = "cancelled"
            self._audit(
                record.plan, sender_id, "cancelled", f"Action cancelled by user"
            )
            return None

    def get_pending_confirmation(
        self, confirmation_id: str
    ) -> Optional[ConfirmationRecord]:
        """Get a pending confirmation by ID."""
        record = self._pending_confirmations.get(confirmation_id)
        if record and record.is_pending:
            return record
        return None

    def cancel_confirmation(self, confirmation_id: str) -> bool:
        """Cancel a pending confirmation."""
        record = self._pending_confirmations.get(confirmation_id)
        if record and record.is_pending:
            record.status = "cancelled"
            return True
        return False

    def get_audit_log(
        self,
        sender_id: Optional[str] = None,
        workspace: Optional[str] = None,
        limit: int = 100,
    ) -> List[AuditRecord]:
        """Get audit log entries.

        Args:
            sender_id: Filter by sender
            workspace: Filter by workspace
            limit: Maximum entries to return

        Returns:
            List of audit records
        """
        records = self._audit_log

        if sender_id:
            records = [r for r in records if r.sender_id == sender_id]

        if workspace:
            records = [r for r in records if r.workspace == workspace]

        # Return most recent first
        return sorted(records, key=lambda r: r.timestamp, reverse=True)[:limit]

    def set_degraded_mode(
        self,
        llm_healthy: Optional[bool] = None,
        edge_healthy: Optional[bool] = None,
        server_healthy: Optional[bool] = None,
    ) -> None:
        """Set degraded mode flags.

        Args:
            llm_healthy: LLM service health status
            edge_healthy: Edge runtime health status
            server_healthy: Server health status
        """
        if llm_healthy is not None:
            self._llm_healthy = llm_healthy
        if edge_healthy is not None:
            self._edge_healthy = edge_healthy
        if server_healthy is not None:
            self._server_healthy = server_healthy

    def is_degraded(self) -> bool:
        """Check if system is in degraded mode."""
        return not (self._llm_healthy and self._edge_healthy and self._server_healthy)

    def _check_degraded_mode(
        self, plan: IntentPlan, tier: ActionTier
    ) -> Optional[AuthorizationCheck]:
        """Check if action should be blocked in degraded mode."""
        if not self.is_degraded():
            return None

        # In degraded mode, block high-risk actions
        if tier == ActionTier.CONFIRM_REQUIRED:
            self._audit(
                plan,
                "system",
                "degraded_blocked",
                f"Action blocked in degraded mode: {plan.requested_action}",
            )
            return AuthorizationCheck(
                result=AuthorizationResult.DEGRADED_BLOCKED,
                reason="High-risk actions disabled during degraded operation",
                audit_log_id=self._get_last_audit_id(),
            )

        # Also block if LLM is down and confidence is low
        if not self._llm_healthy and plan.confidence < 0.8:
            self._audit(
                plan,
                "system",
                "degraded_blocked",
                f"Low confidence action blocked without LLM: {plan.requested_action}",
            )
            return AuthorizationCheck(
                result=AuthorizationResult.DEGRADED_BLOCKED,
                reason="Low confidence routing unavailable during LLM outage",
                audit_log_id=self._get_last_audit_id(),
            )

        return None

    def _audit(
        self, plan: IntentPlan, sender_id: str, result: str, reason: str
    ) -> None:
        """Record an audit entry."""
        record = AuditRecord(
            record_id=f"aud_{int(time.time() * 1000)}",
            timestamp=datetime.now(),
            sender_id=sender_id,
            action_type=plan.requested_action,
            workspace=plan.target_workspace,
            session=plan.target_session,
            risk_level=plan.risk_level.value,
            result=result,
            reason=reason,
            metadata={
                "intent_type": plan.intent_type,
                "confidence": plan.confidence,
                "parameters": plan.parameters,
            },
        )

        self._audit_log.append(record)

        # Keep only last 10000 records (in production, persist to DB)
        if len(self._audit_log) > 10000:
            self._audit_log = self._audit_log[-10000:]

    def _get_last_audit_id(self) -> Optional[str]:
        """Get ID of most recent audit record."""
        if self._audit_log:
            return self._audit_log[-1].record_id
        return None

    def _cleanup_expired_confirmations(self) -> None:
        """Remove expired confirmation records."""
        expired = [
            cid
            for cid, rec in self._pending_confirmations.items()
            if rec.is_expired and rec.status == "pending"
        ]

        for cid in expired:
            self._pending_confirmations[cid].status = "expired"


# Global policy engine instance
_policy_engine: Optional[PolicyEngine] = None


def get_policy_engine() -> PolicyEngine:
    """Get or create the global policy engine instance."""
    global _policy_engine
    if _policy_engine is None:
        _policy_engine = PolicyEngine()
    return _policy_engine


def configure_policy_engine(
    allowed_senders: Optional[Set[str]] = None,
    workspace_permissions: Optional[Dict[str, Set[str]]] = None,
) -> PolicyEngine:
    """Configure the global policy engine."""
    global _policy_engine
    _policy_engine = PolicyEngine(allowed_senders, workspace_permissions)
    return _policy_engine
