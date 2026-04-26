# -*- coding: utf-8 -*-
# @file renderer.py
# @brief Pre-built card templates for common Feishu bot scenarios
# @author sailing-innocent
# @date 2026-04-26
# @version 1.0
# ---------------------------------
"""Pre-built card templates for common Feishu bot scenarios.

Provides ready-to-use card templates for:
- Workspace / session management
- Progress indication
- Confirmation dialogs
- Result display
- Error handling
- Help / welcome screens

All templates are generic and can be used with any Feishu bot.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from feishu_card_kit.core import (
    CardColor,
    ButtonStyle,
    header,
    divider,
    text,
    note,
    section,
    button,
    action_row,
    field_row,
    card,
    get_state_color,
    get_state_icon,
    get_state_label,
)


# ---------------------------------------------------------------------------
# Spinner characters for progress animation
# ---------------------------------------------------------------------------

_SPINNER_CHARS = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]


class CardRenderer:
    """Static card templates for common bot interaction patterns.

    All methods return Feishu card dicts. No external dependencies.
    """

    # ------------------------------------------------------------------
    # Workspace / Session cards
    # ------------------------------------------------------------------

    @staticmethod
    def workspace_selection(
        projects: List[Dict[str, str]],
        session_states: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """Create a workspace selection card.

        Args:
            projects: List of project dicts with keys: slug, label, path
            session_states: Optional dict mapping resolved paths to state strings
        """
        session_states = session_states or {}
        elements: List[Dict[str, Any]] = [
            text("📱 手机端快捷指令", bold=True),
            note("直接发送「启动 <项目名>」即可快速启动"),
            divider(),
        ]

        for proj in projects:
            slug = proj.get("slug", "")
            label = proj.get("label", slug)
            path = proj.get("path", "")
            resolved = str(Path(path).expanduser()) if path else path
            state = session_states.get(resolved, "idle")
            icon = get_state_icon(state)
            state_label = get_state_label(state)

            elements.append(text(f"{icon} **{label}** ({slug})  |  {state_label}"))

            if state in ("idle", "error"):
                cmd_text = f"发送「启动 {slug}」启动此工作区"
            elif state == "running":
                cmd_text = f"发送「使用 {slug}」切换到该工作区"
            else:
                cmd_text = f"当前状态: {state_label}"

            elements.append(note(cmd_text))
            elements.append(divider())

        if not projects:
            elements.append(text("暂无配置的工作区"))
        else:
            elements.append(text("💡 提示", bold=True))
            slugs = [p.get("slug", "") for p in projects if p.get("slug")]
            if slugs:
                elements.append(note(f"可用名称: {', '.join(slugs)}"))

        return card(
            elements=elements,
            title="🖥 选择工作区",
            color=CardColor.BLUE,
        )

    @staticmethod
    def session_status(
        path: str,
        state: str,
        port: Optional[int] = None,
        pid: Optional[int] = None,
        last_error: Optional[str] = None,
        activities: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Create a session status card.

        Args:
            path: Workspace path
            state: State string (idle/starting/running/stopping/error)
            port: Optional port number
            pid: Optional process ID
            last_error: Optional error message
            activities: Optional list of recent activity strings
        """
        color = get_state_color(state)
        icon = get_state_icon(state)
        state_label = get_state_label(state)
        name = Path(path).name if path else "未知"

        elements: List[Dict[str, Any]] = [text(f"{icon} **{state_label}**  |  {name}")]

        info_pairs: List = []
        if port:
            info_pairs.append(("端口", str(port)))
        if pid:
            info_pairs.append(("PID", str(pid)))
        if info_pairs:
            elements.append(field_row(info_pairs))

        if last_error:
            elements.append(divider())
            elements.append(text(f"错误：{last_error[:200]}"))

        if activities:
            elements.append(divider())
            elements.append(text("最近活动：", bold=True))
            for act in activities[-5:]:
                elements.append(note(act))

        return card(
            elements=elements,
            title=f"会话状态：{name}",
            color=color,
        )

    @staticmethod
    def all_sessions(sessions: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Create a card listing all sessions.

        Args:
            sessions: List of session dicts with keys: path, state, port
        """
        elements: List[Dict[str, Any]] = []
        if not sessions:
            elements.append(text("暂无会话"))
        else:
            for s in sessions:
                path = s.get("path", "")
                state = s.get("state", "idle")
                port = s.get("port")
                icon = get_state_icon(state)
                name = str(Path(path).name if path else "?")
                state_label = get_state_label(state)
                port_info = f":{port}" if port else ""
                elements.append(text(f"{icon} **{name}**{port_info}  {state_label}"))

        return card(
            elements=elements,
            title="📊 所有会话",
            color=CardColor.BLUE,
        )

    @staticmethod
    def current_workspace(path: str, mode: str = "coding") -> Dict[str, Any]:
        """Create a current workspace indicator card.

        Args:
            path: Current workspace path
            mode: Current mode (coding/idle)
        """
        name = Path(path).name if path else "未知"

        elements: List[Dict[str, Any]] = [
            text(f"🎯 **当前工作区：{name}**", bold=True),
            note("已切换到该工作区，可以直接发送指令"),
            divider(),
            text("💡 **你可以：**"),
            note("• 直接发送任务指令"),
            note("• 发送「使用 <其他项目>」切换"),
            note(f"• 发送「停止 {name}」停止当前工作区"),
        ]

        return card(
            elements=elements,
            title="🔄 工作区切换成功",
            color=CardColor.GREEN,
        )

    # ------------------------------------------------------------------
    # Progress / Task cards
    # ------------------------------------------------------------------

    @staticmethod
    def progress(
        title: str,
        description: str = "",
        progress_pct: Optional[int] = None,
        elapsed_seconds: Optional[float] = None,
        spinner_tick: int = 0,
        show_cancel_button: bool = False,
        cancel_action_data: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Create a progress indicator card.

        Args:
            title: Progress title
            description: Optional description text
            progress_pct: Optional percentage (0-100)
            elapsed_seconds: Optional elapsed time
            spinner_tick: Spinner animation frame index
            show_cancel_button: Whether to show cancel button
            cancel_action_data: Callback data for cancel button
        """
        spinner = _SPINNER_CHARS[spinner_tick % len(_SPINNER_CHARS)]

        elements: List[Dict[str, Any]] = []
        if description:
            elements.append(text(description))

        if progress_pct is not None:
            filled = progress_pct // 10
            bar = "█" * filled + "░" * (10 - filled)
            elements.append(text(f"{bar}  {progress_pct}%"))
        else:
            elements.append(text(f"{spinner} 处理中，请稍候..."))

        if elapsed_seconds is not None:
            elements.append(note(f"已用时 {int(elapsed_seconds)}s"))

        if show_cancel_button:
            elements.append(divider())
            if cancel_action_data:
                elements.append(
                    action_row(
                        [
                            button(
                                "❌ 取消任务",
                                "callback",
                                cancel_action_data,
                                ButtonStyle.DANGER,
                            )
                        ]
                    )
                )
            else:
                elements.append(note("💡 发送「取消」可中断当前任务"))

        return card(
            elements=elements,
            title=f"⏳ {title}",
            color=CardColor.BLUE,
        )

    @staticmethod
    def timeout_warning(
        operation: str,
        elapsed_seconds: float,
        context_path: str = "",
    ) -> Dict[str, Any]:
        """Create a timeout warning card.

        Args:
            operation: Operation name
            elapsed_seconds: Elapsed time in seconds
            context_path: Optional context path for cancel callback
        """
        elements = [
            text(f"操作「{operation}」比预期用时更长。"),
            text(f"已用时 {int(elapsed_seconds)}s，系统仍在工作中。"),
        ]
        buttons = [button("继续等待", "callback", {"action": "noop"})]
        if context_path:
            buttons.append(
                button(
                    "取消操作",
                    "callback",
                    {"action": "cancel_operation", "path": context_path},
                    ButtonStyle.DANGER,
                )
            )
        elements.append(divider())
        elements.append(action_row(buttons))

        return card(
            elements=elements,
            title="⏰ 操作超时警告",
            color=CardColor.YELLOW,
        )

    # ------------------------------------------------------------------
    # Confirmation / Dialog cards
    # ------------------------------------------------------------------

    @staticmethod
    def confirmation(
        action_summary: str,
        action_detail: str = "",
        risk_level: str = "confirm_required",
        can_undo: bool = False,
        pending_id: str = "",
        timeout_minutes: int = 5,
    ) -> Dict[str, Any]:
        """Create a confirmation dialog card.

        Args:
            action_summary: Short summary of the action
            action_detail: Detailed description
            risk_level: "safe", "guarded", or "confirm_required"
            can_undo: Whether the action can be undone
            pending_id: Unique ID for tracking this confirmation
            timeout_minutes: Confirmation timeout in minutes
        """
        risk_icons = {"safe": "🟢", "guarded": "🟡", "confirm_required": "🔴"}
        risk_labels = {
            "safe": "低风险",
            "guarded": "中等风险",
            "confirm_required": "高风险",
        }

        elements: List[Dict[str, Any]] = [text(action_summary, bold=True)]
        if action_detail:
            elements.append(text(action_detail))

        elements.append(divider())
        elements.append(
            field_row(
                [
                    (
                        "风险等级",
                        f"{risk_icons.get(risk_level, '🔴')} {risk_labels.get(risk_level, '需确认')}",
                    ),
                    ("有效期", f"{timeout_minutes} 分钟"),
                ]
            )
        )

        if can_undo:
            elements.append(note("此操作可在 30 秒内撤销"))

        elements.append(divider())

        button_style = (
            ButtonStyle.DANGER
            if risk_level == "confirm_required"
            else ButtonStyle.PRIMARY
        )
        elements.append(
            action_row(
                [
                    button(
                        "✅ 确认执行",
                        "callback",
                        {
                            "action": "confirm_action",
                            "pending_id": pending_id,
                            "decision": "confirm",
                        },
                        button_style,
                    ),
                    button(
                        "❌ 取消",
                        "callback",
                        {
                            "action": "confirm_action",
                            "pending_id": pending_id,
                            "decision": "cancel",
                        },
                        ButtonStyle.DEFAULT,
                    ),
                ]
            )
        )

        elements.append(note("💡 或回复文字：确认 / 取消"))

        return card(
            elements=elements,
            title="⚠️ 请确认操作",
            color=CardColor.YELLOW,
        )

    # ------------------------------------------------------------------
    # Result / Error cards
    # ------------------------------------------------------------------

    @staticmethod
    def result(
        title: str,
        content: str,
        success: bool = True,
        can_retry: bool = False,
        retry_action: Optional[Dict[str, Any]] = None,
        can_undo: bool = False,
        undo_deadline: Optional[float] = None,
        context_path: str = "",
        max_content_length: int = 8000,
    ) -> Dict[str, Any]:
        """Create a result card.

        Args:
            title: Result title
            content: Result content text
            success: Whether the operation succeeded
            can_retry: Whether retry is available
            retry_action: Callback data for retry button
            can_undo: Whether undo is available
            undo_deadline: Unix timestamp for undo window
            context_path: Optional workspace path for context hints
            max_content_length: Maximum content length before truncation
        """
        color = CardColor.GREEN if success else CardColor.RED
        icon = "✅" if success else "❌"

        elements: List[Dict[str, Any]] = []
        if content:
            display = content[:max_content_length]
            if len(content) > max_content_length:
                display += (
                    f"\n\n[内容过长，共 {len(content)} 字符，"
                    f"已显示前 {max_content_length} 字符]"
                )
            elements.append(text(display))

        notes: List[str] = []
        if can_retry and retry_action:
            notes.append("💡 发送「重试」重新执行")
        if can_undo and undo_deadline:
            remaining = undo_deadline - time.time()
            if remaining > 0:
                notes.append(f"💡 发送「撤销」撤销此操作（{int(remaining)}秒内有效）")
        if context_path:
            notes.append(f"💡 发送「状态 {Path(context_path).name}」查看详情")

        if notes:
            elements.append(divider())
            for n in notes:
                elements.append(note(n))

        return card(
            elements=elements,
            title=f"{icon} {title}",
            color=color,
        )

    @staticmethod
    def error(
        title: str,
        error_message: str,
        context_path: str = "",
        can_retry: bool = True,
        retry_action: Optional[Dict[str, Any]] = None,
        max_content_length: int = 8000,
    ) -> Dict[str, Any]:
        """Create an error card.

        Args:
            title: Error title
            error_message: Error description
            context_path: Optional workspace path
            can_retry: Whether retry is available
            retry_action: Callback data for retry
            max_content_length: Maximum content length
        """
        elements: List[Dict[str, Any]] = [text(error_message[:max_content_length])]

        notes: List[str] = []
        if can_retry and retry_action:
            notes.append("💡 发送「重试」重新执行")
        if context_path:
            notes.append(f"💡 发送「状态 {Path(context_path).name}」查看详情")

        if notes:
            elements.append(divider())
            for n in notes:
                elements.append(note(n))

        return card(
            elements=elements,
            title=f"❌ {title}",
            color=CardColor.RED,
        )

    @staticmethod
    def result_paginated(
        title: str,
        content: str,
        page: int = 1,
        total_pages: int = 1,
        success: bool = True,
    ) -> Dict[str, Any]:
        """Create a paginated result card for very long content.

        Args:
            title: Card title
            content: Content for this page
            page: Current page number (1-indexed)
            total_pages: Total number of pages
            success: Whether the operation succeeded
        """
        color = CardColor.GREEN if success else CardColor.RED
        icon = "✅" if success else "❌"
        elements: List[Dict[str, Any]] = []

        if content:
            elements.append(text(content))

        if total_pages > 1:
            elements.append(divider())
            page_info = f"📄 第 {page}/{total_pages} 页"
            if page < total_pages:
                page_info += " | 发送「下一页」查看更多"
            elements.append(note(page_info))

        return card(
            elements=elements,
            title=f"{icon} {title} ({page}/{total_pages})",
            color=color,
        )

    # ------------------------------------------------------------------
    # Help / Welcome cards
    # ------------------------------------------------------------------

    @staticmethod
    def help(
        commands: Optional[List[tuple]] = None,
        projects: Optional[List[Dict[str, str]]] = None,
        features: Optional[List[tuple]] = None,
        footer: str = "",
    ) -> Dict[str, Any]:
        """Create a help card.

        Args:
            commands: List of (command, description, example) tuples
            projects: List of project dicts
            features: List of (name, status) tuples, e.g. [("LLM", "✅ 已启用")]
            footer: Optional footer note
        """
        elements: List[Dict[str, Any]] = []

        elements.append(text("🚀 **快速开始**", bold=True))
        elements.append(note("直接发送指令即可，支持自然语言"))

        if commands:
            elements.append(divider())
            elements.append(text("📋 **常用指令**", bold=True))
            for cmd, desc, example in commands:
                elements.append(text(f"• **{cmd}** - {desc}"))
                elements.append(note(f"  例：{example}"))

        if projects:
            elements.append(divider())
            elements.append(text("📁 **配置的项目**", bold=True))
            slugs = [p.get("slug", "") for p in projects if p.get("slug")]
            if slugs:
                elements.append(text(f"可用名称：{', '.join(slugs)}"))
            for proj in projects[:5]:
                slug = proj.get("slug", "")
                label = proj.get("label", slug)
                elements.append(note(f"• {label} ({slug})"))
            if len(projects) > 5:
                elements.append(note(f"... 还有 {len(projects) - 5} 个项目"))

        if features:
            elements.append(divider())
            elements.append(text("⚙️ **系统状态**", bold=True))
            elements.append(field_row(features))

        if footer:
            elements.append(divider())
            elements.append(note(footer))

        return card(
            elements=elements,
            title="🤖 使用帮助",
            color=CardColor.BLUE,
        )

    @staticmethod
    def welcome(
        title: str = "欢迎使用",
        description: str = "",
        quick_commands: Optional[List[str]] = None,
        projects: Optional[List[Dict[str, str]]] = None,
        session_states: Optional[Dict[str, str]] = None,
        features: Optional[List[tuple]] = None,
        footer: str = "",
    ) -> Dict[str, Any]:
        """Create a welcome card for new users.

        Args:
            title: Welcome title
            description: Welcome description
            quick_commands: List of quick command hint strings
            projects: List of project dicts
            session_states: Dict mapping paths to state strings
            features: List of (name, status) tuples
            footer: Footer note
        """
        session_states = session_states or {}
        elements: List[Dict[str, Any]] = []

        elements.append(text(f"👋 {title}", bold=True))
        if description:
            elements.append(note(description))

        if features:
            elements.append(divider())
            elements.append(text("⚙️ 系统状态", bold=True))
            elements.append(field_row(features))

        if quick_commands:
            elements.append(divider())
            elements.append(text("💡 快捷指令", bold=True))
            for cmd in quick_commands:
                elements.append(text(cmd))

        if projects:
            elements.append(divider())
            elements.append(text("📁 配置的项目", bold=True))
            for proj in projects[:5]:
                slug = proj.get("slug", "")
                label = proj.get("label", slug)
                path = proj.get("path", "")
                state = session_states.get(path, "idle")
                icon = get_state_icon(state)
                state_label = get_state_label(state)
                elements.append(text(f"{icon} **{label}** ({slug}) - {state_label}"))
            if len(projects) > 5:
                elements.append(note(f"... 还有 {len(projects) - 5} 个项目"))

        if footer:
            elements.append(divider())
            elements.append(note(footer))

        return card(
            elements=elements,
            title=f"🎉 {title}",
            color=CardColor.GREEN,
        )

    # ------------------------------------------------------------------
    # Utility
    # ------------------------------------------------------------------

    @staticmethod
    def workspace_indicator(path: Optional[str] = None, mode: str = "idle") -> str:
        """Generate a simple text indicator for the current workspace.

        Returns a short markdown string to append to messages.
        """
        if mode == "coding" and path:
            name = Path(path).name
            return f"\n\n---\n💻 当前工作区：{name}"
        return ""
