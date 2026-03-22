# -*- coding: utf-8 -*-
# @file cards.py
# @brief Feishu interactive card rendering layer
# @author sailing-innocent
# @date 2026-03-22
# @version 1.0
# ---------------------------------
"""Card rendering layer for Feishu interactive messages.

This module provides templates and renderers for various card types
used in the remote development control plane:
- Workspace home cards
- Session cockpit cards
- Task result cards
- Alert cards
- Confirmation cards
"""

from typing import Dict, Any, List, Optional
from enum import Enum
from datetime import datetime


class CardTemplate(Enum):
    """Available card templates."""

    WORKSPACE_HOME = "workspace_home"
    SESSION_COCKPIT = "session_cockpit"
    TASK_RESULT = "task_result"
    ALERT = "alert"
    CONFIRMATION = "confirmation"
    SIMPLE_TEXT = "simple_text"


class CardRenderer:
    """Renderer for Feishu interactive cards.

    Provides methods to generate card data structures for different
    use cases in the remote development workflow.
    """

    @staticmethod
    def render_workspace_home(
        workspaces: List[Dict[str, Any]],
        active_sessions: List[Dict[str, Any]],
        user_name: str = "Operator",
    ) -> Dict[str, Any]:
        """Render the main workspace home card.

        Shows recent projects, active sessions, and quick actions.

        Args:
            workspaces: List of configured workspaces
            active_sessions: List of currently active sessions
            user_name: Display name of the operator

        Returns:
            Feishu card JSON structure
        """
        elements = [
            {
                "tag": "div",
                "text": {
                    "tag": "lark_md",
                    "content": f"👋 你好，**{user_name}**！这是你的远程开发控制台。",
                },
            },
            {"tag": "hr"},
        ]

        # Active sessions section
        if active_sessions:
            elements.append(
                {"tag": "div", "text": {"tag": "lark_md", "content": "🚀 **活跃会话**"}}
            )

            for session in active_sessions[:5]:  # Show up to 5
                status_emoji = CardRenderer._status_emoji(
                    session.get("status") or "unknown"
                )
                elements.append(
                    {
                        "tag": "div",
                        "text": {
                            "tag": "lark_md",
                            "content": (
                                f"{status_emoji} **{session.get('workspace_name', 'Unknown')}**\n"
                                f"   状态: {session.get('status', 'unknown')} | "
                                f"分支: {session.get('branch', 'N/A')}"
                            ),
                        },
                        "extra": {
                            "tag": "button",
                            "text": {"tag": "plain_text", "content": "查看"},
                            "type": "primary",
                            "value": {
                                "intent": "view_session",
                                "session": session.get("id"),
                                "workspace": session.get("workspace_id"),
                            },
                        },
                    }
                )

            elements.append({"tag": "hr"})

        # Quick actions
        elements.append(
            {"tag": "div", "text": {"tag": "lark_md", "content": "⚡ **快速操作**"}}
        )

        elements.append(
            {
                "tag": "action",
                "layout": "default",
                "actions": [
                    {
                        "tag": "button",
                        "text": {"tag": "plain_text", "content": "🚀 启动会话"},
                        "type": "primary",
                        "value": {"intent": "list_workspaces_for_start"},
                    },
                    {
                        "tag": "button",
                        "text": {"tag": "plain_text", "content": "📊 查看状态"},
                        "type": "default",
                        "value": {"intent": "get_status"},
                    },
                    {
                        "tag": "button",
                        "text": {"tag": "plain_text", "content": "📁 工作区列表"},
                        "type": "default",
                        "value": {"intent": "list_workspaces"},
                    },
                ],
            }
        )

        # Workspaces list (if not too many)
        if workspaces:
            elements.append({"tag": "hr"})
            elements.append(
                {
                    "tag": "div",
                    "text": {
                        "tag": "lark_md",
                        "content": f"📁 **已配置工作区** ({len(workspaces)}个)",
                    },
                }
            )

            for ws in workspaces[:3]:  # Show up to 3
                elements.append(
                    {
                        "tag": "div",
                        "text": {
                            "tag": "lark_md",
                            "content": f"• **{ws.get('name', 'Unknown')}** - {ws.get('path', 'N/A')}",
                        },
                    }
                )

            if len(workspaces) > 3:
                elements.append(
                    {
                        "tag": "div",
                        "text": {
                            "tag": "lark_md",
                            "content": f"_... 还有 {len(workspaces) - 3} 个工作区_",
                        },
                    }
                )

        return {
            "config": {"wide_screen_mode": True},
            "header": {
                "title": {"tag": "plain_text", "content": "🏠 远程开发控制台"},
                "template": "blue",
            },
            "elements": elements,
        }

    @staticmethod
    def render_session_cockpit(
        session: Dict[str, Any],
        recent_events: List[Dict[str, Any]],
        current_task: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Render a session cockpit card.

        Shows session status, progress, recent activity, and controls.

        Args:
            session: Session data including status, workspace, branch
            recent_events: Recent events for this session
            current_task: Optional current active task

        Returns:
            Feishu card JSON structure
        """
        status = session.get("status", "unknown")
        status_emoji = CardRenderer._status_emoji(status)

        elements = [
            {
                "tag": "div",
                "text": {
                    "tag": "lark_md",
                    "content": (
                        f"{status_emoji} **{session.get('workspace_name', 'Unknown')}**\n"
                        f"分支: `{session.get('branch', 'N/A')}` | "
                        f"启动: {session.get('started_at', 'N/A')}"
                    ),
                },
            },
            {"tag": "hr"},
        ]

        # Current task section
        if current_task:
            elements.append(
                {
                    "tag": "div",
                    "text": {
                        "tag": "lark_md",
                        "content": (
                            f"📝 **当前任务**: {current_task.get('title', 'Unknown')}\n"
                            f"进度: {current_task.get('progress', 0)}% | "
                            f"状态: {current_task.get('status', 'unknown')}"
                        ),
                    },
                }
            )
        else:
            elements.append(
                {
                    "tag": "div",
                    "text": {"tag": "lark_md", "content": "💤 当前没有活跃任务"},
                }
            )

        # Recent events
        if recent_events:
            elements.append({"tag": "hr"})
            elements.append(
                {"tag": "div", "text": {"tag": "lark_md", "content": "📋 **最近活动**"}}
            )

            for event in recent_events[:5]:
                event_time = event.get("timestamp", "")
                if isinstance(event_time, str) and len(event_time) > 16:
                    event_time = event_time[11:16]  # HH:MM

                elements.append(
                    {
                        "tag": "div",
                        "text": {
                            "tag": "lark_md",
                            "content": f"`{event_time}` {event.get('description', 'Event')}",
                        },
                    }
                )

        # Action buttons
        elements.append({"tag": "hr"})
        elements.append(
            {
                "tag": "action",
                "layout": "default",
                "actions": CardRenderer._session_actions(session),
            }
        )

        # Header color based on status
        header_template = CardRenderer._status_color(status)

        return {
            "config": {"wide_screen_mode": True},
            "header": {
                "title": {"tag": "plain_text", "content": "💻 会话驾驶舱"},
                "template": header_template,
            },
            "elements": elements,
        }

    @staticmethod
    def render_task_result(
        task: Dict[str, Any],
        result_summary: str,
        details: Optional[str] = None,
        has_error: bool = False,
    ) -> Dict[str, Any]:
        """Render a task result card.

        Shows task completion status, result summary, and follow-up actions.

        Args:
            task: Task data
            result_summary: Summary of the result
            details: Optional detailed output
            has_error: Whether the task had errors

        Returns:
            Feishu card JSON structure
        """
        status_emoji = "❌" if has_error else "✅"
        header_template = "red" if has_error else "green"

        elements = [
            {
                "tag": "div",
                "text": {
                    "tag": "lark_md",
                    "content": f"{status_emoji} **{task.get('title', 'Task')}**",
                },
            },
            {"tag": "div", "text": {"tag": "lark_md", "content": result_summary}},
        ]

        if details:
            elements.append({"tag": "hr"})
            elements.append(
                {
                    "tag": "div",
                    "text": {
                        "tag": "lark_md",
                        "content": f"```\n{details[:500]}\n```",  # Limit length
                    },
                }
            )

        # Action buttons
        elements.append({"tag": "hr"})
        actions = [
            {
                "tag": "button",
                "text": {"tag": "plain_text", "content": "🔄 重试"},
                "type": "default",
                "value": {"intent": "retry_task", "task_id": task.get("id")},
            },
            {
                "tag": "button",
                "text": {"tag": "plain_text", "content": "📊 查看会话"},
                "type": "default",
                "value": {"intent": "view_session", "session": task.get("session_id")},
            },
        ]

        elements.append({"tag": "action", "layout": "default", "actions": actions})

        return {
            "config": {"wide_screen_mode": True},
            "header": {
                "title": {"tag": "plain_text", "content": "📝 任务结果"},
                "template": header_template,
            },
            "elements": elements,
        }

    @staticmethod
    def render_alert(
        alert_type: str,
        title: str,
        message: str,
        severity: str = "warning",
        recovery_actions: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """Render an alert card.

        Shows system alerts with actionable recovery controls.

        Args:
            alert_type: Type of alert (session_stale, agent_offline, etc.)
            title: Alert title
            message: Alert message
            severity: Alert severity (info, warning, error)
            recovery_actions: Optional recovery action buttons

        Returns:
            Feishu card JSON structure
        """
        severity_config = {
            "info": ("ℹ️", "blue"),
            "warning": ("⚠️", "orange"),
            "error": ("🚨", "red"),
        }
        emoji, color = severity_config.get(severity, ("⚠️", "orange"))

        elements = [
            {
                "tag": "div",
                "text": {"tag": "lark_md", "content": f"{emoji} **{title}**"},
            },
            {"tag": "div", "text": {"tag": "lark_md", "content": message}},
        ]

        # Recovery actions
        if recovery_actions:
            elements.append({"tag": "hr"})
            buttons = []
            for action in recovery_actions[:3]:  # Max 3 actions
                buttons.append(
                    {
                        "tag": "button",
                        "text": {
                            "tag": "plain_text",
                            "content": action.get("label", "Action"),
                        },
                        "type": action.get("type", "default"),
                        "value": action.get("value", {}),
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

    @staticmethod
    def render_confirmation(
        title: str,
        description: str,
        action_payload: Dict[str, Any],
        risk_level: str = "medium",
        timeout_seconds: int = 300,
    ) -> Dict[str, Any]:
        """Render a confirmation card.

        Shows confirmation request for sensitive operations.

        Args:
            title: Confirmation title
            description: Description of the action
            action_payload: Data to send back on confirm/cancel
            risk_level: Risk level (low, medium, high)
            timeout_seconds: Confirmation timeout

        Returns:
            Feishu card JSON structure
        """
        risk_config = {
            "low": ("💡", "blue", "确认"),
            "medium": ("⚠️", "orange", "请确认"),
            "high": ("🚨", "red", "高风险操作"),
        }
        emoji, color, header_text = risk_config.get(
            risk_level, ("⚠️", "orange", "请确认")
        )

        return {
            "config": {"wide_screen_mode": True},
            "header": {
                "title": {"tag": "plain_text", "content": f"{emoji} {header_text}"},
                "template": color,
            },
            "elements": [
                {"tag": "div", "text": {"tag": "lark_md", "content": description}},
                {"tag": "hr"},
                {
                    "tag": "action",
                    "layout": "default",
                    "actions": [
                        {
                            "tag": "button",
                            "text": {"tag": "plain_text", "content": "✅ 确认执行"},
                            "type": "primary" if risk_level != "high" else "danger",
                            "value": {
                                **action_payload,
                                "confirm_action": "confirm",
                                "confirmed_at": datetime.now().isoformat(),
                            },
                        },
                        {
                            "tag": "button",
                            "text": {"tag": "plain_text", "content": "❌ 取消"},
                            "type": "default",
                            "value": {**action_payload, "confirm_action": "cancel"},
                        },
                    ],
                },
                {
                    "tag": "note",
                    "elements": [
                        {
                            "tag": "plain_text",
                            "content": f"⏰ 此确认将在 {timeout_seconds // 60} 分钟后过期",
                        }
                    ],
                },
            ],
        }

    @staticmethod
    def render_simple_text(
        text: str, title: Optional[str] = None, template: str = "default"
    ) -> Dict[str, Any]:
        """Render a simple text card for consistent styling.

        Args:
            text: Text content
            title: Optional title
            template: Color template

        Returns:
            Feishu card JSON structure
        """
        elements = [{"tag": "div", "text": {"tag": "lark_md", "content": text}}]

        card = {"config": {"wide_screen_mode": True}, "elements": elements}

        if title:
            card["header"] = {
                "title": {"tag": "plain_text", "content": title},
                "template": template,
            }

        return card

    # Helper methods

    @staticmethod
    def _status_emoji(status: str) -> str:
        """Get emoji for session status."""
        status_map = {
            "running": "🟢",
            "stopped": "🔴",
            "starting": "🟡",
            "stopping": "🟡",
            "error": "❌",
            "recovering": "🔄",
            "idle": "⚪",
        }
        return status_map.get(status.lower(), "⚪")

    @staticmethod
    def _status_color(status: str) -> str:
        """Get header color for session status."""
        color_map = {
            "running": "green",
            "stopped": "grey",
            "starting": "blue",
            "stopping": "blue",
            "error": "red",
            "recovering": "orange",
            "idle": "grey",
        }
        return color_map.get(status.lower(), "grey")

    @staticmethod
    def _session_actions(session: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Generate action buttons for a session based on status."""
        status = session.get("status", "").lower()
        session_id = session.get("id")
        workspace_id = session.get("workspace_id")

        actions = []

        if status == "running":
            actions.extend(
                [
                    {
                        "tag": "button",
                        "text": {"tag": "plain_text", "content": "⏹️ 停止"},
                        "type": "default",
                        "value": {
                            "intent": "stop_session",
                            "session": session_id,
                            "workspace": workspace_id,
                        },
                    },
                    {
                        "tag": "button",
                        "text": {"tag": "plain_text", "content": "🔄 重启"},
                        "type": "default",
                        "value": {
                            "intent": "restart_session",
                            "session": session_id,
                            "workspace": workspace_id,
                        },
                    },
                ]
            )
        elif status in ["stopped", "error"]:
            actions.append(
                {
                    "tag": "button",
                    "text": {"tag": "plain_text", "content": "🚀 启动"},
                    "type": "primary",
                    "value": {
                        "intent": "start_session",
                        "session": session_id,
                        "workspace": workspace_id,
                    },
                }
            )

        # Common actions
        actions.extend(
            [
                {
                    "tag": "button",
                    "text": {"tag": "plain_text", "content": "📝 代码请求"},
                    "type": "default",
                    "value": {
                        "intent": "code_request",
                        "session": session_id,
                        "workspace": workspace_id,
                    },
                },
                {
                    "tag": "button",
                    "text": {"tag": "plain_text", "content": "🏠 返回主页"},
                    "type": "default",
                    "value": {"intent": "home"},
                },
            ]
        )

        return actions
