# -*- coding: utf-8 -*-
# @file session_orchestrator.py
# @brief Session-aware task orchestration for remote control
# @author sailing-innocent
# @date 2026-03-22
# @version 1.0
# ---------------------------------
"""Session-aware task orchestration layer.

This module provides:
- Session creation and selection for work requests
- Session-scoped progress publication
- Result, failure, and resume flow management
- Integration with SailZen unified tasks (via reference, not reuse)
"""

import uuid
import time
from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, auto


class SessionStatus(Enum):
    """Status of an OpenCode session."""

    IDLE = "idle"
    STARTING = "starting"
    RUNNING = "running"
    STOPPING = "stopping"
    STOPPED = "stopped"
    ERROR = "error"
    RECOVERING = "recovering"


class TaskStatus(Enum):
    """Status of a task within a session."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class Session:
    """Remote control session model.

    Sessions are durable runtime containers in the remote-control domain
    that reference (but don't replace) SailZen unified tasks.
    """

    session_id: str
    workspace_id: str
    workspace_name: str
    status: SessionStatus
    desired_state: str  # "running", "stopped", etc.
    observed_state: str
    branch: Optional[str] = None
    started_at: Optional[datetime] = None
    stopped_at: Optional[datetime] = None
    last_heartbeat: Optional[datetime] = None
    agent_node_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def is_active(self) -> bool:
        """Check if session is currently active."""
        return self.status in [
            SessionStatus.STARTING,
            SessionStatus.RUNNING,
            SessionStatus.RECOVERING,
        ]

    @property
    def is_healthy(self) -> bool:
        """Check if session is healthy."""
        if not self.is_active:
            return self.status == SessionStatus.IDLE

        # Check heartbeat staleness (5 minutes threshold)
        if self.last_heartbeat:
            staleness = (datetime.now() - self.last_heartbeat).total_seconds()
            return staleness < 300

        return self.status == SessionStatus.RUNNING


@dataclass
class SessionTask:
    """Task attached to a session.

    References SailZen unified tasks but tracks session-scoped
    progress and state separately.
    """

    task_id: str
    session_id: str
    unified_task_id: Optional[str]  # Reference to SailZen task
    title: str
    description: str
    status: TaskStatus
    progress_percent: int = 0
    current_step: Optional[str] = None
    result_summary: Optional[str] = None
    error_message: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SessionEvent:
    """Event record for session timeline."""

    event_id: str
    session_id: str
    event_type: str
    description: str
    timestamp: datetime
    severity: str = "info"  # info, warning, error
    metadata: Dict[str, Any] = field(default_factory=dict)


class SessionOrchestrator:
    """Orchestrator for session-aware task execution.

    Manages session lifecycle, task attachment, progress publication,
    and result/failure flows.
    """

    def __init__(self):
        """Initialize the session orchestrator."""
        # In-memory stores (should be database in production)
        self._sessions: Dict[str, Session] = {}
        self._tasks: Dict[str, SessionTask] = {}
        self._events: Dict[str, List[SessionEvent]] = {}

        # Progress callbacks
        self._progress_callbacks: List[Callable] = []

    # Session Management

    def create_session(
        self,
        workspace_id: str,
        workspace_name: str,
        branch: Optional[str] = None,
        metadata: Optional[Dict] = None,
    ) -> Session:
        """Create a new session.

        Args:
            workspace_id: Workspace identifier
            workspace_name: Human-readable workspace name
            branch: Git branch (optional)
            metadata: Additional metadata

        Returns:
            Created session
        """
        session_id = f"sess_{uuid.uuid4().hex[:12]}"

        session = Session(
            session_id=session_id,
            workspace_id=workspace_id,
            workspace_name=workspace_name,
            status=SessionStatus.IDLE,
            desired_state="stopped",
            observed_state="stopped",
            branch=branch,
            metadata=metadata or {},
        )

        self._sessions[session_id] = session
        self._events[session_id] = []

        self._record_event(
            session_id=session_id,
            event_type="session_created",
            description=f"Session created for {workspace_name}",
            severity="info",
        )

        return session

    def get_session(self, session_id: str) -> Optional[Session]:
        """Get session by ID."""
        return self._sessions.get(session_id)

    def get_or_create_session(
        self, workspace_id: str, workspace_name: str, auto_create: bool = True
    ) -> Optional[Session]:
        """Get existing active session or create new one.

        Args:
            workspace_id: Workspace identifier
            workspace_name: Workspace name
            auto_create: Whether to create if not found

        Returns:
            Session or None
        """
        # Find existing active session for workspace
        for session in self._sessions.values():
            if session.workspace_id == workspace_id and session.is_active:
                return session

        # Create new if auto_create is enabled
        if auto_create:
            return self.create_session(workspace_id, workspace_name)

        return None

    def list_sessions(
        self, workspace_id: Optional[str] = None, status: Optional[SessionStatus] = None
    ) -> List[Session]:
        """List sessions with optional filtering."""
        sessions = list(self._sessions.values())

        if workspace_id:
            sessions = [s for s in sessions if s.workspace_id == workspace_id]

        if status:
            sessions = [s for s in sessions if s.status == status]

        return sessions

    def update_session_state(
        self,
        session_id: str,
        desired_state: Optional[str] = None,
        observed_state: Optional[str] = None,
        status: Optional[SessionStatus] = None,
        heartbeat: bool = False,
    ) -> bool:
        """Update session state.

        Args:
            session_id: Session to update
            desired_state: New desired state
            observed_state: New observed state
            status: New status
            heartbeat: Whether this is a heartbeat update

        Returns:
            True if updated
        """
        session = self._sessions.get(session_id)
        if not session:
            return False

        if desired_state:
            old_desired = session.desired_state
            session.desired_state = desired_state
            if old_desired != desired_state:
                self._record_event(
                    session_id=session_id,
                    event_type="desired_state_changed",
                    description=f"Desired state: {old_desired} -> {desired_state}",
                    severity="info",
                )

        if observed_state:
            old_observed = session.observed_state
            session.observed_state = observed_state
            if old_observed != observed_state:
                self._record_event(
                    session_id=session_id,
                    event_type="observed_state_changed",
                    description=f"Observed state: {old_observed} -> {observed_state}",
                    severity="info",
                )

        if status:
            session.status = status

        if heartbeat:
            session.last_heartbeat = datetime.now()

        return True

    # Task Management

    def create_task(
        self,
        session_id: str,
        title: str,
        description: str,
        unified_task_id: Optional[str] = None,
    ) -> Optional[SessionTask]:
        """Create a task attached to a session.

        Args:
            session_id: Parent session
            title: Task title
            description: Task description
            unified_task_id: Optional reference to SailZen unified task

        Returns:
            Created task or None if session not found
        """
        session = self._sessions.get(session_id)
        if not session:
            return None

        task_id = f"task_{uuid.uuid4().hex[:12]}"

        task = SessionTask(
            task_id=task_id,
            session_id=session_id,
            unified_task_id=unified_task_id,
            title=title,
            description=description,
            status=TaskStatus.PENDING,
        )

        self._tasks[task_id] = task

        self._record_event(
            session_id=session_id,
            event_type="task_created",
            description=f"Task created: {title}",
            metadata={"task_id": task_id},
        )

        return task

    def update_task_progress(
        self, task_id: str, progress_percent: int, current_step: Optional[str] = None
    ) -> bool:
        """Update task progress.

        Args:
            task_id: Task to update
            progress_percent: 0-100
            current_step: Current step description

        Returns:
            True if updated
        """
        task = self._tasks.get(task_id)
        if not task:
            return False

        task.progress_percent = max(0, min(100, progress_percent))

        if current_step:
            task.current_step = current_step

        if task.status == TaskStatus.PENDING and progress_percent > 0:
            task.status = TaskStatus.RUNNING
            task.started_at = datetime.now()

        # Notify progress subscribers
        self._notify_progress(task)

        return True

    def complete_task(
        self, task_id: str, result_summary: str, success: bool = True
    ) -> bool:
        """Mark task as completed or failed.

        Args:
            task_id: Task to complete
            result_summary: Result description
            success: Whether task succeeded

        Returns:
            True if updated
        """
        task = self._tasks.get(task_id)
        if not task:
            return False

        task.status = TaskStatus.COMPLETED if success else TaskStatus.FAILED
        task.result_summary = result_summary
        task.progress_percent = 100 if success else task.progress_percent
        task.completed_at = datetime.now()

        self._record_event(
            session_id=task.session_id,
            event_type="task_completed" if success else "task_failed",
            description=f"Task {task.title}: {result_summary[:100]}",
            severity="info" if success else "error",
            metadata={"task_id": task_id, "success": success},
        )

        return True

    def get_session_tasks(self, session_id: str) -> List[SessionTask]:
        """Get all tasks for a session."""
        return [task for task in self._tasks.values() if task.session_id == session_id]

    def get_current_task(self, session_id: str) -> Optional[SessionTask]:
        """Get currently active task for session."""
        tasks = self.get_session_tasks(session_id)
        active = [
            t for t in tasks if t.status in [TaskStatus.PENDING, TaskStatus.RUNNING]
        ]

        if active:
            # Return most recently started
            return sorted(active, key=lambda t: t.created_at, reverse=True)[0]

        return None

    # Event Timeline

    def get_session_timeline(
        self, session_id: str, limit: int = 50
    ) -> List[SessionEvent]:
        """Get event timeline for a session."""
        events = self._events.get(session_id, [])
        return sorted(events, key=lambda e: e.timestamp, reverse=True)[:limit]

    def _record_event(
        self,
        session_id: str,
        event_type: str,
        description: str,
        severity: str = "info",
        metadata: Optional[Dict] = None,
    ) -> None:
        """Record a session event."""
        event = SessionEvent(
            event_id=f"evt_{uuid.uuid4().hex[:8]}",
            session_id=session_id,
            event_type=event_type,
            description=description,
            timestamp=datetime.now(),
            severity=severity,
            metadata=metadata or {},
        )

        if session_id not in self._events:
            self._events[session_id] = []

        self._events[session_id].append(event)

        # Keep only last 1000 events per session
        if len(self._events[session_id]) > 1000:
            self._events[session_id] = self._events[session_id][-1000:]

    # Progress Publication

    def register_progress_callback(self, callback: Callable) -> None:
        """Register a callback for progress updates."""
        self._progress_callbacks.append(callback)

    def _notify_progress(self, task: SessionTask) -> None:
        """Notify progress subscribers."""
        for callback in self._progress_callbacks:
            try:
                callback(task)
            except Exception as e:
                print(f"Progress callback error: {e}")

    # Resume Flow

    def get_resumable_sessions(
        self, workspace_id: Optional[str] = None
    ) -> List[Session]:
        """Get sessions that can be resumed.

        Sessions in error state or unexpectedly stopped can be resumed.
        """
        sessions = self.list_sessions(workspace_id)

        resumable = []
        for session in sessions:
            if session.status in [SessionStatus.ERROR, SessionStatus.STOPPED]:
                # Check if it was supposed to be running
                if session.desired_state == "running":
                    resumable.append(session)

        return resumable

    def get_session_summary(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get comprehensive session summary for Feishu display."""
        session = self._sessions.get(session_id)
        if not session:
            return None

        tasks = self.get_session_tasks(session_id)
        events = self.get_session_timeline(session_id, limit=10)
        current_task = self.get_current_task(session_id)

        return {
            "session_id": session_id,
            "workspace": session.workspace_name,
            "status": session.status.value,
            "is_healthy": session.is_healthy,
            "branch": session.branch,
            "started_at": session.started_at.isoformat()
            if session.started_at
            else None,
            "last_heartbeat": session.last_heartbeat.isoformat()
            if session.last_heartbeat
            else None,
            "task_count": len(tasks),
            "completed_tasks": len(
                [t for t in tasks if t.status == TaskStatus.COMPLETED]
            ),
            "failed_tasks": len([t for t in tasks if t.status == TaskStatus.FAILED]),
            "current_task": {
                "title": current_task.title,
                "progress": current_task.progress_percent,
                "step": current_task.current_step,
            }
            if current_task
            else None,
            "recent_events": [
                {
                    "type": e.event_type,
                    "description": e.description,
                    "severity": e.severity,
                    "timestamp": e.timestamp.isoformat(),
                }
                for e in events[:5]
            ],
        }


# Global orchestrator instance
_orchestrator: Optional[SessionOrchestrator] = None


def get_session_orchestrator() -> SessionOrchestrator:
    """Get or create the global session orchestrator."""
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = SessionOrchestrator()
    return _orchestrator
