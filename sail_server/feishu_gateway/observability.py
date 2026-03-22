# -*- coding: utf-8 -*-
# @file observability.py
# @brief Observability, audit, and alerting for remote control
# @author sailing-innocent
# @date 2026-03-22
# @version 1.0
# ---------------------------------
"""Observability layer for remote development control plane.

This module provides:
- Server-owned event streaming
- Health evaluation and alerting
- Audit queries and dashboards
- Actionable alert payloads with recovery controls
"""

import uuid
from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum, auto

from .session_orchestrator import Session, SessionOrchestrator, SessionStatus
from .cards import CardRenderer


class AlertSeverity(Enum):
    """Alert severity levels."""

    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class AlertType(Enum):
    """Types of alerts."""

    SESSION_STALE = "session_stale"
    AGENT_OFFLINE = "agent_offline"
    RECOVERY_FAILURE = "recovery_failure"
    ROUTING_DEGRADED = "routing_degraded"
    SESSION_ERROR = "session_error"
    HEARTBEAT_MISSED = "heartbeat_missed"


@dataclass
class Alert:
    """Alert record."""

    alert_id: str
    alert_type: AlertType
    severity: AlertSeverity
    title: str
    message: str
    session_id: Optional[str]
    workspace_id: Optional[str]
    created_at: datetime
    acknowledged: bool = False
    acknowledged_at: Optional[datetime] = None
    resolved: bool = False
    resolved_at: Optional[datetime] = None
    recovery_actions: List[Dict[str, Any]] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class HealthCheckResult:
    """Result of a health check."""

    component: str
    status: str  # "healthy", "degraded", "unhealthy"
    message: str
    last_check: datetime
    metrics: Dict[str, Any] = field(default_factory=dict)


class ObservabilityService:
    """Observability service for monitoring and alerting.

    Provides health checks, alert generation, audit queries,
    and dashboard summaries.
    """

    def __init__(self, session_orchestrator: Optional[SessionOrchestrator] = None):
        """Initialize the observability service.

        Args:
            session_orchestrator: Session orchestrator instance
        """
        self.session_orchestrator = session_orchestrator or SessionOrchestrator()

        # Alert storage
        self._alerts: Dict[str, Alert] = {}
        self._alert_handlers: List[Callable] = []

        # Health check thresholds
        self._stale_threshold_seconds = 300  # 5 minutes
        self._heartbeat_threshold_seconds = 300
        self._max_recovery_attempts = 3

    # Health Evaluation

    def evaluate_session_health(self, session_id: str) -> HealthCheckResult:
        """Evaluate health of a specific session.

        Args:
            session_id: Session to evaluate

        Returns:
            Health check result
        """
        session = self.session_orchestrator.get_session(session_id)

        if not session:
            return HealthCheckResult(
                component=f"session:{session_id}",
                status="unhealthy",
                message="Session not found",
                last_check=datetime.now(),
            )

        # Check if session is stale
        if session.last_heartbeat:
            staleness = (datetime.now() - session.last_heartbeat).total_seconds()

            if staleness > self._stale_threshold_seconds:
                return HealthCheckResult(
                    component=f"session:{session_id}",
                    status="unhealthy",
                    message=f"Session stale for {staleness:.0f}s",
                    last_check=datetime.now(),
                    metrics={"staleness_seconds": staleness},
                )
            elif staleness > self._stale_threshold_seconds * 0.7:
                return HealthCheckResult(
                    component=f"session:{session_id}",
                    status="degraded",
                    message=f"Session heartbeat delayed ({staleness:.0f}s)",
                    last_check=datetime.now(),
                    metrics={"staleness_seconds": staleness},
                )

        # Check desired vs observed state mismatch
        if session.desired_state != session.observed_state:
            if session.status == SessionStatus.ERROR:
                return HealthCheckResult(
                    component=f"session:{session_id}",
                    status="unhealthy",
                    message=f"State reconciliation failed: {session.observed_state}",
                    last_check=datetime.now(),
                )
            else:
                return HealthCheckResult(
                    component=f"session:{session_id}",
                    status="degraded",
                    message=f"State mismatch: desired={session.desired_state}, observed={session.observed_state}",
                    last_check=datetime.now(),
                )

        return HealthCheckResult(
            component=f"session:{session_id}",
            status="healthy",
            message=f"Session healthy ({session.status.value})",
            last_check=datetime.now(),
        )

    def evaluate_all_sessions(self) -> List[HealthCheckResult]:
        """Evaluate health of all sessions."""
        results = []

        for session in self.session_orchestrator.list_sessions():
            result = self.evaluate_session_health(session.session_id)
            results.append(result)

        return results

    def check_recovery_failures(self, session_id: str) -> Optional[Alert]:
        """Check if session has repeated recovery failures.

        Args:
            session_id: Session to check

        Returns:
            Alert if threshold exceeded, None otherwise
        """
        events = self.session_orchestrator.get_session_timeline(session_id)

        # Count recent recovery attempts and failures
        recovery_events = [
            e for e in events if e.event_type in ["recovery_started", "recovery_failed"]
        ]

        failures = len(
            [e for e in recovery_events if e.event_type == "recovery_failed"]
        )

        if failures >= self._max_recovery_attempts:
            return self._create_alert(
                alert_type=AlertType.RECOVERY_FAILURE,
                severity=AlertSeverity.ERROR,
                title="会话恢复失败",
                message=f"会话 {session_id} 已连续失败 {failures} 次恢复尝试",
                session_id=session_id,
                recovery_actions=[
                    {
                        "label": "手动重启",
                        "type": "primary",
                        "value": {"intent": "restart_session", "session": session_id},
                    },
                    {
                        "label": "查看日志",
                        "type": "default",
                        "value": {"intent": "view_logs", "session": session_id},
                    },
                    {
                        "label": "忽略",
                        "type": "default",
                        "value": {
                            "intent": "acknowledge_alert",
                            "alert_type": "recovery_failure",
                        },
                    },
                ],
            )

        return None

    # Alert Management

    def _create_alert(
        self,
        alert_type: AlertType,
        severity: AlertSeverity,
        title: str,
        message: str,
        session_id: Optional[str] = None,
        workspace_id: Optional[str] = None,
        recovery_actions: Optional[List[Dict]] = None,
        metadata: Optional[Dict] = None,
    ) -> Alert:
        """Create and store an alert."""
        alert_id = f"alt_{uuid.uuid4().hex[:12]}"

        alert = Alert(
            alert_id=alert_id,
            alert_type=alert_type,
            severity=severity,
            title=title,
            message=message,
            session_id=session_id,
            workspace_id=workspace_id,
            created_at=datetime.now(),
            recovery_actions=recovery_actions or [],
            metadata=metadata or {},
        )

        self._alerts[alert_id] = alert

        # Notify alert handlers
        for handler in self._alert_handlers:
            try:
                handler(alert)
            except Exception as e:
                print(f"Alert handler error: {e}")

        return alert

    def register_alert_handler(self, handler: Callable) -> None:
        """Register a handler for new alerts."""
        self._alert_handlers.append(handler)

    def get_alerts(
        self,
        severity: Optional[AlertSeverity] = None,
        acknowledged: Optional[bool] = None,
        resolved: Optional[bool] = None,
        session_id: Optional[str] = None,
        limit: int = 50,
    ) -> List[Alert]:
        """Get alerts with filtering."""
        alerts = list(self._alerts.values())

        if severity:
            alerts = [a for a in alerts if a.severity == severity]

        if acknowledged is not None:
            alerts = [a for a in alerts if a.acknowledged == acknowledged]

        if resolved is not None:
            alerts = [a for a in alerts if a.resolved == resolved]

        if session_id:
            alerts = [a for a in alerts if a.session_id == session_id]

        # Sort by severity and time
        severity_order = {
            AlertSeverity.CRITICAL: 0,
            AlertSeverity.ERROR: 1,
            AlertSeverity.WARNING: 2,
            AlertSeverity.INFO: 3,
        }

        alerts.sort(
            key=lambda a: (severity_order.get(a.severity, 99), a.created_at),
            reverse=True,
        )

        return alerts[:limit]

    def acknowledge_alert(self, alert_id: str) -> bool:
        """Acknowledge an alert."""
        alert = self._alerts.get(alert_id)
        if alert and not alert.acknowledged:
            alert.acknowledged = True
            alert.acknowledged_at = datetime.now()
            return True
        return False

    def resolve_alert(self, alert_id: str) -> bool:
        """Resolve an alert."""
        alert = self._alerts.get(alert_id)
        if alert and not alert.resolved:
            alert.resolved = True
            alert.resolved_at = datetime.now()
            return True
        return False

    # Alert Card Generation

    def generate_alert_card(self, alert: Alert) -> Dict[str, Any]:
        """Generate a Feishu card for an alert with recovery actions."""
        severity_colors = {
            AlertSeverity.INFO: "blue",
            AlertSeverity.WARNING: "orange",
            AlertSeverity.ERROR: "red",
            AlertSeverity.CRITICAL: "red",
        }

        severity_emojis = {
            AlertSeverity.INFO: "ℹ️",
            AlertSeverity.WARNING: "⚠️",
            AlertSeverity.ERROR: "🚨",
            AlertSeverity.CRITICAL: "🔴",
        }

        color = severity_colors.get(alert.severity, "grey")
        emoji = severity_emojis.get(alert.severity, "⚠️")

        elements = [
            {
                "tag": "div",
                "text": {"tag": "lark_md", "content": f"{emoji} **{alert.title}**"},
            },
            {"tag": "div", "text": {"tag": "lark_md", "content": alert.message}},
        ]

        # Add session info if present
        if alert.session_id:
            elements.append(
                {
                    "tag": "div",
                    "text": {
                        "tag": "lark_md",
                        "content": f"会话: `{alert.session_id}`",
                    },
                }
            )

        # Add recovery actions
        if alert.recovery_actions:
            elements.append({"tag": "hr"})
            buttons = []
            for action in alert.recovery_actions:
                buttons.append(
                    {
                        "tag": "button",
                        "text": {"tag": "plain_text", "content": action["label"]},
                        "type": action.get("type", "default"),
                        "value": action["value"],
                    }
                )

            elements.append({"tag": "action", "layout": "default", "actions": buttons})

        return {
            "config": {"wide_screen_mode": True},
            "header": {
                "title": {"tag": "plain_text", "content": f"{emoji} 系统提醒"},
                "template": color,
            },
            "elements": elements,
        }

    # Audit Queries

    def get_recent_actions(
        self, session_id: Optional[str] = None, limit: int = 20
    ) -> List[Dict[str, Any]]:
        """Get recent actions for audit.

        Args:
            session_id: Optional session filter
            limit: Maximum results

        Returns:
            List of action records
        """
        if session_id:
            events = self.session_orchestrator.get_session_timeline(session_id, limit)
            return [
                {
                    "timestamp": e.timestamp.isoformat(),
                    "type": e.event_type,
                    "description": e.description,
                    "severity": e.severity,
                    "metadata": e.metadata,
                }
                for e in events
            ]
        else:
            # Aggregate across all sessions
            all_actions = []
            for session in self.session_orchestrator.list_sessions():
                events = self.session_orchestrator.get_session_timeline(
                    session.session_id, limit // 5
                )
                for e in events:
                    all_actions.append(
                        {
                            "session_id": session.session_id,
                            "workspace": session.workspace_name,
                            "timestamp": e.timestamp.isoformat(),
                            "type": e.event_type,
                            "description": e.description,
                            "severity": e.severity,
                        }
                    )

            all_actions.sort(key=lambda x: x["timestamp"], reverse=True)
            return all_actions[:limit]

    def get_failure_analysis(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get failure analysis for a session.

        Args:
            session_id: Session to analyze

        Returns:
            Failure analysis or None
        """
        session = self.session_orchestrator.get_session(session_id)
        if not session:
            return None

        events = self.session_orchestrator.get_session_timeline(session_id)

        # Find failure events
        failures = [e for e in events if e.severity == "error"]

        if not failures:
            return {
                "session_id": session_id,
                "status": session.status.value,
                "has_failures": False,
                "message": "No failures recorded",
            }

        # Get last successful step
        last_success = None
        for e in reversed(events):
            if e.severity == "info" and e.event_type not in [
                "task_created",
                "session_created",
            ]:
                last_success = e
                break

        latest_failure = failures[0]  # Most recent

        return {
            "session_id": session_id,
            "status": session.status.value,
            "has_failures": True,
            "failure_count": len(failures),
            "latest_failure": {
                "timestamp": latest_failure.timestamp.isoformat(),
                "type": latest_failure.event_type,
                "description": latest_failure.description,
            },
            "last_successful_step": {
                "timestamp": last_success.timestamp.isoformat(),
                "description": last_success.description,
            }
            if last_success
            else None,
            "recommended_action": self._recommend_recovery(session, failures),
        }

    def _recommend_recovery(self, session: Session, failures: List[Any]) -> str:
        """Generate recovery recommendation."""
        # Simple heuristic-based recommendations
        failure_types = [f.event_type for f in failures[:5]]

        if "recovery_failed" in failure_types:
            return "手动重启会话并检查桌面代理状态"
        elif "heartbeat_missed" in failure_types:
            return "检查桌面代理连接，可能需要重新启动代理"
        elif session.status == SessionStatus.ERROR:
            return "查看详细日志，尝试恢复或重置会话"
        else:
            return "监控会话状态，如问题持续请检查配置"

    # Dashboard API

    def get_dashboard_summary(self) -> Dict[str, Any]:
        """Get dashboard summary for multi-session overview.

        Returns:
            Dashboard data
        """
        sessions = self.session_orchestrator.list_sessions()
        health_results = self.evaluate_all_sessions()

        active_alerts = self.get_alerts(acknowledged=False, resolved=False, limit=10)

        return {
            "total_sessions": len(sessions),
            "active_sessions": len([s for s in sessions if s.is_active]),
            "healthy_sessions": len(
                [h for h in health_results if h.status == "healthy"]
            ),
            "degraded_sessions": len(
                [h for h in health_results if h.status == "degraded"]
            ),
            "unhealthy_sessions": len(
                [h for h in health_results if h.status == "unhealthy"]
            ),
            "active_alerts_count": len(active_alerts),
            "recent_alerts": [
                {
                    "id": a.alert_id,
                    "type": a.alert_type.value,
                    "severity": a.severity.value,
                    "title": a.title,
                    "created_at": a.created_at.isoformat(),
                }
                for a in active_alerts[:5]
            ],
            "session_summaries": [
                self.session_orchestrator.get_session_summary(s.session_id)
                for s in sessions[:10]
            ],
        }


# Global observability service instance
_observability: Optional[ObservabilityService] = None


def get_observability_service() -> ObservabilityService:
    """Get or create the global observability service."""
    global _observability
    if _observability is None:
        _observability = ObservabilityService()
    return _observability
