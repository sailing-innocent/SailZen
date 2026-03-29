# -*- coding: utf-8 -*-
# @file bot_control_integration.py
# @brief Integration between Bot Runtime and Control Plane / Edge Runtime
# @author sailing-innocent
# @date 2026-03-29
# @version 1.0
# ---------------------------------
"""Integration layer connecting Feishu Bot to Control Plane and Edge Runtime.

This module provides:
- Workspace session control via Feishu messages/cards
- Session status monitoring and reporting
- Integration with existing control plane APIs
- Edge runtime state synchronization
"""

import asyncio
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from sail_server.feishu_gateway.cards import CardRenderer
from sail_server.feishu_gateway.session_orchestrator import (
    SessionOrchestrator,
    SessionStatus,
    TaskStatus,
    get_session_orchestrator,
)
from sail_server.control_plane.models import (
    RemoteWorkspace,
    OpenCodeSession,
    SessionAction,
)
from sail_server.edge_runtime.runtime import EdgeRuntime
from sail_server.edge_runtime.config import EdgeRuntimeConfig


class BotControlIntegration:
    """Integrates bot runtime with control plane and edge runtime."""

    def __init__(
        self,
        state_manager: Any,
        workspace_root: Optional[Path] = None,
    ):
        """Initialize control integration.

        Args:
            state_manager: Bot state manager
            workspace_root: SailZen workspace root
        """
        self.state_manager = state_manager
        self.workspace_root = workspace_root or Path("D:/ws/repos/SailZen")

        # Session orchestrator
        self.session_orchestrator = get_session_orchestrator()

        # Edge runtime (lazy initialization)
        self._edge_runtime: Optional[EdgeRuntime] = None

        # Workspace cache
        self._workspaces: Dict[str, Dict[str, Any]] = {}

    def _get_edge_runtime(self) -> Optional[EdgeRuntime]:
        """Get or initialize edge runtime."""
        if self._edge_runtime is None:
            try:
                config = EdgeRuntimeConfig(
                    edge_node_key="feishu_bot_node",
                    offline_mode=True,  # Start in offline mode
                    projects=[],  # Will be populated dynamically
                )
                self._edge_runtime = EdgeRuntime(config)
            except Exception as e:
                print(f"[BotControl] Failed to initialize edge runtime: {e}")
                return None
        return self._edge_runtime

    def list_workspaces(self) -> List[Dict[str, Any]]:
        """List available workspaces.

        Returns:
            List of workspace information
        """
        # For Phase 0, use hardcoded workspace
        workspaces = [
            {
                "slug": "sailzen",
                "name": "SailZen",
                "path": str(self.workspace_root),
                "description": "SailZen 主项目",
                "status": "available",
            }
        ]

        # Add session info
        for ws in workspaces:
            sessions = self.session_orchestrator.list_sessions(workspace_id=ws["slug"])
            if sessions:
                ws["active_session"] = {
                    "id": sessions[0].session_id,
                    "status": sessions[0].status.value,
                    "is_healthy": sessions[0].is_healthy,
                }

        return workspaces

    def get_session_status(self, workspace_slug: str) -> Optional[Dict[str, Any]]:
        """Get session status for workspace.

        Args:
            workspace_slug: Workspace identifier

        Returns:
            Session status data or None
        """
        sessions = self.session_orchestrator.list_sessions(workspace_id=workspace_slug)

        if not sessions:
            return None

        session = sessions[0]  # Get most recent
        summary = self.session_orchestrator.get_session_summary(session.session_id)

        # Update state manager
        self.state_manager.update_active_session(
            session.session_id,
            {
                "workspace": workspace_slug,
                "status": session.status.value,
                "observed_state": session.observed_state,
            },
        )

        return summary

    async def start_session(
        self,
        workspace_slug: str,
        branch: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Start a development session.

        Args:
            workspace_slug: Workspace to start
            branch: Optional git branch

        Returns:
            Operation result with session info
        """
        # Get or create session
        session = self.session_orchestrator.get_or_create_session(
            workspace_id=workspace_slug,
            workspace_name="SailZen",
            auto_create=True,
        )

        if not session:
            return {
                "success": False,
                "error": "Failed to create session",
            }

        # Update state
        self.session_orchestrator.update_session_state(
            session_id=session.session_id,
            desired_state="running",
            status=SessionStatus.STARTING,
        )

        # Try to start via edge runtime
        edge = self._get_edge_runtime()
        if edge:
            try:
                workspace_path = str(self.workspace_root)
                result = edge.ensure_workspace_session(workspace_slug, workspace_path)

                # Update session with result
                self.session_orchestrator.update_session_state(
                    session_id=session.session_id,
                    observed_state=result.get("observed_state", "unknown"),
                    status=SessionStatus.RUNNING
                    if result.get("observed_state") == "running"
                    else SessionStatus.ERROR,
                )

                return {
                    "success": True,
                    "session_id": session.session_id,
                    "status": session.status.value,
                    "local_url": result.get("local_url"),
                    "diagnostics": result.get("diagnostics", {}),
                }
            except Exception as e:
                self.session_orchestrator.update_session_state(
                    session_id=session.session_id,
                    status=SessionStatus.ERROR,
                )
                return {
                    "success": False,
                    "error": str(e),
                    "session_id": session.session_id,
                }

        # Fallback: just update state without actual process
        self.session_orchestrator.update_session_state(
            session_id=session.session_id,
            observed_state="starting",
            status=SessionStatus.STARTING,
        )

        return {
            "success": True,
            "session_id": session.session_id,
            "status": "starting",
            "note": "Edge runtime not available, session tracked only",
        }

    async def stop_session(self, workspace_slug: str) -> Dict[str, Any]:
        """Stop a development session.

        Args:
            workspace_slug: Workspace to stop

        Returns:
            Operation result
        """
        sessions = self.session_orchestrator.list_sessions(workspace_id=workspace_slug)

        if not sessions:
            return {
                "success": False,
                "error": f"No active session for {workspace_slug}",
            }

        session = sessions[0]

        # Update state
        self.session_orchestrator.update_session_state(
            session_id=session.session_id,
            desired_state="stopped",
            status=SessionStatus.STOPPING,
        )

        # Try to stop via edge runtime
        edge = self._get_edge_runtime()
        if edge:
            try:
                session_key = f"sess_{workspace_slug}"
                ok, result = edge.run_local_command(
                    workspace_slug,
                    str(self.workspace_root),
                    "opencode_stop",
                )

                self.session_orchestrator.update_session_state(
                    session_id=session.session_id,
                    observed_state="stopped" if ok else "error",
                    status=SessionStatus.STOPPED if ok else SessionStatus.ERROR,
                )

                return {
                    "success": ok,
                    "session_id": session.session_id,
                    "status": "stopped" if ok else "error",
                    "diagnostics": result if not ok else {},
                }
            except Exception as e:
                self.session_orchestrator.update_session_state(
                    session_id=session.session_id,
                    status=SessionStatus.ERROR,
                )
                return {
                    "success": False,
                    "error": str(e),
                    "session_id": session.session_id,
                }

        # Fallback
        self.session_orchestrator.update_session_state(
            session_id=session.session_id,
            observed_state="stopped",
            status=SessionStatus.STOPPED,
        )

        return {
            "success": True,
            "session_id": session.session_id,
            "status": "stopped",
            "note": "Edge runtime not available, session tracked only",
        }

    async def restart_session(self, workspace_slug: str) -> Dict[str, Any]:
        """Restart a development session.

        Args:
            workspace_slug: Workspace to restart

        Returns:
            Operation result
        """
        # Stop first
        stop_result = await self.stop_session(workspace_slug)
        await asyncio.sleep(1)  # Brief pause

        # Then start
        start_result = await self.start_session(workspace_slug)

        return {
            "success": start_result.get("success", False),
            "stop_result": stop_result,
            "start_result": start_result,
        }

    def render_workspace_home_card(self) -> Dict[str, Any]:
        """Render workspace home card.

        Returns:
            Card data structure
        """
        workspaces = self.list_workspaces()

        # Get active sessions
        active_sessions = []
        for ws in workspaces:
            if ws.get("active_session"):
                active_sessions.append(
                    {
                        "id": ws["active_session"]["id"],
                        "workspace_name": ws["name"],
                        "workspace_id": ws["slug"],
                        "status": ws["active_session"]["status"],
                    }
                )

        return CardRenderer.render_workspace_home(
            workspaces=workspaces,
            active_sessions=active_sessions,
            user_name="Developer",
        )

    def render_session_cockpit_card(
        self, workspace_slug: str
    ) -> Optional[Dict[str, Any]]:
        """Render session cockpit card.

        Args:
            workspace_slug: Workspace identifier

        Returns:
            Card data or None
        """
        summary = self.get_session_status(workspace_slug)
        if not summary:
            return None

        # Get recent events
        session_id = summary.get("session_id", "")
        events = []
        if session_id:
            timeline = self.session_orchestrator.get_session_timeline(
                session_id, limit=5
            )
            events = [
                {
                    "type": e.event_type,
                    "description": e.description,
                    "severity": e.severity,
                    "timestamp": e.timestamp.isoformat(),
                }
                for e in timeline
            ]

        return CardRenderer.render_session_cockpit(
            session={
                "id": summary.get("session_id"),
                "workspace_name": summary.get("workspace"),
                "status": summary.get("status"),
                "branch": summary.get("branch"),
                "started_at": summary.get("started_at"),
                "workspace_id": workspace_slug,
            },
            recent_events=events,
            current_task=summary.get("current_task"),
        )

    def handle_card_action(self, action_data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle card action callback.

        Args:
            action_data: Action data from card

        Returns:
            Response data
        """
        intent = action_data.get("intent", "")
        workspace = action_data.get("workspace", "")
        session = action_data.get("session", "")

        # Map intents to actions
        intent_handlers = {
            "list_workspaces": self._handle_list_workspaces,
            "list_workspaces_for_start": self._handle_list_workspaces,
            "get_status": self._handle_get_status,
            "view_session": self._handle_view_session,
            "start_session": self._handle_start_session,
            "stop_session": self._handle_stop_session,
            "restart_session": self._handle_restart_session,
            "home": self._handle_home,
        }

        handler = intent_handlers.get(intent)
        if handler:
            return handler(action_data)

        return {
            "success": False,
            "error": f"Unknown intent: {intent}",
        }

    def _handle_list_workspaces(self, action_data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle list workspaces intent."""
        return {
            "success": True,
            "card": self.render_workspace_home_card(),
        }

    def _handle_get_status(self, action_data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle get status intent."""
        workspaces = self.list_workspaces()
        status_lines = []

        for ws in workspaces:
            session_info = ""
            if ws.get("active_session"):
                sess = ws["active_session"]
                session_info = f" (会话: {sess['id'][:8]}... 状态: {sess['status']})"

            status_lines.append(f"• {ws['name']}{session_info}")

        return {
            "success": True,
            "text": "📊 **系统状态**\n\n" + "\n".join(status_lines),
        }

    def _handle_view_session(self, action_data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle view session intent."""
        workspace = action_data.get("workspace", "sailzen")
        card = self.render_session_cockpit_card(workspace)

        if card:
            return {
                "success": True,
                "card": card,
            }

        return {
            "success": False,
            "text": f"❌ 没有找到 {workspace} 的会话",
        }

    def _handle_start_session(self, action_data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle start session intent."""
        workspace = action_data.get("workspace", "sailzen")

        # This would be async in real implementation
        # For now, return a card indicating the action
        return {
            "success": True,
            "text": f"🚀 正在启动 {workspace} 的会话...\n\n请稍候，完成后会更新状态。",
            "action": "start_session",
            "workspace": workspace,
        }

    def _handle_stop_session(self, action_data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle stop session intent."""
        workspace = action_data.get("workspace", "sailzen")

        return {
            "success": True,
            "text": f"⏹️ 正在停止 {workspace} 的会话...",
            "action": "stop_session",
            "workspace": workspace,
            "requires_confirmation": True,
        }

    def _handle_restart_session(self, action_data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle restart session intent."""
        workspace = action_data.get("workspace", "sailzen")

        return {
            "success": True,
            "text": f"🔄 正在重启 {workspace} 的会话...",
            "action": "restart_session",
            "workspace": workspace,
            "requires_confirmation": True,
        }

    def _handle_home(self, action_data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle home intent."""
        return {
            "success": True,
            "card": self.render_workspace_home_card(),
        }
